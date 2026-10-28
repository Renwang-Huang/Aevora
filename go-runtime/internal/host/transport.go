package host

import (
	"bufio"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"io"
	"net"
	"sync"
	"time"
)

type boundedConn struct {
	net.Conn
	reader  *bufio.Reader
	host    *Host
	session string
	journal *Journal
	ids     map[string]bool
	pending []byte
	writeMu sync.Mutex
	out     []byte
	closed  chan struct{}
	once    sync.Once
}

func (c *boundedConn) done() <-chan struct{} { return c.closed }
func (c *boundedConn) Close() error          { c.once.Do(func() { close(c.closed) }); return c.Conn.Close() }
func (c *boundedConn) Read(p []byte) (int, error) {
	if len(c.pending) == 0 {
		c.Conn.SetReadDeadline(time.Time{})
		if _, e := c.reader.ReadByte(); e != nil {
			return 0, e
		}
		if e := c.reader.UnreadByte(); e != nil {
			return 0, e
		}
		c.Conn.SetReadDeadline(time.Now().Add(10 * time.Second))
		raw, e := wire.Line(c.reader, wire.MaxMessage)
		c.Conn.SetReadDeadline(time.Time{})
		if e != nil {
			return 0, e
		}
		v, e := wire.Decode(raw, wire.MaxMessage)
		if e != nil {
			return 0, e
		}
		method, _ := v["method"].(string)
		switch method {
		case "server/discover", "initialize", "notifications/initialized", "tools/list", "tools/call", "notifications/cancelled", "ping":
		default:
			return 0, wire.ErrInvalid
		}
		if v["jsonrpc"] != "2.0" {
			return 0, wire.ErrInvalid
		}
		if id, exists := v["id"]; exists {
			switch id.(type) {
			case string, json.Number:
			default:
				return 0, wire.ErrInvalid
			}
			b, _ := json.Marshal(id)
			key := string(b)
			if len(key) > 130 || c.ids[key] {
				return 0, wire.ErrInvalid
			}
			c.ids[key] = true
		} else if method != "notifications/initialized" && method != "notifications/cancelled" {
			return 0, wire.ErrInvalid
		}
		c.host.mu.Lock()
		c.host.frames++
		exceeded := c.host.frames > 4096
		c.host.mu.Unlock()
		if exceeded {
			return 0, wire.ErrInvalid
		}
		c.pending = raw
	}
	n := copy(p, c.pending)
	c.pending = c.pending[n:]
	return n, nil
}
func (c *boundedConn) Write(p []byte) (int, error) {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	if len(c.out)+len(p) > wire.MaxMessage {
		return 0, wire.ErrInvalid
	}
	c.out = append(c.out, p...)
	if len(c.out) == 0 || c.out[len(c.out)-1] != '\n' {
		return len(p), nil
	}
	v, e := wire.Decode(c.out, wire.MaxMessage)
	if e != nil {
		return 0, e
	}
	c.Conn.SetWriteDeadline(time.Now().Add(60 * time.Second))
	defer c.Conn.SetWriteDeadline(time.Time{})
	for len(c.out) > 0 {
		n, e := c.Conn.Write(c.out)
		if e != nil {
			return 0, e
		}
		if n == 0 {
			return 0, io.ErrShortWrite
		}
		c.out = c.out[n:]
	}
	if result, ok := v["result"].(map[string]any); ok {
		if meta, ok := result["_meta"].(map[string]any); ok {
			if id, ok := meta["operation_id"].(string); ok {
				journal := c.journal
				if journal == nil {
					journal = c.host.journal
				}
				if e := journal.Event("RESPONSE", c.session, id, "WRITTEN_TO_TRANSPORT"); e != nil {
					c.host.stopConnections()
					return 0, e
				}
			}
		}
	}
	return len(p), nil
}
