//go:build darwin

package platform

import (
	"bytes"
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type accountOutput struct{ bytes.Buffer }

func (b *accountOutput) Write(p []byte) (int, error) {
	if b.Len()+len(p) > 16384 {
		return 0, os.ErrInvalid
	}
	return b.Buffer.Write(p)
}

// macOS without CGO cannot resolve Directory Services through os/user.
// Use the OS utility by numeric UID, never HOME/USER or an arbitrary command.
// See https://github.com/golang/go/issues/24383.
func OwnershipHome() string {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	uid := strconv.Itoa(os.Getuid())
	cmd := exec.CommandContext(ctx, "/usr/bin/dscacheutil", "-q", "user", "-a", "uid", uid)
	cmd.Env = []string{"PATH=/usr/bin:/bin", "LANG=C"}
	var out accountOutput
	cmd.Stdout = &out
	if cmd.Run() != nil {
		return ""
	}
	home, actual := "", ""
	count := 0
	for _, line := range strings.Split(out.String(), "\n") {
		key, value, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		switch strings.TrimSpace(key) {
		case "uid":
			actual = strings.TrimSpace(value)
		case "dir":
			home = strings.TrimSpace(value)
			count++
		}
	}
	if actual != uid || count != 1 || !filepath.IsAbs(home) {
		return ""
	}
	return filepath.Join(home, "Library", "Application Support")
}
