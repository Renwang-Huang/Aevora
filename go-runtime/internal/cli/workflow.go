package cli

import (
	"encoding/json"
	"errors"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/spf13/cobra"
	"io"
	"os"
	"path/filepath"
	"strings"
)

func selectedProject(name string) (local.Project, host.Profile, error) {
	p, e := local.Load(name)
	if e != nil {
		if os.IsNotExist(e) {
			e = errors.New("AEVORA_PROJECT_NOT_REGISTERED")
		}
		return p, host.Profile{}, e
	}
	profile, e := host.Load(p.Profile)
	if e == nil {
		id := host.BackendID(profile)
		if id == "" {
			e = errors.New("AEVORA_PROJECT_BACKEND_UNAVAILABLE")
		} else if id != p.BackendID {
			e = errors.New("AEVORA_PROJECT_BACKEND_CHANGED")
		}
	}
	return p, profile, e
}
func output(cmd *cobra.Command, v any) error {
	machine, _ := cmd.Flags().GetBool("json")
	if machine {
		return json.NewEncoder(cmd.OutOrStdout()).Encode(v)
	}
	switch x := v.(type) {
	case local.Project:
		_, e := fmt.Fprintf(cmd.OutOrStdout(), "Project: %s\nWorkspace: %s\nProfile: %s\nNext: aevora host start --project %s --background\n", x.Name, x.Workspace, x.Profile, x.Name)
		return e
	case []local.Project:
		for _, p := range x {
			if _, e := fmt.Fprintf(cmd.OutOrStdout(), "%s\t%s\n", p.Name, p.Workspace); e != nil {
				return e
			}
		}
		return nil
	}
	raw, e := json.MarshalIndent(v, "", "  ")
	if e != nil {
		return e
	}
	_, e = fmt.Fprintln(cmd.OutOrStdout(), string(raw))
	return e
}
func authorizeTask(cmd *cobra.Command, t local.Task, p host.Profile) error {
	a, e := codec.Normalize(t.Facts)
	if e != nil {
		return e
	}
	b, e := codec.Normalize(p.Session.Facts)
	if e != nil {
		return e
	}
	if len(t.Context) > 0 {
		observation, err := collectContext(cmd, p)
		if err != nil {
			return err
		}
		var old map[string]any
		if json.Unmarshal(t.Facts, &old) != nil {
			return local.ErrInvalid
		}
		if _, measured := old["target_project"]; measured {
			pr, err := local.Load(t.Project)
			if err != nil {
				return err
			}
			observation, err = local.ObserveProject(cmd.Context(), pr, observation)
			if err != nil {
				return err
			}
		}
		b, err = codec.Canonical(observation["facts"])
		if err != nil {
			return err
		}
	}
	if string(a) != string(b) {
		return errors.New("AEVORA_RUN_CONTEXT_CONFLICT")
	}
	if e := local.SetState(t, "AUTHORIZATION_UNKNOWN", ""); e != nil {
		return e
	}
	response, e := host.ManagementCall(cmd.Context(), p, t.Run, "open-run", map[string]any{"public_context": t.Facts, "enable_proposals": t.Proposals})
	if e != nil {
		return e
	}
	id, _ := response["operation_id"].(string)
	if response["status"] != "COMPLETED" {
		state := "FAILED"
		if response["status"] == "UNKNOWN" {
			state = "AUTHORIZATION_UNKNOWN"
		}
		local.SetState(t, state, id)
		return &operationError{response["status"].(string), id, response["code"].(string)}
	}
	return local.SetState(t, "AUTHORIZED", id)
}
func addWorkflow(c *cobra.Command, profilePath, project *string) {
	addUpgrade(c, project)
	addContextCommands(c, project)
	addCapture(c, project)
	addMemory(c, project)
	c.PersistentFlags().StringVar(project, "project", "", "Explicit locally registered project; --config takes precedence")
	var machine bool
	c.PersistentFlags().BoolVar(&machine, "json", false, "Machine-readable local workflow output; legacy JSON contracts unchanged")
	c.PersistentPreRunE = func(cmd *cobra.Command, _ []string) error {
		// Diagnosis and explicit recovery must remain reachable when ordinary
		// project operations correctly fail closed on a changed backend.
		if cmd.Parent() != nil && cmd.Parent().Name() == "project" && (cmd.Name() == "inspect" || cmd.Name() == "recover") {
			return nil
		}
		if *project != "" {
			p, _, e := selectedProject(*project)
			if e != nil {
				return e
			}
			if *profilePath == "" {
				*profilePath = p.Profile
			} else if filepath.Clean(*profilePath) != filepath.Clean(p.Profile) {
				parts := strings.Fields(cmd.CommandPath())
				if len(parts) > 1 {
					switch parts[1] {
					case "project", "task", "connect", "host", "status":
						return errors.New("AEVORA_PROJECT_CONFIG_CONFLICT")
					}
				}
			}
		}
		return nil
	}
	pc := &cobra.Command{Use: "project", Short: "Register and select local projects without moving their data"}
	var name, workspace, facts string
	var proposals bool
	pc.PersistentFlags().StringVar(&name, "name", "", "Local project alias")
	pc.PersistentFlags().StringVar(&workspace, "workspace", "", "Absolute workspace directory")
	addProjectRecovery(pc, &name, project, profilePath)
	pc.AddCommand(&cobra.Command{Use: "list", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		v, e := local.Projects()
		if e != nil {
			return e
		}
		return output(cmd, v)
	}})
	register := func(cmd *cobra.Command) error {
		if *profilePath == "" {
			return errors.New("HOST_CONFIG_REQUIRED")
		}
		p, e := host.Load(*profilePath)
		if e != nil {
			return e
		}
		if p.Database.Kind != "sqlite" {
			return errors.New("AEVORA_NATIVE_CONFIG_REQUIRED")
		}
		if !filepath.IsAbs(workspace) {
			return local.ErrInvalid
		}
		real, e := filepath.EvalSymlinks(workspace)
		if e != nil {
			return e
		}
		info, e := os.Stat(real)
		if e != nil || !info.IsDir() {
			return local.ErrInvalid
		}
		v := local.Project{Schema: "aevora.local-project/1", Name: name, Workspace: real, Profile: *profilePath, BackendID: host.BackendID(p)}
		if e = local.Register(v); e != nil {
			return e
		}
		return output(cmd, v)
	}
	pc.AddCommand(&cobra.Command{Use: "register", Short: "Bind an existing native profile to a workspace", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error { return register(cmd) }})
	init := &cobra.Command{Use: "init", Short: "Create and register a private native project", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		dir, e := local.ProjectDir(name)
		if e != nil {
			return e
		}
		if *profilePath != "" {
			return errors.New("AEVORA_REGISTER_EXISTING_PROFILE")
		}
		*profilePath = filepath.Join(dir, "host.json")
		inner := Command(native.Factory())
		inner.SetArgs([]string{"--config", *profilePath, "init", "--data-dir", filepath.Join(dir, "data"), "--facts", facts})
		inner.SetOut(io.Discard)
		inner.SetErr(cmd.ErrOrStderr())
		if e = inner.ExecuteContext(cmd.Context()); e != nil {
			return e
		}
		return register(cmd)
	}}
	init.Flags().StringVar(&facts, "facts", "{}", "Trusted public facts; unknown stays unknown")
	pc.AddCommand(init)
	c.AddCommand(pc)
	tc := &cobra.Command{Use: "task", Short: "Bind an explicitly authorized local task to its immutable Run"}
	var taskName string
	tc.PersistentFlags().StringVar(&taskName, "name", "", "Task alias in the selected project")
	tc.PersistentFlags().BoolVar(&proposals, "enable-proposals", false, "Allow untrusted proposals for this task")
	tc.AddCommand(&cobra.Command{Use: "list", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		v, e := local.Tasks(*project)
		if e != nil {
			return e
		}
		return output(cmd, v)
	}})
	taskNew := func(cmd *cobra.Command) error {
		if e := inferProject(cmd, project); e != nil {
			return e
		}
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		t, e := newProjectTask(cmd, pr, p, taskName, proposals)
		if e != nil {
			return e
		}
		if e = authorizeTask(cmd, t, p); e != nil {
			return e
		}
		return output(cmd, map[string]any{"status": "AUTHORIZED", "task": t, "next_step": "Use connect export or task run to bind a client; no model was started."})
	}
	tc.AddCommand(&cobra.Command{Use: "new", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error { return taskNew(cmd) }})
	for _, action := range []string{"resume", "close"} {
		tc.AddCommand(&cobra.Command{Use: action, Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
			_, p, e := selectedProject(*project)
			if e != nil {
				return e
			}
			t, _, e := local.LoadTask(*project, taskName)
			if e != nil {
				return e
			}
			if action == "resume" {
				if e = authorizeTask(cmd, t, p); e != nil {
					return e
				}
				return output(cmd, map[string]any{"status": "AUTHORIZED", "task": t})
			}
			v, e := host.ManagementCall(cmd.Context(), p, t.Run, "close-run", map[string]any{})
			if e != nil {
				return e
			}
			if v["status"] != "COMPLETED" {
				return emitOperation(cmd, v)
			}
			if e = local.SetState(t, "CLOSED", ""); e != nil {
				return e
			}
			return output(cmd, map[string]any{"status": "CLOSED", "run_id": t.Run, "history": "PRESERVED"})
		}})
	}
	c.AddCommand(tc)
	addConnections(c, project)
	addHostCommands(c, project)
	addStatus(c, project)
}
