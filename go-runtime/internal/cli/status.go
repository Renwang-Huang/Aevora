package cli

import (
	"errors"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/service"
	"github.com/spf13/cobra"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
)

func addStatus(c *cobra.Command, project *string) {
	var storage bool
	command := &cobra.Command{Use: "status", Short: "Read bounded observations without authentication or business calls", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		state := "UNAVAILABLE_OR_STALE"
		var runtime any
		observed := host.RuntimeStatus{}
		if s, e := host.ReadStatus(p); e == nil {
			state = s.State
			observed = s
			runtime = s
		}
		var manager any
		dir, e := local.ProjectDir(pr.Name)
		if e != nil {
			return e
		}
		if r, e := service.Load(filepath.Join(dir, "service"), pr.BackendID); e == nil {
			manager, _ = service.Show(cmd.Context(), r)
		}
		result := map[string]any{"project": pr.Name, "workspace": pr.Workspace, "profile": pr.Profile, "host_observation": state, "runtime": runtime, "service": manager, "mcp_live_probe": "NOT_PERFORMED; use connect check or doctor", "agent_identity": "UNKNOWN", "agent_tool_call_identity": "NOT_VERIFIED", "business_side_effects": false}
		if storage {
			result["storage_preview"] = storagePreview(p)
		}
		machine, _ := cmd.Flags().GetBool("json")
		if machine {
			return output(cmd, result)
		}
		_, e = fmt.Fprintf(cmd.OutOrStdout(), "Project: %s\nWorkspace: %s\nHost observation: %s\n", pr.Name, pr.Workspace, state)
		if e != nil {
			return e
		}
		if runtime != nil {
			b := observed.Budget
			_, e = fmt.Fprintf(cmd.OutOrStdout(), "Console: %s\nHost epoch: %s (PID %d)\nObserved: %s\nConnections: %d / %d\nRuns: %d active, %d / %d cumulative\nProtocol frames: %d / %d\nManagement authentications: %d / %d\nTool calls observed: %d (Agent identity UNKNOWN)\n", observed.Console, observed.Epoch, observed.PID, observed.Observed, b["consumer_connections"], b["consumer_connection_limit"], b["runs_active"], b["runs_total"], b["run_limit"], b["frames"], b["frame_limit"], b["management_nonces"], b["management_nonce_limit"], observed.ToolCalls)
			if e != nil {
				return e
			}
		}
		budgetWarning, captureWarning := false, false
		for _, warning := range observed.Warnings {
			label := "Budget warning"
			if strings.HasPrefix(warning, "CAPTURE_") {
				label = "Capture warning"
				captureWarning = true
			} else {
				budgetWarning = true
			}
			if _, e = fmt.Fprintf(cmd.OutOrStdout(), "%s: %s\n", label, warning); e != nil {
				return e
			}
		}
		if budgetWarning {
			if _, e = fmt.Fprintln(cmd.OutOrStdout(), "Close unused connections. Cumulative budgets require an explicit host restart and task resume; history is preserved."); e != nil {
				return e
			}
		}
		if captureWarning {
			if _, e = fmt.Fprintln(cmd.OutOrStdout(), "Inspect aevora capture status; pending events are retained."); e != nil {
				return e
			}
		}
		if storage {
			if e = output(cmd, result["storage_preview"]); e != nil {
				return e
			}
		}
		_, e = fmt.Fprintf(cmd.OutOrStdout(), "MCP probe: not performed by status.\nNext: aevora connect check --project %s --task TASK --client codex\n", pr.Name)
		return e
	}}
	command.Flags().BoolVar(&storage, "storage", false, "Read-only disk usage and preservation preview; no file contents or deletion")
	c.AddCommand(command)
}

func storagePreview(p host.Profile) map[string]any {
	files, bytes := 0, int64(0)
	limit := errors.New("bounded inventory")
	err := filepath.WalkDir(p.Session.Root, func(path string, entry fs.DirEntry, e error) error {
		if e != nil {
			return e
		}
		files++
		if files > 10000 {
			return limit
		}
		if entry.Type().IsRegular() {
			info, e := entry.Info()
			if e != nil {
				return e
			}
			bytes += info.Size()
		}
		return nil
	})
	database := int64(0)
	for _, suffix := range []string{"", "-wal", "-shm"} {
		if info, e := os.Lstat(p.Database.Path + suffix); e == nil && info.Mode().IsRegular() {
			database += info.Size()
		}
	}
	complete := "COMPLETE"
	if err != nil {
		complete = "PARTIAL_OR_UNAVAILABLE"
	}
	return map[string]any{"session_root": p.Session.Root, "session_bytes_observed": bytes, "entries_observed": files, "inventory": complete, "database_with_sidecars_bytes_observed": database, "measurement": "FILE_LENGTHS; LIVE_OBSERVATION_NOT_A_BACKUP", "cleanup_actions": []string{}, "preserve": []string{"database and sidecars", "original session and operation journals", "task bindings and evidence"}, "next_step": "Stop writers before a consistent backup or manual archival. No automatic deletion is offered."}
}
