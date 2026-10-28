package cli

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/taskcapture"
	"github.com/google/uuid"
	"github.com/spf13/cobra"
)

// A child result has already been reported by the child. Do not replace its
// exit code with a generic CLI error or expose its argv through an ExecError.
type checkExit struct{ code int }

func (e *checkExit) Error() string { return "AEVORA_LOCAL_CHECK_EXIT" }

func addRunCheck(command *cobra.Command, project *string) {
	var task, session string
	run := &cobra.Command{
		Use:   "run-check --task LABEL [--session LABEL] -- COMMAND [ARGS...]",
		Short: "Run an explicit local test check and queue its bounded untrusted result",
		Args:  cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			// This entry never interprets shell source. A shell, pipeline or unknown
			// check family must use its own integration rather than an inferred PASS.
			if cmd.ArgsLenAtDash() != 0 || taskcapture.CheckAction(args) == "COMMAND" {
				return domain.ErrInvalid
			}
			pr, p, err := selectedProject(*project)
			if err != nil {
				return err
			}
			if p.Database.Kind != "sqlite" {
				return domain.ErrInvalid
			}
			event := domain.Map{"schema_version": domain.TaskEventVersion, "project": pr.Name, "task_ref": task, "session_ref": session, "turn_ref": "check-" + uuid.NewString(), "item_ref": "local-check", "kind": "CHECK", "status": "UNKNOWN", "action": taskcapture.CheckAction(args), "summary": "Explicit local check; result unknown", "exit_code": nil, "occurred_at": nil, "revision": nil}
			if err = domain.ValidateTaskEvent(event); err != nil {
				return err // Invalid public labels must never start a process.
			}
			ctx, stop := signal.NotifyContext(cmd.Context(), os.Interrupt, syscall.SIGTERM)
			defer stop()
			child := exec.CommandContext(ctx, args[0], args[1:]...)
			child.Dir = pr.Workspace
			child.Stdin, child.Stdout, child.Stderr = cmd.InOrStdin(), cmd.OutOrStdout(), cmd.ErrOrStderr()
			child.WaitDelay = 2 * time.Second
			err = child.Run()
			code := 0
			switch {
			case err == nil:
				event["status"], event["exit_code"] = "COMPLETED", 0
			case ctx.Err() != nil:
				code = 130 // Interruption is UNKNOWN, never a successful check.
			default:
				var exit *exec.ExitError
				if errors.As(err, &exit) && exit.ExitCode() >= 1 && exit.ExitCode() <= 255 {
					code = exit.ExitCode()
					event["status"], event["exit_code"] = "FAILED", code
				} else {
					code = 2 // Not started, signalled or output delivery incomplete.
				}
			}
			event["occurred_at"] = time.Now().UTC().Format(time.RFC3339Nano)
			event["summary"] = fmt.Sprintf("Explicit local check %s %s; output not retained; not an independent verification", event["action"], event["status"])
			state := "QUEUED_UNTRUSTED"
			if err = taskcapture.Enqueue(p.Session.Root, event); err != nil {
				state = "CAPTURE_FAILED"
			}
			// Capture cannot turn a failing check into success or change its code.
			receipt := domain.Map{"schema_version": "aevora.local-check-capture/1", "observed_at": event["occurred_at"], "status": state, "project": pr.Name, "task_ref": task, "source_id": domain.TaskSourceID(event), "check_status": event["status"], "exit_code": event["exit_code"], "authority": "UNTRUSTED_LOCAL_CHECK; NOT_INDEPENDENT_OUTCOME"}
			raw, _ := json.Marshal(receipt)
			if platform.Atomic(filepath.Join(p.Session.Root, "local-check-status.json"), raw) != nil {
				fmt.Fprintln(cmd.ErrOrStderr(), "Aevora local check status could not be saved; inspect the capture receipt and queue.")
			}
			fmt.Fprintf(cmd.ErrOrStderr(), "\nAevora check capture: %s\n", raw)
			if code != 0 {
				return &checkExit{code}
			}
			return nil
		},
	}
	run.Flags().StringVar(&task, "task", "", "Public task label; do not put paths or credentials here")
	run.Flags().StringVar(&session, "session", "local-checks", "Public episode label; reuse to associate checks for this task")
	command.AddCommand(run)
}
