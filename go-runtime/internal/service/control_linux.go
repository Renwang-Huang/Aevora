//go:build linux

package service

import (
	"bytes"
	"context"
	"os/exec"
	"time"
)

type bounded struct{ bytes.Buffer }

func (b *bounded) Write(p []byte) (int, error) {
	if b.Len()+len(p) > 65536 {
		return 0, ErrUnavailable
	}
	return b.Buffer.Write(p)
}
func control(ctx context.Context, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, 80*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "systemctl", append([]string{"--user"}, args...)...)
	var out, stderr bounded
	cmd.Stdout = &out
	cmd.Stderr = &stderr
	cmd.WaitDelay = 2 * time.Second
	if e := cmd.Run(); e != nil {
		if exit, ok := e.(*exec.ExitError); ok && exit.ExitCode() == 4 && len(args) > 0 && args[0] == "show" && bytes.Contains(out.Bytes(), []byte("ActiveState=")) {
			return out.String(), nil
		}
		return "", ErrUnavailable
	}
	return out.String(), nil
}
