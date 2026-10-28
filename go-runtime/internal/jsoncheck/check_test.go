package jsoncheck

import (
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"testing"
)

func TestIndependentJSONChecksPassFailAndMissingPointer(t *testing.T) {
	suite := []byte(`{"schema_version":"aevora.json-contract-suite/1","checks":[{"name":"source-reader","pointer":"/tools","contains":{"name":"read_observation_sources"}},{"name":"version","pointer":"/version","equals":1}]}`)
	for _, tc := range []struct {
		raw  string
		want int
	}{{`{"version":1,"tools":[{"name":"read_observation_sources","extra":true}]}`, 0}, {`{"version":1,"tools":[]}`, 1}, {`{"version":1}`, 1}} {
		junit, code, e := Evaluate([]byte(tc.raw), suite)
		if e != nil || code != tc.want {
			t.Fatal(code, e)
		}
		tests, e := domain.ReadJUnit(junit, []string{"json_contract::source-reader", "json_contract::version"})
		if e != nil || tests["collected"] != 2 {
			t.Fatal(tests, e)
		}
	}
	if _, _, e := Evaluate([]byte(`{}`), []byte(`{"schema_version":"aevora.json-contract-suite/1","checks":[{"name":"bad","pointer":"","equals":{},"contains":{}}]}`)); e == nil {
		t.Fatal("ambiguous check accepted")
	}
}
