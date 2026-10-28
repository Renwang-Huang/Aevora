package observatory

import (
	"context"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func TestEmbeddedReplayMatchesPython(t *testing.T) {
	if e := ValidateAssets(); e != nil {
		t.Fatal(e)
	}
	raw, e := contracts.Files.ReadFile("reference.json")
	if e != nil {
		t.Fatal(e)
	}
	var refs struct {
		Cases []struct{ Case, Stage, SHA256 string } `json:"replay_cases"`
	}
	if e = json.Unmarshal(raw, &refs); e != nil {
		t.Fatal(e)
	}
	if len(refs.Cases) != 5 {
		t.Fatal("missing independent replay vectors")
	}
	for _, v := range refs.Cases {
		value, e := replayOverview(Selection{Case: v.Case, Stage: v.Stage})
		if e != nil {
			t.Fatal(v.Case, e)
		}
		hash, e := codec.Digest(value)
		if e != nil || hash != v.SHA256 {
			t.Fatalf("%s/%s differs from Python: %s != %s: %v", v.Case, v.Stage, hash, v.SHA256, e)
		}
	}
}

func TestUsageClaimProjectionPreservesPublicCandidateAndDropsPrivateFields(t *testing.T) {
	p := project("ExternalObservation", Map{"id": "external:example", "record_kind": "OBSERVATION_USE_CLAIM", "candidate_id": "candidate:task-11111111-2222-3333-4444-555555555555:example", "disposition": "INVESTIGATED", "public_summary": "Untrusted use report", "private_field": "must not appear"})
	if p["record_kind"] != "OBSERVATION_USE_CLAIM" || p["candidate_id"] == nil || p["disposition"] != "INVESTIGATED" || p["private_field"] != nil {
		t.Fatal("incorrect external observation projection", p)
	}
}
func TestLivePagesReadRecordedSnapshotsWithoutWrites(t *testing.T) {
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
	for range 7 {
		e = s.Write(ctx, func(repo *storage.Repository) error {
			_, e := (domain.Service{Repo: domain.Repo{Repository: repo}, Run: "test-run", Facts: Map{}}).ResolveExperience(ctx, Map{})
			return e
		})
		if e != nil {
			t.Fatal(e)
		}
	}
	reader := Reader{Store: s}
	handler, e := NewHandler(&reader)
	if e != nil {
		t.Fatal(e)
	}
	request := httptest.NewRequest("GET", "http://127.0.0.1/api/overview?limit=2&run=test-run", nil)
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != 200 {
		t.Fatal(response.Code, response.Body.String())
	}
	v, e := codec.Parse(response.Body.Bytes())
	if e != nil {
		t.Fatal(e)
	}
	body := domain.M(v)
	if len(domain.A(body["activity_queries"])) != 2 || len(domain.A(body["decisions"])) != 0 {
		t.Fatal("query page or legitimate empty result lost", body)
	}
	cursor := domain.S(domain.M(domain.M(body["pagination"])["queries"])["next_cursor"])
	if cursor == "" {
		t.Fatal("missing bounded continuation")
	}
	request = httptest.NewRequest("GET", "http://127.0.0.1/api/decisions?limit=2&run=other-run&cursor="+cursor, nil)
	response = httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != 400 {
		t.Fatal("cross-selection cursor accepted", response.Code)
	}
	for _, method := range []string{"POST", "PUT", "DELETE"} {
		response = httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest(method, "http://127.0.0.1/api/overview", nil))
		if response.Code != 403 {
			t.Fatal("read-only boundary failed", method)
		}
	}
	request = httptest.NewRequest("GET", "http://127.0.0.1/api/overview", nil)
	request.Header.Set("Origin", "http://foreign.invalid")
	response = httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != 403 {
		t.Fatal("origin accepted")
	}
	count, e := s.Read().Count(ctx, "Query", "")
	if e != nil || count != 7 {
		t.Fatal("viewer created or mutated Query", count, e)
	}
	if e = s.Write(ctx, func(repo *storage.Repository) error {
		return repo.PutNode(ctx, "Experience", Map{"id": "experience:available", "title": "Explicit synthetic viewer fixture", "strategy": "Unverified synthetic strategy", "public_summary": "Viewer acceptance only", "source_type": "synthetic_or_test_fixture"})
	}); e != nil {
		t.Fatal(e)
	}
	response = httptest.NewRecorder()
	handler.ServeHTTP(response, httptest.NewRequest("GET", "http://127.0.0.1/api/overview?run=absent&experience=experience:absent", nil))
	if response.Code != 200 {
		t.Fatal(response.Code, response.Body.String())
	}
	v, e = codec.Parse(response.Body.Bytes())
	if e != nil {
		t.Fatal(e)
	}
	body = domain.M(v)
	if domain.M(body["project"])["state"] != "EXPERIENCE_AVAILABLE" || domain.M(body["selection"])["experience_status"] != "NOT_FOUND" {
		t.Fatal("selection changed project readiness", body)
	}
	for _, key := range []string{"experiences", "available_experience_ids", "activity_queries", "decisions"} {
		if len(domain.A(body[key])) != 0 {
			t.Fatal("missing selection substituted records", key)
		}
	}
	count, e = s.Read().Count(ctx, "Query", "")
	if e != nil || count != 7 {
		t.Fatal("readiness created Query", count, e)
	}
}
