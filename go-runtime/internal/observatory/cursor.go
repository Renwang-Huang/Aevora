package observatory

import (
	"encoding/base64"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
)

type Selection struct {
	Run, Experience, Case, Stage, Mode, Resource string
	Limit, Offset                                int
	After                                        map[string]string
}

var pageKeys = map[string]bool{"sessions": true, "queries": true, "experiences": true, "candidates": true, "timeline": true, "recorded_decisions": true, "trusted": true, "external": true, "graph": true}

func nullable(v string) any {
	if v == "" {
		return nil
	}
	return v
}
func decodeCursor(token string, s Selection) (map[string]string, error) {
	out := map[string]string{}
	if token == "" {
		return out, nil
	}
	if len(token) > 3800 {
		return nil, storage.ErrInvalid
	}
	raw, e := base64.RawURLEncoding.Strict().DecodeString(token)
	if e != nil {
		return nil, storage.ErrInvalid
	}
	value, e := codec.Parse(raw)
	if e != nil {
		return nil, e
	}
	v := domain.M(value)
	if len(v) != 4 || !codec.Equal(v["v"], 1) || !codec.Equal(v["run"], nullable(s.Run)) || !codec.Equal(v["experience"], nullable(s.Experience)) {
		return nil, storage.ErrInvalid
	}
	after := domain.M(v["after"])
	if after == nil {
		return nil, storage.ErrInvalid
	}
	for k, v := range after {
		id, ok := v.(string)
		if !pageKeys[k] || !ok || !storage.ValidID(id) {
			return nil, storage.ErrInvalid
		}
		out[k] = id
	}
	return out, nil
}
func cursor(after map[string]string, s Selection) string {
	values := Map{}
	for k, v := range after {
		values[k] = v
	}
	raw, e := codec.Canonical(Map{"v": 1, "run": nullable(s.Run), "experience": nullable(s.Experience), "after": values})
	if e != nil {
		return ""
	}
	return base64.RawURLEncoding.EncodeToString(raw)
}
