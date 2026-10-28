package cli

import (
	"context"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/service"
	"github.com/spf13/cobra"
	"os"
	"path/filepath"
	"strconv"
	"time"
)

func addHostCommands(c *cobra.Command, project *string) {
	hc := &cobra.Command{Use: "host", Short: "Manage one local Host through the user's service manager"}
	var background, autostart bool
	for _, action := range []string{"start", "stop", "restart", "status", "remove"} {
		v := &cobra.Command{Use: action, Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
			pr, p, e := selectedProject(*project)
			if e != nil {
				return e
			}
			dir, e := local.ProjectDir(pr.Name)
			if e != nil {
				return e
			}
			dir = filepath.Join(dir, "service")
			if action == "start" && !background {
				inner := Command(native.Factory())
				inner.SetArgs([]string{"--config", pr.Profile, "serve", "--port", "0"})
				inner.SetOut(cmd.OutOrStdout())
				inner.SetErr(cmd.ErrOrStderr())
				return inner.ExecuteContext(cmd.Context())
			}
			var r service.Record
			if action == "start" {
				exe, e := os.Executable()
				if e != nil {
					return e
				}
				exe, e = filepath.EvalSymlinks(exe)
				if e != nil {
					return e
				}
				r, e = service.Install(cmd.Context(), dir, pr.BackendID, pr.Profile, exe)
				if e != nil {
					return e
				}
			} else {
				r, e = service.Load(dir, pr.BackendID)
				if e != nil {
					return e
				}
			}
			if action == "status" {
				s, e := service.Show(cmd.Context(), r)
				if e != nil {
					return e
				}
				return output(cmd, map[string]any{"project": pr.Name, "service": s, "readiness": "USE_EXPLICIT_CHECK_FOR_MCP_PROOF"})
			}
			if action == "remove" {
				if e = service.Remove(cmd.Context(), dir, r); e != nil {
					return e
				}
				return output(cmd, map[string]any{"status": "REMOVED", "project": pr.Name, "data": "PRESERVED"})
			}
			if e = service.Action(cmd.Context(), dir, r, action); e != nil {
				return e
			}
			if action == "stop" {
				return output(cmd, map[string]any{"status": "STOPPED", "project": pr.Name, "history": "PRESERVED"})
			}
			if autostart {
				if e = service.Action(cmd.Context(), dir, r, "enable"); e != nil {
					return e
				}
			}
			end := time.Now().Add(20 * time.Second)
			for time.Now().Before(end) {
				s, e := host.ReadStatus(p)
				if e == nil && s.State == "READY" {
					unit, e := service.Show(cmd.Context(), r)
					if e != nil {
						return e
					}
					pid, e := strconv.Atoi(unit["MainPID"])
					if e == nil && pid == s.PID && unit["ActiveState"] == "active" {
						probeCtx, cancel := context.WithTimeout(cmd.Context(), 5*time.Second)
						probe, e := host.Probe(probeCtx, p)
						cancel()
						console, consoleErr := consoleProbe(cmd.Context(), p)
						if e == nil && consoleErr == nil && console["status"] == "READY" {
							return output(cmd, map[string]any{"console_probe": console, "status": "READY", "project": pr.Name, "console": s.Console, "runtime": s, "mcp": probe, "login_autostart_requested": autostart})
						}
					}
				}
				select {
				case <-cmd.Context().Done():
					return cmd.Context().Err()
				case <-time.After(50 * time.Millisecond):
				}
			}
			return errors.New("AEVORA_HOST_READINESS_TIMEOUT")
		}}
		if action == "start" {
			v.Flags().BoolVar(&background, "background", false, "Explicitly register/start this project's user service")
		}
		if action == "start" || action == "restart" {
			v.Flags().BoolVar(&autostart, "autostart", false, "Explicitly enable login startup; otherwise unchanged")
		}
		hc.AddCommand(v)
	}
	c.AddCommand(hc)
}
