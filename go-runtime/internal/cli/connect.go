package cli

import (
	"context"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/clientconfig"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/spf13/cobra"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"
)

func connectionBinding(project, task string) (local.Project, host.Profile, local.Task, clientconfig.Binding, error) {
	pr, p, e := selectedProject(project)
	if e != nil {
		return pr, p, local.Task{}, clientconfig.Binding{}, e
	}
	t, _, e := local.LoadTask(project, task)
	if e != nil {
		return pr, p, t, clientconfig.Binding{}, e
	}
	binary, e := os.Executable()
	if e != nil {
		return pr, p, t, clientconfig.Binding{}, e
	}
	binary, e = filepath.EvalSymlinks(binary)
	return pr, p, t, clientconfig.New(binary, p.Session.Root, t.Run), e
}
func codexHome(explicit string) string {
	if explicit != "" {
		return explicit
	}
	if h := os.Getenv("CODEX_HOME"); h != "" {
		return h
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".codex")
}
func addConnections(c *cobra.Command, project *string) {
	var task, client, binary, home string
	var apply, routeWorkspace bool
	cc := &cobra.Command{Use: "connect", Short: "Export or inspect a fixed task binding; no model is started"}
	cc.PersistentFlags().StringVar(&task, "task", "", "Existing task alias (no implicit Run authorization)")
	cc.PersistentFlags().StringVar(&client, "client", "codex", "codex or generic stdio export")
	cc.PersistentFlags().StringVar(&binary, "client-bin", "codex", "Official Codex executable or explicit path")
	cc.PersistentFlags().StringVar(&home, "client-home", "", "Explicit Codex config root; otherwise CODEX_HOME")
	cc.PersistentFlags().BoolVar(&routeWorkspace, "route-workspace", false, "Route automatic connections by their registered working directory")
	addConnectionMigration(cc, project, &home, &client)
	var automaticProposals bool
	var routeProjects []string
	auto := &cobra.Command{Use: "automatic", Short: "Use a fresh Host-measured Run for each ordinary client session", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		if client != "codex" {
			return errors.New("AEVORA_CLIENT_UNSUPPORTED")
		}
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		executable, e := os.Executable()
		if e != nil {
			return e
		}
		routes := []any{}
		seen := map[string]bool{pr.Name: true}
		if len(routeProjects) > 64 {
			return errors.New("AEVORA_AUTO_POLICY_CONFLICT")
		}
		for _, name := range routeProjects {
			if seen[name] {
				return errors.New("AEVORA_AUTO_POLICY_CONFLICT")
			}
			seen[name] = true
			other, err := local.Load(name)
			if err != nil || other.BackendID != pr.BackendID {
				return errors.New("AEVORA_PROJECT_NOT_AUTHORIZED")
			}
			routes = append(routes, map[string]any{"project": other.Name, "workspace": other.Workspace})
		}
		binding := clientconfig.Automatic(executable, p.Session.Root)
		if routeWorkspace || len(routes) > 0 {
			binding = clientconfig.AutomaticWorkspace(executable, p.Session.Root)
		}
		if !apply {
			return output(cmd, map[string]any{"status": "PREVIEW", "binding": binding, "project": pr.Name, "routes": routes, "fresh_task_per_session": true, "host_measured_context": true})
		}
		dir, e := local.ProjectDir(pr.Name)
		if e != nil {
			return e
		}
		state := filepath.Join(dir, "connections")
		if e = clientconfig.CheckInstructions(codexHome(home), state, false); e != nil {
			return e
		}
		policy := map[string]any{"project": pr.Name, "workspace": pr.Workspace, "proposals": automaticProposals}
		if len(routes) > 0 {
			policy["routes"] = routes
		}
		response, e := host.ManagementCall(cmd.Context(), p, "", "configure-automatic", policy)
		if e != nil {
			return e
		}
		if response["status"] != "COMPLETED" {
			return emitOperation(cmd, response)
		}
		result, e := clientconfig.Apply(codexHome(home), state, binding, false)
		if e != nil {
			return e
		}
		if e = clientconfig.ApplyInstructions(codexHome(home), state, false); e != nil {
			return e
		}
		return output(cmd, map[string]any{"status": result, "fresh_task_per_session": true, "context": "HOST_MEASURED", "client_reconnect_required": true, "legacy_tasks": "PRESERVED"})
	}}
	auto.Flags().BoolVar(&apply, "apply", false, "Apply the managed default connection and enrollment policy")
	auto.Flags().BoolVar(&automaticProposals, "enable-proposals", false, "Allow untrusted observations in automatically created tasks")
	auto.Flags().StringArrayVar(&routeProjects, "route-project", nil, "Add an explicitly authorized same-Host project (repeat for every route)")
	cc.AddCommand(auto)
	var revokeProject string
	var revokeApply bool
	revoke := &cobra.Command{Use: "revoke-route", Short: "Preview or remove an inactive automatic project route", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		_, profile, err := selectedProject(*project)
		if err != nil {
			return err
		}
		response, err := host.ManagementCall(cmd.Context(), profile, "", "automatic-route", map[string]any{"project": revokeProject, "apply": revokeApply})
		if err != nil {
			return err
		}
		return emitOperation(cmd, response)
	}}
	revoke.Flags().StringVar(&revokeProject, "route-project", "", "Additional project route to remove; the default route is protected")
	revoke.Flags().BoolVar(&revokeApply, "apply", false, "Remove only after all active automatic tasks on this route are closed")
	cc.AddCommand(revoke)
	cc.AddCommand(&cobra.Command{Use: "export", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		_, _, _, binding, e := connectionBinding(*project, task)
		if e != nil {
			return e
		}
		if client == "generic" {
			return output(cmd, binding)
		}
		if client != "codex" {
			return errors.New("AEVORA_CLIENT_UNSUPPORTED")
		}
		v, e := binding.TOML()
		if e == nil {
			_, e = cmd.OutOrStdout().Write([]byte(v))
		}
		return e
	}})
	cc.AddCommand(&cobra.Command{Use: "check", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		if client != "codex" {
			return errors.New("AEVORA_CLIENT_UNSUPPORTED")
		}
		_, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		var t local.Task
		var binding clientconfig.Binding
		if task == "" {
			exe, err := os.Executable()
			if err != nil {
				return err
			}
			binding = clientconfig.Automatic(exe, p.Session.Root)
			if routeWorkspace {
				binding = clientconfig.AutomaticWorkspace(exe, p.Session.Root)
			}
		} else {
			_, _, t, binding, e = connectionBinding(*project, task)
			if e != nil {
				return e
			}
		}
		path, e := exec.LookPath(binary)
		if e != nil {
			return errors.New("AEVORA_CLIENT_EXECUTABLE_REQUIRED")
		}
		config, e := clientconfig.Probe(cmd.Context(), path, binding, home)
		if e != nil {
			return e
		}
		ctx, cancel := context.WithTimeout(cmd.Context(), 5*time.Second)
		defer cancel()
		var probe map[string]any
		if task == "" {
			probe, e = host.ProbeAutomatic(ctx, p)
		} else {
			probe, e = host.ProbeRun(ctx, p, t.Run)
		}
		if e != nil {
			return e
		}
		result := map[string]any{"status": "MCP_READY", "client_config": config, "mcp": probe, "actual_agent_tool_call": "NOT_PROVEN"}
		if task == "" {
			result["connection_mode"] = "AUTOMATIC_MEASURED_TASK"
		} else {
			result["run_id"] = t.Run
		}
		return output(cmd, result)
	}})
	edit := func(remove bool) *cobra.Command {
		use := "apply"
		if remove {
			use = "remove"
		}
		v := &cobra.Command{Use: use, Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
			if client != "codex" {
				return errors.New("AEVORA_CLIENT_UNSUPPORTED")
			}
			var pr local.Project
			var binding clientconfig.Binding
			var e error
			if remove && task == "" {
				var p host.Profile
				pr, p, e = selectedProject(*project)
				if e == nil {
					var exe string
					exe, e = os.Executable()
					binding = clientconfig.Automatic(exe, p.Session.Root)
				}
			} else {
				pr, _, _, binding, e = connectionBinding(*project, task)
			}
			if e != nil {
				return e
			}
			if !apply {
				return output(cmd, map[string]any{"status": "PREVIEW", "target": filepath.Join(codexHome(home), "config.toml"), "binding": binding, "remove": remove, "workflow_instructions": filepath.Join(codexHome(home), "AGENTS.md"), "next_step": "Use --apply to manage the Aevora MCP entry and automatic-use instructions; unrelated user bytes remain intact. Reconnect afterward."})
			}
			dir, e := local.ProjectDir(pr.Name)
			if e != nil {
				return e
			}
			state := filepath.Join(dir, "connections")
			if e = clientconfig.CheckInstructions(codexHome(home), state, remove); e != nil {
				return e
			}
			result, e := clientconfig.Apply(codexHome(home), state, binding, remove)
			if e != nil {
				return e
			}
			if e = clientconfig.ApplyInstructions(codexHome(home), state, remove); e != nil {
				return e
			}
			return output(cmd, map[string]any{"status": result, "target": filepath.Join(codexHome(home), "config.toml"), "workflow_instructions": filepath.Join(codexHome(home), "AGENTS.md"), "client_reconnect_required": true})
		}}
		v.Flags().BoolVar(&apply, "apply", false, "Explicitly apply this local client config edit")
		return v
	}
	cc.AddCommand(edit(false), edit(true))
	c.AddCommand(cc)
	// Task run calls the official CLI with only a scoped MCP table override.
	taskCmd, _, _ := c.Find([]string{"task"})
	var name string
	var proposals bool
	run := &cobra.Command{Use: "run [-- CODEX_ARGS...]", Short: "Authorize a task and start the user's official Codex CLI", Args: cobra.ArbitraryArgs, RunE: func(cmd *cobra.Command, args []string) error {
		if client != "codex" {
			return errors.New("AEVORA_CLIENT_UNSUPPORTED")
		}
		if clientconfig.OverridesBinding(args) {
			return errors.New("AEVORA_CLIENT_BINDING_OVERRIDE_DENIED")
		}
		if e := inferProject(cmd, project); e != nil {
			return e
		}
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		path, e := exec.LookPath(binary)
		if e != nil {
			return errors.New("AEVORA_CLIENT_EXECUTABLE_REQUIRED")
		}
		t, e := newProjectTask(cmd, pr, p, name, proposals)
		if e != nil {
			return e
		}
		if e = authorizeTask(cmd, t, p); e != nil {
			return e
		}
		_, _, _, binding, e := connectionBinding(*project, t.Name)
		if e != nil {
			return e
		}
		if _, e = clientconfig.Probe(cmd.Context(), path, binding, home); e != nil {
			local.SetState(t, "INTERRUPTED", "")
			closeTaskChannel(cmd, p, t)
			return e
		}
		runCtx, stop := signal.NotifyContext(cmd.Context(), os.Interrupt, syscall.SIGTERM)
		defer stop()
		child := exec.CommandContext(runCtx, path, append([]string{"-c", binding.Override(), "-C", pr.Workspace}, args...)...)
		child.Stdin = cmd.InOrStdin()
		child.Stdout = cmd.OutOrStdout()
		child.Stderr = cmd.ErrOrStderr()
		child.Env = os.Environ()
		if home != "" {
			child.Env = append(child.Env, "CODEX_HOME="+home)
		}
		e = child.Run()
		state := "CLIENT_EXITED"
		if e != nil {
			state = "INTERRUPTED"
		}
		local.SetState(t, state, "")
		closeErr := closeTaskChannel(cmd, p, t)
		if e != nil {
			return errors.New("AEVORA_CLIENT_EXITED_UNSUCCESSFULLY")
		}
		return closeErr
	}}
	run.Flags().StringVar(&name, "name", "", "New task alias")
	run.Flags().StringVar(&client, "client", "codex", "Official client")
	run.Flags().StringVar(&binary, "client-bin", "codex", "Official Codex executable")
	run.Flags().StringVar(&home, "client-home", "", "Explicit CODEX_HOME without copying credentials")
	run.Flags().BoolVar(&proposals, "enable-proposals", false, "Allow untrusted proposals for this task")
	taskCmd.AddCommand(run)
}
func closeTaskChannel(cmd *cobra.Command, p host.Profile, t local.Task) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	v, e := host.ManagementCall(ctx, p, t.Run, "close-run", map[string]any{})
	if e != nil {
		return e
	}
	if v["status"] != "COMPLETED" {
		return errors.New("AEVORA_TASK_CLOSE_UNKNOWN")
	}
	return nil
}
