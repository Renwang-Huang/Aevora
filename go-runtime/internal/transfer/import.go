package transfer

import (
	"bufio"
	"bytes"
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"os"
	"path/filepath"
)

func exact(m Map, keys ...string) bool {
	if len(m) != len(keys) {
		return false
	}
	for _, k := range keys {
		if _, ok := m[k]; !ok {
			return false
		}
	}
	return true
}
func freshTarget(path string) error {
	if !filepath.IsAbs(path) || filepath.Clean(path) != path {
		return domain.ErrInvalid
	}
	if _, e := os.Lstat(path); !os.IsNotExist(e) {
		return platform.ErrUnsafe
	}
	return platform.PrivateDir(filepath.Dir(path), true)
}
func Import(ctx context.Context, input, pin, target string) (receipt Map, err error) {
	if !validPin(pin) {
		return nil, domain.ErrInvalid
	}
	if e := freshTarget(target); e != nil {
		return nil, e
	}
	files, e := domain.OpenEvidence(input)
	if e != nil {
		return nil, e
	}
	defer files.Close()
	raw, e := files.Read("manifest.json", 65536, pin)
	if e != nil {
		return nil, e
	}
	v, e := codec.Parse(raw)
	if e != nil {
		return nil, e
	}
	m := domain.M(v)
	if !exact(m, "schema_version", "logical_schema", "query_version", "source_engine", "created_at", "counts", "files", "source_state", "capabilities_included") || m["schema_version"] != "aevora.logical-transfer/1" || m["logical_schema"] != storage.LogicalSchema || m["query_version"] != storage.QueryVersion || (m["source_engine"] != "python-falkordb" && m["source_engine"] != "go-sqlite") || m["capabilities_included"] != false {
		return nil, storage.ErrIncompatible
	}
	refs := domain.M(m["files"])
	if !exact(refs, "nodes", "edges", "witnesses") {
		return nil, domain.ErrInvalid
	}
	payloads := map[string][]byte{}
	for _, key := range []string{"nodes", "edges", "witnesses"} {
		ref := domain.M(refs[key])
		if !validPin(domain.S(ref["sha256"])) {
			return nil, domain.ErrInvalid
		}
		if !exact(ref, "path", "sha256", "bytes") || ref["path"] != key+map[string]string{"nodes": ".jsonl", "edges": ".jsonl", "witnesses": ".json"}[key] {
			return nil, domain.ErrInvalid
		}
		limit := int64(64 * 1024 * 1024)
		if key == "witnesses" {
			limit = 8 * 1024 * 1024
		}
		b, e := files.Read(domain.S(ref["path"]), limit, domain.S(ref["sha256"]))
		if e != nil {
			return nil, e
		}
		if !codec.Equal(ref["bytes"], len(b)) {
			return nil, domain.ErrConflict
		}
		payloads[key] = b
	}
	witnessValue, e := wire.Decode(payloads["witnesses"], 8*1024*1024)
	if e != nil || !exact(witnessValue, "cases") {
		return nil, domain.ErrInvalid
	}
	witnesses, ok := witnessValue["cases"].([]any)
	if !ok || len(witnesses) < 1 || len(witnesses) > 32 {
		return nil, domain.ErrInvalid
	}
	s, e := storage.Open(ctx, target, storage.Options{Create: true})
	if e != nil {
		return nil, e
	}
	defer s.Close()
	counts := map[string]int{"nodes": 0, "edges": 0}
	e = s.Write(ctx, func(repo *storage.Repository) error {
		for _, kind := range []string{"nodes", "edges"} {
			scanner := bufio.NewScanner(bytes.NewReader(payloads[kind]))
			scanner.Buffer(make([]byte, 4096), 1024*1024)
			after := ""
			for scanner.Scan() {
				if ctx.Err() != nil {
					return ctx.Err()
				}
				row, e := wire.Decode(scanner.Bytes(), 1024*1024)
				if e != nil {
					return e
				}
				id := domain.S(row["id"])
				if !storage.ValidID(id) || id <= after {
					return domain.ErrConflict
				}
				after = id
				payload := []byte(domain.S(row["payload_json"]))
				value, e := codec.Parse(payload)
				if e != nil {
					return e
				}
				p := domain.M(value)
				canonical, e := codec.Canonical(p)
				if e != nil || !bytes.Equal(canonical, payload) || p["id"] != id || domain.H(p) != row["sha256"] {
					return domain.ErrConflict
				}
				if kind == "nodes" {
					if !exact(row, "label", "id", "payload_json", "sha256") {
						return domain.ErrInvalid
					}
					label := domain.S(row["label"])
					if e = domain.ValidateRecord(label, p); e != nil {
						return e
					}
					if e = repo.PutNode(ctx, label, p); e != nil {
						return e
					}
				} else {
					if !exact(row, "id", "relation", "source_label", "source_id", "target_label", "target_id", "payload_json", "sha256") {
						return domain.ErrInvalid
					}
					relation, sl, sid, tl, tid := domain.S(row["relation"]), domain.S(row["source_label"]), domain.S(row["source_id"]), domain.S(row["target_label"]), domain.S(row["target_id"])
					if id != "edge:"+domain.H([]any{relation, sl, sid, tl, tid}) {
						return domain.ErrConflict
					}
					if e = repo.PutEdge(ctx, relation, sl, sid, tl, tid, p); e != nil {
						return e
					}
				}
				counts[kind]++
				if counts[kind] > map[string]int{"nodes": 100000, "edges": 200000}[kind] {
					return storage.ErrReadBudget
				}
			}
			if e = scanner.Err(); e != nil {
				return e
			}
			if len(payloads[kind]) > 0 && !bytes.HasSuffix(payloads[kind], []byte{'\n'}) {
				return domain.ErrInvalid
			}
		}
		if !codec.Equal(Map{"nodes": counts["nodes"], "edges": counts["edges"]}, domain.M(m["counts"])) {
			return domain.ErrConflict
		}
		return nil
	})
	if e != nil {
		return nil, e
	}
	source := domain.M(m["source_state"])
	fingerprint, e := Fingerprint(ctx, s.Read(), domain.S(source["graph_name"]))
	if e != nil {
		return nil, e
	}
	if !codec.Equal(fingerprint, source) {
		return nil, domain.ErrConflict
	}
	receipt, e = Audit(ctx, s, witnesses)
	if e != nil {
		return nil, e
	}
	receipt["manifest_sha256"], receipt["logical_schema"], receipt["source_state"], receipt["target_database"] = pin, storage.LogicalSchema, source, target
	raw, e = codec.Canonical(receipt)
	if e != nil {
		return nil, e
	}
	if e = platform.Exclusive(target+".receipt.json", raw); e != nil {
		return nil, e
	}
	return receipt, nil
}
