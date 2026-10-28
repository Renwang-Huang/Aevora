// Package domain owns experience semantics independently of MCP and HTTP.
package domain

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

type Map = map[string]any

var ErrInvalid = storage.ErrInvalid
var ErrConflict = storage.ErrConflict

const RuleVersion = "aevora.when/1.2"
const CandidateVersion = "aevora.candidate/1.0"
const MCPVersion = "aevora.mcp/1.1"

var semantic = stringSet("operation_semantics authority_model authority_validation clock_domain failure_domain contract_version lease_expiry_semantics supported_operation_set observed_failure_mode")
var sourceTypes = stringSet("natural_agent_run maintainer_seed synthetic_or_test_fixture independent_project")
var states = stringSet("PROPOSED EVIDENCE_PENDING REJECTED ADMITTED_BOUNDED PUBLISHING PUBLISHED WITHDRAWN SUPERSEDED")
var transitions = map[string]map[string]bool{"PROPOSED": stringSet("EVIDENCE_PENDING REJECTED"), "EVIDENCE_PENDING": stringSet("REJECTED ADMITTED_BOUNDED"), "ADMITTED_BOUNDED": stringSet("PUBLISHING WITHDRAWN"), "PUBLISHING": stringSet("PUBLISHED WITHDRAWN"), "PUBLISHED": stringSet("WITHDRAWN SUPERSEDED")}
var sensitive = regexp.MustCompile(`(?i)(sk-[a-z0-9-]{16,}|/home/|/maintainer/|/proc/|hidden_tests|private_manifests|private_labels|reference_patches|(?:ignore|override) (?:all |previous |system )?instructions|system prompt)`)
var shaPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)
var idPatternLocal = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.:/@+\-]{0,239}$`)

func stringSet(s string) map[string]bool {
	m := map[string]bool{}
	for _, x := range strings.Fields(s) {
		m[x] = true
	}
	return m
}
func S(v any) string { x, _ := v.(string); return x }
func M(v any) Map    { x, _ := v.(map[string]any); return x }
func A(v any) []any {
	x, _ := v.([]any)
	if x == nil {
		return []any{}
	}
	return x
}
func B(v any) bool { x, _ := v.(bool); return x }
func I(v any) int {
	switch n := v.(type) {
	case int:
		return n
	case int64:
		return int(n)
	case json.Number:
		x, _ := strconv.Atoi(string(n))
		return x
	}
	return 0
}
func Clone(p Map) Map {
	m := Map{}
	for k, v := range p {
		m[k] = v
	}
	return m
}
func H(v any) string {
	s, e := codec.Digest(v)
	if e != nil {
		panic(e)
	}
	return s
}
func Now() string { return time.Now().UTC().Format("2006-01-02T15:04:05.000000+00:00") }
func timestamp(v any) (time.Time, error) {
	s, ok := v.(string)
	if !ok {
		return time.Time{}, ErrInvalid
	}
	t, e := time.Parse(time.RFC3339Nano, s)
	if e != nil {
		return t, ErrInvalid
	}
	return t, nil
}
func has(m Map, k string) bool { _, ok := m[k]; return ok }
func text(v any, max int) bool {
	s, ok := v.(string)
	return ok && strings.TrimSpace(s) != "" && utf8.RuneCountInString(s) <= max && !strings.ContainsRune(s, 0)
}
func publicText(v any, max int) bool { return text(v, max) && !sensitive.MatchString(S(v)) }
func stringsOf(v any) []string {
	out := []string{}
	for _, x := range A(v) {
		out = append(out, S(x))
	}
	return out
}
func values(ss []string) []any {
	out := []any{}
	for _, s := range ss {
		out = append(out, s)
	}
	return out
}
func sortedSet(set map[string]bool) []any {
	ss := []string{}
	for x, yes := range set {
		if yes {
			ss = append(ss, x)
		}
	}
	sort.Strings(ss)
	return values(ss)
}
func keys(m Map) []string {
	out := []string{}
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
func contains(v any, x any) bool {
	for _, item := range A(v) {
		if codec.Equal(item, x) {
			return true
		}
	}
	return false
}
func defaultValue(m Map, k string, fallback any) any {
	if x, ok := m[k]; ok {
		return x
	}
	return fallback
}
func subset(m Map, allowed string) bool {
	set := stringSet(allowed)
	for k := range m {
		if !set[k] {
			return false
		}
	}
	return true
}
func exact(m Map, allowed string) bool {
	return m != nil && len(m) == len(stringSet(allowed)) && subset(m, allowed)
}
func integer(v any) bool {
	switch n := v.(type) {
	case int, int64:
		return true
	case json.Number:
		return !strings.ContainsAny(string(n), ".eE")
	}
	return false
}
func boundedInteger(v any, maximum int) bool {
	if !integer(v) {
		return false
	}
	s := ""
	switch x := v.(type) {
	case int:
		s = strconv.Itoa(x)
	case int64:
		s = strconv.FormatInt(x, 10)
	case json.Number:
		s = string(x)
	}
	n, e := strconv.Atoi(s)
	return e == nil && n >= 0 && n <= maximum
}
func scalar(v any) bool {
	switch v.(type) {
	case string, bool, json.Number, int, int64, float64:
		return true
	}
	return false
}
func NormalizeContext(p Map, allowOnlyPublic bool) error {
	if p == nil || len(p) > 64 {
		return ErrInvalid
	}
	for k, v := range p {
		if !storage.ValidID(k) || (allowOnlyPublic && !facts[k]) {
			return ErrInvalid
		}
		if v != nil && !scalar(v) {
			return ErrInvalid
		}
		if e := validateFact(k, v); e != nil {
			return e
		}
	}
	_, e := codec.Canonical(p)
	return e
}
func ValidateScope(v any) error {
	p, ok := v.(Map)
	if !ok || len(p) > 32 {
		return ErrInvalid
	}
	for k, x := range p {
		a, ok := x.([]any)
		if !facts[k] || !ok || len(a) < 1 || len(a) > 32 {
			return ErrInvalid
		}
		for _, value := range a {
			if !scalar(value) {
				return ErrInvalid
			}
			if e := validateFact(k, value); e != nil {
				return e
			}
		}
	}
	return nil
}
func FactState(p Map, k string) string {
	v, ok := p[k]
	if !ok {
		return "MISSING"
	}
	s := strings.ToLower(strings.TrimSpace(S(v)))
	if _, ok := v.(string); ok && strings.ReplaceAll(strings.ReplaceAll(s, "-", "_"), " ", "_") == "not_observed" {
		return "NOT_OBSERVED"
	}
	if v == nil || (s == "unknown" || s == "unavailable" || s == "unspecified") {
		return "UNKNOWN"
	}
	return "KNOWN"
}
func ScopeRelation(context, scope Map) (string, []any) {
	unknown := []any{}
	for _, k := range keys(scope) {
		if FactState(context, k) != "KNOWN" {
			unknown = append(unknown, k)
		} else if !contains(scope[k], context[k]) {
			return "UNRELATED", []any{}
		}
	}
	if len(unknown) > 0 {
		return "UNKNOWN", unknown
	}
	return "MATCH", unknown
}
func ValidateProposal(p Map) error {
	base := Clone(p)
	delete(base, "derived_from_candidate_id")
	if !exact(base, "candidate_key title strategy public_summary necessary_conditions inapplicable_conditions scope unknown_fields limitations source_references") {
		return ErrInvalid
	}
	if parent, ok := p["derived_from_candidate_id"]; ok && !storage.ValidID(S(parent)) {
		return ErrInvalid
	}
	key := S(p["candidate_key"])
	if !storage.ValidID(key) || len(key) > 64 || strings.ContainsAny(key, ":/") {
		return ErrInvalid
	}
	for _, k := range []string{"title", "strategy", "public_summary"} {
		if !publicText(p[k], 4000) {
			return ErrInvalid
		}
	}
	for _, k := range []string{"necessary_conditions", "inapplicable_conditions", "scope"} {
		if e := ValidateScope(p[k]); e != nil {
			return e
		}
		for _, allowed := range M(p[k]) {
			for _, value := range A(allowed) {
				if text, ok := value.(string); ok && sensitive.MatchString(text) {
					return ErrInvalid
				}
			}
		}
	}
	// Empty applicability fields are valid untrusted drafts. Admission retains
	// its independent requirement for nonempty, verified conditions and scope.
	for _, k := range []string{"unknown_fields", "limitations"} {
		rows, ok := p[k].([]any)
		if !ok || len(rows) > 32 {
			return ErrInvalid
		}
		for _, x := range rows {
			if !publicText(x, 1000) || (k == "unknown_fields" && !facts[S(x)]) {
				return ErrInvalid
			}
		}
	}
	refs, ok := p["source_references"].([]any)
	if !ok || len(refs) > 32 {
		return ErrInvalid
	}
	for _, v := range refs {
		r := M(v)
		if !exact(r, "kind id") || !stringSet("Query Decision ObservedAction")[S(r["kind"])] || !storage.ValidID(S(r["id"])) {
			return ErrInvalid
		}
	}
	raw, e := codec.Canonical(p)
	if e != nil || len(raw) > 16384 {
		return ErrInvalid
	}
	return nil
}
func ValidateRecord(label string, p Map) error {
	if !storage.AllowedLabel(label) || !storage.ValidID(S(p["id"])) {
		return ErrInvalid
	}
	raw, e := codec.Canonical(p)
	if e != nil || len(raw) > 262144 {
		return ErrInvalid
	}
	switch label {
	case "Experience":
		if !sourceTypes[S(p["source_type"])] {
			return ErrInvalid
		}
		for _, k := range []string{"strategy", "title", "public_summary"} {
			if !text(p[k], 262144) {
				return ErrInvalid
			}
		}
	case "Evidence":
		if !sourceTypes[S(p["source_type"])] {
			return ErrInvalid
		}
		if _, ok := p["public_summary"].(string); !ok {
			return ErrInvalid
		}
	case "VerifiedOutcome":
		for _, k := range []string{"run_id", "submission_digest", "evaluator_fingerprint", "test_suite_fingerprint", "verifier_identity"} {
			if !text(p[k], 262144) {
				return ErrInvalid
			}
		}
		if has(p, "verified") || !stringSet("PASS FAIL ERROR TIMEOUT NOT_IMPLEMENTED")[S(p["verdict"])] {
			return ErrInvalid
		}
	case "Premise":
		if !storage.ValidID(S(p["fact_key"])) || len(A(p["allowed_values"])) < 1 || len(A(p["allowed_values"])) > 32 {
			return ErrInvalid
		}
		for _, v := range A(p["allowed_values"]) {
			if !scalar(v) {
				return ErrInvalid
			}
		}
		if has(p, "required") {
			if _, ok := p["required"].(bool); !ok {
				return ErrInvalid
			}
		}
	case "ExperienceRevision":
		if p["revision_kind"] == "rule_publication" {
			if !storage.ValidID(S(p["experience_id"])) || !storage.ValidID(S(p["declared_rule_id"])) || !storage.ValidID(S(p["publication_audit_id"])) || !text(p["revision_reason"], 4000) || !sourceTypes[S(p["source_type"])] {
				return ErrInvalid
			}
			if e := ValidateScope(p["scope"]); e != nil {
				return e
			}
			if !uniqueIDs(p["supersedes_ids"], 32) {
				return ErrInvalid
			}
			start, e := timestamp(p["valid_from"])
			if e != nil {
				return e
			}
			if p["valid_until"] != nil {
				end, e := timestamp(p["valid_until"])
				if e != nil || !end.After(start) {
					return ErrInvalid
				}
			}
		}
	case "GovernanceEvent":
		if !subset(p, "id target_id target_label event_type source_type public_reason scope effective_at created_at material_fact_keys completion_audit_id authority source_reference_sha256") || p["authority"] != "TRUSTED_HOST_GOVERNANCE" || !stringSet("Evidence ExperienceRevision")[S(p["target_label"])] || !storage.ValidID(S(p["target_id"])) || !storage.ValidID(S(p["completion_audit_id"])) || !stringSet("withdraw expire restrict_scope")[S(p["event_type"])] || !sourceTypes[S(p["source_type"])] || !text(p["public_reason"], 4000) {
			return ErrInvalid
		}
		if e := ValidateScope(p["scope"]); e != nil {
			return e
		}
		if !uniqueFacts(defaultValue(p, "material_fact_keys", []any{}), 32) {
			return ErrInvalid
		}
		for _, k := range []string{"effective_at", "created_at"} {
			if _, e = timestamp(p[k]); e != nil {
				return e
			}
		}
	case "QuerySnapshot":
		content := M(p["content"])
		if content == nil || p["content_sha256"] != H(content) || p["id"] != "snapshot:"+H(content) {
			return ErrInvalid
		}
	case "Candidate":
		if e := ValidateProposal(M(p["body"])); e != nil {
			return e
		}
		if p["body_sha256"] != H(p["body"]) || p["authority"] != "UNTRUSTED_PROPOSAL" || !storage.ValidID(S(p["run_id"])) || p["provenance"] != "UNVERIFIED_UNTIL_HOST_REVIEW" {
			return ErrInvalid
		}
		_, e = timestamp(p["created_at"])
		return e
	case "LifecycleHead":
		if !storage.ValidID(S(p["candidate_id"])) || !storage.ValidID(S(p["event_id"])) || !states[S(p["state"])] || !boundedInteger(p["sequence"], 127) {
			return ErrInvalid
		}
	case "CandidateEvent":
		if !storage.ValidID(S(p["candidate_id"])) || !states[S(p["to_state"])] || !boundedInteger(p["sequence"], 127) {
			return ErrInvalid
		}
		_, e = timestamp(p["created_at"])
		return e
	case "SourceVerification":
		if p["authority"] != "TRUSTED_HOST_SOURCE_VERIFIER" || !stringSet("natural_agent_run maintainer_seed synthetic_or_test_fixture external_unverified independent_project")[S(p["origin"])] || !storage.ValidID(S(p["run_id"])) || !shaPattern.MatchString(S(p["source_sha256"])) || !shaPattern.MatchString(S(p["submission_sha256"])) || (p["origin"] == "natural_agent_run" && S(p["outcome_id"]) == "") {
			return ErrInvalid
		}
		return NormalizeContext(M(p["facts"]), false)
	case "ExternalObservation":
		if p["authority"] != "EXTERNAL_UNVERIFIED" || p["trusted_outcome"] != "NOT_CREATED" || !storage.ValidID(S(p["run_id"])) || !publicText(p["public_summary"], 4000) || !shaPattern.MatchString(S(p["source_sha256"])) {
			return ErrInvalid
		}
		if p["record_kind"] == TaskEventKind {
			return validateTaskSource(p)
		}
		if p["record_kind"] == "OBSERVATION_USE_CLAIM" {
			if !exact(p, "id run_id record_kind candidate_id candidate_body_sha256 source_sha256 status authority trusted_outcome attribution created_at purpose disposition elapsed_seconds public_summary") ||
				!storage.ValidID(S(p["candidate_id"])) || !shaPattern.MatchString(S(p["candidate_body_sha256"])) ||
				p["status"] != "UNTRUSTED_USAGE_CLAIM" || p["attribution"] != "UNKNOWN" ||
				!stringSet("DEBUGGING PLANNING IMPLEMENTATION VALIDATION OTHER")[S(p["purpose"])] ||
				!stringSet("INVESTIGATED REUSED REJECTED NOT_RELEVANT INCONCLUSIVE")[S(p["disposition"])] ||
				(p["elapsed_seconds"] != nil && !boundedInteger(p["elapsed_seconds"], 86400)) {
				return ErrInvalid
			}
			if _, e := timestamp(p["created_at"]); e != nil {
				return e
			}
		}
		if p["record_kind"] == "CODEX_DIAGNOSTIC_SIGNAL" {
			e, run, cid, err := captureSourceIdentity(p)
			legacy := exact(p, "id run_id record_kind status authority trusted_outcome attribution created_at source_sha256 event public_summary") || exact(p, "id run_id candidate_id record_kind status authority trusted_outcome attribution created_at source_sha256 event public_summary")
			versioned := exact(p, "id run_id candidate_id grouping template_sha256 record_kind status authority trusted_outcome attribution created_at source_sha256 event public_summary")
			if err != nil || !(legacy || versioned) || (versioned && S(p["grouping"]) == "") || (has(p, "candidate_id") && p["candidate_id"] != cid) ||
				p["id"] != "external-observation:capture:"+e.ID || p["run_id"] != run || p["source_sha256"] != H(e.Map()) ||
				p["status"] != "UNTRUSTED_HOOK_CLAIM" || p["attribution"] != "UNKNOWN" {
				return ErrInvalid
			}
			if _, err = timestamp(p["created_at"]); err != nil {
				return err
			}
		}
	}
	return nil
}
func uniqueIDs(v any, max int) bool {
	rows, ok := v.([]any)
	if !ok || len(rows) > max {
		return false
	}
	seen := map[string]bool{}
	for _, x := range rows {
		s := S(x)
		if !storage.ValidID(s) || seen[s] {
			return false
		}
		seen[s] = true
	}
	return true
}
func uniqueFacts(v any, max int) bool {
	if !uniqueIDs(v, max) {
		return false
	}
	for _, x := range A(v) {
		if !facts[S(x)] {
			return false
		}
	}
	return true
}

type Repo struct{ *storage.Repository }

func (r Repo) Get(ctx context.Context, label, id string) (Map, error) {
	p, e := r.Repository.Get(ctx, label, id)
	if e != nil || p == nil {
		return p, e
	}
	if e = ValidateRecord(label, p); e != nil {
		return nil, e
	}
	return p, nil
}
func (r Repo) Put(ctx context.Context, label string, p Map) error {
	if e := ValidateRecord(label, p); e != nil {
		return e
	}
	return r.Repository.PutNode(ctx, label, p)
}
func (r Repo) Required(ctx context.Context, label, id string) (Map, error) {
	p, e := r.Get(ctx, label, id)
	if e != nil {
		return nil, e
	}
	if p == nil {
		return nil, fmt.Errorf("%w: required %s", ErrConflict, label)
	}
	return p, nil
}
func (r Repo) Public(ctx context.Context, label, id string) (Map, error) {
	p, e := r.Required(ctx, label, id)
	if e != nil {
		return nil, e
	}
	return storage.Public(label, p), nil
}
func (r Repo) List(ctx context.Context, label string, f storage.Filter) ([]Map, error) {
	rows, e := r.Repository.List(ctx, label, f)
	if e != nil {
		return nil, e
	}
	for _, p := range rows {
		if e = ValidateRecord(label, p); e != nil {
			return nil, e
		}
	}
	return rows, nil
}
