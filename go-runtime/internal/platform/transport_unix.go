//go:build linux || darwin

package platform

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

func socketBase() string {
	base, e := filepath.EvalSymlinks("/tmp")
	if e != nil {
		return ""
	}
	return filepath.Join(base, "aevora-ipc-"+strconv.Itoa(os.Getuid()))
}
func Address(folder string) string {
	address := filepath.Join(folder, "mcp.sock")
	if len([]byte(address)) <= 103 {
		return address
	}
	base := socketBase()
	if base == "" {
		return ""
	}
	h := sha256.Sum256([]byte(folder))
	return filepath.Join(base, hex.EncodeToString(h[:16]), "mcp.sock")
}

type socketListener struct {
	net.Listener
	directory string
}

func (l *socketListener) Close() error { e := l.Listener.Close(); os.Remove(l.directory); return e }
func Listen(address string) (net.Listener, error) {
	if address == "" || !filepath.IsAbs(address) || len([]byte(address)) > 103 {
		return nil, errors.New("SESSION_PATH_TOO_LONG")
	}
	short := false
	base := socketBase()
	if base != "" && strings.HasPrefix(address, base+string(filepath.Separator)) {
		short = true
		if e := PrivateDir(base, true); e != nil {
			return nil, e
		}
		if e := PrivateDir(filepath.Dir(address), true); e != nil {
			return nil, e
		}
	} else if e := PrivateDir(filepath.Dir(address), false); e != nil {
		return nil, e
	}
	l, e := net.Listen("unix", address)
	if e != nil {
		return nil, e
	}
	if e = os.Chmod(address, 0600); e != nil {
		l.Close()
		return nil, e
	}
	if short {
		return &socketListener{Listener: l, directory: filepath.Dir(address)}, nil
	}
	return l, nil
}
func Dial(ctx context.Context, address string) (net.Conn, error) {
	return (&net.Dialer{Timeout: 10 * time.Second}).DialContext(ctx, "unix", address)
}
