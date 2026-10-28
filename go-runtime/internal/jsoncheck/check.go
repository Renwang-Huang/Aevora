// Package jsoncheck executes an independent, pinned JSON artifact contract.
// It executes no submitted code and does not infer runtime behavior or causation.
package jsoncheck

import (
	"bytes"
	"context"
	"encoding/json"
	"encoding/xml"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const OperationSemantics = "json_artifact_contract_only"
const Evaluator = "aevora.json-artifact-contract/1: RFC6901 pointers; exact equals or subset membership; missing pointers fail; no submitted code execution"

type Invoke func(context.Context, string, domain.Map) (domain.Map, error)
type Plan struct {
	Schema           string `json:"schema_version"`
	Project          string `json:"project"`
	Submission       string `json:"submission"`
	Suite            string `json:"suite"`
	SourcePolicy     string `json:"source_policy"`
	AutomationPolicy string `json:"automation_policy"`
	OutputRoot       string `json:"output_root"`
	TaskRef          string `json:"task_ref"`
	Workspace        string `json:"-"`
	PlanPath         string `json:"-"`
	Unavailable      bool   `json:"-"`
}
type Suite struct {
	Schema string  `json:"schema_version"`
	Checks []Check `json:"checks"`
}
type Check struct {
	Name     string          `json:"name"`
	Pointer  string          `json:"pointer"`
	Equals   json.RawMessage `json:"equals,omitempty"`
	Contains json.RawMessage `json:"contains,omitempty"`
}
type testCase struct {
	Class   string  `xml:"classname,attr"`
	Name    string  `xml:"name,attr"`
	Failure *string `xml:"failure,omitempty"`
}
type testSuite struct {
	XMLName  xml.Name   `xml:"testsuite"`
	Tests    int        `xml:"tests,attr"`
	Failures int        `xml:"failures,attr"`
	Cases    []testCase `xml:"testcase"`
}

func Load(path string) (Plan, error) {
	var p Plan
	raw, e := platform.ReadPrivate(path, 65536)
	if e != nil {
		return p, e
	}
	if _, e = codec.Parse(raw); e != nil {
		return p, e
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	if e = d.Decode(&p); e != nil {
		return p, e
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return p, domain.ErrInvalid
	}
	if p.Schema != "aevora.json-check-plan/1" || p.Project == "" {
		return p, domain.ErrInvalid
	}
	for _, v := range []string{p.Submission, p.Suite, p.SourcePolicy, p.AutomationPolicy, p.OutputRoot} {
		if !filepath.IsAbs(v) {
			return p, domain.ErrInvalid
		}
	}
	return p, nil
}
func pointer(v any, path string) (any, bool) {
	if path == "" {
		return v, true
	}
	if !strings.HasPrefix(path, "/") {
		return nil, false
	}
	for _, part := range strings.Split(path[1:], "/") {
		for i := 0; i < len(part); i++ {
			if part[i] == '~' {
				if i+1 >= len(part) || (part[i+1] != '0' && part[i+1] != '1') {
					return nil, false
				}
				i++
			}
		}
		part = strings.ReplaceAll(strings.ReplaceAll(part, "~1", "/"), "~0", "~")
		switch x := v.(type) {
		case map[string]any:
			var ok bool
			v, ok = x[part]
			if !ok {
				return nil, false
			}
		case []any:
			i, e := strconv.Atoi(part)
			if e != nil || (len(part) > 1 && part[0] == '0') || i < 0 || i >= len(x) {
				return nil, false
			}
			v = x[i]
		default:
			return nil, false
		}
	}
	return v, true
}
func Evaluate(submission, suite []byte) ([]byte, int, error) {
	value, e := codec.Parse(submission)
	if e != nil {
		return nil, 0, e
	}
	if _, e = codec.Parse(suite); e != nil {
		return nil, 0, e
	}
	var s Suite
	d := json.NewDecoder(bytes.NewReader(suite))
	d.DisallowUnknownFields()
	if e = d.Decode(&s); e != nil {
		return nil, 0, e
	}
	if s.Schema != "aevora.json-contract-suite/1" || len(s.Checks) < 1 || len(s.Checks) > 100 {
		return nil, 0, domain.ErrInvalid
	}
	tests := testSuite{}
	seen := map[string]bool{}
	for _, c := range s.Checks {
		if c.Name == "" || len(c.Name) > 96 || strings.ContainsAny(c.Name, "/\\<>:\x00") || seen[c.Name] || len(c.Pointer) > 512 || (len(c.Equals) == 0) == (len(c.Contains) == 0) {
			return nil, 0, domain.ErrInvalid
		}
		seen[c.Name] = true
		actual, ok := pointer(value, c.Pointer)
		pass := false
		if len(c.Equals) > 0 {
			expected, e := codec.Parse(c.Equals)
			if e != nil {
				return nil, 0, e
			}
			pass = ok && codec.Equal(actual, expected)
		} else {
			expected, e := codec.Parse(c.Contains)
			if e != nil || domain.M(expected) == nil {
				return nil, 0, domain.ErrInvalid
			}
			if rows, yes := actual.([]any); ok && yes {
				for _, row := range rows {
					match := domain.M(row) != nil
					for k, v := range domain.M(expected) {
						if actual, exists := domain.M(row)[k]; !exists || !codec.Equal(actual, v) {
							match = false
						}
					}
					if match {
						pass = true
						break
					}
				}
			}
		}
		tc := testCase{Class: "json_contract", Name: c.Name}
		if !pass {
			message := "Independent JSON contract did not match"
			tc.Failure = &message
			tests.Failures++
		}
		tests.Cases = append(tests.Cases, tc)
	}
	tests.Tests = len(tests.Cases)
	raw, e := xml.Marshal(tests)
	code := 0
	if tests.Failures > 0 {
		code = 1
	}
	return raw, code, e
}
func readSubmission(path string) ([]byte, error) {
	f, e := os.OpenFile(path, platform.EvidenceFlags(), 0)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	before, e := platform.EvidenceStamp(f)
	if e != nil {
		return nil, e
	}
	raw, e := io.ReadAll(io.LimitReader(f, 1024*1024+1))
	if e != nil || len(raw) > 1024*1024 {
		return nil, domain.ErrInvalid
	}
	after, e := platform.EvidenceStamp(f)
	if e != nil || before != after {
		return nil, domain.ErrConflict
	}
	return raw, nil
}
func Run(ctx context.Context, p Plan, candidate string, invoke Invoke) (domain.Map, error) {
	if p.Workspace != "" {
		if e := ValidateWorkspace(p, p.PlanPath, p.Workspace); e != nil {
			return nil, e
		}
	}
	source, e := domain.LoadPolicy(p.SourcePolicy)
	if e != nil {
		return nil, e
	}
	if domain.M(source["facts"])["target_project"] != p.Project || domain.M(source["facts"])["operation_semantics"] != OperationSemantics || source["origin"] != "independent_project" {
		return nil, domain.ErrInvalid
	}
	suite, e := platform.ReadPrivate(p.Suite, 256*1024)
	if e != nil {
		return nil, e
	}
	if domain.BytesSHA(suite) != source["suite_sha256"] || domain.BytesSHA([]byte(Evaluator)) != source["evaluator_sha256"] {
		return nil, domain.ErrConflict
	}
	submission, e := readSubmission(p.Submission)
	if e != nil {
		return nil, e
	}
	if e = platform.PrivateDir(p.OutputRoot, true); e != nil {
		return nil, e
	}
	view, e := invoke(ctx, "inspect", domain.Map{"candidate_id": candidate})
	if e != nil {
		return nil, e
	}
	c := domain.M(view["candidate"])

	auto, e := domain.LoadAutomationPolicy(p.AutomationPolicy)
	if e != nil {
		return nil, e
	}
	scopeOK := false
	for _, v := range domain.A(domain.M(auto["scope"])["operation_semantics"]) {
		if v == OperationSemantics {
			scopeOK = true
		}
	}
	if !scopeOK {
		return nil, domain.ErrInvalid
	}
	view, e = invoke(ctx, "memory-json-projection", domain.Map{"candidate_id": candidate, "project": p.Project, "suite_sha256": source["suite_sha256"], "evaluator_sha256": source["evaluator_sha256"], "source_policy_sha256": domain.H(source), "automation_policy_sha256": domain.H(auto), "required_tests": source["required_tests"]})
	if e != nil {
		return nil, e
	}
	c = domain.M(view["candidate"])
	candidate = domain.S(c["id"])
	basis := domain.H([]any{domain.BytesSHA(submission), domain.BytesSHA(suite), domain.H(source), domain.H(auto)})
	guard, e := invoke(ctx, "memory-check-guard", domain.Map{"candidate_id": candidate, "project": p.Project, "basis": basis, "record": false})
	if e != nil {
		return nil, e
	}
	if guard["status"] == "UNCHANGED_VERIFIED" || guard["status"] == "INACTIVE" || guard["status"] == "INPUT_CHANGED_WITHDRAWN" {
		return guard, nil
	}
	root := filepath.Join(p.OutputRoot, "check-"+domain.H([]any{candidate, basis}))
	if e = platform.PrivateDir(root, true); e != nil {
		return nil, e
	}
	intentPath := filepath.Join(root, "intent.json")
	intent := domain.Map{"head": view["head_sha256"], "candidate_body_sha256": c["body_sha256"]}
	if raw, e2 := platform.ReadPrivate(intentPath, 4096); e2 == nil {
		v, e2 := codec.Parse(raw)
		if e2 != nil || domain.M(v)["candidate_body_sha256"] != c["body_sha256"] {
			return nil, domain.ErrConflict
		}
		intent = domain.M(v)
	} else if os.IsNotExist(e2) {
		raw, e2 := codec.Canonical(intent)
		if e2 != nil {
			return nil, e2
		}
		if e2 = platform.Exclusive(intentPath, raw); e2 != nil {
			return nil, e2
		}
	} else {
		return nil, e2
	}
	started := time.Now().UTC().Format(time.RFC3339Nano)
	junit, exit, e := Evaluate(submission, suite)
	if e != nil {
		return nil, e
	}
	artifacts := domain.Map{}
	for name, data := range map[string][]byte{"submission": submission, "suite": suite, "evaluator": []byte(Evaluator), "junit": junit} {
		file := name + ".data"
		if e = writeSame(filepath.Join(root, file), data); e != nil {
			return nil, e
		}
		artifacts[name] = domain.Map{"path": file, "sha256": domain.BytesSHA(data)}
	}
	receipt := domain.Map{"schema_version": domain.ReceiptVersion, "candidate_id": candidate, "candidate_body_sha256": c["body_sha256"], "run_id": c["run_id"], "verifier_id": source["verifier_id"], "origin": source["origin"], "facts": source["facts"], "started_at": started, "ended_at": time.Now().UTC().Format(time.RFC3339Nano), "exit_code": exit, "artifacts": artifacts}
	raw, e := codec.Canonical(receipt)
	if e != nil {
		return nil, e
	}
	receiptPath := filepath.Join(root, "receipt.json")
	if old, e2 := platform.ReadPrivate(receiptPath, 256*1024); e2 == nil {
		v, e2 := codec.Parse(old)
		if e2 != nil {
			return nil, e2
		}
		prior := domain.M(v)
		for _, key := range []string{"schema_version", "candidate_id", "candidate_body_sha256", "run_id", "verifier_id", "origin", "facts", "exit_code", "artifacts"} {
			if !codec.Equal(prior[key], receipt[key]) {
				return nil, domain.ErrConflict
			}
		}
		raw = old
	} else if os.IsNotExist(e2) {
		if e = platform.Exclusive(receiptPath, raw); e != nil {
			return nil, e
		}
	} else {
		return nil, e2
	}
	// Existing verifier and standing-policy gates remain the only promotion path.
	result, e := invoke(ctx, "candidate-automate", domain.Map{"candidate_id": candidate, "expected_head_sha256": intent["head"], "policy_file": p.AutomationPolicy, "source_policy_file": p.SourcePolicy, "evidence_root": root, "receipt_sha256": domain.BytesSHA(raw)})
	if e != nil {
		return nil, e
	}
	if result["status"] == "PUBLISHED" || result["status"] == "ADMITTED_BOUNDED" {
		if _, e = invoke(ctx, "memory-check-guard", domain.Map{"candidate_id": candidate, "project": p.Project, "basis": basis, "record": true}); e != nil {
			return nil, e
		}
	}
	result["check_scope"] = "PINNED_JSON_ARTIFACT_ONLY; NOT_RUNTIME_EXECUTION_OR_CAUSAL_BENEFIT"
	result["evidence_root"] = root
	return result, nil
}

func writeSame(path string, raw []byte) error {
	if e := platform.Exclusive(path, raw); e != nil {
		if !os.IsExist(e) {
			return e
		}
		old, e := platform.ReadPrivate(path, 32*1024*1024)
		if e != nil || !bytes.Equal(old, raw) {
			return domain.ErrConflict
		}
	}
	return nil
}

func ValidateWorkspace(p Plan, planPath, workspace string) error {
	real, e := filepath.EvalSymlinks(p.Submission)
	if e != nil {
		return e
	}
	rel, e := filepath.Rel(workspace, real)
	if e != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return domain.ErrInvalid
	}

	for _, file := range []string{planPath, p.Suite, p.SourcePolicy, p.AutomationPolicy} {
		real, e := filepath.EvalSymlinks(file)
		if e != nil {
			return e
		}
		rel, e := filepath.Rel(workspace, real)
		if e != nil || rel == "." || (!strings.HasPrefix(rel, ".."+string(filepath.Separator)) && rel != "..") {
			return domain.ErrInvalid
		}
	}
	return nil
}
