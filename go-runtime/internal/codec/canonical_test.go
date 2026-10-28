package codec

import (
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"testing"
)

func TestPythonCanonicalReference(t *testing.T) {
	raw, e := contracts.Files.ReadFile("reference.json")
	if e != nil {
		t.Fatal(e)
	}
	var fixture struct {
		Cases []struct{ Input, Canonical, SHA256 string } `json:"canonical_cases"`
	}
	if e = json.Unmarshal(raw, &fixture); e != nil {
		t.Fatal(e)
	}
	if len(fixture.Cases) < 250 {
		t.Fatal("reference fixture missing")
	}
	for _, c := range fixture.Cases {
		v, e := Parse([]byte(c.Input))
		if e != nil {
			t.Fatalf("parse %s: %v", c.Input, e)
		}
		b, e := Canonical(v)
		if e != nil || string(b) != c.Canonical {
			t.Fatalf("%s: got %s want %s (%v)", c.Input, b, c.Canonical, e)
		}
		sha, e := Digest(v)
		if e != nil || sha != c.SHA256 {
			t.Fatalf("digest mismatch %s", c.Input)
		}
	}
}

func TestRejectLossyOrNonfiniteValues(t *testing.T) {
	for _, raw := range []string{`{"a":1,"a":2}`, `1e999`, `"\ud800"`, `NaN`, `{"a":}`} {
		if _, e := Parse([]byte(raw)); e == nil {
			t.Fatalf("accepted %s", raw)
		}
	}
}
