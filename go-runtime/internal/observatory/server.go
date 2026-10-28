package observatory

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"golang.org/x/net/netutil"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

type Handler struct {
	Reader *Reader
	slots  chan struct{}
}

func NewHandler(reader *Reader) (*Handler, error) {
	if e := ValidateAssets(); e != nil {
		return nil, e
	}
	return &Handler{Reader: reader, slots: make(chan struct{}, 4)}, nil
}
func failure(code string) Map { return Map{"status": "UNAVAILABLE", "error": code, "fallback": false} }
func respond(w http.ResponseWriter, status int, v any) {
	// Buffer once and reject amplification before any successful response header.
	var b boundedBuffer
	b.limit = 8 * 1024 * 1024
	e := json.NewEncoder(&b).Encode(v)
	if e != nil {
		status = 413
		b.data = []byte(`{"status":"PARTIAL","error":"GRAPH_READ_BUDGET_EXCEEDED","fallback":false}`)
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	w.Write(b.data)
}

type boundedBuffer struct {
	data  []byte
	limit int
}

func (b *boundedBuffer) Write(v []byte) (int, error) {
	if len(b.data)+len(v) > b.limit {
		return 0, storage.ErrReadBudget
	}
	b.data = append(b.data, v...)
	return len(v), nil
}
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
	host := r.Host
	name, port, e := net.SplitHostPort(host)
	if e != nil {
		name = host
		port = ""
	}
	if (name != "127.0.0.1" && name != "localhost") || (port == "" && host != name) || (port != "" && !validPort(port)) {
		respond(w, 403, failure("LOOPBACK_HOST_REQUIRED"))
		return
	}
	if origin := r.Header.Get("Origin"); origin != "" && origin != "http://"+host {
		respond(w, 403, failure("CROSS_ORIGIN_VIEWER_DENIED"))
		return
	}
	if len(r.Header.Values("Origin")) > 1 || len(r.URL.String()) > 4096 || len(r.Header) > 64 || r.ContentLength > 8192 || r.ContentLength < 0 {
		respond(w, 413, failure("REQUEST_BOUND_EXCEEDED"))
		return
	}
	if r.Method != "GET" {
		respond(w, 403, failure("READ_ONLY_VIEWER"))
		return
	}
	if !strings.HasPrefix(r.URL.Path, "/api/") {
		name := "static/" + strings.TrimPrefix(r.URL.Path, "/")
		if r.URL.Path == "/" {
			name = "static/index.html"
		}
		allowed := name == "static/index.html" || name == "static/assets/app.js" || name == "static/assets/app.css"
		if !allowed || r.URL.RawQuery != "" && r.URL.Path != "/" {
			respond(w, 404, failure("ARTIFACT_NOT_PUBLIC"))
			return
		}
		raw, e := asset(name)
		if e != nil {
			respond(w, 404, failure("ARTIFACT_NOT_PUBLIC"))
			return
		}
		kind := "text/html; charset=utf-8"
		if strings.HasSuffix(name, ".js") {
			kind = "text/javascript; charset=utf-8"
		}
		if strings.HasSuffix(name, ".css") {
			kind = "text/css; charset=utf-8"
		}
		w.Header().Set("Content-Type", kind)
		w.Write(raw)
		return
	}
	q, e := url.ParseQuery(r.URL.RawQuery)
	if e != nil {
		respond(w, 400, failure("INVALID_QUERY"))
		return
	}
	proof := strings.HasPrefix(r.URL.Path, "/api/proof/")
	allowed := map[string]bool{"mode": true, "case": true, "experience": true, "run": true, "context": true, "stage": true, "limit": true, "offset": true, "cursor": true}
	if r.URL.Path == "/api/observations" {
		allowed = map[string]bool{"mode": true, "query": true, "limit": true}
	}
	if r.URL.Path == "/api/capture-sources" || r.URL.Path == "/api/task-sources" {
		allowed = map[string]bool{"mode": true, "candidate": true, "after": true, "limit": true}
	}
	if proof {
		allowed = map[string]bool{"mode": true, "candidate": true}
	}
	for k, values := range q {
		if !allowed[k] || len(values) != 1 {
			respond(w, 400, failure("INVALID_QUERY"))
			return
		}
	}
	s := Selection{Mode: q.Get("mode"), Case: q.Get("case"), Stage: q.Get("stage"), Resource: strings.TrimPrefix(r.URL.Path, "/api/"), Run: q.Get("run"), Experience: q.Get("experience"), Limit: 20}
	if s.Mode == "" {
		s.Mode = "LIVE"
		if proof {
			s.Mode = "REPLAY"
		}
	}
	if s.Case == "" {
		s.Case = "case-a"
	}
	if s.Stage == "" {
		s.Stage = "before"
	}
	if (s.Mode != "LIVE" && s.Mode != "REPLAY") || (s.Case != "case-a" && s.Case != "case-b" && s.Case != "case-c") || (s.Stage != "before" && s.Stage != "after" && s.Stage != "restored") || (q.Get("context") != "" && q.Get("context") != "threads" && q.Get("context") != "workers" && q.Get("context") != "unknown") {
		respond(w, 400, failure("INVALID_SELECTOR"))
		return
	}
	for _, key := range []string{"run", "experience", "candidate"} {
		if v, ok := q[key]; ok && (v[0] == "" || !storage.ValidID(v[0])) {
			respond(w, 400, failure("INVALID_ID"))
			return
		}
	}
	if v, ok := q["limit"]; ok {
		s.Limit, e = strconv.Atoi(v[0])
		if e != nil || s.Limit < 1 || s.Limit > 100 {
			respond(w, 400, failure("PAGE_BOUND_EXCEEDED"))
			return
		}
	}
	if v, ok := q["offset"]; ok {
		s.Offset, e = strconv.Atoi(v[0])
		if e != nil || s.Offset < 0 || s.Offset > 1000 {
			respond(w, 400, failure("PAGE_BOUND_EXCEEDED"))
			return
		}
	}
	if token, ok := q["cursor"]; ok {
		if token[0] == "" || s.Mode != "LIVE" || s.Offset != 0 {
			respond(w, 400, failure("INVALID_CURSOR"))
			return
		}
		s.After, e = decodeCursor(token[0], s)
		if e != nil {
			respond(w, 400, failure("INVALID_CURSOR"))
			return
		}
	}
	if !proof && r.URL.Path != "/api/observations" && r.URL.Path != "/api/capture-sources" && r.URL.Path != "/api/task-sources" && !map[string]bool{"overview": true, "sessions": true, "decisions": true, "experiences": true, "graph": true, "timeline": true, "outcomes": true, "health": true}[s.Resource] {
		respond(w, 403, failure("RESOURCE_NOT_PUBLIC"))
		return
	}
	timer := time.NewTimer(200 * time.Millisecond)
	defer timer.Stop()
	select {
	case h.slots <- struct{}{}:
		defer func() { <-h.slots }()
	case <-timer.C:
		respond(w, 503, failure("READ_CONCURRENCY_BOUND"))
		return
	case <-r.Context().Done():
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	if r.URL.Path == "/api/capture-sources" || r.URL.Path == "/api/task-sources" {
		if q.Get("mode") != "LIVE" || h.Reader == nil || h.Reader.Store == nil {
			respond(w, 400, failure("LIVE_SOURCES_REQUIRED"))
			return
		}
		limit := 10
		if q.Get("limit") != "" {
			limit = s.Limit
		}
		var result Map
		err := h.Reader.Store.Snapshot(ctx, func(repo *storage.Repository) error {
			repo.Bounded()
			var e error
			if r.URL.Path == "/api/task-sources" {
				r := domain.Repo{Repository: repo}
				candidate, e2 := r.Required(ctx, "Candidate", q.Get("candidate"))
				if e2 != nil {
					return e2
				}
				sources, e2 := repo.ExternalByKind(ctx, "", domain.S(candidate["run_id"]), domain.TaskEventKind, 1)
				if e2 != nil || len(sources) == 0 {
					return domain.ErrInvalid
				}
				result, e = r.TaskCandidateSources(ctx, q.Get("candidate"), q.Get("after"), limit, domain.S(domain.M(sources[0]["event"])["project"]))
			} else {
				result, e = (domain.Repo{Repository: repo}).CaptureSources(ctx, q.Get("candidate"), q.Get("after"), limit)
			}
			return e
		})
		if err != nil {
			respond(w, 400, failure("CAPTURE_SOURCES_UNAVAILABLE"))
			return
		}
		result["mode"] = "LIVE"
		respond(w, 200, result)
		return
	}
	if r.URL.Path == "/api/observations" {
		for key, values := range q {
			if (key != "query" && key != "limit" && key != "mode") || len(values) != 1 {
				respond(w, 400, failure("INVALID_QUERY"))
				return
			}
		}
		if q.Get("mode") != "LIVE" || h.Reader == nil || h.Reader.Store == nil {
			respond(w, 400, failure("LIVE_OBSERVATIONS_REQUIRED"))
			return
		}
		limit := 10
		if q.Get("limit") != "" {
			var err error
			limit, err = strconv.Atoi(q.Get("limit"))
			if err != nil {
				respond(w, 400, failure("INVALID_LIMIT"))
				return
			}
		}
		repo := h.Reader.Store.Read()
		repo.Bounded()
		result, err := (domain.Repo{Repository: repo}).SearchObservations(ctx, q.Get("query"), limit)
		if err != nil {
			respond(w, 400, failure("OBSERVATION_SEARCH_UNAVAILABLE"))
			return
		}
		result["mode"] = "LIVE"
		respond(w, 200, result)
		return
	}
	var body Map
	if proof {
		name := strings.TrimPrefix(r.URL.Path, "/api/proof/")
		candidate := q.Get("candidate")
		if candidate != "" && name != "lifecycle" {
			respond(w, 400, failure("INVALID_SELECTOR"))
			return
		}
		if s.Mode == "LIVE" {
			if name != "lifecycle" {
				respond(w, 404, failure("LIVE_PROOF_NOT_AVAILABLE"))
				return
			}
			if candidate == "" {
				respond(w, 400, failure("CANDIDATE_REQUIRED"))
				return
			}
			if h.Reader == nil {
				respond(w, 503, failure("LIVE_NOT_CONFIGURED"))
				return
			}
			body, e = h.Reader.Proof(ctx, candidate)
		} else {
			body, e = replayProof(name, candidate)
		}
	} else if s.Mode == "LIVE" {
		if h.Reader == nil {
			respond(w, 503, failure("LIVE_NOT_CONFIGURED"))
			return
		}
		body, e = h.Reader.Overview(ctx, s)
	} else {
		body, e = replayOverview(s)
		if e == nil && s.Resource != "overview" {
			value := body[s.Resource]
			if rows, ok := value.([]any); ok {
				start := min(s.Offset, len(rows))
				value = rows[start:min(start+s.Limit, len(rows))]
			}
			body = Map{"mode": "REPLAY", "visibility": "PUBLIC", "status": body["status"], "captured_at": body["captured_at"], "archive": body["archive"], "contract_sha256": ReplayPin, "resource": s.Resource, "data": value, "offset": s.Offset, "limit": s.Limit}
		}
	}
	if e != nil {
		status, code := 422, "INVALID_STORED_RECORD"
		if errors.Is(e, storage.ErrReadBudget) {
			status, code = 413, "GRAPH_READ_BUDGET_EXCEEDED"
		} else if errors.Is(e, storage.ErrConflict) {
			code = "ImmutableConflict"
		} else if errors.Is(e, context.DeadlineExceeded) {
			status, code = 503, "READ_DEADLINE_EXCEEDED"
		}
		if s.Mode == "REPLAY" {
			code = "REPLAY_VERIFICATION_FAILED"
		}
		if errors.Is(e, errArtifactNotPublic) {
			status, code = 403, "ARTIFACT_NOT_PUBLIC"
		}
		v := failure(code)
		v["mode"] = s.Mode
		respond(w, status, v)
		return
	}
	if body == nil {
		respond(w, 404, failure("PROOF_OBJECT_NOT_FOUND"))
		return
	}
	respond(w, 200, body)
}
func validPort(raw string) bool { v, e := strconv.Atoi(raw); return e == nil && v > 0 && v <= 65535 }

type Server struct {
	http     *http.Server
	listener net.Listener
	done     chan struct{}
	err      error
	URL      string
}

func Listen(ctx context.Context, port int, reader *Reader) (*Server, error) {
	if port != 0 && (port < 1024 || port > 65535) {
		return nil, domain.ErrInvalid
	}
	handler, e := NewHandler(reader)
	if e != nil {
		return nil, e
	}
	listener, e := net.Listen("tcp4", fmt.Sprintf("127.0.0.1:%d", port))
	if e != nil {
		return nil, errors.New("CONSOLE_BIND_FAILED")
	}
	s := &Server{listener: netutil.LimitListener(listener, 16), done: make(chan struct{}), URL: "http://" + listener.Addr().String()}
	s.http = &http.Server{Handler: handler, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 5 * time.Second, MaxHeaderBytes: 8192, ErrorLog: log.New(io.Discard, "", 0), BaseContext: func(net.Listener) context.Context { return ctx }}
	go func() {
		e := s.http.Serve(s.listener)
		if errors.Is(e, http.ErrServerClosed) {
			e = nil
		}
		s.err = e
		close(s.done)
	}()
	return s, nil
}
func (s *Server) Close() error {
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
	defer cancel()
	if e := s.http.Shutdown(ctx); e != nil {
		s.http.Close()
		return e
	}
	return s.Wait()
}
func (s *Server) Wait() error           { <-s.done; return s.err }
func (s *Server) Done() <-chan struct{} { return s.done }
