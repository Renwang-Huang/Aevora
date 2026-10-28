package clientconfig

import (
	"bytes"
	"reflect"
	"strings"

	"github.com/pelletier/go-toml/v2"
)

// Official client writers may append unrelated TOML tables before trailing
// comments, including our END marker. Recognize only an exact owned prefix,
// move our own comment, and require the entire parsed config to stay equal.
// Never put the intervening settings (e.g. hook trust) into an undo receipt.
func normalizeManagedBlock(raw []byte, receipt Receipt) ([]byte, bool, error) {
	if ownedBlock(raw, receipt) {
		return raw, false, nil
	}
	if !strings.HasPrefix(receipt.Block, begin) || !strings.HasSuffix(receipt.Block, end) || bytes.Count(raw, []byte(begin)) != 1 || bytes.Count(raw, []byte(end)) != 1 {
		return nil, false, ErrConflict
	}
	prefix := []byte(strings.TrimSuffix(receipt.Block, end))
	if bytes.Count(raw, prefix) != 1 {
		return nil, false, ErrConflict
	}
	start := bytes.Index(raw, prefix) + len(prefix)
	close := bytes.Index(raw, []byte(end))
	if close < start {
		return nil, false, ErrConflict
	}
	next := append([]byte{}, raw[:start]...)
	next = append(next, []byte(end)...)
	next = append(next, raw[start:close]...)
	next = append(next, raw[close+len(end):]...)
	var before, after map[string]any
	if toml.Unmarshal(raw, &before) != nil || toml.Unmarshal(next, &after) != nil || !reflect.DeepEqual(before, after) || !ownedBlock(next, receipt) {
		return nil, false, ErrConflict
	}
	return next, true, nil
}
