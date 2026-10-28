package domain

import (
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"strings"
	"testing"
)

func TestCandidatePublicNarrativeNeverProjectsRawReferencesOrPrivateFields(t *testing.T) {
	body := Map{"candidate_key": "public", "title": "Public observation", "strategy": "Inspect scope", "public_summary": "Public summary",
		"necessary_conditions": Map{}, "inapplicable_conditions": Map{}, "scope": Map{}, "unknown_fields": []any{}, "limitations": []any{},
		"source_references": []any{Map{"kind": "Query", "id": "query:private-reference-marker"}}}
	candidate := Map{"body": body, "body_sha256": H(body), "private_receipt": "private-receipt-marker"}
	public, err := PublicCandidate(candidate)
	if err != nil {
		t.Fatal(err)
	}
	raw, err := codec.Canonical(public)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), "private-reference-marker") || strings.Contains(string(raw), "private-receipt-marker") || public["title"] != "Public observation" {
		t.Fatal("public projection boundary", public)
	}
	body["scope"] = Map{"shared_state_kind": []any{"/home/private-path-marker"}}
	candidate["body_sha256"] = H(body)
	if _, err = PublicCandidate(candidate); err == nil {
		t.Fatal("sensitive declaration exposed")
	}
}
