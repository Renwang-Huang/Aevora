// Package retrieval prepares lexical text for SQLite FTS5. Relevance is never
// an applicability fact or a confidence/probability of engineering success.
package retrieval

import (
	"sort"
	"strings"
	"unicode"
)

// Terms preserves identifiers and adds overlapping Han bigrams. FTS5's porter
// unicode61 tokenizer supplies English stemming and Unicode token handling.
// This is lexical recall, not an embedding or general translation service.
func Terms(text string) []string {
	seen := map[string]bool{}
	var word, han []rune
	flushWord := func() {
		if len(word) > 1 && len(word) <= 128 {
			seen[strings.ToLower(string(word))] = true
		}
		word = nil
	}
	flushHan := func() {
		if len(han) == 1 {
			seen[string(han)] = true
		}
		for i := 0; i+1 < len(han); i++ {
			seen[string(han[i:i+2])] = true
		}
		han = nil
	}
	for _, r := range text {
		switch {
		case unicode.Is(unicode.Han, r):
			flushWord()
			han = append(han, r)
		case unicode.IsLetter(r) || unicode.IsDigit(r):
			flushHan()
			word = append(word, r)
		default:
			flushWord()
			flushHan()
		}
	}
	flushWord()
	flushHan()
	out := make([]string, 0, len(seen))
	for term := range seen {
		out = append(out, term)
	}
	sort.Strings(out)
	return out
}

// Alias groups are a small, release-controlled engineering vocabulary. They
// expand queries only, never facts or evidence; disclose them in the response.
var aliases = [][]string{
	{"原生", "native"}, {"队列", "queue", "queued"},
	{"模型", "model", "models"}, {"推理强度", "reasoning", "effort"},
	{"会话", "session", "sessions"}, {"重启", "restart", "restarting", "reboot"},
	{"回收站", "trash", "recycle"}, {"代理", "proxy"},
	{"权限", "permission", "permissions"}, {"取消", "cancel", "cancellation"},
}

var stop = func() map[string]bool {
	m := map[string]bool{}
	for _, term := range strings.Fields("the and or not with for from this that how what when where why please using use into can could should would have has had are was were will about task tasks") {
		m[term] = true
	}
	return m
}()

func Query(text string) (string, []string, bool) {
	original := Terms(text)
	originalSet := map[string]bool{}
	set := map[string]bool{}
	for _, term := range original {
		originalSet[term] = true
		if !stop[term] {
			set[term] = true
		}
	}
	expanded := []string{}
	anchors := []string{}
	for _, group := range aliases {
		matched := false
		for _, alias := range group {
			if originalSet[alias] || (containsHan(alias) && strings.Contains(text, alias)) {
				matched = true
			}
		}
		if matched {
			concept := map[string]bool{}
			for _, alias := range group {
				for _, term := range Terms(alias) {
					concept[term] = true
					if !set[term] {
						set[term] = true
						expanded = append(expanded, term)
					}
				}
			}
			words := []string{}
			for term := range concept {
				words = append(words, `"`+term+`"`)
			}
			sort.Strings(words)
			anchors = append(anchors, "("+strings.Join(words, " OR ")+")")
		}
	}
	terms := []string{}
	for term := range set {
		terms = append(terms, term)
	}
	sort.Strings(terms)
	sort.Strings(expanded)
	limited := len(terms) > 64
	if limited {
		terms = terms[:64]
	}
	// Never expose FTS operators, prefixes, column names or SQL from caller text.
	for i, term := range terms {
		terms[i] = `"` + strings.ReplaceAll(term, `"`, `""`) + `"`
	}
	all := strings.Join(terms, " OR ")
	if len(anchors) > 0 {
		// All explicitly recognized concepts must match. A lone "native" match
		// must not recommend a Host restart for a "native queue" task. The OR
		// arm retains other lexical terms for BM25 ranking; anchors decide
		// membership. This is a disclosed vocabulary, not inferred semantics.
		return "(" + strings.Join(anchors, " AND ") + ") AND (" + all + ")", expanded, limited
	}
	return all, expanded, limited
}

func containsHan(s string) bool {
	for _, r := range s {
		if unicode.Is(unicode.Han, r) {
			return true
		}
	}
	return false
}
