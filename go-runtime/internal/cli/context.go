package cli

import (
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/google/uuid"
	"github.com/spf13/cobra"
	"os"
	"path/filepath"
)

func inferProject(cmd *cobra.Command, project *string) error {
	if *project != "" {
		return nil
	}
	dir, err := os.Getwd()
	if err != nil {
		return err
	}
	p, err := local.SelectWorkspace(dir)
	if err == nil {
		configured, _ := cmd.Root().PersistentFlags().GetString("config")
		if configured != "" && filepath.Clean(configured) != filepath.Clean(p.Profile) {
			return errors.New("AEVORA_PROJECT_CONFIG_CONFLICT")
		}
		*project = p.Name
	}
	return err
}

func collectContext(cmd *cobra.Command, p host.Profile) (domain.Map, error) {
	response, err := trustedCall(cmd.Context(), p, "", "context", domain.Map{})
	if err != nil {
		return nil, err
	}
	if response["status"] != "COMPLETED" {
		return nil, &operationError{domain.S(response["status"]), domain.S(response["operation_id"]), domain.S(response["code"])}
	}
	raw, err := json.Marshal(response["result"])
	if err != nil {
		return nil, err
	}
	value, err := codec.Parse(raw)
	if err != nil {
		return nil, err
	}
	observation := domain.M(value)
	if observation["source"] != "TRUSTED_NATIVE_RUNTIME_OBSERVATION" || observation["facts_sha256"] != domain.H(observation["facts"]) {
		return nil, errors.New("AEVORA_CONTEXT_OBSERVATION_INVALID")
	}
	return observation, nil
}

func newProjectTask(cmd *cobra.Command, pr local.Project, p host.Profile, name string, proposals bool) (local.Task, error) {
	observation, err := collectContext(cmd, p)
	if err != nil {
		return local.Task{}, err
	}
	observation, err = local.ObserveProject(cmd.Context(), pr, observation)
	if err != nil {
		return local.Task{}, err
	}
	facts, err := codec.Canonical(observation["facts"])
	if err != nil {
		return local.Task{}, err
	}
	raw, err := codec.Canonical(observation)
	if err != nil {
		return local.Task{}, err
	}
	if name == "" {
		name = "task-" + uuid.NewString()
	}
	return local.NewObservedTask(pr, name, facts, raw, proposals)
}

func addContextCommands(c *cobra.Command, project *string) {
	context := &cobra.Command{Use: "context", Short: "Inspect the public fact catalog and trusted local observations"}
	context.AddCommand(&cobra.Command{Use: "catalog", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error { return output(cmd, domain.FactCatalog()) }})
	context.AddCommand(&cobra.Command{Use: "collect", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		if err := inferProject(cmd, project); err != nil {
			return err
		}
		pr, p, err := selectedProject(*project)
		if err != nil {
			return err
		}
		value, err := collectContext(cmd, p)
		if err != nil {
			return err
		}
		value, err = local.ObserveProject(cmd.Context(), pr, value)
		if err != nil {
			return err
		}
		return output(cmd, value)
	}})
	c.AddCommand(context)
}
