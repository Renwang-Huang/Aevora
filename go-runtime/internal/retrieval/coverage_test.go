package retrieval

import (
	"strings"
	"testing"
)

func TestCoverageCountsConceptsNotSynonymsOrCallerOperators(t *testing.T) {
	for _, tc := range []struct {
		query           string
		groups, minimum int
	}{
		{"native queue", 2, 2}, {"原生队列", 2, 2}, {"queue queued 队列", 1, 1},
		{"DNS traffic steering", 3, 2}, {"the and or", 0, 0}, {"SQLite 数据库写争用", 1, 1},
	} {
		g, minimum, limited := Coverage(tc.query)
		if len(g) != tc.groups || minimum != tc.minimum || limited {
			t.Fatal(tc, g, minimum, limited)
		}
	}
	g, _, _ := Coverage(`sqlite" OR title:secret*`)
	for _, term := range g {
		if !strings.HasPrefix(term, `"`) || !strings.HasSuffix(term, `"`) || strings.ContainsAny(term, ":*") {
			t.Fatal("unquoted operator", g)
		}
	}
	query := ""
	for i := 0; i < 80; i++ {
		query += " token" + strings.Repeat("z", i+1)
	}
	g, minimum, limited := Coverage(query)
	if len(g) != 64 || minimum != 39 || !limited {
		t.Fatal(len(g), minimum, limited)
	}
}
