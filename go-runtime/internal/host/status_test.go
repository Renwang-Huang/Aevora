package host

import "testing"

func TestStatusBudgetWarningsKeepLowAndExhaustedDistinct(t *testing.T) {
	for _, c := range []struct {
		used int
		want string
	}{{54, ""}, {55, "DISTINCT_RUNS_LOW"}, {64, "DISTINCT_RUNS_EXHAUSTED"}, {65, "DISTINCT_RUNS_EXHAUSTED"}} {
		b := map[string]int{"runs_total": c.used, "run_limit": 64}
		warnings := budgetWarnings(b)
		if c.want == "" {
			if len(warnings) != 0 {
				t.Fatal(warnings)
			}
		} else if len(warnings) != 1 || warnings[0] != c.want {
			t.Fatal(c.used, warnings)
		}
		if b["runs_total"] != c.used {
			t.Fatal("observation changed budget")
		}
	}
}
