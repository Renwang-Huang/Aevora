package cli

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/jsoncheck"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/taskcapture"
	"github.com/spf13/cobra"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

func addMemory(c *cobra.Command, project *string) {
	command := &cobra.Command{Use: "memory", Short: "Observe engineering tasks and maintain bounded local memory"}
	addRunCheck(command, project)
	var task, client, binary string
	status := &cobra.Command{Use: "status", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		result := taskcapture.Status(p.Session.Root)
		response, e := trustedCall(cmd.Context(), p, "", "memory-state", domain.Map{"project": pr.Name})
		if e != nil {
			result["jobs"] = domain.Map{"status": "UNAVAILABLE"}
		} else {
			jobs, e := memoryResult(response)
			if e != nil {
				return e
			}
			result["jobs"] = jobs
		}
		return output(cmd, result)
	}}
	command.AddCommand(status)
	var enabledPlan string
	enable := &cobra.Command{Use: "enable-check", Short: "Delegate a protected plan to the persistent Host memory actor", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		if e = taskcapture.InstallCheck(p.Session.Root, pr.BackendID, pr.Name, pr.Workspace, enabledPlan); e != nil {
			return e
		}
		return output(cmd, domain.Map{"status": "CHECK_PLAN_ENABLED", "project": pr.Name, "next_step": "The owned Host processes this plan without per-memory human review."})
	}}
	enable.Flags().StringVar(&enabledPlan, "plan", "", "Protected check plan outside the workspace")
	command.AddCommand(enable)
	command.AddCommand(&cobra.Command{Use: "disable-check", Short: "Stop the owned Host plan without deleting memory or evidence", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		if e = taskcapture.DisableCheck(p.Session.Root, pr.BackendID, pr.Name); e != nil {
			return e
		}
		return output(cmd, domain.Map{"status": "CHECK_PLAN_DISABLED", "history": "PRESERVED"})
	}})
	command.AddCommand(&cobra.Command{Use: "reset-scan", Short: "Archive a retained task scan cursor and start a new scan", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		_, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		archive, e := taskcapture.ResetScan(p.Session.Root)
		if e != nil {
			return e
		}
		return output(cmd, domain.Map{"status": "RESET", "retained_cursor": archive})
	}})
	command.AddCommand(&cobra.Command{Use: "evaluator", Short: "Show the built-in JSON contract verifier identity", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		return output(cmd, domain.Map{"schema_version": "aevora.json-artifact-contract/1", "evaluator": jsoncheck.Evaluator, "sha256": domain.BytesSHA([]byte(jsoncheck.Evaluator))})
	}})
	observe := &cobra.Command{Use: "codex [-- app-server-options]", Short: "Relay an official Codex app-server stdio session and queue sanitized completed items", RunE: func(cmd *cobra.Command, args []string) error {
		pr, p, err := selectedProject(*project)
		if err != nil {
			return err
		}
		if task == "" {
			return domain.ErrInvalid
		}
		if err = taskcapture.Record(p.Session.Root, client, "STARTING"); err != nil {
			return err
		}
		child := exec.CommandContext(cmd.Context(), binary, append([]string{"app-server"}, args...)...)
		child.Stdin = cmd.InOrStdin()
		child.Stderr = cmd.ErrOrStderr()
		stdout, err := child.StdoutPipe()
		if err != nil {
			return err
		}
		if err = child.Start(); err != nil {
			return err
		}
		// Reader chunks are always forwarded unchanged; oversized frames are skipped only by the observer.
		router := taskcapture.NewRouter(pr.Workspace, pr.Name, task)
		reader := bufio.NewReaderSize(stdout, 32*1024)
		line := []byte{}
		over := false
		for {
			chunk, e := reader.ReadSlice('\n')
			if len(chunk) > 0 {
				if _, err = cmd.OutOrStdout().Write(chunk); err != nil {
					child.Process.Kill()
					child.Wait()
					return err
				}
				if !over {
					if len(line)+len(chunk) > taskcapture.MaxInput {
						line = nil
						over = true
					} else {
						line = append(line, chunk...)
					}
				}
			}
			if e != bufio.ErrBufferFull {
				if len(line) > 0 && !over {
					event, parseErr := router.Observe(line)
					if parseErr != nil {
						taskcapture.Record(p.Session.Root, client, "INVALID_COMPLETED_ITEM")
					} else if event != nil {
						if parseErr = taskcapture.Enqueue(p.Session.Root, event); parseErr != nil {
							taskcapture.Record(p.Session.Root, client, "OUTBOX_WRITE_FAILED")
							fmt.Fprintln(cmd.ErrOrStderr(), "Aevora task capture retained no event: inspect memory status")
						} else {
							taskcapture.Record(p.Session.Root, client, "EVENT_QUEUED")
						}
					}
				}
				if over {
					taskcapture.Record(p.Session.Root, client, "FRAME_OBSERVATION_SKIPPED_TOO_LARGE")
				}
				line = nil
				over = false
			}
			if e != nil && e != bufio.ErrBufferFull {
				if e != io.EOF {
					child.Process.Kill()
					child.Wait()
					return e
				}
				break
			}
		}
		return child.Wait()
	}}
	observe.Flags().StringVar(&task, "task", "", "Stable task label; the runtime supplies session/turn/item identity")
	observe.Flags().StringVar(&client, "client", "codex", "Observed adapter label: codex, codex1 or codex2")
	observe.Flags().StringVar(&binary, "codex-binary", "codex", "Official Codex executable")
	command.AddCommand(observe)
	var eventText string
	record := &cobra.Command{Use: "record", Short: "Retain an explicit public task observation; never verifies or publishes it", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		v, e := object(eventText)
		if e != nil {
			return e
		}
		v["project"] = pr.Name
		if e = taskcapture.Enqueue(p.Session.Root, v); e != nil {
			return e
		}
		return output(cmd, domain.Map{"status": "QUEUED_UNTRUSTED", "source_id": domain.TaskSourceID(v)})
	}}
	record.Flags().StringVar(&eventText, "event", "", "Bounded public event JSON; project is selected by the Host")
	command.AddCommand(record)

	var limit int
	work := &cobra.Command{Use: "work", Short: "Process bounded pending task summaries", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		if e = drainTaskQueue(cmd.Context(), p, pr.Name); e != nil {
			return e
		}
		response, e := trustedCall(cmd.Context(), p, "", "memory-process", domain.Map{"project": pr.Name, "limit": limit})
		if e != nil {
			return e
		}
		return emitOperation(cmd, response)
	}}
	work.Flags().IntVar(&limit, "limit", 8, "Maximum jobs, 1..16")
	command.AddCommand(work)
	var source string
	revoke := &cobra.Command{Use: "revoke-source", Short: "Revoke a source and withdraw dependent candidates, preserving history", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		v, e := trustedCall(cmd.Context(), p, "", "memory-revoke-source", domain.Map{"source_id": source, "project": pr.Name})
		if e != nil {
			return e
		}
		return emitOperation(cmd, v)
	}}
	revoke.Flags().StringVar(&source, "source", "", "Exact structured source ID")
	command.AddCommand(revoke)
	var planPath, candidate string
	check := &cobra.Command{Use: "check", Short: "Run a protected independent JSON artifact contract and standing policy", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		plan, e := jsoncheck.Load(planPath)
		if e != nil {
			return e
		}
		if plan.Project != pr.Name {
			return domain.ErrInvalid
		}
		for _, file := range []string{plan.Suite, plan.SourcePolicy, plan.AutomationPolicy, planPath} {
			real, e := filepath.EvalSymlinks(file)
			if e != nil {
				return e
			}
			rel, e := filepath.Rel(pr.Workspace, real)
			if e != nil || rel == "." || (!strings.HasPrefix(rel, ".."+string(filepath.Separator)) && rel != "..") {
				return domain.ErrInvalid
			}
		}
		invoke := func(ctx context.Context, op string, args domain.Map) (domain.Map, error) {
			v, e := trustedCall(ctx, p, "", op, args)
			if e != nil {
				return nil, e
			}
			return memoryResult(v)
		}
		plan.Workspace = pr.Workspace
		plan.PlanPath = planPath
		result, e := jsoncheck.Run(cmd.Context(), plan, candidate, invoke)
		if e != nil {
			return e
		}
		return output(cmd, result)
	}}
	check.Flags().StringVar(&planPath, "plan", "", "Protected JSON check plan outside the project workspace")
	check.Flags().StringVar(&candidate, "candidate", "", "Candidate ID")
	command.AddCommand(check)

	var watchPlan string
	var once bool
	watch := &cobra.Command{Use: "watch", Short: "Continuously process and independently check a configured task category", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		plan, e := jsoncheck.Load(watchPlan)
		if e != nil {
			return e
		}
		if plan.Project != pr.Name || plan.TaskRef == "" {
			return domain.ErrInvalid
		}
		if e = jsoncheck.ValidateWorkspace(plan, watchPlan, pr.Workspace); e != nil {
			return e
		}
		invoke := func(ctx context.Context, op string, args domain.Map) (domain.Map, error) {
			v, e := trustedCall(ctx, p, "", op, args)
			if e != nil {
				return nil, e
			}
			return memoryResult(v)
		}
		plan.Workspace = pr.Workspace
		plan.PlanPath = watchPlan
		cursor := ""
		for {
			if e = drainTaskQueue(cmd.Context(), p, pr.Name); e != nil {
				return e
			}
			result, e := jsoncheck.Sweep(cmd.Context(), plan, cursor, invoke)
			if e != nil {
				return e
			}
			if e = output(cmd, result); e != nil {
				return e
			}
			if once {
				return nil
			}
			cursor = domain.S(result["next_cursor"])
			select {
			case <-cmd.Context().Done():
				return cmd.Context().Err()
			case <-time.After(2 * time.Second):
			}
		}
	}}
	watch.Flags().StringVar(&watchPlan, "plan", "", "Protected JSON check plan outside the project workspace")
	watch.Flags().BoolVar(&once, "once", false, "Process one bounded page and exit")
	command.AddCommand(watch)

	var sourceCandidate, sourceAfter string
	var sourceLimit int
	sources := &cobra.Command{Use: "sources", Short: "Read bounded engineering sources for a candidate", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		pr, p, e := selectedProject(*project)
		if e != nil {
			return e
		}
		v, e := trustedCall(cmd.Context(), p, "", "memory-sources", domain.Map{"candidate_id": sourceCandidate, "project": pr.Name, "after": sourceAfter, "limit": sourceLimit})
		if e != nil {
			return e
		}
		return emitOperation(cmd, v)
	}}
	sources.Flags().StringVar(&sourceCandidate, "candidate", "", "Candidate ID")
	sources.Flags().StringVar(&sourceAfter, "after", "", "Previous next_cursor")
	sources.Flags().IntVar(&sourceLimit, "limit", 10, "Maximum records, 1..20; transport budget may reduce the page")
	command.AddCommand(sources)
	c.AddCommand(command)
}

func memoryResult(v domain.Map) (domain.Map, error) {
	if v["status"] != "COMPLETED" {
		return nil, fmt.Errorf("memory operation did not complete: %s", domain.S(v["code"]))
	}
	if raw, ok := v["result"].(json.RawMessage); ok {
		p, e := codec.Parse(raw)
		return domain.M(p), e
	}
	result := domain.M(v["result"])
	if result == nil {
		return nil, domain.ErrInvalid
	}
	return result, nil
}

func drainTaskQueue(ctx context.Context, p host.Profile, project string) error {
	rows, _, e := taskcapture.Scan(p.Session.Root, 64)
	if e != nil {
		return e
	}
	for _, row := range rows {
		if row.Event["project"] != project {
			continue
		}
		response, e := trustedCall(ctx, p, "", "task-event-ingest", domain.Map{"event": row.Event})
		if e != nil {
			return e
		}
		result, e := memoryResult(response)
		if e != nil || result["source_id"] != domain.TaskSourceID(row.Event) {
			return domain.ErrConflict
		}
		if e = taskcapture.Ack(row); e != nil && !os.IsNotExist(e) {
			return e
		}
	}
	return nil
}
