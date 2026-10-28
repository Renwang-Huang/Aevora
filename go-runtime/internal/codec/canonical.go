// Package codec preserves the Python reference's immutable JSON identity.
package codec

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"math"
	"math/big"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"
)

var ErrInvalid = errors.New("AEVORA_INVALID_RECORD")

// Parse accepts scalars and arrays as well as objects, without losing integer
// versus floating point identity. The shared decoder enforces structural bounds.
func Parse(raw []byte) (any, error) {
	v, e := wire.DecodeValue(raw, wire.MaxMessage)
	if e != nil {
		return nil, ErrInvalid
	}
	return v, nil
}

func Canonical(v any) ([]byte, error) { return appendValue(nil, v, 0) }
func Normalize(raw []byte) ([]byte, error) {
	v, e := Parse(raw)
	if e != nil {
		return nil, e
	}
	return Canonical(v)
}
func Digest(v any) (string, error) {
	b, e := Canonical(v)
	if e != nil {
		return "", e
	}
	s := sha256.Sum256(b)
	return hex.EncodeToString(s[:]), nil
}
func Equal(a, b any) bool {
	x, e := Canonical(a)
	if e != nil {
		return false
	}
	y, e := Canonical(b)
	return e == nil && string(x) == string(y)
}

func quote(dst []byte, s string) ([]byte, error) {
	if !utf8.ValidString(s) {
		return nil, ErrInvalid
	}
	dst = append(dst, '"')
	for _, r := range s {
		switch r {
		case '"', '\\':
			dst = append(dst, '\\', byte(r))
		case '\b':
			dst = append(dst, `\b`...)
		case '\f':
			dst = append(dst, `\f`...)
		case '\n':
			dst = append(dst, `\n`...)
		case '\r':
			dst = append(dst, `\r`...)
		case '\t':
			dst = append(dst, `\t`...)
		default:
			if r < 32 {
				const h = "0123456789abcdef"
				dst = append(dst, '\\', 'u', '0', '0', h[r>>4], h[r&15])
			} else {
				dst = utf8.AppendRune(dst, r)
			}
		}
	}
	return append(dst, '"'), nil
}

func floatString(f float64) (string, error) {
	if math.IsNaN(f) || math.IsInf(f, 0) {
		return "", ErrInvalid
	}
	if f == 0 {
		if math.Signbit(f) {
			return "-0.0", nil
		}
		return "0.0", nil
	}
	s := strconv.FormatFloat(f, 'e', -1, 64)
	parts := strings.Split(s, "e")
	exponent, _ := strconv.Atoi(parts[1])
	if exponent < -4 || exponent >= 16 {
		sign := "+"
		if exponent < 0 {
			sign = "-"
			exponent = -exponent
		}
		digits := strconv.Itoa(exponent)
		if exponent < 10 {
			digits = "0" + digits
		}
		return parts[0] + "e" + sign + digits, nil
	}
	s = strconv.FormatFloat(f, 'f', -1, 64)
	if !strings.Contains(s, ".") {
		s += ".0"
	}
	return s, nil
}

func appendValue(dst []byte, v any, depth int) ([]byte, error) {
	if depth > 16 {
		return nil, ErrInvalid
	}
	switch n := v.(type) {
	case nil:
		return append(dst, "null"...), nil
	case bool:
		return strconv.AppendBool(dst, n), nil
	case string:
		return quote(dst, n)
	case json.Number:
		if strings.ContainsAny(string(n), ".eE") {
			f, e := strconv.ParseFloat(string(n), 64)
			if e != nil && !errors.Is(e, strconv.ErrRange) {
				return nil, ErrInvalid
			}
			s, e := floatString(f)
			return append(dst, s...), e
		}
		integer, ok := new(big.Int).SetString(string(n), 10)
		if !ok || len(n) > 4300 {
			return nil, ErrInvalid
		}
		return append(dst, integer.String()...), nil
	case float64:
		s, e := floatString(n)
		return append(dst, s...), e
	case int:
		return strconv.AppendInt(dst, int64(n), 10), nil
	case int64:
		return strconv.AppendInt(dst, n, 10), nil
	case uint64:
		return strconv.AppendUint(dst, n, 10), nil
	case []any:
		dst = append(dst, '[')
		for i, item := range n {
			if i > 0 {
				dst = append(dst, ',')
			}
			var e error
			dst, e = appendValue(dst, item, depth+1)
			if e != nil {
				return nil, e
			}
		}
		return append(dst, ']'), nil
	case map[string]any:
		keys := make([]string, 0, len(n))
		for k := range n {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		dst = append(dst, '{')
		for i, k := range keys {
			if i > 0 {
				dst = append(dst, ',')
			}
			var e error
			dst, e = quote(dst, k)
			if e != nil {
				return nil, e
			}
			dst = append(dst, ':')
			dst, e = appendValue(dst, n[k], depth+1)
			if e != nil {
				return nil, e
			}
		}
		return append(dst, '}'), nil
	case json.RawMessage:
		normalized, e := Normalize(n)
		return append(dst, normalized...), e
	default:
		return nil, ErrInvalid
	}
}
