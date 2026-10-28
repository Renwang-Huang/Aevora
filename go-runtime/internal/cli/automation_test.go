package cli_test

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/cli"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestAutomationCLICompletesOfflineAndReconcilesThroughLiveHost(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	base, err := os.MkdirTemp("", "av-auto-cli-")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(base)
	root := filepath.Join(base, "owned")
	if err = platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	db, err := storage.Open(ctx, filepath.Join(root, "data.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	facts := domain.Map{"concurrency_scope": "independent_processes", "shared_state_kind": "sqlite_file"}
	body := domain.Map{"candidate_key": "automatic", "title": "Synthetic CLI contract", "strategy": "Apply only the verified fixture contract", "public_summary": "Synthetic CLI integration only", "necessary_conditions": domain.Map{"shared_state_kind": []any{"sqlite_file"}}, "scope": domain.Map{"concurrency_scope": []any{"independent_processes"}}, "inapplicable_conditions": domain.Map{}, "unknown_fields": []any{}, "limitations": []any{"Not an actual user-benefit evaluation"}, "source_references": []any{}}
	var candidate, head string
	err = db.Write(ctx, func(repo *storage.Repository) error {
		r := domain.Repo{Repository: repo}
		v, err := r.Propose(ctx, "cli-automation-fixture", body)
		if err != nil {
			return err
		}
		candidate = domain.S(v["candidate_id"])
		view, err := r.Inspect(ctx, candidate)
		head = domain.S(view["head_sha256"])
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	if err = db.Close(); err != nil {
		t.Fatal(err)
	}
	p := host.Profile{Schema: "aevora.host-config/2"}
	p.Database.Kind = "sqlite"
	p.Database.Path = filepath.Join(root, "data.db")
	p.Session.Root = filepath.Join(root, "sessions")
	if err = platform.PrivateDir(p.Session.Root, true); err != nil {
		t.Fatal(err)
	}
	p.Session.Facts, _ = codec.Canonical(facts)
	p.Console.Port = 17805
	backend := host.BackendID(p)
	defer func() {
		dir := host.RegistryDir(backend)
		for _, name := range []string{"management.json", "binding.json", "runtime.json"} {
			os.Remove(filepath.Join(dir, name))
		}
		os.Remove(dir)
	}()
	files := map[string][]byte{"submission.txt": []byte("synthetic submission"), "suite.txt": []byte("protected test suite"), "runner.txt": []byte("protected test runner"), "junit.xml": []byte(`<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="fixture" name="pass"/></testsuite>`)}
	artifacts := domain.Map{}
	for kind, name := range map[string]string{"submission": "submission.txt", "suite": "suite.txt", "evaluator": "runner.txt", "junit": "junit.xml"} {
		if err = os.WriteFile(filepath.Join(root, name), files[name], 0600); err != nil {
			t.Fatal(err)
		}
		artifacts[kind] = domain.Map{"path": name, "sha256": domain.BytesSHA(files[name])}
	}
	source := domain.Map{"schema_version": domain.PolicyVersion, "verifier_id": "fixture:ci-job", "origin": "synthetic_or_test_fixture", "suite_sha256": domain.BytesSHA(files["suite.txt"]), "evaluator_sha256": domain.BytesSHA(files["runner.txt"]), "required_tests": []any{"fixture::pass"}, "facts": facts}
	policy := domain.Map{"schema_version": domain.AutomationPolicyVersion, "policy_id": "local-ci", "backend_id": backend, "source_policy_sha256": domain.H(source), "scope": body["scope"], "target_state": "PUBLISHED"}
	receipt := domain.Map{"schema_version": domain.ReceiptVersion, "candidate_id": candidate, "candidate_body_sha256": domain.H(body), "run_id": "cli-automation-fixture", "verifier_id": source["verifier_id"], "origin": source["origin"], "facts": facts, "started_at": "2026-10-26T00:00:00Z", "ended_at": "2026-10-26T00:00:01Z", "exit_code": 0, "artifacts": artifacts}
	for name, v := range map[string]any{"host.json": p, "source.json": source, "receipt.json": receipt} {
		raw, err := json.Marshal(v)
		if err != nil {
			t.Fatal(err)
		}
		if err = os.WriteFile(filepath.Join(root, name), raw, 0600); err != nil {
			t.Fatal(err)
		}
	}
	var policyOut, policyErr bytes.Buffer
	policyArgs := []string{"--config", filepath.Join(root, "host.json"), "candidate", "automation-policy", "--name", "local-ci", "--source-policy", filepath.Join(root, "source.json"), "--scope", `{"concurrency_scope":["independent_processes"]}`, "--target-state", "PUBLISHED", "--output", filepath.Join(root, "automation.json")}
	if code := cli.Execute(ctx, policyArgs, bytes.NewReader(nil), &policyOut, &policyErr, native.Factory()); code != 0 {
		t.Fatal(code, policyErr.String())
	}
	generated, err := domain.LoadAutomationPolicy(filepath.Join(root, "automation.json"))
	if err != nil || !codec.Equal(generated, policy) {
		t.Fatal("generated policy differs", generated, err)
	}
	policyOut.Reset()
	policyErr.Reset()
	if code := cli.Execute(ctx, policyArgs, bytes.NewReader(nil), &policyOut, &policyErr, native.Factory()); code == 0 {
		t.Fatal("existing policy replaced")
	}
	raw, err := os.ReadFile(filepath.Join(root, "receipt.json"))
	if err != nil {
		t.Fatal(err)
	}
	args := []string{"--config", filepath.Join(root, "host.json"), "candidate", "automate", "--candidate", candidate, "--expected-head", head, "--policy", filepath.Join(root, "automation.json"), "--source-policy", filepath.Join(root, "source.json"), "--evidence-root", root, "--receipt-sha256", domain.BytesSHA(raw)}
	// A result rejected before delivery must roll back all composed writes,
	// including source evidence and lifecycle changes, not just the final head.
	owner, err := host.Own(p)
	if err != nil {
		t.Fatal(err)
	}
	checkStore, err := storage.Open(ctx, p.Database.Path, storage.Options{Owner: owner})
	if err != nil {
		owner.Close()
		t.Fatal(err)
	}
	runtime, err := native.New(ctx, checkStore, host.Scope(p, "delivery-check", false))
	if err != nil {
		checkStore.Close()
		owner.Close()
		t.Fatal(err)
	}
	requestArgs, _ := json.Marshal(map[string]any{"candidate_id": candidate, "expected_head_sha256": head, "policy_file": filepath.Join(root, "automation.json"), "source_policy_file": filepath.Join(root, "source.json"), "evidence_root": root, "receipt_sha256": domain.BytesSHA(raw)})
	_, err = runtime.Manage(ctx, engine.Request{ID: strings.Repeat("a", 64), Operation: "candidate-automate", Arguments: requestArgs, BeforeDispatch: func() error { return nil }, ValidateResult: func(json.RawMessage) error { return engine.ErrResultLimit }})
	if !errors.Is(err, engine.ErrResultLimit) {
		t.Fatal("delivery failure not preserved", err)
	}
	for label, want := range map[string]int{"Experience": 0, "SourceVerification": 0, "CandidateEvent": 1} {
		n, err := checkStore.Read().Count(ctx, label, "")
		if err != nil || n != want {
			t.Fatal("partial automation commit", label, n, want, err)
		}
	}
	runtime.Close()
	owner.Close()
	call := func() domain.Map {
		t.Helper()
		var out, stderr bytes.Buffer
		if code := cli.Execute(ctx, args, bytes.NewReader(nil), &out, &stderr, native.Factory()); code != 0 {
			t.Fatal(code, stderr.String())
		}
		v, err := codec.Parse(out.Bytes())
		if err != nil {
			t.Fatal(err)
		}
		return domain.M(domain.M(v)["result"])
	}
	first := call()
	if first["status"] != "PUBLISHED" {
		t.Fatal(first)
	}
	h, err := host.New(ctx, p, "automation-live", false, native.Factory())
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if err = h.Ready("http://127.0.0.1:17805"); err != nil {
		t.Fatal(err)
	}
	go h.Serve(ctx)
	second := call()
	if second["status"] != "PUBLISHED" || second["experience_id"] != first["experience_id"] || second["idempotent_replay"] != true {
		t.Fatal(second)
	}
	if err = h.Close(); err != nil {
		t.Fatal(err)
	}
	if err = os.Chmod(filepath.Join(root, "automation.json"), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err = domain.LoadAutomationPolicy(filepath.Join(root, "automation.json")); err == nil {
		t.Fatal("publicly readable policy accepted")
	}
}
