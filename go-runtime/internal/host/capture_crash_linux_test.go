package host_test

import (
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/capture"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"testing"
	"time"
)

type crashAfterCapture struct {
	engine.Engine
	manager engine.Manager
	stage   string
}

func (c *crashAfterCapture) Manage(ctx context.Context, request engine.Request) (json.RawMessage, error) {
	if request.Operation == "capture-ingest" && c.stage == "before" {
		syscall.Kill(os.Getpid(), syscall.SIGKILL)
		select {}
	}
	result, err := c.manager.Manage(ctx, request)
	if request.Operation == "capture-ingest" && err == nil && c.stage == "after" {
		syscall.Kill(os.Getpid(), syscall.SIGKILL)
		select {}
	}
	return result, err
}

func TestCaptureCrashChild(t *testing.T) {
	root := os.Getenv("AEVORA_CAPTURE_CRASH_ROOT")
	if root == "" {
		return
	}
	raw, err := os.ReadFile(filepath.Join(root, "host.json"))
	if err != nil {
		t.Fatal(err)
	}
	var p host.Profile
	if err = json.Unmarshal(raw, &p); err != nil {
		t.Fatal(err)
	}
	factory := func(ctx context.Context, owner *os.File, p host.Profile, scope engine.RunContext) (engine.Engine, error) {
		value, err := native.Factory()(ctx, owner, p, scope)
		if err != nil {
			return nil, err
		}
		return &crashAfterCapture{Engine: value, manager: value.(engine.Manager), stage: os.Getenv("AEVORA_CAPTURE_CRASH_STAGE")}, nil
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	h, err := host.New(ctx, p, "control", false, factory)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if err = h.Ready("http://127.0.0.1:17805"); err != nil {
		t.Fatal(err)
	}
	go h.Serve(ctx)
	pr, err := local.Load("fixture")
	if err != nil {
		t.Fatal(err)
	}
	out, err := host.ManagementCall(ctx, p, "", "configure-automatic", map[string]any{"project": pr.Name, "workspace": pr.Workspace, "proposals": true})
	if err != nil || out["status"] != "COMPLETED" {
		t.Fatal(out, err)
	}
	<-ctx.Done()
	t.Fatal("capture never reached crash boundary")
}

func TestCaptureSIGKILLBeforeAndAfterCommitKeepsOneRecoverableSource(t *testing.T) {
	for _, stage := range []string{"before", "after"} {
		t.Run(stage, func(t *testing.T) {
			base, err := os.MkdirTemp("", "av-cap-kill-")
			if err != nil {
				t.Fatal(err)
			}
			defer os.RemoveAll(base)
			t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(base, "registry"))
			private := filepath.Join(base, "private")
			if err = platform.PrivateDir(private, true); err != nil {
				t.Fatal(err)
			}
			p := host.Profile{Schema: "aevora.host-config/2"}
			p.Database.Kind = "sqlite"
			p.Database.Path = filepath.Join(private, "db.sqlite")
			p.Session.Root = filepath.Join(private, "sessions")
			p.Session.Facts = json.RawMessage(`{}`)
			p.Console.Port = 17805
			ctx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
			defer cancel()
			db, err := storage.Open(ctx, p.Database.Path, storage.Options{Create: true})
			if err != nil {
				t.Fatal(err)
			}
			db.Close()
			if err = platform.PrivateDir(p.Session.Root, true); err != nil {
				t.Fatal(err)
			}
			workspace := filepath.Join(base, "workspace")
			if err = os.Mkdir(workspace, 0700); err != nil {
				t.Fatal(err)
			}
			raw, _ := json.Marshal(p)
			if err = os.WriteFile(filepath.Join(private, "host.json"), raw, 0600); err != nil {
				t.Fatal(err)
			}
			pr := local.Project{Schema: "aevora.local-project/1", Name: "fixture", Workspace: workspace, Profile: filepath.Join(private, "host.json"), BackendID: host.BackendID(p)}
			if err = local.Register(pr); err != nil {
				t.Fatal(err)
			}
			defer func() {
				dir := host.RegistryDir(pr.BackendID)
				for _, name := range []string{"management.json", "binding.json", "runtime.json"} {
					os.Remove(filepath.Join(dir, name))
				}
				os.Remove(dir)
			}()
			event, err := captureformat.New(pr.Name, "session-1", "turn-1", "call-1", "BASH", "JSON_DECODE_ERROR")
			if err != nil {
				t.Fatal(err)
			}
			if _, err = capture.Enqueue(p.Session.Root, event); err != nil {
				t.Fatal(err)
			}
			child := exec.CommandContext(ctx, os.Args[0], "-test.run=^TestCaptureCrashChild$")
			child.Env = append(os.Environ(), "AEVORA_CAPTURE_CRASH_ROOT="+private, "AEVORA_CAPTURE_CRASH_STAGE="+stage)
			output, err := child.CombinedOutput()
			if err == nil || child.ProcessState == nil {
				t.Fatal("child did not crash", string(output), err)
			}
			status, ok := child.ProcessState.Sys().(syscall.WaitStatus)
			if !ok || !status.Signaled() || status.Signal() != syscall.SIGKILL {
				t.Fatal("unexpected child failure", string(output), err)
			}
			if scan, e := capture.Scan(p.Session.Root, 10); e != nil || scan.Pending != 1 {
				t.Fatal("pending source lost at crash", scan, e)
			}
			db, err = storage.Open(ctx, p.Database.Path, storage.Options{})
			if err != nil {
				t.Fatal(err)
			}
			count, err := db.Read().Count(ctx, "ExternalObservation", "")
			db.Close()
			want := 0
			if stage == "after" {
				want = 1
			}
			if err != nil || count != want {
				t.Fatal("wrong commit boundary", count, want, err)
			}
			h, err := host.New(ctx, p, "control", false, native.Factory())
			if err != nil {
				t.Fatal(err)
			}
			if err = h.Ready("http://127.0.0.1:17805"); err != nil {
				t.Fatal(err)
			}
			go h.Serve(ctx)
			deadline := time.Now().Add(8 * time.Second)
			for time.Now().Before(deadline) {
				scan, e := capture.Scan(p.Session.Root, 10)
				if e == nil && scan.Pending == 0 {
					break
				}
				time.Sleep(30 * time.Millisecond)
			}
			if scan, e := capture.Scan(p.Session.Root, 10); e != nil || scan.Pending != 0 {
				h.Close()
				t.Fatal("crash recovery did not drain", scan, e)
			}
			if err = h.Close(); err != nil {
				t.Fatal(err)
			}
			db, err = storage.Open(ctx, p.Database.Path, storage.Options{})
			if err != nil {
				t.Fatal(err)
			}
			defer db.Close()
			for _, label := range []string{"ExternalObservation", "Candidate"} {
				n, e := db.Read().Count(ctx, label, "")
				if e != nil || n != 1 {
					t.Fatal("crash replay duplicated or lost data", label, n, e)
				}
			}
		})
	}
}
