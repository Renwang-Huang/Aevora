package domain

import (
	"context"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"path/filepath"
	"testing"
)

func TestCaptureEpisodesSeparateTurnsAndEnumerateAllImmutableSources(t *testing.T) {
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
	ingest := func(session, turn, call string) string {
		t.Helper()
		e, err := captureformat.New("fixture", session, turn, call, "BASH", "JSON_DECODE_ERROR")
		if err != nil {
			t.Fatal(err)
		}
		var result Map
		if err = db.Write(ctx, func(raw *storage.Repository) error {
			var e2 error
			result, e2 = (Repo{raw}).IngestCapture(ctx, e.Map())
			return e2
		}); err != nil {
			t.Fatal(err)
		}
		return S(result["candidate_id"])
	}
	id := ingest("session-1", "turn-1", "call-1")
	for i := 2; i <= 12; i++ {
		if got := ingest("session-1", "turn-1", fmt.Sprintf("call-%d", i)); got != id {
			t.Fatal("one turn fragmented", got, id)
		}
	}
	if got := ingest("session-1", "turn-2", "call-next"); got == id {
		t.Fatal("independent turn merged")
	}
	if got := ingest("session-2", "turn-1", "call-next"); got == id {
		t.Fatal("independent session merged")
	}
	after := ""
	seen := map[string]bool{}
	for page := 0; page < 4; page++ {
		r := Repo{db.Read()}
		out, err := r.CaptureSources(ctx, id, after, 5)
		if err != nil {
			t.Fatal(err)
		}
		rows := A(out["sources"])
		if len(rows) > 5 || I(M(out["summary"])["source_record_count"]) != 12 {
			t.Fatal(out)
		}
		for _, v := range rows {
			source := M(v)
			sid := S(source["observation_id"])
			if seen[sid] || source["session_ref"] != "session-1" || source["turn_ref"] != "turn-1" || source["authority"] != "UNTRUSTED_HOOK_CLAIM" {
				t.Fatal("wrong source page", source)
			}
			seen[sid] = true
		}
		if out["more"] != true {
			break
		}
		next := S(out["next_cursor"])
		if next == "" || next == after {
			t.Fatal("page failed to advance", out)
		}
		after = next
	}
	if len(seen) != 12 {
		t.Fatal("source page omitted records", len(seen))
	}
	if _, err := (Repo{db.Read()}).CaptureSources(ctx, id, "", 51); err == nil {
		t.Fatal("source bound bypassed")
	}
}
