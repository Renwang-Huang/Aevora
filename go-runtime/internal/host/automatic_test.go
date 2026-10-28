package host_test

import (
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestAutomaticConsumerGetsMeasuredDistinctTasksAndSurvivesRestart(t *testing.T) {
	root, err := os.MkdirTemp("", "av-auto-")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(root)
	t.Setenv("AEVORA_WORKFLOW_HOME", filepath.Join(root, "registry"))
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	private := filepath.Join(root, "private")
	platform.PrivateDir(private, true)
	p := host.Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind, p.Database.Path = "sqlite", filepath.Join(private, "data.db")
	p.Session.Root = filepath.Join(private, "sessions")
	p.Session.Facts = json.RawMessage(`{}`)
	p.Console.Port = 17805
	db, err := storage.Open(ctx, p.Database.Path, storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	db.Close()
	pr := local.Project{Schema: "aevora.local-project/1", Name: "controlled", Workspace: root, Profile: filepath.Join(private, "host.json"), BackendID: host.BackendID(p)}
	if err = local.Register(pr); err != nil {
		t.Fatal(err)
	}
	nested := filepath.Join(root, "nested")
	if err = os.Mkdir(nested, 0700); err != nil {
		t.Fatal(err)
	}
	child := local.Project{Schema: "aevora.local-project/1", Name: "nested", Workspace: nested, Profile: pr.Profile, BackendID: pr.BackendID}
	if err = local.Register(child); err != nil {
		t.Fatal(err)
	}
	start := func() *host.Host {
		h, err := host.New(ctx, p, "control", false, native.Factory())
		if err != nil {
			t.Fatal(err)
		}
		if err = h.Ready("http://127.0.0.1:17805"); err != nil {
			t.Fatal(err)
		}
		go h.Serve(ctx)
		return h
	}
	h := start()
	defer func() {
		h.Close()
		dir := host.RegistryDir(host.BackendID(p))
		for _, name := range []string{"management.json", "binding.json", "runtime.json"} {
			os.Remove(filepath.Join(dir, name))
		}
		os.Remove(dir)
	}()
	result, err := host.ManagementCall(ctx, p, "", "configure-automatic", map[string]any{"project": pr.Name, "workspace": pr.Workspace, "proposals": true})
	if err != nil || result["status"] != "COMPLETED" {
		t.Fatal(result, err)
	}
	if _, err = host.AutomaticProjectCall(ctx, p.Session.Root, "", child.Name, "auto-open"); err == nil {
		t.Fatal("unlisted project acquired an automatic task")
	}
	foreign := child
	foreign.Name, foreign.BackendID = "foreign", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
	if err = local.Register(foreign); err != nil {
		t.Fatal(err)
	}
	badPolicy := map[string]any{"project": pr.Name, "workspace": pr.Workspace, "proposals": true, "routes": []any{map[string]any{"project": foreign.Name, "workspace": foreign.Workspace}}}
	result, err = host.ManagementCall(ctx, p, "", "configure-automatic", badPolicy)
	if err != nil || result["status"] == "COMPLETED" {
		t.Fatal("route to a different backend was accepted", result, err)
	}
	policy := map[string]any{"project": pr.Name, "workspace": pr.Workspace, "proposals": true, "routes": []any{map[string]any{"project": child.Name, "workspace": child.Workspace}}}
	result, err = host.ManagementCall(ctx, p, "", "configure-automatic", policy)
	if err != nil || result["status"] != "COMPLETED" {
		t.Fatal("owner could not add same-Host route", result, err)
	}
	unscoped, err := host.AutomaticProjectCall(ctx, p.Session.Root, "", "@unregistered-workspace", "auto-open")
	if err != nil || unscoped["workspace_scope"] != "UNREGISTERED_RUNTIME_FACTS_ONLY" {
		t.Fatal("unregistered workspace could not receive bounded runtime context", unscoped, err)
	}
	unscopedName, _ := unscoped["task_name"].(string)
	unscopedTask, _, err := local.LoadTask(pr.Name, unscopedName)
	if err != nil {
		t.Fatal(err)
	}
	var unscopedFacts map[string]any
	if json.Unmarshal(unscopedTask.Facts, &unscopedFacts) != nil || unscopedFacts["runtime_engine"] != "go_native" || unscopedFacts["target_project"] != nil || unscopedFacts["target_revision"] != nil {
		t.Fatal("unregistered workspace inherited target claims", unscopedFacts)
	}
	if _, err = host.AutomaticProjectCall(ctx, p.Session.Root, unscopedName, pr.Name, "auto-open"); err == nil {
		t.Fatal("unregistered task was rebound to a registered project")
	}
	selected, err := host.AutomaticProjectCall(ctx, p.Session.Root, "", child.Name, "auto-open")
	if err != nil {
		t.Fatal("authorized route unavailable", err)
	}
	childName, _ := selected["task_name"].(string)
	childTask, _, err := local.LoadTask(child.Name, childName)
	if err != nil {
		t.Fatal(err)
	}
	var childFacts map[string]any
	if json.Unmarshal(childTask.Facts, &childFacts) != nil || childFacts["target_project"] != child.Name {
		t.Fatal("Host failed to measure selected project", childFacts)
	}
	if _, err = host.AutomaticProjectCall(ctx, p.Session.Root, childName, pr.Name, "auto-open"); err == nil {
		t.Fatal("child task resumed in default project")
	}
	preview, err := host.ManagementCall(ctx, p, "", "automatic-route", map[string]any{"project": child.Name, "apply": false})
	if err != nil || preview["status"] != "COMPLETED" || preview["result"].(map[string]any)["removable"] != false {
		t.Fatal("active route preview failed", preview, err)
	}
	active := preview["result"].(map[string]any)["active_tasks"].([]any)
	if len(active) != 1 || active[0] != childName {
		t.Fatal("route preview omitted active task", active)
	}
	protected, err := host.ManagementCall(ctx, p, "", "automatic-route", map[string]any{"project": pr.Name, "apply": true})
	if err != nil || protected["status"] != "FAILED_KNOWN" || protected["code"] != "AEVORA_ROUTE_NOT_REMOVABLE" {
		t.Fatal("default route was not protected", protected, err)
	}
	blocked, err := host.ManagementCall(ctx, p, "", "automatic-route", map[string]any{"project": child.Name, "apply": true})
	if err != nil || blocked["status"] != "FAILED_KNOWN" || blocked["code"] != "AEVORA_ROUTE_IN_USE" {
		t.Fatal("active route was revoked", blocked, err)
	}
	grantRaw, err := platform.ReadPrivate(filepath.Join(p.Session.Root, "automatic-grant.json"), 4096)
	if err != nil {
		t.Fatal(err)
	}
	grant, err := wire.Decode(grantRaw, 4096)
	if err != nil {
		t.Fatal(err)
	}
	conn, err := platform.Dial(ctx, grant["socket"].(string))
	if err != nil {
		t.Fatal(err)
	}
	if err = wire.WritePacket(conn, map[string]any{"schema_version": "aevora.management-auth/1", "backend_id": pr.BackendID, "token": grant["token"], "nonce": strings.Repeat("a", 64)}); err != nil {
		t.Fatal(err)
	}
	if _, err = wire.ReadPacket(conn); err != nil {
		t.Fatal(err)
	}
	if err = wire.WritePacket(conn, map[string]any{"schema_version": "aevora.management-request/1", "run_id": "", "operation": "automatic-route", "arguments": map[string]any{"project": child.Name, "apply": true}}); err != nil {
		t.Fatal(err)
	}
	denialRaw, err := wire.ReadPacket(conn)
	conn.Close()
	denial, decodeErr := wire.Decode(denialRaw, 4096)
	if err != nil || decodeErr != nil || denial["code"] != "AEVORA_INVALID_OR_UNAUTHORIZED_INPUT" {
		t.Fatal("enrollment capability could manage routes", denial, err, decodeErr)
	}
	result, err = host.ManagementCall(ctx, p, "", "configure-automatic", map[string]any{"project": pr.Name, "workspace": pr.Workspace, "proposals": true})
	if err != nil || result["status"] == "COMPLETED" {
		t.Fatal("active owner policy silently lost a route", result, err)
	}
	client := func(routeWorkspace bool) (*mcp.ClientSession, func()) {
		inR, inW := io.Pipe()
		outR, outW := io.Pipe()
		lifetime, stop := context.WithCancel(ctx)
		done := make(chan error, 1)
		go func() {
			defer outW.Close()
			if routeWorkspace {
				done <- host.PersistentWorkspaceBridge(lifetime, p.Session.Root, inR, outW)
			} else {
				done <- host.PersistentBridge(lifetime, p.Session.Root, "", "", true, inR, outW)
			}
		}()
		s, err := mcp.NewClient(&mcp.Implementation{Name: "controlled", Version: "1"}, nil).Connect(ctx, &mcp.IOTransport{Reader: outR, Writer: inW}, &mcp.ClientSessionOptions{ProtocolVersion: "2025-11-25"})
		if err != nil {
			t.Fatal(err)
		}
		return s, func() {
			s.Close()
			inW.Close()
			outR.Close()
			stop()
			select {
			case <-done:
			case <-time.After(3 * time.Second):
				t.Fatal("proxy did not close")
			}
		}
	}
	a, closeA := client(false)
	defer closeA()
	b, closeB := client(false)
	defer closeB()
	query := func(s *mcp.ClientSession) map[string]any {
		response, err := s.CallTool(ctx, &mcp.CallToolParams{Name: "resolve_experience", Arguments: map[string]any{"task_context": map[string]any{}}})
		if err != nil || response.IsError {
			t.Fatal(response, err)
		}
		encoded, _ := json.Marshal(response.StructuredContent)
		var value map[string]any
		if json.Unmarshal(encoded, &value) != nil {
			t.Fatal(response)
		}
		return value
	}
	first := query(a)
	second := query(b)
	unknown, closeUnknown := client(true)
	if !strings.Contains(unknown.InitializeResult().Instructions, "working directory is not a registered project") {
		t.Fatal("missing unregistered workspace explanation")
	}
	unknownResult := query(unknown)
	if unknownResult["context"].(map[string]any)["target_project"] != nil {
		t.Fatal("unregistered connector claimed a target project", unknownResult)
	}
	closeUnknown()
	if first["run_id"] == second["run_id"] {
		t.Fatal("ordinary clients shared a daily Run")
	}
	facts := first["context"].(map[string]any)
	if facts["runtime_engine"] != "go_native" || facts["runtime_version"] != "0.6.0-dev" {
		t.Fatal("missing trusted context", facts)
	}
	if err = h.Close(); err != nil {
		t.Fatal(err)
	}
	h = start()
	unscopedResume, err := host.AutomaticProjectCall(ctx, p.Session.Root, unscopedName, "@unregistered-workspace", "auto-open")
	if err != nil || unscopedResume["run_id"] != unscopedTask.Run {
		t.Fatal("unregistered task did not survive same-context restart", unscopedResume, err)
	}
	if _, err = host.AutomaticProjectCall(ctx, p.Session.Root, unscopedName, "@unregistered-workspace", "auto-close"); err != nil {
		t.Fatal(err)
	}
	continued, err := host.AutomaticProjectCall(ctx, p.Session.Root, childName, child.Name, "auto-open")
	if err != nil || continued["run_id"] != childTask.Run {
		t.Fatal("authorized route did not survive restart", continued, err)
	}
	if _, err = host.AutomaticProjectCall(ctx, p.Session.Root, childName, child.Name, "auto-close"); err != nil {
		t.Fatal(err)
	}
	removed, err := host.ManagementCall(ctx, p, "", "automatic-route", map[string]any{"project": child.Name, "apply": true})
	if err != nil || removed["status"] != "COMPLETED" || removed["result"].(map[string]any)["status"] != "REMOVED" {
		t.Fatal("inactive route could not be revoked", removed, err)
	}
	if _, err = host.AutomaticProjectCall(ctx, p.Session.Root, "", child.Name, "auto-open"); err == nil {
		t.Fatal("revoked route opened a new task")
	}
	if _, state, err := local.LoadTask(child.Name, childName); err != nil || state.State != "CLOSED" {
		t.Fatal("revocation changed task history", state, err)
	}
	if err = h.Close(); err != nil {
		t.Fatal(err)
	}
	h = start()
	if _, err = host.AutomaticProjectCall(ctx, p.Session.Root, "", child.Name, "auto-open"); err == nil {
		t.Fatal("revoked route returned after Host restart")
	}
	resumed := query(a)
	if resumed["run_id"] != first["run_id"] {
		t.Fatal("restart silently replaced task")
	}
	var taskName string
	for _, entry := range mustTasks(t, pr.Name) {
		task := entry["task"].(local.Task)
		if task.Run == first["run_id"] {
			taskName = task.Name
		}
	}
	if taskName == "" {
		t.Fatal("automatic task not persisted")
	}
	if _, err = host.AutomaticCall(ctx, p.Session.Root, taskName, "review"); err == nil {
		t.Fatal("enrollment capability allowed review")
	}
	if _, err = host.AutomaticCall(ctx, p.Session.Root, taskName, "auto-close"); err != nil {
		t.Fatal(err)
	}
	response, err := a.CallTool(ctx, &mcp.CallToolParams{Name: "resolve_experience", Arguments: map[string]any{"task_context": map[string]any{}}})
	if err != nil || !response.IsError {
		t.Fatal("revoked task auto-authorized or downstream transport lost", response, err)
	}
}
func mustTasks(t *testing.T, project string) []map[string]any {
	t.Helper()
	tasks, err := local.Tasks(project)
	if err != nil {
		t.Fatal(err)
	}
	return tasks
}
