package observatory

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"testing"
)

func TestCaptureSourceHTTPUsesBoundedReadonlyPages(t *testing.T) {
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
	candidate := ""
	for i := 0; i < 3; i++ {
		e, e2 := captureformat.New("fixture", "session-1", "turn-1", fmt.Sprintf("call-%d", i), "BASH", "JSON_DECODE_ERROR")
		if e2 != nil {
			t.Fatal(e2)
		}
		if err = db.Write(ctx, func(raw *storage.Repository) error {
			out, e := (domain.Repo{Repository: raw}).IngestCapture(ctx, e.Map())
			candidate = domain.S(out["candidate_id"])
			return e
		}); err != nil {
			t.Fatal(err)
		}
	}
	handler, err := NewHandler(&Reader{Store: db})
	if err != nil {
		t.Fatal(err)
	}
	read := func(q url.Values, want int) Map {
		t.Helper()
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest("GET", "http://127.0.0.1/api/capture-sources?"+q.Encode(), nil))
		if response.Code != want {
			t.Fatal(response.Code, response.Body.String())
		}
		var out Map
		if e := json.Unmarshal(response.Body.Bytes(), &out); e != nil {
			t.Fatal(e)
		}
		return out
	}
	q := url.Values{"mode": {"LIVE"}, "candidate": {candidate}, "limit": {"2"}}
	first := read(q, 200)
	if len(domain.A(first["sources"])) != 2 || first["more"] != true || first["authority"] != "UNTRUSTED_SOURCES_ONLY" {
		t.Fatal(first)
	}
	q.Set("after", domain.S(first["next_cursor"]))
	second := read(q, 200)
	if len(domain.A(second["sources"])) != 1 || second["more"] != false {
		t.Fatal(second)
	}
	q.Set("limit", "51")
	read(q, 400)
	q.Set("limit", "2")
	q.Set("mode", "REPLAY")
	read(q, 400)
	q.Set("mode", "LIVE")
	q.Set("private", "yes")
	read(q, 400)
	n, err := db.Read().Count(ctx, "ExternalObservation", "")
	if err != nil || n != 3 {
		t.Fatal("viewer changed source data", n, err)
	}
	overview := httptest.NewRecorder()
	handler.ServeHTTP(overview, httptest.NewRequest("GET", "http://127.0.0.1/api/overview", nil))
	if overview.Code != 200 {
		t.Fatal(overview.Code, overview.Body.String())
	}
	var body Map
	json.Unmarshal(overview.Body.Bytes(), &body)
	if rows := domain.A(body["candidates"]); len(rows) != 1 || domain.M(rows[0])["capture_sources"] == nil {
		t.Fatal("primary Console omitted source access", body["candidates"])
	}
}
