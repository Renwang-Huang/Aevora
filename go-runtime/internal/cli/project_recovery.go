package cli

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"strconv"

	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/google/uuid"
	"github.com/spf13/cobra"
)

// Recovery reuses the verified backup importer. A physical identity change is
// not evidence that a database is the original enrollment. Never rewrite its
// binding, copy session authority, resume tasks, or reuse standing policies.
func addProjectRecovery(pc *cobra.Command, name, selected, profilePath *string) {
	choose := func() (local.Project, error) {
		n := *name
		if n == "" {
			n = *selected
		} else if *selected != "" && n != *selected {
			return local.Project{}, errors.New("AEVORA_PROJECT_CONFIG_CONFLICT")
		}
		pr, e := local.Load(n)
		if e == nil && *profilePath != "" && filepath.Clean(*profilePath) != filepath.Clean(pr.Profile) {
			return pr, errors.New("AEVORA_PROJECT_CONFIG_CONFLICT")
		}
		return pr, e
	}
	pc.AddCommand(&cobra.Command{Use: "inspect", Short: "Diagnose a binding without authorizing its current database", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, e := choose()
		if e != nil {
			return e
		}
		state, code, observed := "PROFILE_UNAVAILABLE", "HOST_CONFIG_REQUIRED", ""
		p, e := host.Load(pr.Profile)
		if e != nil {
			code = publicError(e)
		}
		if e == nil {
			observed = host.BackendID(p)
			switch {
			case observed == "":
				state, code = "BACKEND_UNAVAILABLE", "AEVORA_PROJECT_BACKEND_UNAVAILABLE"
			case observed != pr.BackendID:
				state, code = "BACKEND_CHANGED", "AEVORA_PROJECT_BACKEND_CHANGED"
			default:
				state, code = "MATCHED", ""
			}
		}
		return output(cmd, map[string]any{"schema_version": "aevora.project-inspection/1", "project": pr.Name, "workspace": pr.Workspace, "profile": pr.Profile, "state": state, "code": code, "registered_backend_id": pr.BackendID, "observed_backend_id": observed, "identity_policy": "PHYSICAL_FILE_AND_DATABASE_UUID", "business_side_effects": false, "recovery": "Preserve the original. Create a consistent backup with its explicit --config, then project recover --name OLD --as NEW --backup FILE --sha256 PIN. New Runs and connection authorization are required; identity change alone does not establish its cause."})
	}})
	var alias, backup, pin string
	var port int
	recover := &cobra.Command{Use: "recover", Short: "Verify a pinned backup into a new alias without inheriting authorization", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, e := choose()
		if e != nil {
			return e
		}
		if !local.Name.MatchString(alias) || alias == pr.Name || !filepath.IsAbs(backup) {
			return local.ErrInvalid
		}
		if _, e = os.Lstat(filepath.Join(local.Home(), "projects", alias)); !os.IsNotExist(e) {
			return errors.New("AEVORA_PROJECT_ALREADY_EXISTS")
		}
		// Partial imports stay outside projects, so a failed pin or audit cannot
		// poison enumeration. Retain them for inspection instead of deleting data.
		parent := filepath.Join(local.Home(), "recoveries")
		if e = platform.PrivateDir(parent, true); e != nil {
			return e
		}
		root := filepath.Join(parent, uuid.NewString())
		if e = platform.NewPrivateDir(root); e != nil {
			return e
		}
		profile := filepath.Join(root, "host.json")
		inner := Command(native.Factory())
		inner.SetArgs([]string{"restore", "--config", profile, "--data-dir", filepath.Join(root, "data"), "--input", backup, "--sha256", pin, "--port", strconv.Itoa(port), "--facts", "{}"})
		inner.SetOut(io.Discard)
		inner.SetErr(cmd.ErrOrStderr())
		if e = inner.ExecuteContext(cmd.Context()); e != nil {
			return e
		}
		p, e := host.Load(profile)
		if e != nil {
			return e
		}
		next := local.Project{Schema: "aevora.local-project/1", Name: alias, Workspace: pr.Workspace, Profile: profile, BackendID: host.BackendID(p)}
		if next.BackendID == "" || next.BackendID == pr.BackendID {
			return platform.ErrUnsafe
		}
		if e = local.Register(next); e != nil {
			return e
		}
		return output(cmd, map[string]any{"schema_version": "aevora.project-recovery/1", "status": "VERIFIED_NEW_PROJECT", "source_project": pr.Name, "project": next, "backup_sha256": pin, "source": "PRESERVED", "old_runs": "NOT_AUTHORIZED", "standing_policies": "NOT_COPIED", "connections": "NOT_CHANGED", "public_context": "EMPTY_REQUIRES_NEW_OBSERVATION", "next_step": "Start the new Host, create a fresh task or explicitly configure automatic enrollment, then reconnect the client. Original bindings and data remain unchanged."})
	}}
	recover.Flags().StringVar(&alias, "as", "", "Fresh project alias; existing aliases cannot be replaced")
	recover.Flags().StringVar(&backup, "backup", "", "Closed consistent SQLite backup, preserved as input")
	recover.Flags().StringVar(&pin, "sha256", "", "Approved SHA256 of the backup")
	recover.Flags().IntVar(&port, "port", 17805, "New loopback Console port")
	pc.AddCommand(recover)
}
