// Package wire enforces bounds before data enters SDK or Worker decoders.
package wire

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"math"
	"strconv"
	"strings"
	"unicode/utf8"
)

const MaxMessage = 262144

var ErrInvalid = errors.New("AEVORA_INVALID_FRAME")

func Decode(raw []byte, limit int) (map[string]any, error) {
	v, err := DecodeValue(raw, limit)
	if err != nil {
		return nil, err
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, ErrInvalid
	}
	return m, nil
}

// DecodeValue shares strict JSON validation with immutable scalar records.
func DecodeValue(raw []byte, limit int) (any, error) {
	if len(raw) == 0 || len(raw) > limit || !utf8.Valid(raw) {
		return nil, ErrInvalid
	}
	// encoding/json replaces unpaired UTF-16 escapes with U+FFFD. Refuse that
	// lossy normalization before SDK decoding or evidence hashing.
	for i := 0; i < len(raw); i++ {
		if raw[i] != '\\' {
			continue
		}
		i++
		if i >= len(raw) {
			return nil, ErrInvalid
		}
		if raw[i] != 'u' {
			continue
		}
		if i+4 >= len(raw) {
			return nil, ErrInvalid
		}
		n, e := strconv.ParseUint(string(raw[i+1:i+5]), 16, 16)
		if e != nil {
			return nil, ErrInvalid
		}
		i += 4
		if n >= 0xD800 && n <= 0xDBFF {
			if i+6 >= len(raw) || raw[i+1] != '\\' || raw[i+2] != 'u' {
				return nil, ErrInvalid
			}
			low, e := strconv.ParseUint(string(raw[i+3:i+7]), 16, 16)
			if e != nil || low < 0xDC00 || low > 0xDFFF {
				return nil, ErrInvalid
			}
			i += 6
		} else if n >= 0xDC00 && n <= 0xDFFF {
			return nil, ErrInvalid
		}
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	nodes := 0
	var value func(int) (any, error)
	value = func(depth int) (any, error) {
		nodes++
		if depth > 16 || nodes > 20000 {
			return nil, ErrInvalid
		}
		t, err := d.Token()
		if err != nil {
			return nil, ErrInvalid
		}
		if n, ok := t.(json.Number); ok && strings.ContainsAny(string(n), ".eE") {
			f, e := strconv.ParseFloat(string(n), 64)
			if (e != nil && !errors.Is(e, strconv.ErrRange)) || math.IsInf(f, 0) || math.IsNaN(f) {
				return nil, ErrInvalid
			}
		}
		if delimiter, ok := t.(json.Delim); ok {
			switch delimiter {
			case '{':
				m := map[string]any{}
				for d.More() {
					key, err := d.Token()
					if err != nil {
						return nil, ErrInvalid
					}
					k, ok := key.(string)
					if !ok {
						return nil, ErrInvalid
					}
					if _, exists := m[k]; exists {
						return nil, ErrInvalid
					}
					v, err := value(depth + 1)
					if err != nil {
						return nil, err
					}
					m[k] = v
				}
				end, err := d.Token()
				if err != nil || end != json.Delim('}') {
					return nil, ErrInvalid
				}
				return m, nil
			case '[':
				a := []any{}
				for d.More() {
					v, err := value(depth + 1)
					if err != nil {
						return nil, err
					}
					a = append(a, v)
				}
				end, err := d.Token()
				if err != nil || end != json.Delim(']') {
					return nil, ErrInvalid
				}
				return a, nil
			default:
				return nil, ErrInvalid
			}
		}
		return t, nil
	}
	v, err := value(0)
	if err != nil {
		return nil, err
	}
	if _, err = d.Token(); err != io.EOF {
		return nil, ErrInvalid
	}
	return v, nil
}

func Line(r *bufio.Reader, maximum int) ([]byte, error) {
	var line []byte
	for {
		part, err := r.ReadSlice('\n')
		if len(line)+len(part) > maximum {
			return nil, ErrInvalid
		}
		line = append(line, part...)
		if err == bufio.ErrBufferFull {
			continue
		}
		if err != nil {
			return nil, err
		}
		if _, err := Decode(line, maximum); err != nil {
			return nil, err
		}
		return line, nil
	}
}

func ReadPacket(r io.Reader) ([]byte, error) {
	return ReadPacketLimit(r, MaxMessage)
}
func ReadPacketLimit(r io.Reader, maximum int) ([]byte, error) {
	var header [4]byte
	if _, err := io.ReadFull(r, header[:]); err != nil {
		return nil, err
	}
	n := binary.BigEndian.Uint32(header[:])
	if n == 0 || n > uint32(maximum) {
		return nil, ErrInvalid
	}
	raw := make([]byte, int(n))
	if _, err := io.ReadFull(r, raw); err != nil {
		return nil, err
	}
	if _, err := Decode(raw, maximum); err != nil {
		return nil, err
	}
	return raw, nil
}

func WritePacket(w io.Writer, v any) error {
	raw, err := json.Marshal(v)
	if err != nil {
		return err
	}
	if _, err = Decode(raw, MaxMessage); err != nil {
		return err
	}
	var b [4]byte
	binary.BigEndian.PutUint32(b[:], uint32(len(raw)))
	for _, part := range [][]byte{b[:], raw} {
		for len(part) > 0 {
			n, err := w.Write(part)
			if err != nil {
				return err
			}
			if n == 0 {
				return io.ErrShortWrite
			}
			part = part[n:]
		}
	}
	return nil
}
