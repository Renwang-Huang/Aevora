package domain

import (
	"context"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func recallStore(t *testing.T) (*storage.Store, string) {
	t.Helper()
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.PrivateDir(root, true); err != nil {
		t.Fatal(err)
	}
	s, err := storage.Open(context.Background(), filepath.Join(root, "experience.db"), storage.Options{Create: true})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	return s, root
}

// Use the actual proposal -> pinned synthetic receipt -> admission -> publish
// path. This fixture proves interface contracts, never real task utility.
func publishRecall(t *testing.T, s *storage.Store, root, key, title, strategy string, facts Map) (string, string) {
	t.Helper()
	ctx := context.Background()
	var eid, cid string
	err := s.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		body := Map{"candidate_key": key, "title": title, "strategy": strategy, "public_summary": "Explicit synthetic recall acceptance fixture", "necessary_conditions": Map{"target_project": []any{facts["target_project"]}}, "inapplicable_conditions": Map{}, "scope": Map{"target_project": []any{facts["target_project"]}}, "unknown_fields": []any{}, "limitations": []any{"Synthetic source; no real adoption or causal benefit"}, "source_references": []any{}}
		proposal, err := r.Propose(ctx, "recall-fixture", body)
		if err != nil {
			return err
		}
		cid = S(proposal["candidate_id"])
		candidate, err := r.Required(ctx, "Candidate", cid)
		if err != nil {
			return err
		}
		files := map[string][]byte{"submission": []byte("synthetic submission"), "suite": []byte("fixed recall contract"), "evaluator": []byte("independent fixture verifier"), "junit": []byte(`<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="recall" name="contract"/></testsuite>`)}
		artifacts := Map{}
		for name, content := range files {
			if err := os.WriteFile(filepath.Join(root, name), content, 0600); err != nil {
				return err
			}
			artifacts[name] = Map{"path": name, "sha256": BytesSHA(content)}
		}
		policy := Map{"schema_version": PolicyVersion, "verifier_id": "fixture:recall", "origin": "synthetic_or_test_fixture", "suite_sha256": BytesSHA(files["suite"]), "evaluator_sha256": BytesSHA(files["evaluator"]), "required_tests": []any{"recall::contract"}, "facts": facts}
		receipt := Map{"schema_version": ReceiptVersion, "candidate_id": cid, "candidate_body_sha256": candidate["body_sha256"], "run_id": "recall-fixture", "verifier_id": policy["verifier_id"], "origin": policy["origin"], "facts": facts, "started_at": "2026-10-26T00:00:00+00:00", "ended_at": "2026-10-26T00:00:01+00:00", "exit_code": 0, "artifacts": artifacts}
		data, err := codec.Canonical(receipt)
		if err != nil {
			return err
		}
		if err = os.WriteFile(filepath.Join(root, "receipt.json"), data, 0600); err != nil {
			return err
		}
		source, err := r.VerifyProjectCandidate(ctx, cid, policy, root, BytesSHA(data))
		if err != nil {
			return err
		}
		grant := ReviewGrant{Principal: "fixture:trusted", ExpiresAt: time.Now().Add(time.Minute).UTC().Format(time.RFC3339Nano)}
		for _, state := range []string{"EVIDENCE_PENDING", "ADMITTED_BOUNDED"} {
			view, err := r.Inspect(ctx, cid)
			if err != nil {
				return err
			}
			metadata := Map{}
			if state == "ADMITTED_BOUNDED" {
				metadata = Map{"source_id": M(source["source"])["id"], "scope": body["scope"], "strength": "BOUNDED_SUPPORT_NOT_CAUSAL"}
			}
			if _, err := r.Transition(ctx, cid, state, S(view["head_sha256"]), strings.ToLower(state), "Fixture contract", grant, metadata); err != nil {
				return err
			}
		}
		view, err := r.Inspect(ctx, cid)
		if err != nil {
			return err
		}
		published, err := r.Publish(ctx, cid, S(view["head_sha256"]), "publish", "Fixture bounded publication", grant)
		eid = S(published["experience_id"])
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	return eid, cid
}

func TestTaskRecallKeepsRelevanceSeparateFromTrustAndReplaysEvidence(t *testing.T) {
	s, root := recallStore(t)
	ctx := context.Background()
	facts := Map{"target_project": "demo"}
	eid, cid := publishRecall(t, s, root, "queue", "Native queue for running sessions", "Queue the next instruction without interrupting the running session", facts)
	publishRecall(t, s, root, "restart", "Native Host restart recovery", "Reconnect the existing MCP transport after the native server restarts", facts)
	var first Map
	call := func(facts, claims Map, text string) Map {
		t.Helper()
		var out Map
		err := s.Write(ctx, func(raw *storage.Repository) error {
			var err error
			out, err = (Service{Repo: Repo{raw}, Run: "task-recall", Facts: facts}).Call(ctx, "resolve_experience", Map{"task_context": claims, "query": text})
			return err
		})
		if err != nil {
			t.Fatal(err)
		}
		return out
	}
	for _, text := range []string{"原生队列", "native queued instructions"} {
		result := call(facts, Map{}, text)
		if len(A(result["candidates"])) != 1 || M(A(result["candidates"])[0])["experience_id"] != eid || M(A(result["candidates"])[0])["decision"] != "APPLY" {
			t.Fatal(text, result)
		}
		if M(result["retrieval"])["query_authority"] != "UNTRUSTED_RELEVANCE_ONLY" || M(A(result["candidates"])[0])["evidence_bundle"] != nil {
			t.Fatal("summary leaked full evidence or granted text authority", result)
		}
		first = result
	}
	for _, text := range []string{"web model selection", "", "the and or"} {
		if result := call(facts, Map{}, text); len(A(result["candidates"])) != 0 {
			t.Fatal("unrelated task got Host advice", text, result)
		}
	}
	unknown := call(Map{}, Map{"target_project": "demo"}, "native queue")
	if M(A(unknown["candidates"])[0])["decision"] == "APPLY" || M(unknown["pinned_public_context"])["target_project"] != nil {
		t.Fatal("untrusted target claim became authority", unknown)
	}
	other := call(Map{"target_project": "other"}, Map{}, "native queue")
	if M(A(other["candidates"])[0])["decision"] != "ABSTAIN" {
		t.Fatal("wrong project accepted", other)
	}
	var bundle Map
	if err := s.Write(ctx, func(raw *storage.Repository) error {
		service := Service{Repo: Repo{raw}, Run: "task-recall", Facts: facts}
		var err error
		bundle, err = service.Bundle(ctx, eid, S(first["query_id"]))
		if err != nil {
			return err
		}
		if _, err = service.RecordDecision(ctx, Map{"query_id": first["query_id"], "experience_id": eid, "decision": "APPLY", "reason": "Actual returned identity, claim only"}); err != nil {
			return err
		}
		if _, err = service.RecordDecision(ctx, Map{"query_id": first["query_id"], "experience_id": cid, "decision": "APPLY", "reason": "A candidate is not an experience"}); err == nil {
			t.Fatal("candidate observation acquired experience authority")
		}
		view, err := service.Repo.Inspect(ctx, cid)
		if err != nil {
			return err
		}
		_, err = service.Repo.Transition(ctx, cid, "WITHDRAWN", S(view["head_sha256"]), "withdraw", "Fixture withdrawal", ReviewGrant{Principal: "fixture:trusted", ExpiresAt: time.Now().Add(time.Minute).UTC().Format(time.RFC3339Nano)}, Map{})
		return err
	}); err != nil {
		t.Fatal(err)
	}
	if result := call(facts, Map{}, "native queue"); len(A(result["candidates"])) != 0 {
		t.Fatal("withdrawn experience remained in task recall", result)
	}
	if err := s.Write(ctx, func(raw *storage.Repository) error {
		service := Service{Repo: Repo{raw}, Run: "task-recall", Facts: facts, Recall: &RecallPlan{Label: "Experience", Query: "paraphrase", IDs: []string{eid}, Ready: true, Metadata: Map{"semantic_recall": "READY"}}}
		result, e := service.Call(ctx, "resolve_experience", Map{"task_context": Map{}, "query": "paraphrase"})
		if e == nil && len(A(result["candidates"])) != 0 {
			t.Fatal("prepared semantic ID bypassed current withdrawal", result)
		}
		return e
	}); err != nil {
		t.Fatal(err)
	}
	if err := s.Write(ctx, func(raw *storage.Repository) error {
		replayed, err := (Service{Repo: Repo{raw}, Run: "task-recall", Facts: facts}).Bundle(ctx, eid, S(first["query_id"]))
		if err == nil && !codec.Equal(replayed, bundle) {
			t.Fatal("historical query evidence changed")
		}
		return err
	}); err != nil {
		t.Fatal(err)
	}
}

func TestTaskRecallBeyondOldCorpusLimitAndBoundedProjection(t *testing.T) {
	s, _ := recallStore(t)
	ctx := context.Background()
	if err := s.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		for i := 0; i < 330; i++ {
			id := fmt.Sprintf("experience:%04d", i)
			if err := r.Put(ctx, "Experience", Map{"id": id, "source_type": "synthetic_or_test_fixture", "title": "Queue 任务 " + strings.Repeat("文字", 700), "public_summary": strings.Repeat("摘要", 700), "strategy": strings.Repeat("策略", 700)}); err != nil {
				return err
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if err := s.Write(ctx, func(raw *storage.Repository) error {
		service := Service{Repo: Repo{raw}, Run: "bounded-recall", Facts: Map{}}
		result, err := service.Call(ctx, "resolve_experience", Map{"task_context": Map{}, "query": "queue", "limit": 20})
		if err != nil {
			return err
		}
		encoded, err := codec.Canonical(result)
		if err != nil || len(encoded) > SummaryBytes || len(A(result["candidates"])) == 0 || len(A(result["candidates"])) >= 20 {
			t.Fatal("projection budget/corpus limit", len(encoded), result, err)
		}
		if M(result["retrieval"])["output_truncated"] != true {
			t.Fatal("truncation not disclosed")
		}
		query, err := raw.Get(ctx, "Query", S(result["query_id"]))
		if err != nil || len(A(query["candidate_experience_ids"])) != len(A(result["candidates"])) {
			t.Fatal("unreturned identities authorized", query, err)
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
}

func TestRankedObservationRecallRemainsUntrustedAndLiteralIsCompatible(t *testing.T) {
	s, _ := recallStore(t)
	ctx := context.Background()
	if err := s.Write(ctx, func(raw *storage.Repository) error {
		r := Repo{raw}
		_, err := r.Propose(ctx, "draft-recall", Map{"candidate_key": "queue", "title": "Native queue instructions", "public_summary": "An unverified draft", "strategy": "Use the native queue", "necessary_conditions": Map{}, "scope": Map{}, "inapplicable_conditions": Map{}, "unknown_fields": []any{}, "limitations": []any{"No verifier"}, "source_references": []any{}})
		if err != nil {
			return err
		}
		service := Service{Repo: r, Run: "draft-recall", Facts: Map{}}
		ranked, err := service.Call(ctx, "search_observations", Map{"query": "原生队列", "mode": "ranked"})
		if err != nil || len(A(ranked["observations"])) != 1 || ranked["authority"] != "UNTRUSTED_OBSERVATIONS_ONLY" || ranked["applicability"] != "NOT_EVALUATED" {
			t.Fatal(ranked, err)
		}
		literal, err := service.Call(ctx, "search_observations", Map{"query": "原生队列"})
		if err != nil || len(A(literal["observations"])) != 0 {
			t.Fatal("literal compatibility changed", literal, err)
		}
		query, err := service.Call(ctx, "resolve_experience", Map{"query": "原生队列", "task_context": Map{}})
		if err != nil || len(A(query["candidates"])) != 0 {
			t.Fatal("draft entered experience resolver", query, err)
		}
		_, err = service.RecordDecision(ctx, Map{"query_id": query["query_id"], "experience_id": M(A(ranked["observations"])[0])["candidate_id"], "decision": "APPLY", "reason": "Observation cannot grant an experience identity"})
		if err == nil {
			t.Fatal("ranked draft granted APPLY")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
}
