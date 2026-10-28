package domain

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"testing"
)

func TestTemplateEvolutionPreservesOldSourceAssignmentAndAcceptsNewEvents(t *testing.T) {
	for _, grouping := range []string{"", previousCaptureGrouping, captureGrouping} {
		t.Run("legacy-"+grouping, func(t *testing.T) {
			ctx := context.Background()
			root := filepath.Join(t.TempDir(), "private")
			if err := platform.PrivateDir(root, true); err != nil {
				t.Fatal(err)
			}
			db, err := storage.Open(ctx, filepath.Join(root, "db.sqlite"), storage.Options{Create: true})
			if err != nil {
				t.Fatal(err)
			}
			defer db.Close()
			oldEvent, err := captureformat.New("fixture", "session-1", "turn-1", "call-old", "BASH", "JSON_DECODE_ERROR")
			if err != nil {
				t.Fatal(err)
			}
			oldBody := captureCandidate(oldEvent)
			oldBody["strategy"] = "A previous release's bounded diagnostic wording"
			template := ""
			if grouping != "" {
				template = H(oldBody)
			}
			oldRun, oldCandidate := captureIdentity(oldEvent, grouping, template)
			source := Map{"id": "external-observation:capture:" + oldEvent.ID, "run_id": oldRun, "candidate_id": oldCandidate, "record_kind": "CODEX_DIAGNOSTIC_SIGNAL", "status": "UNTRUSTED_HOOK_CLAIM", "authority": "EXTERNAL_UNVERIFIED", "trusted_outcome": "NOT_CREATED", "attribution": "UNKNOWN", "created_at": Now(), "source_sha256": H(oldEvent.Map()), "event": oldEvent.Map(), "public_summary": "Previous release source claim"}
			if grouping != "" {
				source["grouping"], source["template_sha256"] = grouping, template
			}
			if err = db.Write(ctx, func(raw *storage.Repository) error {
				r := Repo{raw}
				if _, e := r.Propose(ctx, oldRun, oldBody); e != nil {
					return e
				}
				if e := r.Put(ctx, "ExternalObservation", source); e != nil {
					return e
				}
				return r.PutEdge(ctx, "DERIVED_FROM", "Candidate", oldCandidate, "ExternalObservation", S(source["id"]), nil)
			}); err != nil {
				t.Fatal(err)
			}
			if err = db.Write(ctx, func(raw *storage.Repository) error {
				out, e := (Repo{raw}).IngestCapture(ctx, oldEvent.Map())
				if e == nil && (out["candidate_id"] != oldCandidate || out["status"] != "ALREADY_RECORDED_UNTRUSTED") {
					t.Fatal("replay was rebound", out)
				}
				return e
			}); err != nil {
				t.Fatal(err)
			}
			stored, err := (Repo{db.Read()}).Get(ctx, "ExternalObservation", S(source["id"]))
			if err != nil || !codec.Equal(stored, source) {
				t.Fatal("legacy source changed", err)
			}
			fresh, err := captureformat.New("fixture", "session-1", "turn-1", "call-new", "BASH", "JSON_DECODE_ERROR")
			if err != nil {
				t.Fatal(err)
			}
			if err = db.Write(ctx, func(raw *storage.Repository) error {
				out, e := (Repo{raw}).IngestCapture(ctx, fresh.Map())
				if e == nil && out["candidate_id"] == oldCandidate {
					t.Fatal("new template reused old group", out)
				}
				return e
			}); err != nil {
				t.Fatal(err)
			}
			for _, pair := range [][2]string{{oldRun, oldCandidate}, {captureCurrentRun(fresh), captureCandidateID(fresh)}} {
				summary, e := (Repo{db.Read()}).CaptureSummary(ctx, pair[1], pair[0])
				if e != nil || I(summary["source_record_count"]) != 1 {
					t.Fatal("historical/new source query failed", summary, e)
				}
			}
		})
	}
}
