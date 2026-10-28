package domain

import (
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestPythonGovernanceReference(t *testing.T) {
	raw, e := contracts.Files.ReadFile("reference.json")
	if e != nil {
		t.Fatal(e)
	}
	root, e := codec.Parse(raw)
	if e != nil {
		t.Fatal(e)
	}
	if len(A(M(root)["governance_cases"])) < 24 {
		t.Fatal("Python governance reference missing")
	}
	for _, v := range A(M(root)["governance_cases"]) {
		c := M(v)
		got, e := Project(M(c["view"]), M(c["context"]), S(c["as_of"]))
		if e != nil || !codec.Equal(got, c["expected"]) {
			a, _ := json.Marshal(got)
			b, _ := json.Marshal(c["expected"])
			t.Fatalf("governance mismatch\ngot %s\nwant %s\n%v", a, b, e)
		}
	}
}
func TestProjectReceiptToPublicationSnapshotAndWithdrawal(t *testing.T) {
	ctx := context.Background()
	base, e := os.MkdirTemp("", "av-domain-")
	if e != nil {
		t.Fatal(e)
	}
	defer os.RemoveAll(base)
	root := filepath.Join(base, "owned")
	if e = platform.PrivateDir(root, true); e != nil {
		t.Fatal(e)
	}
	s, e := storage.Open(ctx, filepath.Join(root, "experience.db"), storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	run := "synthetic-domain-test"
	facts := Map{"concurrency_scope": "independent_processes", "shared_state_kind": "sqlite_file"}
	proposal := Map{"candidate_key": "observed", "title": "Synthetic rule", "strategy": "Bounded operation", "public_summary": "Synthetic domain integration fixture", "necessary_conditions": Map{"shared_state_kind": []any{"sqlite_file"}}, "inapplicable_conditions": Map{}, "scope": Map{"concurrency_scope": []any{"independent_processes"}}, "unknown_fields": []any{}, "limitations": []any{}, "source_references": []any{}}
	var id, queryID, sourceID, eid string
	grant := ReviewGrant{Principal: "host:test", ExpiresAt: time.Now().Add(10 * time.Minute).UTC().Format(time.RFC3339Nano)}
	execute := func(fn func(Repo) error) {
		t.Helper()
		if err := s.Write(ctx, func(r *storage.Repository) error { return fn(Repo{r}) }); err != nil {
			t.Fatal(err)
		}
	}
	execute(func(r Repo) error {
		result, e := r.Propose(ctx, run, proposal)
		id = S(result["candidate_id"])
		return e
	})
	execute(func(r Repo) error {
		view, e := r.Inspect(ctx, id)
		if e != nil {
			return e
		}
		_, e = r.Transition(ctx, id, "EVIDENCE_PENDING", S(view["head_sha256"]), "pending", "Independent verification required", grant, Map{})
		return e
	})
	files := map[string][]byte{"submission.txt": []byte("synthetic artifact"), "suite.txt": []byte("independent pinned suite"), "evaluator.txt": []byte("independent pinned evaluator"), "junit.xml": []byte(`<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="fixture" name="test_pass" time="0.1"/></testsuite>`)}
	for name, raw := range files {
		if e = os.WriteFile(filepath.Join(root, name), raw, 0600); e != nil {
			t.Fatal(e)
		}
	}
	policy := Map{"schema_version": PolicyVersion, "verifier_id": "fixture:verifier", "origin": "synthetic_or_test_fixture", "suite_sha256": BytesSHA(files["suite.txt"]), "evaluator_sha256": BytesSHA(files["evaluator.txt"]), "required_tests": []any{"fixture::test_pass"}, "facts": facts}
	artifacts := Map{}
	for kind, name := range map[string]string{"submission": "submission.txt", "suite": "suite.txt", "evaluator": "evaluator.txt", "junit": "junit.xml"} {
		artifacts[kind] = Map{"path": name, "sha256": BytesSHA(files[name])}
	}
	receipt := Map{"schema_version": ReceiptVersion, "candidate_id": id, "candidate_body_sha256": H(proposal), "run_id": run, "verifier_id": policy["verifier_id"], "origin": policy["origin"], "facts": facts, "started_at": "2026-10-20T00:00:00+00:00", "ended_at": "2026-10-20T00:00:01+00:00", "exit_code": 0, "artifacts": artifacts}
	raw, e := codec.Canonical(receipt)
	if e != nil {
		t.Fatal(e)
	}
	if e = os.WriteFile(filepath.Join(root, "receipt.json"), raw, 0600); e != nil {
		t.Fatal(e)
	}
	pin := BytesSHA(raw)
	execute(func(r Repo) error {
		result, e := r.VerifyProjectCandidate(ctx, id, policy, root, pin)
		sourceID = S(M(result["source"])["id"])
		return e
	})
	execute(func(r Repo) error {
		view, e := r.Inspect(ctx, id)
		if e != nil {
			return e
		}
		_, e = r.Transition(ctx, id, "ADMITTED_BOUNDED", S(view["head_sha256"]), "admit", "Bounded independently checked fixture", grant, Map{"source_id": sourceID, "scope": proposal["scope"], "strength": "BOUNDED_SUPPORT_NOT_CAUSAL"})
		return e
	})
	execute(func(r Repo) error {
		view, e := r.Inspect(ctx, id)
		if e != nil {
			return e
		}
		result, e := r.Publish(ctx, id, S(view["head_sha256"]), "publish", "Publish bounded fixture", grant)
		eid = S(result["experience_id"])
		return e
	})
	execute(func(r Repo) error {
		service := Service{Repo: r, Run: run, Facts: facts}
		result, e := service.ResolveExperience(ctx, Map{})
		if e != nil {
			return e
		}
		c := M(A(result["candidates"])[0])
		if c["decision"] != "APPLY" {
			t.Fatalf("unexpected applicability %v", c["reason"])
		}
		queryID = S(result["query_id"])
		_, e = service.RecordDecision(ctx, Map{"query_id": queryID, "experience_id": eid, "decision": "APPLY", "reason": "Untrusted fixture decision"})
		return e
	})
	execute(func(r Repo) error {
		result, e := r.FeedbackSource(ctx, sourceID)
		if e != nil {
			return e
		}
		if result["feedback_status"] != "outcome_observed_no_attribution" || len(A(result["receipts"])) != 1 {
			t.Fatal(result)
		}
		return nil
	})
	execute(func(r Repo) error {
		view, e := r.Inspect(ctx, id)
		if e != nil {
			return e
		}
		_, e = r.Transition(ctx, id, "WITHDRAWN", S(view["head_sha256"]), "withdraw", "Withdraw synthetic publication", grant, Map{})
		return e
	})
	execute(func(r Repo) error {
		service := Service{Repo: r, Run: run, Facts: facts}
		replay, e := service.Bundle(ctx, eid, queryID)
		if e != nil {
			return e
		}
		if M(replay["publication_lifecycle"])["state"] != "PUBLISHED" {
			t.Fatal("immutable historical snapshot changed")
		}
		result, e := service.ResolveExperience(ctx, Map{})
		if e != nil {
			return e
		}
		if len(A(result["candidates"])) != 0 {
			t.Fatal("withdrawn publication still available")
		}
		_, e = Service{Repo: r, Run: "foreign", Facts: facts}.Bundle(ctx, eid, queryID)
		if e == nil {
			t.Fatal("foreign Run authorized")
		}
		return nil
	})
}
func TestJUnitRejectsSyntheticAuthorityAndInconsistentCounts(t *testing.T) {
	for _, raw := range []string{`<!DOCTYPE x><testsuite/>`, `<testsuite tests="2"><testcase classname="fixture" name="test_pass"/></testsuite>`, `<testsuite><testcase classname="fixture" name="test_pass"><failure/><error/></testcase></testsuite>`, `<testsuite><testcase classname="fixture" name="test_pass" time="NaN"/></testsuite>`} {
		if _, e := ReadJUnit([]byte(raw), []string{"fixture::test_pass"}); e == nil {
			t.Fatalf("accepted invalid JUnit %s", raw)
		}
	}
}
