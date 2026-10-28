package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestTaskObservationsArePinnedAndLegacyTasksRemainExplicit(t *testing.T) {
	root, err := os.MkdirTemp("", "av-context-")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(root)
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "workflow"))
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	private := filepath.Join(root, "private")
	if err = platform.PrivateDir(private, true); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(private, "experience.db")
	s, err := storage.Open(ctx, path, storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	s.Close()
	p := host.Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind, p.Database.Path = "sqlite", path
	p.Session.Root = filepath.Join(private, "sessions")
	p.Session.Facts = json.RawMessage(`{}`)
	p.Console.Port = 17805
	h, err := host.New(ctx, p, "initial", false, native.Factory())
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if err = h.Ready("http://127.0.0.1:17805"); err != nil {
		t.Fatal(err)
	}
	go h.Serve(ctx)
	defer func() {
		h.Close()
		dir := host.RegistryDir(host.BackendID(p))
		for _, name := range []string{"management.json", "binding.json", "runtime.json"} {
			os.Remove(filepath.Join(dir, name))
		}
		os.Remove(dir)
	}()
	pr := local.Project{Schema: "aevora.local-project/1", Name: "native", Workspace: root, Profile: filepath.Join(private, "host.json"), BackendID: host.BackendID(p)}
	if err = local.Register(pr); err != nil {
		t.Fatal(err)
	}
	cmd := Command(native.Factory())
	cmd.SetContext(ctx)
	cmd.SetOut(&bytes.Buffer{})
	first, err := newProjectTask(cmd, pr, p, "", false)
	if err != nil {
		t.Fatal(err)
	}
	second, err := newProjectTask(cmd, pr, p, "", false)
	if err != nil {
		t.Fatal(err)
	}
	if first.Name == second.Name || first.Run == second.Run || len(first.Context) == 0 {
		t.Fatal("tasks shared identity or lost observation")
	}
	if err = authorizeTask(cmd, first, p); err != nil {
		t.Fatal(err)
	}
	var facts domain.Map
	if err = json.Unmarshal(first.Facts, &facts); err != nil {
		t.Fatal(err)
	}
	if facts["runtime_engine"] != "go_native" || facts["storage_backend"] != "sqlite" {
		t.Fatal(facts)
	}
	// A persisted task cannot silently adopt changed conditions on resume.
	facts["runtime_engine"] = "python_reference"
	first.Facts, _ = json.Marshal(facts)
	if err = authorizeTask(cmd, first, p); err == nil {
		t.Fatal("changed pinned observation resumed")
	}
	legacy, err := local.NewTask(pr, "legacy", p.Session.Facts, false)
	if err != nil {
		t.Fatal(err)
	}
	if err = authorizeTask(cmd, legacy, p); err != nil {
		t.Fatal("legacy fixed task broken", err)
	}
}
