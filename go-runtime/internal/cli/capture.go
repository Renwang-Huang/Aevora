package cli

import (
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/capture"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/clientconfig"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/spf13/cobra"
	"io"
	"os"
	"path/filepath"
)

func addCapture(c *cobra.Command, project *string) {
	command := &cobra.Command{Use: "capture", Short: "Capture bounded untrusted local Codex diagnostics"}
	var root string
	hook := &cobra.Command{Use: "hook", Short: "Accept a Codex PostToolUse event from stdin", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		reason := "INVALID_INPUT"
		raw, err := io.ReadAll(io.LimitReader(cmd.InOrStdin(), capture.MaxInput+1))
		if err == nil && len(raw) > capture.MaxInput {
			err = capture.ErrInvalid
		}
		if err == nil {
			var event capture.Event
			event, reason, err = capture.ClassifyHookForRoot(root, raw)
			if err == nil && reason == "SIGNAL" {
				var created bool
				created, err = capture.Enqueue(root, event)
				if err == nil {
					reason = "ALREADY_QUEUED"
					if created {
						reason = "QUEUED"
					}
				} else {
					reason = "QUEUE_UNAVAILABLE"
					if errors.Is(err, capture.ErrFull) {
						reason = "QUEUE_FULL"
					}
				}
			}
		}
		response := map[string]any{}
		callbackErr := capture.RecordCallback(root, reason)
		if callbackErr != nil && err == nil {
			response["systemMessage"] = "Aevora could not save handler status; inspect capture status. The tool result is unchanged."
		}
		if err != nil {
			code := "AEVORA_CAPTURE_UNAVAILABLE"
			if errors.Is(err, capture.ErrInvalid) {
				code = "AEVORA_CAPTURE_INVALID"
			}
			if errors.Is(err, capture.ErrFull) {
				code = "AEVORA_CAPTURE_OUTBOX_FULL"
			}
			// PostToolUse exit code 2 replaces the original tool result. A
			// capture failure is advisory and must never alter that result.
			response["systemMessage"] = "Aevora could not queue this diagnostic (" + code + "). Inspect capture status; the tool result is unchanged."
		}
		return json.NewEncoder(cmd.OutOrStdout()).Encode(response)
	}}
	hook.Flags().StringVar(&root, "session-root", "", "Protected Host session root for the private outbox")
	command.AddCommand(hook)
	var clientHome, binary string
	var apply bool
	configure := func(remove bool) *cobra.Command {
		name := "install"
		if remove {
			name = "remove"
		}
		return &cobra.Command{Use: name, Short: "Preview or apply the owned Codex hook definition", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
			pr, profile, err := selectedProject(*project)
			if err != nil {
				return err
			}
			exe := binary
			if exe == "" {
				exe, err = os.Executable()
				if err != nil {
					return err
				}
			}
			raw, err := clientconfig.CaptureHook(exe, profile.Session.Root)
			if err != nil {
				return err
			}
			home := codexHome(clientHome)
			var definition map[string]any
			if err = json.Unmarshal(raw, &definition); err != nil {
				return err
			}
			if !apply {
				return output(cmd, map[string]any{"status": "PREVIEW", "action": name, "path": filepath.Join(home, "hooks.json"), "definition": definition, "trust": "REVIEW_REQUIRED", "hook_execution": "NOT_VERIFIED"})
			}
			dir, err := local.ProjectDir(pr.Name)
			if err != nil {
				return err
			}
			state := filepath.Join(dir, "connections")
			status := ""
			if remove {
				status, err = clientconfig.RemoveCaptureHook(home, state, raw)
			} else {
				status, err = clientconfig.InstallCaptureHook(home, state, raw)
			}
			if err != nil {
				return err
			}
			return output(cmd, map[string]any{"status": status, "trust": "REVIEW_REQUIRED", "hook_execution": "NOT_VERIFIED", "raw_tool_content": "NOT_STORED"})
		}}
	}
	for _, remove := range []bool{false, true} {
		setup := configure(remove)
		setup.Flags().StringVar(&clientHome, "client-home", "", "Codex configuration root; otherwise CODEX_HOME")
		setup.Flags().StringVar(&binary, "binary", "", "Absolute stable Aevora executable path; otherwise current executable")
		setup.Flags().BoolVar(&apply, "apply", false, "Apply the displayed action without replacing other hook files")
		command.AddCommand(setup)
	}
	var statusHome string
	statusCommand := &cobra.Command{Use: "status", Short: "Inspect callback evidence, managed configuration and retained work", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, err := selectedProject(*project)
		if err != nil {
			return err
		}
		scan, err := capture.Scan(p.Session.Root, 128)
		if err != nil {
			return err
		}
		result := map[string]any{"pending": scan.Pending, "invalid_observed": scan.Invalid, "scanned": scan.Scanned, "source": "HOOK_EXECUTION_NOT_VERIFIED", "raw_hook_content": "NOT_STORED", "authority": "UNTRUSTED"}
		result["batch_limited"] = scan.Limited
		callback, e := capture.ReadCallback(p.Session.Root)
		if e != nil {
			callback = map[string]any{"status": "CALLBACK_STATE_UNAVAILABLE"}
		}
		result["callback"] = callback
		count, e := capture.QuarantineCount(p.Session.Root)
		if e == nil {
			result["quarantined"] = count
		} else {
			result["quarantine_status"] = "UNAVAILABLE"
		}
		dir, e := local.ProjectDir(pr.Name)
		if e != nil {
			return e
		}
		result["configuration"] = clientconfig.InspectCaptureHook(codexHome(statusHome), filepath.Join(dir, "connections"))
		result["codex_trust"] = "UNKNOWN_REVIEW_IN_CODEX"
		result["callback_scope"] = "SHARED_HOST; PRODUCER_AND_CLIENT_HOME_NOT_AUTHENTICATED"
		if status, err := host.ReadStatus(p); err == nil {
			result["host_capture"] = status.Capture
		} else {
			result["host_capture"] = "HOST_NOT_OBSERVED"
		}
		return output(cmd, result)
	}}
	statusCommand.Flags().StringVar(&statusHome, "client-home", "", "Inspect a specific Codex configuration root")
	command.AddCommand(statusCommand)
	var sourceCandidate, sourceAfter string
	var sourceLimit int
	sources := &cobra.Command{Use: "sources", Short: "Read bounded immutable source references for one capture candidate", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		_, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		response, e := trustedCall(cmd.Context(), p, "", "capture-sources", map[string]any{"candidate_id": sourceCandidate, "after": sourceAfter, "limit": sourceLimit})
		if e != nil {
			return e
		}
		return emitOperation(cmd, response)
	}}
	sources.Flags().StringVar(&sourceCandidate, "candidate", "", "Actual capture candidate identity")
	sources.Flags().StringVar(&sourceAfter, "after", "", "Source identity returned as next_cursor")
	sources.Flags().IntVar(&sourceLimit, "limit", 10, "Maximum sources per page (1..50)")
	command.AddCommand(sources)
	for _, restore := range []bool{false, true} {
		var eventID string
		var moveApply bool
		name := "quarantine"
		if restore {
			name = "restore"
		}
		move := &cobra.Command{Use: name, Short: "Preview or reversibly move one retained event", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
			_, p, e := selectedProject(*project)
			if e != nil {
				return e
			}
			if !captureformat.IsDigest(eventID) {
				return capture.ErrInvalid
			}
			if !moveApply {
				return output(cmd, map[string]any{"status": "PREVIEW", "action": name, "event_id": eventID, "contents": "NOT_DISPLAYED"})
			}
			if e = capture.MoveRecord(p.Session.Root, eventID, restore); e != nil {
				return e
			}
			return output(cmd, map[string]any{"status": "MOVED", "action": name, "event_id": eventID, "data": "PRESERVED"})
		}}
		move.Flags().StringVar(&eventID, "event", "", "Exact retained event identity")
		move.Flags().BoolVar(&moveApply, "apply", false, "Move this record; retained contents are not deleted")
		command.AddCommand(move)
	}
	var resetApply bool
	reset := &cobra.Command{Use: "reset-cursor", Short: "Preserve the old scan cursor and reset restart progress", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		_, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		if !resetApply {
			return output(cmd, map[string]any{"status": "PREVIEW", "event_data": "PRESERVED", "next": "Applies to the next Host restart; an invalid cursor can recover on the next scan"})
		}
		if e = capture.ResetCursor(p.Session.Root); e != nil {
			return e
		}
		return output(cmd, map[string]any{"status": "CURSOR_RESET", "previous_cursor": "PRESERVED", "event_data": "UNCHANGED"})
	}}
	reset.Flags().BoolVar(&resetApply, "apply", false, "Reset scan progress while preserving the previous cursor")
	command.AddCommand(reset)
	c.AddCommand(command)
}
