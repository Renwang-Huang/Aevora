package wire

import (
	"bufio"
	"strings"
	"testing"
)

func TestRejectAmbiguousAndOversizedFrames(t *testing.T) {
	for _, raw := range []string{`{"x":1,"x":2}`, `{"x":NaN}`, `{"x":1e9999}`, `{"x":"\ud800"}`, `[]`, `{"x":1} {}`, `{"x":` + strings.Repeat("[", 17) + `0` + strings.Repeat("]", 17) + `}`} {
		if _, err := Decode([]byte(raw), MaxMessage); err == nil {
			t.Fatalf("accepted %s", raw)
		}
	}
	if _, err := Line(bufio.NewReader(strings.NewReader(`{"n":9007199254740993}`+"\n")), MaxMessage); err != nil {
		t.Fatal(err)
	}
	if _, err := Line(bufio.NewReader(strings.NewReader(strings.Repeat(" ", MaxMessage)+"{}\n")), MaxMessage); err == nil {
		t.Fatal("oversized frame accepted")
	}
}
