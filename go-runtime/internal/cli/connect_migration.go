package cli

import (
	"errors"
	"os"
	"path/filepath"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/clientconfig"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/spf13/cobra"
)

func addConnectionMigration(cc *cobra.Command, project, home, client *string) {
	var from string
	var apply, undo, proposals, workspace bool
	var routes []string
	m := &cobra.Command{Use: "migrate", Short: "Preview or migrate an owned client binding with resumable public receipts", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		if *client != "codex" {
			return errors.New("AEVORA_CLIENT_UNSUPPORTED")
		}
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		source, e := local.Load(from)
		if e != nil {
			return e
		}
		if source.Name == pr.Name {
			return local.ErrInvalid
		}
		old, e := host.Load(source.Profile)
		if e != nil {
			return e
		}
		exe, e := os.Executable()
		if e != nil {
			return e
		}
		exe, e = filepath.EvalSymlinks(exe)
		if e != nil {
			return e
		}
		binding := clientconfig.Automatic(exe, p.Session.Root)
		if workspace || len(routes) > 0 {
			binding = clientconfig.AutomaticWorkspace(exe, p.Session.Root)
		}
		oldState := filepath.Join(local.Home(), "projects", source.Name, "connections")
		newState := filepath.Join(local.Home(), "projects", pr.Name, "connections")
		preview, e := clientconfig.Migrate(codexHome(*home), oldState, newState, old.Session.Root, binding, false, undo)
		if e != nil {
			return e
		}
		allowed := []any{}
		seen := map[string]bool{pr.Name: true}
		if len(routes) > 64 {
			return local.ErrInvalid
		}
		for _, name := range routes {
			other, e := local.Load(name)
			if e != nil || seen[name] || other.BackendID != pr.BackendID {
				return errors.New("AEVORA_PROJECT_NOT_AUTHORIZED")
			}
			seen[name] = true
			allowed = append(allowed, map[string]any{"project": other.Name, "workspace": other.Workspace})
		}
		if !apply {
			return output(cmd, map[string]any{"status": "PREVIEW", "migration": preview, "from_project": source.Name, "project": pr.Name, "business_side_effects": false, "undo": undo, "enable_proposals": proposals, "routes": allowed})
		}
		if !undo {
			policy := map[string]any{"project": pr.Name, "workspace": pr.Workspace, "proposals": proposals}
			if len(allowed) > 0 {
				policy["routes"] = allowed
			}
			response, e := host.ManagementCall(cmd.Context(), p, "", "configure-automatic", policy)
			if e != nil {
				return e
			}
			if response["status"] != "COMPLETED" {
				return emitOperation(cmd, response)
			}
		}
		result, e := clientconfig.Migrate(codexHome(*home), oldState, newState, old.Session.Root, binding, true, undo)
		if e != nil {
			return e
		}
		return output(cmd, map[string]any{"status": result.Status, "migration": result, "from_project": source.Name, "project": pr.Name, "old_tasks": "PRESERVED_NOT_REAUTHORIZED", "undo_scope": "CLIENT_BLOCK_AND_PUBLIC_RECEIPT_OWNERSHIP_ONLY; HOST_POLICY_NOT_REVOKED", "next_step": "Reconnect the client. Retry this exact command to reconcile a partial migration; --undo --apply restores the old owned block without resuming old tasks."})
	}}
	m.Flags().StringVar(&from, "from-project", "", "Original owner; its backend need not be available")
	m.Flags().BoolVar(&apply, "apply", false, "Apply the reviewed migration; default is read-only preview")
	m.Flags().BoolVar(&undo, "undo", false, "Restore the prior owned client block; no Run is authorized")
	m.Flags().BoolVar(&proposals, "enable-proposals", false, "Explicitly allow untrusted proposals on the destination Host")
	m.Flags().BoolVar(&workspace, "route-workspace", false, "Use the registered workspace routing policy")
	m.Flags().StringArrayVar(&routes, "route-project", nil, "Explicit same-Host route (repeat)")
	cc.AddCommand(m)
}
