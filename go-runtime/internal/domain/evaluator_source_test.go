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
)

func TestAuthorizedEvaluatorPlanRequiresIndependentPinAndKeepsOutcomeOnlyScope(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	if e := platform.PrivateDir(root, true); e != nil {
		t.Fatal(e)
	}
	s, e := storage.Open(ctx, filepath.Join(root, "experience.db"), storage.Options{Create: true})
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	facts := Map{"worker_count": 1.0}
	run := "synthetic-evaluator-test"
	manifest, verifier := strings.Repeat("1", 64), strings.Repeat("2", 64)
	outcome := Map{"id": "outcome:" + run, "run_id": run, "verdict": "PASS", "submission_digest": strings.Repeat("3", 64), "patch_sha256": strings.Repeat("4", 64), "evaluator_fingerprint": strings.Repeat("5", 64), "test_suite_fingerprint": strings.Repeat("6", 64), "verifier_identity": "SYNTHETIC_TEST_FIXTURE", "attribution": "UNKNOWN", "test_count": 1, "evaluated_at": "2026-10-24T00:00:00+00:00"}
	outcome["immutable_digest"] = H(outcome)
	sourceID := "source-verification:evaluator:" + H([]any{run, nil, manifest, verifier})
	source := Map{"id": sourceID, "run_id": run, "authority": "TRUSTED_HOST_SOURCE_VERIFIER", "origin": "synthetic_or_test_fixture", "source_sha256": manifest, "submission_sha256": outcome["patch_sha256"], "outcome_id": outcome["id"], "facts": facts, "causal_benefit": "UNKNOWN"}
	plan := Map{"schema_version": "aevora.evaluator-plan/1", "verifier_id": "test-verifier", "verifier_source_sha256": verifier, "source_manifest_sha256": manifest, "verification_scope": "OUTCOME_ONLY", "records": Map{"outcome": outcome, "context": Map{"id": "context:" + run, "facts": facts}, "task": Map{"id": "task:" + run, "public_title": "Synthetic evaluator boundary test"}, "source": source}, "native_proof": Map{"source_kind": "SYNTHETIC_TEST_FIXTURE"}}
	evidence := filepath.Join(root, "evidence")
	if e = platform.PrivateDir(evidence, true); e != nil {
		t.Fatal(e)
	}
	raw, e := codec.Canonical(plan)
	if e != nil {
		t.Fatal(e)
	}
	if e = platform.Exclusive(filepath.Join(evidence, "authorized_source.json"), raw); e != nil {
		t.Fatal(e)
	}
	policy := Map{"schema_version": "aevora.evaluator-policy/1", "verifier_id": "test-verifier", "verifier_source_sha256": verifier, "plan_sha256": strings.Repeat("0", 64), "source_manifest_sha256": manifest, "run_id": run, "candidate_id": nil, "candidate_body_sha256": nil, "facts": facts, "origin": "synthetic_or_test_fixture", "verification_scope": "OUTCOME_ONLY"}
	path := filepath.Join(root, "policy.json")
	writePolicy := func() {
		t.Helper()
		b, e := codec.Canonical(policy)
		if e != nil {
			t.Fatal(e)
		}
		if e = os.WriteFile(path, b, 0600); e != nil {
			t.Fatal(e)
		}
	}
	writePolicy()
	call := func() (Map, error) {
		var result Map
		e := s.Write(ctx, func(r *storage.Repository) error {
			var e error
			result, e = (Repo{r}).AuthorizeEvaluatorSource(ctx, path, evidence)
			return e
		})
		return result, e
	}
	if _, e = call(); e == nil {
		t.Fatal("unapproved plan pin accepted")
	}
	n, e := s.Read().Count(ctx, "VerifiedOutcome", "")
	if e != nil || n != 0 {
		t.Fatal("failed source wrote Outcome", n, e)
	}
	policy["plan_sha256"] = H(plan)
	writePolicy()
	result, e := call()
	if e != nil || result["verification_scope"] != "OUTCOME_ONLY" {
		t.Fatal(result, e)
	}
	e = s.Write(ctx, func(r *storage.Repository) error { result, e = (Repo{r}).FeedbackSource(ctx, sourceID); return e })
	if e != nil {
		t.Fatal(e)
	}
	n, e = s.Read().Count(ctx, "Feedback", "")
	if e != nil || n != 0 {
		t.Fatal("feedback invented an unrecorded exposure", n, e)
	}
	n, e = s.Read().Count(ctx, "Candidate", "")
	if e != nil || n != 0 {
		t.Fatal("outcome-only source invented Candidate", n, e)
	}
}
