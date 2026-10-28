package cli

import (
	"github.com/spf13/cobra"
	"strings"
)

func workflowCommand(c *cobra.Command, args []string) bool {
	cmd, _, e := c.Find(args)
	if e != nil || cmd == nil {
		return false
	}
	p := strings.Fields(cmd.CommandPath())
	if len(p) < 2 {
		return false
	}
	switch p[1] {
	case "project", "task", "connect", "host", "status", "context", "candidate", "capture":
		return true
	}
	return false
}
func advice(code string) string {
	switch code {
	case "AEVORA_PROJECT_AMBIGUOUS":
		return "Several aliases select the same workspace. Choose --project NAME explicitly; no implicit project was authorized."
	case "AEVORA_PROJECT_NOT_REGISTERED":
		return "Run aevora project list, or project register --name NAME --workspace PATH --config PROFILE."
	case "AEVORA_LOCAL_BINDING_INVALID":
		return "Use a simple project/task name and absolute paths; preserve existing bindings."
	case "AEVORA_PROJECT_BACKEND_CHANGED":
		return "Run project inspect --name NAME. Preserve the original binding; project recover verifies a pinned backup into a new alias with fresh authorization."
	case "AEVORA_PROJECT_BACKEND_UNAVAILABLE":
		return "Run project inspect --name NAME; check database availability and private-file permissions. Unavailable identity does not establish that the backend was replaced."
	case "AEVORA_PROJECT_CONFIG_CONFLICT":
		return "Use the selected project's registered profile; omit --config or select the matching project. Legacy --config commands retain explicit profile precedence."
	case "AEVORA_USER_SERVICE_UNAVAILABLE":
		return "Check systemctl --user status. Without a user service manager, run aevora host start --project NAME in a terminal."
	case "AEVORA_SERVICE_CONFIGURATION_CONFLICT":
		return "Inspect the existing owned service. Stop/remove that service before registering another executable or profile."
	case "AEVORA_HOST_READINESS_TIMEOUT":
		return "Run aevora status --project NAME and host status --project NAME; inspect the owned unit with journalctl --user -u UNIT. Do not reset the database."
	case "AEVORA_CLIENT_CONFIG_CONFLICT":
		return "A client entry was changed or is not managed by Aevora. Use connect export and review that entry manually."
	case "AEVORA_CLIENT_MIGRATION_INCOMPLETE":
		return "Preserve external edits and inspect the migration journal. Retry the exact migrate command to reconcile owned blocks, or preview --undo. Run grants were not transferred."
	case "AEVORA_CLIENT_CONFIG_CHECK_FAILED", "AEVORA_CLIENT_EXECUTABLE_REQUIRED":
		return "Select the official Codex executable with --client-bin PATH and the intended --client-home PATH; no model is required for connect check."
	case "AEVORA_CAPTURE_HOOK_CONFLICT", "AEVORA_CAPTURE_HOOK_RECEIPT_FAILED":
		return "Preserve the existing hooks.json and inspect the capture install preview and its ownership receipt; no existing hook was overwritten."
	case "AEVORA_CAPTURE_INVALID", "AEVORA_CAPTURE_OUTBOX_FULL", "AEVORA_CAPTURE_RECOVERY_CONFLICT":
		return "Inspect capture status. Quarantine one exact retained event only after review; restore never replaces an existing record. Preserve the original data."
	case "AEVORA_ROUTE_IN_USE":
		return "Preview the route, close its listed automatic tasks, then retry the explicit revoke. Task history is preserved."
	case "AEVORA_ROUTE_NOT_REMOVABLE":
		return "Only an existing additional route can be revoked; the default project route is protected."
	case "AEVORA_RUN_CONTEXT_CONFLICT":
		return "Keep this task's original facts and capabilities, or create a new task name."
	case "AEVORA_HOST_UNAVAILABLE", "SESSION_NOT_STARTED", "AEVORA_GRANT_UNAVAILABLE":
		return "Start the project's Host, then explicitly task resume --project NAME --name TASK. Reconnect the client; do not retry an unknown tool operation."
	case "AEVORA_AUDIT_LIMIT":
		return "Preserve and archive the full journal. Explicitly restart the Host and resume only authorized tasks; never truncate original audit evidence."
	case "AEVORA_RUN_LIMIT":
		return "The Host has reached its cumulative Run limit. Close tasks and explicitly host restart, then resume only the tasks you authorize."
	case "AEVORA_TASK_NOT_FOUND":
		return "Run aevora task list --project NAME, or create a new task with task new --name TASK."
	default:
		return "Preserve this task and operation identity. Check aevora status and the local workflow guide before changing data."
	}
}
