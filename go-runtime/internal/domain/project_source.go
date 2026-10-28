package domain

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/xml"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"io"
	"math"
	"regexp"
	"strconv"
	"strings"
)

const PolicyVersion = "aevora.project-source-policy/1"
const ReceiptVersion = "aevora.project-source-receipt/1"
const ProjectVerifier = "AevoraProjectSource/1"

var dtdPattern = regexp.MustCompile(`(?i)<!\s*(?:DOCTYPE|ENTITY)\b`)

type xmlNode struct {
	name     string
	attrs    map[string]string
	children []*xmlNode
}

func (n *xmlNode) all(name string) []*xmlNode {
	out := []*xmlNode{}
	if n.name == name {
		out = append(out, n)
	}
	for _, c := range n.children {
		out = append(out, c.all(name)...)
	}
	return out
}
func (n *xmlNode) direct(name string) int {
	count := 0
	for _, c := range n.children {
		if c.name == name {
			count++
		}
	}
	return count
}
func parseXML(raw []byte) (*xmlNode, error) {
	if dtdPattern.Match(raw) {
		return nil, ErrInvalid
	}
	d := xml.NewDecoder(bytes.NewReader(raw))
	d.Strict = true
	var root *xmlNode
	stack := []*xmlNode{}
	count := 0
	for {
		token, e := d.Token()
		if errors.Is(e, io.EOF) {
			break
		}
		if e != nil {
			return nil, ErrInvalid
		}
		count++
		if count > 100000 {
			return nil, ErrInvalid
		}
		switch v := token.(type) {
		case xml.StartElement:
			if v.Name.Space != "" || len(stack) >= 40 {
				return nil, ErrInvalid
			}
			n := &xmlNode{name: v.Name.Local, attrs: map[string]string{}}
			for _, a := range v.Attr {
				if a.Name.Space != "" {
					return nil, ErrInvalid
				}
				if _, exists := n.attrs[a.Name.Local]; exists {
					return nil, ErrInvalid
				}
				n.attrs[a.Name.Local] = a.Value
			}
			if len(stack) == 0 {
				if root != nil {
					return nil, ErrInvalid
				}
				root = n
			} else {
				parent := stack[len(stack)-1]
				parent.children = append(parent.children, n)
			}
			stack = append(stack, n)
		case xml.EndElement:
			if len(stack) == 0 {
				return nil, ErrInvalid
			}
			stack = stack[:len(stack)-1]
		case xml.Directive:
			return nil, ErrInvalid
		case xml.CharData:
			if len(stack) == 0 && strings.TrimSpace(string(v)) != "" {
				return nil, ErrInvalid
			}
		}
	}
	if root == nil || len(stack) != 0 || (root.name != "testsuite" && root.name != "testsuites") {
		return nil, ErrInvalid
	}
	return root, nil
}
func ReadJUnit(raw []byte, required []string) (Map, error) {
	root, e := parseXML(raw)
	if e != nil {
		return nil, e
	}
	suites := append(root.all("testsuite"), root.all("testsuites")...)
	for _, suite := range suites {
		cases := suite.all("testcase")
		actual := map[string]int{"tests": len(cases), "failures": 0, "errors": 0, "skipped": 0}
		for _, c := range cases {
			for _, pair := range [][2]string{{"failure", "failures"}, {"error", "errors"}, {"skipped", "skipped"}} {
				if c.direct(pair[0]) > 0 {
					actual[pair[1]]++
				}
			}
		}
		for key, number := range actual {
			if text, ok := suite.attrs[key]; ok {
				if text == "" {
					return nil, ErrInvalid
				}
				for _, c := range text {
					if c < '0' || c > '9' {
						return nil, ErrInvalid
					}
				}
				n, e := strconv.Atoi(text)
				if e != nil || n != number {
					return nil, ErrInvalid
				}
			}
		}
	}
	counts := Map{"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
	tests := []any{}
	identities := map[string]int{}
	for _, c := range root.all("testcase") {
		if c.direct("failure")+c.direct("error")+c.direct("skipped") > 1 {
			return nil, ErrInvalid
		}
		durationText := c.attrs["time"]
		if durationText == "" {
			durationText = "0"
		}
		duration, e := strconv.ParseFloat(durationText, 64)
		if (e != nil && !errors.Is(e, strconv.ErrRange)) || math.IsInf(duration, 0) || math.IsNaN(duration) || duration < 0 {
			return nil, ErrInvalid
		}
		outcome, category := "PASS", "passed"
		if c.direct("error") > 0 {
			outcome, category = "ERROR", "errors"
		} else if c.direct("failure") > 0 {
			outcome, category = "FAIL", "failed"
		} else if c.direct("skipped") > 0 {
			outcome, category = "SKIPPED", "skipped"
		}
		id := c.attrs["classname"] + "::" + c.attrs["name"]
		identities[id]++
		counts["collected"] = I(counts["collected"]) + 1
		counts[category] = I(counts[category]) + 1
		tests = append(tests, Map{"name": c.attrs["name"], "nodeid": id, "outcome": outcome})
	}
	if len(identities) != len(required) {
		return nil, ErrInvalid
	}
	for _, id := range required {
		if identities[id] != 1 {
			return nil, ErrInvalid
		}
	}
	counts["tests"] = tests
	return counts, nil
}
func ValidatePolicy(p Map) error {
	if !exact(p, "schema_version verifier_id origin suite_sha256 evaluator_sha256 required_tests facts") || p["schema_version"] != PolicyVersion || !storageID(S(p["verifier_id"])) || !stringSet("independent_project synthetic_or_test_fixture")[S(p["origin"])] || !shaPattern.MatchString(S(p["suite_sha256"])) || !shaPattern.MatchString(S(p["evaluator_sha256"])) {
		return ErrInvalid
	}
	tests, ok := p["required_tests"].([]any)
	if !ok || len(tests) < 1 || len(tests) > 1000 {
		return ErrInvalid
	}
	seen := map[string]bool{}
	for _, v := range tests {
		s, ok := v.(string)
		if !ok || s == "" || len([]rune(s)) > 512 || !strings.Contains(s, "::") || seen[s] {
			return ErrInvalid
		}
		seen[s] = true
	}
	if len(M(p["facts"])) == 0 {
		return ErrInvalid
	}
	return NormalizeContext(M(p["facts"]), true)
}
func LoadPolicy(path string) (Map, error) {
	raw, e := platform.ReadPrivate(path, 256*1024)
	if e != nil {
		return nil, e
	}
	v, e := codec.Parse(raw)
	if e != nil {
		return nil, e
	}
	p := M(v)
	if e = ValidatePolicy(p); e != nil {
		return nil, e
	}
	return p, nil
}
func (r Repo) VerifyProjectCandidate(ctx context.Context, id string, policy Map, root, pin string) (Map, error) {
	if e := ValidatePolicy(policy); e != nil {
		return nil, e
	}
	if !shaPattern.MatchString(pin) {
		return nil, ErrInvalid
	}
	view, e := r.Inspect(ctx, id)
	if e != nil {
		return nil, e
	}
	candidate := M(view["candidate"])
	files, e := OpenEvidence(root)
	if e != nil {
		return nil, e
	}
	defer files.Close()
	raw, e := files.Read("receipt.json", 256*1024, pin)
	if e != nil {
		return nil, e
	}
	value, e := codec.Parse(raw)
	if e != nil {
		return nil, e
	}
	receipt := M(value)
	if !exact(receipt, "schema_version candidate_id candidate_body_sha256 run_id verifier_id origin facts started_at ended_at exit_code artifacts") || receipt["schema_version"] != ReceiptVersion || receipt["candidate_id"] != id || receipt["candidate_body_sha256"] != candidate["body_sha256"] || receipt["run_id"] != candidate["run_id"] || receipt["verifier_id"] != policy["verifier_id"] || receipt["origin"] != policy["origin"] || !codec.Equal(receipt["facts"], policy["facts"]) {
		return nil, ErrInvalid
	}
	start, e := timestamp(receipt["started_at"])
	if e != nil {
		return nil, e
	}
	end, e := timestamp(receipt["ended_at"])
	if e != nil || end.Before(start) || !boundedInteger(receipt["exit_code"], 255) {
		return nil, ErrInvalid
	}
	code := I(receipt["exit_code"])
	artifacts := M(receipt["artifacts"])
	if !exact(artifacts, "submission suite evaluator junit") {
		return nil, ErrInvalid
	}
	seen := map[string]bool{}
	var junit []byte
	for _, item := range []struct {
		name  string
		limit int64
	}{{"submission", 32 * 1024 * 1024}, {"suite", 8 * 1024 * 1024}, {"evaluator", 1024 * 1024}, {"junit", 8 * 1024 * 1024}} {
		ref := M(artifacts[item.name])
		if !exact(ref, "path sha256") || !shaPattern.MatchString(S(ref["sha256"])) || seen[S(ref["path"])] {
			return nil, ErrInvalid
		}
		seen[S(ref["path"])] = true
		if (item.name == "suite" || item.name == "evaluator") && ref["sha256"] != policy[item.name+"_sha256"] {
			return nil, ErrInvalid
		}
		data, e := files.Read(S(ref["path"]), item.limit, S(ref["sha256"]))
		if e != nil || len(data) == 0 {
			return nil, ErrInvalid
		}
		if item.name == "junit" {
			junit = data
		}
	}
	tests, e := ReadJUnit(junit, stringsOf(policy["required_tests"]))
	if e != nil {
		return nil, e
	}
	verdict := "ERROR"
	if code == 0 {
		if tests["passed"] != tests["collected"] {
			return nil, ErrInvalid
		}
		verdict = "PASS"
	} else if code == 1 && I(tests["failed"]) > 0 && I(tests["errors"]) == 0 && I(tests["skipped"]) == 0 {
		verdict = "FAIL"
	}
	suffix := H([]any{ProjectVerifier, id, pin, policy})
	origin := policy["origin"]
	testCounts := Map{}
	for _, k := range []string{"passed", "failed", "errors", "skipped"} {
		testCounts[k] = tests[k]
	}
	outcome := Map{"id": "project-outcome:" + suffix, "run_id": candidate["run_id"], "verdict": verdict, "submission_digest": M(artifacts["submission"])["sha256"], "evaluator_fingerprint": policy["evaluator_sha256"], "test_suite_fingerprint": policy["suite_sha256"], "verifier_identity": ProjectVerifier, "source_type": origin, "attribution": "UNKNOWN", "test_count": tests["collected"], "test_counts": testCounts, "source_receipt_sha256": pin, "source_policy_sha256": H(policy), "junit_sha256": M(artifacts["junit"])["sha256"], "evaluated_at": receipt["ended_at"], "assurance": "Host-authorized independent verifier receipt and pinned artifacts; not runtime attestation"}
	context := Map{"id": "context:project-source:" + suffix, "facts": policy["facts"], "source_type": origin}
	task := Map{"id": "task:project-source:" + suffix, "public_title": "Independent project verification in a bounded factual scope"}
	source := Map{"id": "source-verification:project:" + suffix, "candidate_id": id, "run_id": candidate["run_id"], "authority": "TRUSTED_HOST_SOURCE_VERIFIER", "origin": origin, "facts": policy["facts"], "source_sha256": pin, "submission_sha256": outcome["submission_digest"], "outcome_id": outcome["id"], "verifier_id": policy["verifier_id"], "verifier_version": ProjectVerifier, "source_epoch": "project-receipt:sha256:" + pin, "native_thread_id": "UNAVAILABLE", "causal_benefit": "UNKNOWN"}
	records := []struct {
		label string
		p     Map
	}{{"VerifiedOutcome", outcome}, {"Context", context}, {"Task", task}, {"SourceVerification", source}}
	for _, row := range records {
		if e = ValidateRecord(row.label, row.p); e != nil {
			return nil, e
		}
	}
	for _, row := range records {
		if e = r.Put(ctx, row.label, row.p); e != nil {
			return nil, e
		}
	}
	for _, edge := range [][5]string{{"IN_CONTEXT", "VerifiedOutcome", S(outcome["id"]), "Context", S(context["id"])}, {"FOR_TASK", "Context", S(context["id"]), "Task", S(task["id"])}, {"HAS_SOURCE_VERIFICATION", "Candidate", id, "SourceVerification", S(source["id"])}} {
		if e = r.PutEdge(ctx, edge[0], edge[1], edge[2], edge[3], edge[4], nil); e != nil {
			return nil, e
		}
	}
	admission := "BLOCKED_NON_PASS"
	if verdict == "PASS" {
		admission = "ELIGIBLE_FOR_BOUNDED_REVIEW"
	}
	return Map{"status": "SOURCE_VERIFIED", "source": source, "outcome_verdict": verdict, "admission": admission, "lifecycle_state": M(view["head"])["state"], "agent_adoption": "UNKNOWN", "causal_benefit": "UNKNOWN"}, nil
}
func BytesSHA(raw []byte) string { h := sha256.Sum256(raw); return hex.EncodeToString(h[:]) }
