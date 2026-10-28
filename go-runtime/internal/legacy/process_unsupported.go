//go:build !linux && !darwin

package legacy

import (
	"os/exec"
)

func configureProcess(cmd *exec.Cmd) {}
func terminate(cmd *exec.Cmd) {
	if cmd.Process != nil {
		cmd.Process.Kill()
	}
}
