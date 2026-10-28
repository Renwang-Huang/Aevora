package domain

import (
	"context"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"strings"
)

const captureGrouping = "session-turn-template/1"
const previousCaptureGrouping = "project-signal-template/1"

// captureRun retains the first released grouping identity for legacy sources.
func captureRun(e captureformat.Event) string { run, _ := captureIdentity(e, "", ""); return run }

func captureIdentity(e captureformat.Event, grouping, template string) (string, string) {
	parts := []any{e.Project, e.Signal}
	if grouping != "" {
		parts = []any{grouping, e.Project, e.Signal, template}
		if grouping == captureGrouping {
			parts = append(parts, e.SessionRef, e.TurnRef)
		}
	}
	run := "capture-" + H(parts)[:24]
	return run, "candidate:" + run + ":" + captureCandidateKey(e)
}
func captureCurrentRun(e captureformat.Event) string {
	run, _ := captureIdentity(e, captureGrouping, H(captureCandidate(e)))
	return run
}

func captureCandidateKey(e captureformat.Event) string {
	return "codex-signal-" + strings.ToLower(strings.ReplaceAll(e.Signal, "_", "-"))
}
func captureCandidateID(e captureformat.Event) string {
	_, id := captureIdentity(e, captureGrouping, H(captureCandidate(e)))
	return id
}

// A stored source retains its original grouping and template assignment.
// Legacy identities are checked using their historical algorithm, never the
// current release's mutable wording.
func captureSourceIdentity(source Map) (captureformat.Event, string, string, error) {
	e, err := captureformat.Parse(M(source["event"]))
	if err != nil {
		return e, "", "", ErrInvalid
	}
	grouping, template := S(source["grouping"]), S(source["template_sha256"])
	if has(source, "grouping") || has(source, "template_sha256") {
		if (grouping != captureGrouping && grouping != previousCaptureGrouping) || !shaPattern.MatchString(template) {
			return e, "", "", ErrInvalid
		}
	}
	run, id := captureIdentity(e, grouping, template)
	return e, run, id, nil
}
func captureCandidate(e captureformat.Event) Map {
	title, strategy := "", ""
	switch e.Signal {
	case "JSON_DECODE_ERROR":
		title = "JSONDecodeError 解码异常线索"
		strategy = "查看实际输入、响应边界和异常位置，确认是数据格式、上游返回还是传输问题；修复后重新验证。"
	case "RUN_CONTEXT_CONFLICT":
		title = "Run context conflict 上下文冲突线索"
		strategy = "比较固定任务条件与当前可信观察；条件改变时建立新任务并保留历史，不自动重放结果不明的写操作。"
	case "RECONNECT_REQUIRED":
		title = "Reconnect required 连接恢复线索"
		strategy = "检查 Host 状态与任务授权；重连前核对未确认写操作的实际结果，不把连接恢复当作业务成功。"
	case "CONNECTION_REFUSED":
		title = "Connection refused 连接拒绝线索"
		strategy = "核对目标地址、进程和监听状态，再验证网络与重试条件；不要在未定位时改动无关服务。"
	case "PERMISSION_DENIED":
		title = "Permission denied 权限拒绝线索"
		strategy = "检查实际所有权、访问权限与执行上下文，验证拒绝发生的位置和原因，避免扩大无关权限。"
	}
	return Map{"candidate_key": captureCandidateKey(e), "title": title, "strategy": strategy,
		"public_summary":       "Codex hook 输出命中了固定诊断词汇；来源和项目提示未核验，尚未确定失败、原因或修复结果。",
		"necessary_conditions": Map{}, "scope": Map{}, "inapplicable_conditions": Map{}, "unknown_fields": []any{},
		"limitations":       []any{"词汇命中可能是引用或其他文本，不能证明实际错误。", "项目提示、根因与适用范围尚未独立核验；该草稿不能准入或发布。"},
		"source_references": []any{}}
}

