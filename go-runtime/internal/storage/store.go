// Package storage implements a bounded, append-only domain repository in SQLite.
// Consumer input never selects SQL or table/column names.
package storage

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	_ "modernc.org/sqlite"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

const LogicalSchema = "aevora.graph/1.2"
const QueryVersion = "aevora.multihop/1.1"
const PhysicalVersion = 1
const applicationID = 0x41565241

var ErrConflict = errors.New("AEVORA_IMMUTABLE_CONFLICT")
var ErrInvalid = codec.ErrInvalid
var ErrIncompatible = errors.New("AEVORA_STORAGE_INCOMPATIBLE")
var idPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.:/@+\-]{0,239}$`)

//go:embed schema.sql
var schemaSQL string

type Catalog struct {
	Schemas      map[string]struct{ Labels, Relationships []string } `json:"schemas"`
	PublicFields map[string][]string                                 `json:"public_fields"`
	Guidance     map[string]map[string]any                           `json:"lifecycle_guidance"`
}

var catalog = func() Catalog {
	var c Catalog
	raw, e := contracts.Files.ReadFile("reference.json")
	if e != nil {
		panic(e)
	}
	if e = json.Unmarshal(raw, &c); e != nil {
		panic(e)
	}
	return c
}()

func ValidID(id string) bool { return idPattern.MatchString(id) }
func LifecycleGuidance(state string) map[string]any {
	out := map[string]any{}
	for k, v := range catalog.Guidance[state] {
		out[k] = v
	}
	return out
}
func AllowedLabel(label string) bool {
	for _, x := range catalog.Schemas[LogicalSchema].Labels {
		if x == label {
			return true
		}
	}
	return false
}
func AllowedRelation(relation string) bool {
	for _, x := range catalog.Schemas[LogicalSchema].Relationships {
		if x == relation {
			return true
		}
	}
	return false
}
func Public(label string, p map[string]any) map[string]any {
	out := map[string]any{}
	for _, k := range catalog.PublicFields[label] {
		if v, ok := p[k]; ok {
			out[k] = v
		}
	}
	return out
}

type Options struct {
	Create bool
	Owner  *os.File
}
type Store struct {
	writer, readers, heads *sql.DB
	file                   *os.File
	owns                   bool
	path                   string
	backendID              string
}
type queryer interface {
	QueryContext(context.Context, string, ...any) (*sql.Rows, error)
	QueryRowContext(context.Context, string, ...any) *sql.Row
	ExecContext(context.Context, string, ...any) (sql.Result, error)
}
type Repository struct {
	s      *Store
	q      queryer
	write  bool
	budget *ReadBudget
}

func dsn(path, mode string) string {
	p := filepath.ToSlash(path)
	if filepath.VolumeName(path) != "" {
		p = "/" + p
	}
	u := url.URL{Scheme: "file", Path: p}
	v := url.Values{"mode": {mode}, "_pragma": {"foreign_keys(1)", "synchronous(FULL)", "busy_timeout(1000)"}}
	u.RawQuery = v.Encode()
	return u.String()
}
func Open(ctx context.Context, path string, o Options) (s *Store, err error) {
	if !filepath.IsAbs(path) {
		return nil, ErrInvalid
	}
	if err = platform.PrivateDir(filepath.Dir(path), o.Create); err != nil {
		return nil, err
	}
	if o.Create {
		if err = platform.Exclusive(path, nil); err != nil {
			return nil, err
		}
	}
	s = &Store{path: path}
	cleanup := s
	defer func() {
		if err != nil {
			cleanup.Close()
		}
	}()
	check, e := platform.OpenPrivate(path, os.O_RDWR)
	if e != nil {
		return nil, e
	}
	actual, e := check.Stat()
	check.Close()
	if e != nil {
		return nil, e
	}
	if o.Owner != nil {
		selected, e := o.Owner.Stat()
		if e != nil || !os.SameFile(actual, selected) {
			return nil, platform.ErrUnsafe
		}
		s.file = o.Owner
	} else {
		s.file, err = platform.LockData(path)
		s.owns = true
		if err != nil {
			return nil, err
		}
	}
	for _, suffix := range []string{"-wal", "-shm"} {
		if _, e = os.Lstat(path + suffix); e == nil {
			f, e := platform.OpenPrivate(path+suffix, os.O_RDWR)
			if e != nil {
				return nil, e
			}
			f.Close()
		} else if !os.IsNotExist(e) {
			return nil, e
		}
	}
	s.writer, err = sql.Open("sqlite", dsn(path, "rw"))
	if err != nil {
		return nil, err
	}
	s.writer.SetMaxOpenConns(1)
	if err = s.writer.PingContext(ctx); err != nil {
		return nil, err
	}
	if o.Create {
		tx, e := s.writer.BeginTx(ctx, nil)
		if e != nil {
			return nil, e
		}
		defer tx.Rollback()
		if _, err = tx.ExecContext(ctx, schemaSQL); err != nil {
			return nil, err
		}
		h := sha256.Sum256([]byte(schemaSQL))
		var nonce [16]byte
		if _, err = rand.Read(nonce[:]); err != nil {
			return nil, err
		}
		if _, err = tx.ExecContext(ctx, "INSERT INTO metadata VALUES('schema_sha256',?),('logical_schema',?),('backend_uuid',?)", hex.EncodeToString(h[:]), LogicalSchema, hex.EncodeToString(nonce[:])); err != nil {
			return nil, err
		}
		if _, err = tx.ExecContext(ctx, fmt.Sprintf("PRAGMA application_id=%d;PRAGMA user_version=%d", applicationID, PhysicalVersion)); err != nil {
			return nil, err
		}
		if err = tx.Commit(); err != nil {
			return nil, err
		}
	}
	var app, version int
	if err = s.writer.QueryRowContext(ctx, "PRAGMA application_id").Scan(&app); err != nil {
		return nil, err
	}
	if err = s.writer.QueryRowContext(ctx, "PRAGMA user_version").Scan(&version); err != nil {
		return nil, err
	}
	if app != applicationID || version != PhysicalVersion {
		return nil, ErrIncompatible
	}
	var logical, hash string
	if err = s.writer.QueryRowContext(ctx, "SELECT value FROM metadata WHERE key='logical_schema'").Scan(&logical); err != nil {
		return nil, err
	}
	if err = s.writer.QueryRowContext(ctx, "SELECT value FROM metadata WHERE key='schema_sha256'").Scan(&hash); err != nil {
		return nil, err
	}
	h := sha256.Sum256([]byte(schemaSQL))
	if logical != LogicalSchema || hash != hex.EncodeToString(h[:]) {
		return nil, ErrIncompatible
	}
	if err = checkDDL(ctx, s.writer); err != nil {
		return nil, err
	}
	var uuid string
	if err = s.writer.QueryRowContext(ctx, "SELECT value FROM metadata WHERE key='backend_uuid'").Scan(&uuid); err != nil {
		return nil, err
	}
	decoded, e := hex.DecodeString(uuid)
	if e != nil || len(decoded) != 16 {
		return nil, ErrIncompatible
	}
	physical, e := platform.FileIdentity(s.file)
	if e != nil {
		return nil, e
	}
	backendHash := sha256.Sum256([]byte(physical + "/" + uuid))
	s.backendID = hex.EncodeToString(backendHash[:])
	var mode string
	if err = s.writer.QueryRowContext(ctx, "PRAGMA journal_mode=WAL").Scan(&mode); err != nil || mode != "wal" {
		if err == nil {
			err = ErrIncompatible
		}
		return nil, err
	}
	var integrity string
	if err = s.writer.QueryRowContext(ctx, "PRAGMA quick_check(1)").Scan(&integrity); err != nil || integrity != "ok" {
		if err == nil {
			err = ErrIncompatible
		}
		return nil, err
	}
	s.readers, err = sql.Open("sqlite", dsn(path, "ro"))
	if err != nil {
		return nil, err
	}
	s.readers.SetMaxOpenConns(4)
	s.heads, err = sql.Open("sqlite", dsn(path, "ro"))
	if err != nil {
		return nil, err
	}
	s.heads.SetMaxOpenConns(1)
	if o.Create {
		payload := map[string]any{"id": LogicalSchema, "version": LogicalSchema}
		err = s.Write(ctx, func(r *Repository) error { return r.PutNode(ctx, "Schema", payload) })
	}
	return s, err
}
func (s *Store) Close() error {
	var result error
	for _, db := range []*sql.DB{s.heads, s.readers, s.writer} {
		if db != nil {
			result = errors.Join(result, db.Close())
		}
	}
	if s.file != nil && s.owns {
		result = errors.Join(result, s.file.Close())
	}
	return result
}
func (s *Store) Identity() (string, error) {
	physical, e := platform.FileIdentity(s.file)
	if e != nil {
		return "", e
	}
	var uuid string
	if e = s.readers.QueryRow("SELECT value FROM metadata WHERE key='backend_uuid'").Scan(&uuid); e != nil {
		return "", e
	}
	return physical + "/" + uuid, nil
}
func (s *Store) Read() *Repository { return &Repository{s: s, q: s.readers} }
func (s *Store) BackendID() string { return s.backendID }
func (s *Store) check() error {
	f, e := platform.OpenPrivate(s.path, os.O_RDONLY)
	if e != nil {
		return e
	}
	defer f.Close()
	a, e := f.Stat()
	if e != nil {
		return e
	}
	b, e := s.file.Stat()
	if e != nil || !os.SameFile(a, b) {
		return platform.ErrUnsafe
	}
	return nil
}
func (s *Store) Write(ctx context.Context, fn func(*Repository) error) error {
	if e := s.check(); e != nil {
		return e
	}
	tx, e := s.writer.BeginTx(ctx, nil)
	if e != nil {
		return e
	}
	defer tx.Rollback()
	// A no-op write obtains SQLite's writer reservation before observing state.
	if _, e = tx.ExecContext(ctx, "UPDATE metadata SET value=value WHERE key='logical_schema'"); e != nil {
		return e
	}
	if e = fn(&Repository{s: s, q: tx, write: true}); e != nil {
		return e
	}
	return tx.Commit()
}
func (s *Store) Snapshot(ctx context.Context, fn func(*Repository) error) error {
	tx, e := s.readers.BeginTx(ctx, &sql.TxOptions{ReadOnly: true})
	if e != nil {
		return e
	}
	defer tx.Rollback()
	return fn(&Repository{s: s, q: tx})
}

func decode(label string, raw []byte, sha string) (map[string]any, error) {
	v, e := codec.Parse(raw)
	if e != nil {
		return nil, e
	}
	p, ok := v.(map[string]any)
	if !ok {
		return nil, ErrInvalid
	}
	actual, e := codec.Digest(p)
	if e != nil || actual != sha {
		return nil, ErrConflict
	}
	id, ok := p["id"].(string)
	if !ok || !ValidID(id) || (!AllowedLabel(label) && label != "edge") {
		return nil, ErrInvalid
	}
	return p, nil
}
func (r *Repository) Get(ctx context.Context, label, id string) (map[string]any, error) {
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	if !AllowedLabel(label) || !ValidID(id) {
		return nil, ErrInvalid
	}
	var raw []byte
	var sha string
	e := r.q.QueryRowContext(ctx, "SELECT CASE WHEN length(payload)<=262144 THEN payload ELSE null END,sha256 FROM nodes WHERE label=? AND id=?", label, id).Scan(&raw, &sha)
	if errors.Is(e, sql.ErrNoRows) {
		return nil, nil
	}
	if e != nil {
		return nil, e
	}
	if raw == nil {
		return nil, ErrReadBudget
	}
	if e = r.charge(label, id, raw); e != nil {
		return nil, e
	}
	p, e := decode(label, raw, sha)
	if e == nil && p["id"] != id {
		return nil, ErrConflict
	}
	return p, e
}
func (r *Repository) FreshHead(ctx context.Context, id string) (map[string]any, error) {
	if r.write {
		return r.Get(ctx, "LifecycleHead", id)
	}
	return (&Repository{s: r.s, q: r.s.heads, budget: r.budget}).Get(ctx, "LifecycleHead", id)
}
func (r *Repository) PutNode(ctx context.Context, label string, p map[string]any) error {
	if !r.write || !AllowedLabel(label) {
		return ErrInvalid
	}
	id, ok := p["id"].(string)
	if !ok || !ValidID(id) {
		return ErrInvalid
	}
	raw, e := codec.Canonical(p)
	if e != nil || len(raw) > 262144 {
		return ErrInvalid
	}
	sha, e := codec.Digest(p)
	if e != nil {
		return e
	}
	_, e = r.q.ExecContext(ctx, "INSERT INTO nodes(label,id,payload,sha256) VALUES(?,?,?,?) ON CONFLICT(label,id) DO NOTHING", label, id, raw, sha)
	if e != nil {
		return e
	}
	var old string
	e = r.q.QueryRowContext(ctx, "SELECT sha256 FROM nodes WHERE label=? AND id=?", label, id).Scan(&old)
	if e != nil {
		return e
	}
	if old != sha {
		return ErrConflict
	}
	return nil
}
func (r *Repository) CASHead(ctx context.Context, id, expected string, p map[string]any) error {
	if !r.write || p["id"] != id {
		return ErrInvalid
	}
	raw, e := codec.Canonical(p)
	if e != nil {
		return e
	}
	sha, e := codec.Digest(p)
	if e != nil {
		return e
	}
	result, e := r.q.ExecContext(ctx, "UPDATE nodes SET payload=?,sha256=? WHERE label='LifecycleHead' AND id=? AND sha256=?", raw, sha, id, expected)
	if e != nil {
		return e
	}
	n, e := result.RowsAffected()
	if e != nil {
		return e
	}
	if n != 1 {
		return ErrConflict
	}
	return nil
}

type Edge struct {
	ID, Relation, SourceLabel, SourceID, TargetLabel, TargetID string
	Payload                                                    map[string]any
	SHA256                                                     string
}

func (r *Repository) PutEdge(ctx context.Context, relation, sl, sid, tl, tid string, p map[string]any) error {
	if !r.write || !AllowedRelation(relation) || !AllowedLabel(sl) || !AllowedLabel(tl) || !ValidID(sid) || !ValidID(tid) {
		return ErrInvalid
	}
	sha, e := codec.Digest([]any{relation, sl, sid, tl, tid})
	if e != nil {
		return e
	}
	id := "edge:" + sha
	value := map[string]any{}
	for k, v := range p {
		value[k] = v
	}
	if old, ok := value["id"]; ok && old != id {
		return ErrConflict
	}
	value["id"] = id
	raw, e := codec.Canonical(value)
	if e != nil {
		return e
	}
	sha, e = codec.Digest(value)
	if e != nil {
		return e
	}
	_, e = r.q.ExecContext(ctx, "INSERT INTO edges VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING", id, relation, sl, sid, tl, tid, raw, sha)
	if e != nil {
		return e
	}
	var old string
	e = r.q.QueryRowContext(ctx, "SELECT sha256 FROM edges WHERE id=?", id).Scan(&old)
	if e != nil {
		return e
	}
	if old != sha {
		return ErrConflict
	}
	return nil
}
func (r *Repository) Edges(ctx context.Context, label, id, relation string, incoming bool) ([]Edge, error) {
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	if !AllowedLabel(label) || !ValidID(id) || (relation != "" && !AllowedRelation(relation)) {
		return nil, ErrInvalid
	}
	column := "source_label=? AND source_id=?"
	if incoming {
		column = "target_label=? AND target_id=?"
	}
	args := []any{label, id}
	if relation != "" {
		column += " AND relation=?"
		args = append(args, relation)
	}
	rows, e := r.q.QueryContext(ctx, "SELECT id,relation,source_label,source_id,target_label,target_id,CASE WHEN length(payload)<=262144 THEN payload ELSE null END,sha256 FROM edges WHERE "+column+" ORDER BY id LIMIT 1201", args...)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	result := []Edge{}
	for rows.Next() {
		var row Edge
		var raw []byte
		if e = rows.Scan(&row.ID, &row.Relation, &row.SourceLabel, &row.SourceID, &row.TargetLabel, &row.TargetID, &raw, &row.SHA256); e != nil {
			return nil, e
		}
		if raw == nil {
			return nil, ErrReadBudget
		}
		if e = r.charge("edge", row.ID, raw); e != nil {
			return nil, e
		}
		row.Payload, e = decode("edge", raw, row.SHA256)
		if e != nil {
			return nil, e
		}
		identity, e := codec.Digest([]any{row.Relation, row.SourceLabel, row.SourceID, row.TargetLabel, row.TargetID})
		if e != nil || row.ID != "edge:"+identity || row.Payload["id"] != row.ID || !AllowedRelation(row.Relation) || !AllowedLabel(row.SourceLabel) || !AllowedLabel(row.TargetLabel) {
			return nil, ErrConflict
		}
		result = append(result, row)
		if len(result) > 1200 {
			return nil, ErrInvalid
		}
	}
	return result, rows.Err()
}
func (r *Repository) RequireEdge(ctx context.Context, relation, sl, sid, tl, tid string) error {
	if e := r.chargeQuery(); e != nil {
		return e
	}
	sha, e := codec.Digest([]any{relation, sl, sid, tl, tid})
	if e != nil {
		return e
	}
	var raw []byte
	var recorded string
	e = r.q.QueryRowContext(ctx, "SELECT CASE WHEN length(payload)<=262144 THEN payload ELSE null END,sha256 FROM edges WHERE id=? AND relation=? AND source_label=? AND source_id=? AND target_label=? AND target_id=?", "edge:"+sha, relation, sl, sid, tl, tid).Scan(&raw, &recorded)
	if e != nil {
		return ErrConflict
	}
	if raw == nil {
		return ErrReadBudget
	}
	if e = r.charge("edge", "edge:"+sha, raw); e != nil {
		return e
	}
	_, e = decode("edge", raw, recorded)
	return e
}

type Filter struct {
	Run, Candidate, Experience, After string
	Limit                             int
}

func (r *Repository) List(ctx context.Context, label string, f Filter) ([]map[string]any, error) {
	if e := r.chargeQuery(); e != nil {
		return nil, e
	}
	if !AllowedLabel(label) || f.Limit < 1 || f.Limit > 4097 {
		return nil, ErrInvalid
	}
	query := "SELECT CASE WHEN length(payload)<=262144 THEN payload ELSE null END,sha256 FROM nodes WHERE label=? AND id>?"
	args := []any{label, f.After}
	for _, term := range []struct{ name, value string }{{"run_id", f.Run}, {"candidate_id", f.Candidate}, {"experience_id", f.Experience}} {
		if term.value != "" {
			if !ValidID(term.value) {
				return nil, ErrInvalid
			}
			query += " AND json_extract(payload,'$." + term.name + "')=?"
			args = append(args, term.value)
		}
	}
	query += " ORDER BY id LIMIT ?"
	args = append(args, f.Limit)
	rows, e := r.q.QueryContext(ctx, query, args...)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	result := []map[string]any{}
	for rows.Next() {
		var raw []byte
		var sha string
		if e = rows.Scan(&raw, &sha); e != nil {
			return nil, e
		}
		if raw == nil {
			return nil, ErrReadBudget
		}
		p, e := decode(label, raw, sha)
		if e != nil {
			return nil, e
		}
		if e = r.charge(label, p["id"].(string), raw); e != nil {
			return nil, e
		}
		result = append(result, p)
	}
	return result, rows.Err()
}
func (s *Store) BindRun(ctx context.Context, run, hash string, facts []byte) error {
	return s.Write(ctx, func(r *Repository) error {
		_, e := r.q.ExecContext(ctx, "INSERT INTO run_contexts VALUES(?,?,?) ON CONFLICT(run_id) DO NOTHING", run, hash, facts)
		if e != nil {
			return e
		}
		var old string
		e = r.q.QueryRowContext(ctx, "SELECT context_sha256 FROM run_contexts WHERE run_id=?", run).Scan(&old)
		if e != nil {
			return e
		}
		if old != hash {
			return ErrConflict
		}
		return nil
	})
}

func (s *Store) Backup(ctx context.Context, target string) error {
	if !filepath.IsAbs(target) || strings.ContainsRune(target, 0) {
		return ErrInvalid
	}
	if e := platform.PrivateDir(filepath.Dir(target), false); e != nil {
		return e
	}
	if e := platform.Exclusive(target, nil); e != nil {
		return e
	}
	// VACUUM INTO is SQLite's documented consistent snapshot alternative. Failed
	// outputs remain for inspection and are never silently loaded as a new DB.
	_, e := s.writer.ExecContext(ctx, "VACUUM INTO ?", target)
	if e != nil {
		return e
	}
	f, e := platform.OpenPrivate(target, os.O_RDWR)
	if e != nil {
		return e
	}
	defer f.Close()
	return f.Sync()
}
