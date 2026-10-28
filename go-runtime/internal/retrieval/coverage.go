package retrieval

import (
	"sort"
	"strings"
)

const CoveragePolicy = "lexical-concept-coverage/1"

// Coverage keeps broad recall from becoming a recommendation on one shared
// word. Each explicit alias group gets one vote, regardless of how many
// synonyms match. Other non-Han terms get one vote each. SQLite performs the
// matching with the same Porter tokenizer as BM25; no approximate Go stemmer
// or corpus-dependent score threshold is used.
//
// Unknown Han bigrams cannot be translated here. In mixed queries they remain
// recall hints, not extra independent votes against the known Latin terms.
// Pure Han queries fall back to their lexical bigrams. This is deliberately not
// a general multilingual answerability classifier.
func Coverage(text string) (groups []string, minimum int, limited bool) {
	original := Terms(text)
	set := map[string]bool{}
	for _, word := range original {
		if !stop[word] {
			set[word] = true
		}
	}
	consumed := map[string]bool{}
	for _, aliases := range aliases {
		matched := false
		for _, alias := range aliases {
			if set[alias] || (containsHan(alias) && strings.Contains(text, alias)) {
				matched = true
			}
		}
		if !matched {
			continue
		}
		concept := map[string]bool{}
		for _, alias := range aliases {
			for _, word := range Terms(alias) {
				concept[word], consumed[word] = true, true
			}
		}
		words := []string{}
		for word := range concept {
			words = append(words, quoteTerm(word))
		}
		sort.Strings(words)
		groups = append(groups, "("+strings.Join(words, " OR ")+")")
	}
	han := []string{}
	for _, word := range original {
		if stop[word] || consumed[word] {
			continue
		}
		if containsHan(word) {
			han = append(han, quoteTerm(word))
		} else {
			groups = append(groups, quoteTerm(word))
		}
	}
	if len(groups) == 0 {
		groups = han
	}
	sort.Strings(groups)
	if len(groups) > 64 {
		groups, limited = groups[:64], true
	}
	// Fixed before looking at this iteration's quality results. Requiring a
	// majority of distinct query concepts trades some recall for abstention.
	minimum = (3*len(groups) + 4) / 5 // ceil(0.6*n), including n=0.
	return groups, minimum, limited
}

func quoteTerm(word string) string { return `"` + strings.ReplaceAll(word, `"`, `""`) + `"` }