// IngestCapture stores a typed untrusted hook claim. The exact content and ID
// are deterministic, making a receiver commit followed by a lost ack safe to
// reconcile; it never creates a verified outcome or an applicability fact.
func (r Repo) IngestCapture(ctx context.Context, input Map) (Map, error) {
	e, err := captureformat.Parse(input)
	if err != nil {
		return nil, ErrInvalid
	}
	id := "external-observation:capture:" + e.ID
	old, err := r.Get(ctx, "ExternalObservation", id)
	if err != nil {
		return nil, err
	}
	if old != nil {
		if err = ValidateRecord("ExternalObservation", old); err != nil {
			return nil, err
		}
		if !codec.Equal(old["event"], input) {
			return nil, ErrConflict
		}
		result := Map{"status": "ALREADY_RECORDED_UNTRUSTED", "event_id": e.ID, "observation_id": id, "source_sha256": H(input), "authority": "EXTERNAL_UNVERIFIED", "outcome": "NOT_CREATED", "candidate_id": old["candidate_id"]}
		if has(old, "candidate_id") {
			_, run, cid, e2 := captureSourceIdentity(old)
			if e2 != nil {
				return nil, e2
			}
			if _, e2 = r.CaptureSummary(ctx, cid, run); e2 != nil {
				return nil, e2
			}
		} else {
			result["consolidation"] = "LEGACY_SOURCE_UNGROUPED"
		}
		return result, nil
	}
	created := Now()
	candidateID := captureCandidateID(e)
	claim := Map{"id": id, "run_id": captureCurrentRun(e), "candidate_id": candidateID, "record_kind": "CODEX_DIAGNOSTIC_SIGNAL", "status": "UNTRUSTED_HOOK_CLAIM",
		"grouping": captureGrouping, "template_sha256": H(captureCandidate(e)),
		"authority": "EXTERNAL_UNVERIFIED", "trusted_outcome": "NOT_CREATED", "attribution": "UNKNOWN", "created_at": created,
		"source_sha256": H(input), "event": input,
		"public_summary": fmt.Sprintf("Codex hook reported %s for %s; inspect the original tool result independently. Project and event origin are unverified.", e.Signal, e.Tool)}
	if err = r.Put(ctx, "ExternalObservation", claim); err != nil {
		return nil, err
	}
	body := captureCandidate(e)
	candidate, err := r.Get(ctx, "Candidate", candidateID)
	if err != nil {
		return nil, err
	}
	if candidate == nil {
		proposal, e2 := r.Propose(ctx, captureCurrentRun(e), body)
		if e2 != nil {
			return nil, e2
		}
		if proposal["candidate_id"] != candidateID {
			return nil, ErrConflict
		}
	} else if candidate["run_id"] != captureCurrentRun(e) || !codec.Equal(candidate["body"], body) {
		return nil, ErrConflict
	}
	anchors, err := r.Edges(ctx, "Candidate", candidateID, "DERIVED_FROM", false)
	if err != nil {
		return nil, err
	}
	anchored := false
	for _, edge := range anchors {
		if edge.TargetLabel != "ExternalObservation" {
			continue
		}
		source, e2 := r.Required(ctx, "ExternalObservation", edge.TargetID)
		if e2 != nil {
			return nil, e2
		}
		_, _, priorID, e2 := captureSourceIdentity(source)
		if e2 != nil || priorID != candidateID {
			return nil, ErrConflict
		}
		anchored = true
	}
	if !anchored {
		if err = r.PutEdge(ctx, "DERIVED_FROM", "Candidate", candidateID, "ExternalObservation", id, nil); err != nil {
			return nil, err
		}
	}
	status := "RECORDED_UNTRUSTED"
	if old != nil {
		status = "ALREADY_RECORDED_UNTRUSTED"
	}
	return Map{"status": status, "event_id": e.ID, "observation_id": id, "candidate_id": candidateID, "source_sha256": H(input), "authority": "EXTERNAL_UNVERIFIED", "outcome": "NOT_CREATED"}, nil
}

