package cli_test

import (
	"bytes"
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/cli"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestNativeCLIInitializesWithoutServicesAndPreservesExistingProject(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	root := filepath.Join(t.TempDir(), "private")
	if e := platform.PrivateDir(root, true); e != nil {
		t.Fatal(e)
	}
	profile := filepath.Join(root, "host.json")
	data := filepath.Join(root, "data")
	run := func(args ...string) (int, []byte) {
		t.Helper()
		var out, stderr bytes.Buffer
		code := cli.Execute(ctx, append([]string{"--config", profile}, args...), bytes.NewReader(nil), &out, &stderr, native.Factory())
		if code != 0 {
			return code, stderr.Bytes()
		}
		return code, out.Bytes()
	}
	code, raw := run("init", "--data-dir", data)
	if code != 0 {
		t.Fatal(string(raw))
	}
	p, e := host.Load(profile)
	if e != nil {
		t.Fatal(e)
	}
	if p.Schema != "aevora.host-config/2" || p.Database.Kind != "sqlite" {
		t.Fatal("wrong default backend")
	}
	before, e := os.ReadFile(profile)
	if e != nil {
		t.Fatal(e)
	}
	id := host.BackendID(p)
	initial, e := os.ReadDir(p.Session.Root)
	if e != nil {
		t.Fatal(e)
	}
	known := map[string]bool{}
	for _, entry := range initial {
		known[entry.Name()] = true
	}
	defer func() {
		entries, _ := os.ReadDir(p.Session.Root)
		for _, entry := range entries {
			if !known[entry.Name()] {
				os.RemoveAll(filepath.Join(p.Session.Root, entry.Name()))
			}
		}
		if len(initial) == 0 {
			os.Remove(p.Session.Root)
		}
		registry := host.RegistryDir(id)
		os.Remove(filepath.Join(registry, "binding.json"))
		os.Remove(filepath.Join(registry, "runtime.json"))
		os.Remove(registry)
	}()
	if code, raw = run("init", "--data-dir", data); code == 0 {
		t.Fatal("existing project replaced", string(raw))
	}
	after, e := os.ReadFile(profile)
	if e != nil || !bytes.Equal(before, after) {
		t.Fatal("profile changed", e)
	}
	code, raw = run("doctor")
	if code != 0 {
		t.Fatal(string(raw))
	}
	value, e := codec.Parse(raw)
	if e != nil {
		t.Fatal(e)
	}
	result := domain.M(domain.M(value)["result"])
	if result["database"] != "READY" || result["runtime_ready"] != "NOT_PROVEN" {
		t.Fatal("offline doctor invented active runtime", result)
	}
	s, e := storage.Open(ctx, p.Database.Path, storage.Options{})
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	n, e := s.Read().Count(ctx, "Query", "")
	if e != nil || n != 0 {
		t.Fatal("doctor created a Query", n, e)
	}
}
