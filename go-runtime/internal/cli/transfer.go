package cli

import (
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/transfer"
	"github.com/spf13/cobra"
	"os"
	"path/filepath"
)

// Each transfer writes a new profile only after verification. Existing profiles
// and source databases are never replaced, renamed, or used as staging areas.
func addTransferCommands(c *cobra.Command, profilePath *string) {
	for _, kind := range []string{"import", "restore"} {
		var input, pin, data, facts string
		var port int
		command := &cobra.Command{Use: kind, Short: "Verify transferred data into a new native project", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
			path := *profilePath
			if path == "" {
				path = host.ProfilePath()
			}
			if !filepath.IsAbs(path) || !filepath.IsAbs(data) {
				return engine.ErrInvalid
			}
			if _, e := os.Lstat(path); !os.IsNotExist(e) {
				return errors.New("AEVORA_PROJECT_ALREADY_EXISTS")
			}
			if _, e := os.Lstat(data); !os.IsNotExist(e) {
				return errors.New("AEVORA_TARGET_MUST_BE_NEW")
			}
			value, e := object(facts)
			if e != nil {
				return e
			}
			if e = domain.NormalizeContext(value, true); e != nil {
				return e
			}
			if port < 1024 || port > 65535 {
				return engine.ErrInvalid
			}
			if e = platform.PrivateDir(filepath.Dir(path), true); e != nil {
				return e
			}
			if e = platform.NewPrivateDir(data); e != nil {
				return e
			}
			target := filepath.Join(data, "experience.db")
			var receipt domain.Map
			if kind == "import" {
				receipt, e = transfer.Import(cmd.Context(), input, pin, target)
			} else {
				receipt, e = transfer.Restore(cmd.Context(), input, pin, target)
			}
			if e != nil {
				return e
			}
			p := host.Profile{Schema: "aevora.host-config/2"}
			p.Database.Kind, p.Database.Path = "sqlite", target
			p.Console.Port = port
			p.Session.Facts, e = codec.Canonical(value)
			if e != nil {
				return e
			}
			id := host.BackendID(p)
			if len(id) != 64 {
				return platform.ErrUnsafe
			}
			p.Session.Root = filepath.Join(platform.OwnershipHome(), "aevora", "sessions", id[:12])
			if e = platform.PrivateDir(p.Session.Root, true); e != nil {
				return e
			}
			raw, e := json.MarshalIndent(p, "", "  ")
			if e != nil {
				return e
			}
			if e = platform.Exclusive(path, raw); e != nil {
				return e
			}
			return json.NewEncoder(cmd.OutOrStdout()).Encode(domain.Map{"status": "VERIFIED_NEW_PROJECT", "config": path, "receipt": receipt, "source": "PRESERVED", "next_step": "Keep source immutable. Start the new project with a new Run; no dual writer or automatic source deletion."})
		}}
		command.Flags().StringVar(&input, "input", "", "Absolute logical export directory or closed standalone backup file")
		command.Flags().StringVar(&pin, "sha256", "", "Independently approved manifest or backup SHA256")
		command.Flags().StringVar(&data, "data-dir", "", "New private target directory; must not exist")
		command.Flags().StringVar(&facts, "facts", "{}", "Independently approved facts for new Runs")
		command.Flags().IntVar(&port, "port", 17805, "New project's loopback Console port")
		c.AddCommand(command)
	}
}
