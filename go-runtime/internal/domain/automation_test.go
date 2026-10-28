package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

type automationFixture struct {
	store                          *storage.Store
	id, head, root, backend, pin   string
	policy, sourcePolicy, proposal Map
}

func automationTestFixture(t *testing.T, change func(Map)) *automationFixture {
	t.Helper()
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "owned")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	s, err := storage.Open(ctx, filepath.Join(root, "data.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	facts := Map{"concurrency_scope": "independent_processes", "shared_state_kind": "sqlite_file"}
	p := Map{"candidate_key": "automatic", "title": "Synthetic automation contract", "strategy": "Use the verified local contract", "public_summary": "Synthetic workflow test only", "necessary_conditions": Map{"shared_state_kind": []any{"sqlite_file"}}, "scope": Map{"concurrency_scope": []any{"independent_processes", "threads"}}, "inapplicable_conditions": Map{}, "unknown_fields": []any{}, "limitations": []any{"Synthetic fixture, not real-world utility evidence"}, "source_references": []any{}}
	if change != nil {
		change(p)
	}
	f := &automationFixture{store: s, root: root, backend: strings.Repeat("b", 64), proposal: p}
	err = s.Write(ctx, func(repo *storage.Repository) error {
		r := Repo{repo}
		v, err := r.Propose(ctx, "automation-fixture", p)
		if err != nil {
			return err
		}
		f.id = S(v["candidate_id"])
		view, err := r.Inspect(ctx, f.id)
		if err != nil {
			return err
		}
		f.head = S(view["head_sha256"])
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	files := map[string][]byte{"submission.txt": []byte("synthetic submission"), "suite.txt": []byte("independent fixed suite"), "evaluator.txt": []byte("independent fixed runner"), "junit.xml": []byte(`<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="fixture" name="contract" time="0.01"/></testsuite>`)}
	artifacts := Map{}
	for kind, name := range map[string]string{"submission": "submission.txt", "suite": "suite.txt", "evaluator": "evaluator.txt", "junit": "junit.xml"} {
		if err = os.WriteFile(filepath.Join(root, name), files[name], 0600); err != nil {
			t.Fatal(err)
		}
		artifacts[kind] = Map{"path": name, "sha256": BytesSHA(files[name])}
	}
	f.sourcePolicy = Map{"schema_version": PolicyVersion, "verifier_id": "fixture:protected-job", "origin": "synthetic_or_test_fixture", "suite_sha256": BytesSHA(files["suite.txt"]), "evaluator_sha256": BytesSHA(files["evaluator.txt"]), "required_tests": []any{"fixture::contract"}, "facts": facts}
	receipt := Map{"schema_version": ReceiptVersion, "candidate_id": f.id, "candidate_body_sha256": H(p), "run_id": "automation-fixture", "verifier_id": f.sourcePolicy["verifier_id"], "origin": f.sourcePolicy["origin"], "facts": facts, "started_at": "2026-10-26T00:00:00Z", "ended_at": "2026-10-26T00:00:01Z", "exit_code": 0, "artifacts": artifacts}
	raw, err := codec.Canonical(receipt)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(root, "receipt.json"), raw, 0600); err != nil {
		t.Fatal(err)
	}
	f.pin = BytesSHA(raw)
	f.policy = Map{"schema_version": AutomationPolicyVersion, "policy_id": "local-tests", "backend_id": f.backend, "source_policy_sha256": H(f.sourcePolicy), "scope": Map{"concurrency_scope": []any{"independent_processes"}}, "target_state": "PUBLISHED"}
	return f
}

func (f *automationFixture) automate() (Map, error) {
	var result Map
	err := f.store.Write(context.Background(), func(repo *storage.Repository) error {
		var err error
		result, err = (Repo{repo}).AutomateCandidate(context.Background(), f.backend, f.id, f.head, f.policy, f.sourcePolicy, f.root, f.pin)
		return err
	})
	return result, err
}

func TestAutomaticPromotionPublishesBoundedExperienceAndReconciles(t *testing.T) {
	f := automationTestFixture(t, nil)
	first, err := f.automate()
	if err != nil {
		t.Fatal(err)
	}
	if first["status"] != "PUBLISHED" || first["causal_benefit"] != "UNKNOWN" {
		t.Fatal(first)
	}
	second, err := f.automate()
	if err != nil || second["idempotent_replay"] != true || second["experience_id"] != first["experience_id"] {
		t.Fatal(second, err)
	}
	err = f.store.Write(context.Background(), func(repo *storage.Repository) error {
		r := Repo{repo}
		view, err := r.Inspect(context.Background(), f.id)
		if err != nil {
			return err
		}
		if len(A(view["events"])) != 5 {
			t.Fatal("duplicate lifecycle events", view)
		}
		for _, v := range A(view["events"])[1:] {
			if !strings.HasPrefix(S(M(v)["principal"]), "automation:local-tests:") {
				t.Fatal(v)
			}
		}
		facts := Map{"concurrency_scope": "independent_processes", "shared_state_kind": "sqlite_file"}
		q, err := (Service{Repo: r, Run: "next-work-item", Facts: facts}).ResolveExperience(context.Background(), Map{})
		if err != nil {
			return err
		}
		if M(A(q["candidates"])[0])["decision"] != "APPLY" {
			t.Fatal(q)
		}
		facts["concurrency_scope"] = "threads"
		q, err = (Service{Repo: r, Run: "outside-bounds", Facts: facts}).ResolveExperience(context.Background(), Map{})
		if err != nil {
			return err
		}
		if M(A(q["candidates"])[0])["decision"] != "ABSTAIN" {
			t.Fatal("policy cap escaped", q)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}

func TestAutomationRejectsWrongAuthorityStaleHeadAndReceipt(t *testing.T) {
	for _, change := range []struct {
		name string
		f    func(*automationFixture)
	}{
		{"backend", func(f *automationFixture) { f.backend = strings.Repeat("c", 64) }},
		{"source-policy", func(f *automationFixture) { f.sourcePolicy["verifier_id"] = "other:job" }},
		{"stale-head", func(f *automationFixture) { f.head = strings.Repeat("d", 64) }},
		{"receipt", func(f *automationFixture) { f.pin = strings.Repeat("e", 64) }},
		{"scope", func(f *automationFixture) { f.policy["scope"] = Map{"concurrency_scope": []any{"other-context"}} }},
	} {
		t.Run(change.name, func(t *testing.T) {
			f := automationTestFixture(t, nil)
			change.f(f)
			if _, err := f.automate(); err == nil {
				t.Fatal("unauthorized promotion")
			}
			for _, label := range []string{"Experience", "VerifiedOutcome", "SourceVerification"} {
				n, err := f.store.Read().Count(context.Background(), label, "")
				if err != nil || n != 0 {
					t.Fatal("partial write", label, n, err)
				}
			}
		})
	}
}

func TestAutomationKeepsUnscopedObservationsAndRollsBackUnknownRequiredFacts(t *testing.T) {
	f := automationTestFixture(t, func(p Map) { p["scope"] = Map{} })
	result, err := f.automate()
	if err != nil || result["status"] != "KEPT_AS_OBSERVATION" {
		t.Fatal(result, err)
	}
	f = automationTestFixture(t, func(p Map) { p["unknown_fields"] = []any{"shared_state_kind"} })
	if _, err = f.automate(); err == nil {
		t.Fatal("unknown required fact admitted")
	}
	n, err := f.store.Read().Count(context.Background(), "SourceVerification", "")
	if err != nil || n != 0 {
		t.Fatal("failed admission leaked source", n, err)
	}
}

func TestAutomaticAdmissionCanBePublishedByAnotherAuthorizedJobButNotRevived(t *testing.T) {
	f := automationTestFixture(t, nil)
	f.policy["target_state"] = "ADMITTED_BOUNDED"
	if result, err := f.automate(); err != nil || result["status"] != "ADMITTED_BOUNDED" {
		t.Fatal(result, err)
	}
	err := f.store.Write(context.Background(), func(repo *storage.Repository) error {
		view, err := (Repo{repo}).Inspect(context.Background(), f.id)
		f.head = S(view["head_sha256"])
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	f.policy["target_state"] = "PUBLISHED"
	if _, err = f.automate(); err != nil {
		t.Fatal(err)
	}
	if result, err := f.automate(); err != nil || result["idempotent_replay"] != true {
		t.Fatal(result, err)
	}
	err = f.store.Write(context.Background(), func(repo *storage.Repository) error {
		r := Repo{repo}
		view, err := r.Inspect(context.Background(), f.id)
		if err != nil {
			return err
		}
		_, err = r.Transition(context.Background(), f.id, "WITHDRAWN", S(view["head_sha256"]), "withdraw", "Synthetic regression withdrawal", ReviewGrant{Principal: "host:test", ExpiresAt: time.Now().Add(time.Minute).UTC().Format(time.RFC3339Nano)}, Map{})
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	if _, err = f.automate(); err == nil {
		t.Fatal("withdrawn experience revived")
	}
}

func TestCandidateCannotInvokeAutomationThroughConsumerService(t *testing.T) {
	f := automationTestFixture(t, nil)
	err := f.store.Write(context.Background(), func(repo *storage.Repository) error {
		_, err := (Service{Repo: Repo{repo}, Run: "automation-fixture", Proposals: true}).Call(context.Background(), "candidate-automate", Map{})
		if err == nil {
			t.Fatal("consumer gained promotion authority")
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}

func TestAutomaticVerificationRetainsFailureWithoutPromotion(t *testing.T) {
	f := automationTestFixture(t, nil)
	junit := []byte(`<testsuite tests="1" failures="1" errors="0" skipped="0"><testcase classname="fixture" name="contract"><failure>contract failed</failure></testcase></testsuite>`)
	if err := os.WriteFile(filepath.Join(f.root, "junit.xml"), junit, 0600); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(filepath.Join(f.root, "receipt.json"))
	if err != nil {
		t.Fatal(err)
	}
	v, err := codec.Parse(raw)
	if err != nil {
		t.Fatal(err)
	}
	receipt := M(v)
	receipt["exit_code"] = 1
	M(M(receipt["artifacts"])["junit"])["sha256"] = BytesSHA(junit)
	raw, err = codec.Canonical(receipt)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(f.root, "receipt.json"), raw, 0600); err != nil {
		t.Fatal(err)
	}
	f.pin = BytesSHA(raw)
	result, err := f.automate()
	if err != nil || result["status"] != "NOT_PROMOTED" {
		t.Fatal(result, err)
	}
	for label, want := range map[string]int{"VerifiedOutcome": 1, "SourceVerification": 1, "Experience": 0, "CandidateEvent": 1} {
		n, err := f.store.Read().Count(context.Background(), label, "")
		if err != nil || n != want {
			t.Fatal(label, n, want, err)
		}
	}
}