// CaptureSummary keeps project as a source hint and counts immutable records;
// neither the count nor the first source anchor establishes true failures.
func (r Repo) CaptureSummary(ctx context.Context, candidate, run string) (Map, error) {
	if !strings.HasPrefix(run, "capture-") {
		return nil, nil
	}
	rows, err := r.Repository.ExternalByKind(ctx, "", run, "CODEX_DIAGNOSTIC_SIGNAL", 1)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, nil
	}
	if err = ValidateRecord("ExternalObservation", rows[0]); err != nil {
		return nil, err
	}
	e, priorRun, priorID, err := captureSourceIdentity(rows[0])
	if err != nil || priorID != candidate || priorRun != run {
		return nil, ErrConflict
	}
	if template := S(rows[0]["template_sha256"]); template != "" {
		p, e2 := r.Required(ctx, "Candidate", candidate)
		if e2 != nil {
			return nil, e2
		}
		if p["body_sha256"] != template {
			return nil, ErrConflict
		}
	}
	count, err := r.Repository.CountExternalByKind(ctx, run, "CODEX_DIAGNOSTIC_SIGNAL")
	if err != nil {
		return nil, err
	}
	anchors, err := r.Edges(ctx, "Candidate", candidate, "DERIVED_FROM", false)
	if err != nil {
		return nil, err
	}
	anchored := false
	for _, edge := range anchors {
		if edge.TargetLabel != "ExternalObservation" {
			continue
		}
		source, e2 := r.Required(ctx, "ExternalObservation", edge.TargetID)
		if e2 != nil {
			return nil, e2
		}
		_, _, priorID, e2 := captureSourceIdentity(source)
		if e2 != nil || priorID != candidate {
			return nil, ErrConflict
		}
		anchored = true
	}
	if !anchored {
		return nil, ErrConflict
	}
	return Map{"source_record_count": count, "sample_observation_id": rows[0]["id"], "signal": e.Signal, "project_hint": e.Project, "session_ref": e.SessionRef, "turn_ref": e.TurnRef, "tool_ref": e.ToolRef,
		"episode_id": captureEpisode(e), "episode_authority": "UNVERIFIED_SESSION_TURN_HINT; NOT_ROOT_CAUSE",
		"grouping": rows[0]["grouping"], "template_sha256": rows[0]["template_sha256"],
		"project_authority": "UNVERIFIED_HOOK_HINT", "failure": "NOT_PROVEN", "outcome": "NOT_CREATED", "ordering": "ID_NOT_RECENCY"}, nil
}

func captureEpisode(e captureformat.Event) string {
	return "episode-" + H([]any{e.Project, e.SessionRef, e.TurnRef})[:24]
}

func (r Repo) CaptureSources(ctx context.Context, candidate, after string, limit int) (Map, error) {
	if limit < 1 || limit > 50 || (after != "" && !strings.HasPrefix(after, "external-observation:capture:")) {
		return nil, ErrInvalid
	}
	p, err := r.Required(ctx, "Candidate", candidate)
	if err != nil {
		return nil, err
	}
	run := S(p["run_id"])
	summary, err := r.CaptureSummary(ctx, candidate, run)
	if err != nil {
		return nil, err
	}
	if summary == nil {
		return nil, ErrInvalid
	}
	rows, err := r.Repository.CaptureSourcePage(ctx, run, after, limit+1)
	if err != nil {
		return nil, err
	}
	more := len(rows) > limit
	if more {
		rows = rows[:limit]
	}
	items := []any{}
	for _, source := range rows {
		if err = ValidateRecord("ExternalObservation", source); err != nil {
			return nil, err
		}
		e, sourceRun, cid, e2 := captureSourceIdentity(source)
		if e2 != nil || cid != candidate || sourceRun != run {
			return nil, ErrConflict
		}
		items = append(items, Map{"observation_id": source["id"], "event_id": e.ID, "project_hint": e.Project, "session_ref": e.SessionRef, "turn_ref": e.TurnRef, "tool_ref": e.ToolRef, "tool": e.Tool, "signal": e.Signal, "episode_id": captureEpisode(e), "recorded_at": source["created_at"], "authority": "UNTRUSTED_HOOK_CLAIM"})
	}
	next := ""
	if more && len(rows) > 0 {
		next = S(rows[len(rows)-1]["id"])
	}
	return Map{"candidate_id": candidate, "sources": items, "summary": summary, "more": more, "next_cursor": next, "limit": limit, "authority": "UNTRUSTED_SOURCES_ONLY", "ordering": "ID_NOT_RECENCY; REFRESH_FOR_NEW_LOWER_IDS", "outcome": "NOT_CREATED"}, nil
}
