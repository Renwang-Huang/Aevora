package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestCandidateChecklistMatchesIndependentReference(t *testing.T) {
	raw, err := contracts.Files.ReadFile("reference.json")
	if err != nil {
		t.Fatal(err)
	}
	value, err := codec.Parse(raw)
	if err != nil {
		t.Fatal(err)
	}
	cases := A(M(value)["candidate_checklists"])
	if len(cases) != 15 {
		t.Fatal("missing Python reference")
	}
	for _, value := range cases {
		row := M(value)
		if !codec.Equal(CandidateChecklist(M(row["body"]), S(row["state"])), row["expected"]) {
			t.Fatal(row)
		}
	}
}

func TestNativeExperienceWorkflowAcrossRunsAndProjectBoundaries(t *testing.T) {
	ctx := context.Background()
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	s, err := storage.Open(ctx, filepath.Join(root, "experience.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	apply := func(fn func(Repo) error) {
		t.Helper()
		if err := s.Write(ctx, func(repo *storage.Repository) error { return fn(Repo{repo}) }); err != nil {
			t.Fatal(err)
		}
	}
	facts := Map{"runtime_os": "linux", "runtime_arch": "amd64", "runtime_engine": "go_native", "storage_backend": "sqlite", "console_access": "loopback_read_only"}
	grant := ReviewGrant{Principal: "host:fixture", ExpiresAt: time.Now().Add(time.Minute * 10).UTC().Format(time.RFC3339Nano)}
	var firstID string
	for index, key := range []string{"console-observation", "storage-observation"} {
		apply(func(repo Repo) error {
			body := Map{"candidate_key": key, "title": "Explicit native workflow fixture", "strategy": "Bounded runtime observation", "public_summary": "Synthetic workflow acceptance only", "necessary_conditions": Map{}, "inapplicable_conditions": Map{}, "scope": Map{}, "unknown_fields": []any{}, "limitations": []any{"Synthetic receipt; does not establish real task benefit"}, "source_references": []any{}}
			draft, err := repo.Propose(ctx, "task-observe", body)
			if err != nil {
				return err
			}
			draftID := S(draft["candidate_id"])
			plan, err := repo.CandidatePlan(ctx, draftID)
			if err != nil {
				return err
			}
			if plan["next_action"] != "DECLARE_BOUNDS" || len(A(plan["missing_fields"])) != 2 {
				t.Fatal("draft plan", plan)
			}
			conditions := Map{"runtime_engine": []any{"go_native"}}
			scope := Map{"storage_backend": []any{"sqlite"}}
			if index == 0 {
				scope = Map{"console_access": []any{"loopback_read_only"}, "runtime_os": []any{"linux"}}
			}
			derived, err := repo.DeriveCandidate(ctx, draftID, key+"-bounded", conditions, scope)
			if err != nil {
				return err
			}
			id := S(derived["candidate_id"])
			if index == 0 {
				firstID = id
			}
			original, err := repo.Required(ctx, "Candidate", draftID)
			if err != nil {
				return err
			}
			if original["body_sha256"] != H(body) || len(M(M(original["body"])["scope"])) != 0 {
				t.Fatal("original overwritten")
			}
			candidate, err := repo.Required(ctx, "Candidate", id)
			if err != nil {
				return err
			}
			if M(candidate["body"])["derived_from_candidate_id"] != draftID {
				t.Fatal("lineage missing")
			}
			plan, err = repo.CandidatePlan(ctx, id)
			if err != nil {
				return err
			}
			if plan["verification_status"] != "NO_MATCHING_VERIFIED_SOURCE" {
				t.Fatal("declared bounds became verified")
			}
			if _, err = repo.Admission(ctx, candidate, Map{}); err == nil {
				t.Fatal("self declaration admitted")
			}
			view, err := repo.Inspect(ctx, id)
			if err != nil {
				return err
			}
			if _, err = repo.Transition(ctx, id, "EVIDENCE_PENDING", S(view["head_sha256"]), "pending", "Fixture verifier required", grant, Map{}); err != nil {
				return err
			}
			files := map[string][]byte{"submission.txt": []byte("synthetic submission"), "suite.txt": []byte("fixed fixture suite"), "evaluator.txt": []byte("fixed fixture verifier"), "junit.xml": []byte(`<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="fixture" name="native_contract"/></testsuite>`)}
			artifacts := Map{}
			for kind, name := range map[string]string{"submission": "submission.txt", "suite": "suite.txt", "evaluator": "evaluator.txt", "junit": "junit.xml"} {
				if err := os.WriteFile(filepath.Join(root, name), files[name], 0600); err != nil {
					return err
				}
				artifacts[kind] = Map{"path": name, "sha256": BytesSHA(files[name])}
			}
			policy := Map{"schema_version": PolicyVersion, "verifier_id": "fixture:native", "origin": "synthetic_or_test_fixture", "suite_sha256": BytesSHA(files["suite.txt"]), "evaluator_sha256": BytesSHA(files["evaluator.txt"]), "required_tests": []any{"fixture::native_contract"}, "facts": facts}
			receipt := Map{"schema_version": ReceiptVersion, "candidate_id": id, "candidate_body_sha256": candidate["body_sha256"], "run_id": "task-observe", "verifier_id": policy["verifier_id"], "origin": policy["origin"], "facts": facts, "started_at": "2026-10-24T00:00:00+00:00", "ended_at": "2026-10-24T00:00:01+00:00", "exit_code": 0, "artifacts": artifacts}
			raw, err := codec.Canonical(receipt)
			if err != nil {
				return err
			}
			if err = os.WriteFile(filepath.Join(root, "receipt.json"), raw, 0600); err != nil {
				return err
			}
			if _, err = repo.VerifyProjectCandidate(ctx, id, policy, root, BytesSHA([]byte("wrong pin"))); err == nil {
				t.Fatal("unauthorized receipt accepted")
			}
			source, err := repo.VerifyProjectCandidate(ctx, id, policy, root, BytesSHA(raw))
			if err != nil {
				return err
			}
			plan, err = repo.CandidatePlan(ctx, id)
			if err != nil {
				return err
			}
			if plan["next_action"] != "REVIEW_ADMISSION" {
				t.Fatal("source plan", plan)
			}
			view, err = repo.Inspect(ctx, id)
			if err != nil {
				return err
			}
			if _, err = repo.Transition(ctx, id, "ADMITTED_BOUNDED", S(view["head_sha256"]), "admit", "Bounded fixture", grant, Map{"source_id": M(source["source"])["id"], "scope": scope, "strength": "BOUNDED_SUPPORT_NOT_CAUSAL"}); err != nil {
				return err
			}
			view, err = repo.Inspect(ctx, id)
			if err != nil {
				return err
			}
			_, err = repo.Publish(ctx, id, S(view["head_sha256"]), "publish", "Synthetic acceptance only", grant)
			return err
		})
	}
	apply(func(repo Repo) error {
		result, err := (Service{Repo: repo, Run: "task-reuse", Facts: facts}).ResolveExperience(ctx, Map{})
		if err != nil {
			return err
		}
		if len(A(result["candidates"])) != 2 {
			t.Fatal("reuse count", result)
		}
		for _, candidate := range A(result["candidates"]) {
			if M(candidate)["decision"] != "APPLY" {
				t.Fatal("expected bounded apply", candidate)
			}
		}
		unknown, err := (Service{Repo: repo, Run: "task-unknown", Facts: Map{}}).ResolveExperience(ctx, Map{})
		if err != nil {
			return err
		}
		for _, candidate := range A(unknown["candidates"]) {
			if M(candidate)["decision"] != "VERIFY" {
				t.Fatal("unknown facts did not retain verification requirement")
			}
		}
		if _, err = (Service{Repo: repo, Run: "task-claims", Facts: facts}).ResolveExperience(ctx, Map{"runtime_os": "windows"}); err == nil {
			t.Fatal("claims overrode trusted facts")
		}
		conflicting := Clone(facts)
		conflicting["runtime_os"] = "windows"
		result, err = (Service{Repo: repo, Run: "task-conflict", Facts: conflicting}).ResolveExperience(ctx, Map{})
		if err != nil {
			return err
		}
		found := false
		for _, candidate := range A(result["candidates"]) {
			row := M(candidate)
			if M(row["evidence_bundle"])["experience"] != nil && row["decision"] == "ABSTAIN" {
				found = true
			}
		}
		if !found {
			t.Fatal("conflict did not abstain", result)
		}
		view, err := repo.Inspect(ctx, firstID)
		if err != nil {
			return err
		}
		if _, err = repo.Transition(ctx, firstID, "WITHDRAWN", S(view["head_sha256"]), "withdraw", "Withdraw fixture", grant, Map{}); err != nil {
			return err
		}
		result, err = (Service{Repo: repo, Run: "task-after-withdraw", Facts: facts}).ResolveExperience(ctx, Map{})
		if err != nil {
			return err
		}
		if len(A(result["candidates"])) != 1 {
			t.Fatal("withdrawn experience reused")
		}
		return nil
	})
	other, err := storage.Open(ctx, filepath.Join(root, "other-project.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	defer other.Close()
	if err = other.Write(ctx, func(repo *storage.Repository) error {
		result, err := (Service{Repo: Repo{repo}, Run: "other-project-task", Facts: facts}).ResolveExperience(ctx, Map{})
		if err == nil && len(A(result["candidates"])) != 0 {
			t.Fatal("experience crossed project database")
		}
		return err
	}); err != nil {
		t.Fatal(err)
	}
}
