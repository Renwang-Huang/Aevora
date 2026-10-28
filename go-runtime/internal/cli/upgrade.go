package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/service"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/upgrade"
	"github.com/spf13/cobra"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"time"
)

// Upgrade delegates all Host supervision to its existing OS service manager.
// No business operations are replayed, and a rollback never overwrites the DB.
type upgradeFailure struct {
	state, receipt string
	cause          error
}

func (e *upgradeFailure) Error() string { return "AEVORA_UPGRADE_" + e.state }
func (e *upgradeFailure) Unwrap() error { return e.cause }

type upgradeOutputBuffer struct{ bytes.Buffer }

func (b *upgradeOutputBuffer) Write(p []byte) (int, error) {
	if b.Len()+len(p) > 65536 {
		return 0, upgrade.ErrInvalid
	}
	return b.Buffer.Write(p)
}

func addUpgrade(c *cobra.Command, project *string) {
	var binary, pin, target string
	var tasks []string
	u := &cobra.Command{Use: "upgrade", Short: "Install a pinned local binary, back up data and restart the selected owned Host", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) (err error) {
		if runtime.GOOS != "linux" {
			return errors.New("AEVORA_UPGRADE_PLATFORM_NOT_VALIDATED; use the owning package manager")
		}
		if *project == "" || !filepath.IsAbs(binary) {
			return errors.New("AEVORA_UPGRADE_REQUIRES_PROJECT_AND_ABSOLUTE_BINARY")
		}
		if target == "" {
			target, err = os.Executable()
			if err != nil {
				return err
			}
		}
		if !filepath.IsAbs(target) {
			return upgrade.ErrInvalid
		}
		target = filepath.Clean(target)
		oldHash, err := upgrade.Digest(target)
		if err != nil {
			return err
		}
		if oldHash == pin {
			return output(cmd, map[string]any{"status": "ALREADY_CURRENT", "binary": target, "sha256": pin})
		}
		staged, err := upgrade.CopyPinned(binary, filepath.Dir(target), pin)
		if err != nil {
			return err
		}
		defer os.Remove(staged)
		next, err := upgrade.ReadVersion(cmd.Context(), staged)
		if err != nil {
			return err
		}
		old, err := upgrade.ReadVersion(cmd.Context(), target)
		if err != nil {
			return err
		}
		if next.OS != runtime.GOOS || next.Arch != runtime.GOARCH || next.Storage != storage.PhysicalVersion || (old.Storage != 0 && old.Storage != next.Storage) {
			return errors.New("AEVORA_UPGRADE_PLATFORM_OR_SCHEMA_MISMATCH")
		}
		pr, p, err := selectedProject(*project)
		if err != nil {
			return err
		}
		projectDir, err := local.ProjectDir(pr.Name)
		if err != nil {
			return err
		}
		serviceDir := filepath.Join(projectDir, "service")
		r, err := service.Load(serviceDir, pr.BackendID)
		if err != nil {
			return err
		}
		if r.Executable != target {
			return errors.New("AEVORA_UPGRADE_TARGET_IS_NOT_OWNED_SERVICE_EXECUTABLE")
		}
		state, err := service.Show(cmd.Context(), r)
		if err != nil {
			return err
		}
		active := state["ActiveState"] == "active"
		if !active && len(tasks) > 0 {
			return errors.New("AEVORA_UPGRADE_RESUME_REQUIRES_RUNNING_HOST")
		}
		for _, name := range tasks {
			if _, _, err = local.LoadTask(pr.Name, name); err != nil {
				return err
			}
		}
		projects, err := local.Projects()
		if err != nil {
			return err
		}
		for _, other := range projects {
			if other.Name == pr.Name {
				continue
			}
			dir, e := local.ProjectDir(other.Name)
			if e != nil {
				return e
			}
			record, e := service.Load(filepath.Join(dir, "service"), other.BackendID)
			if os.IsNotExist(e) {
				continue
			}
			if e != nil {
				return e
			}
			if record.Executable == target {
				status, e := service.Show(cmd.Context(), record)
				if e != nil {
					return e
				}
				if status["ActiveState"] == "active" {
					return errors.New("AEVORA_UPGRADE_OTHER_HOSTS_ACTIVE; stop other projects using this binary first")
				}
			}
		}
		port := r.Port
		if active {
			status, e := host.ReadStatus(p)
			if e != nil {
				return e
			}
			pid, e := strconv.Atoi(state["MainPID"])
			if e != nil || pid != status.PID || status.State != "READY" {
				return errors.New("AEVORA_UPGRADE_HOST_NOT_READY")
			}
			parsed, e := url.Parse(status.Console)
			if e != nil {
				return e
			}
			port, e = strconv.Atoi(parsed.Port())
			if e != nil {
				return e
			}
		}
		upgradeDir := filepath.Join(platform.OwnershipHome(), "aevora", "upgrades")
		if err = platform.PrivateDir(upgradeDir, true); err != nil {
			return err
		}
		lock, err := platform.Lock(filepath.Join(upgradeDir, "upgrade.lock"))
		if err != nil {
			return err
		}
		defer lock.Close()
		folder, err := os.MkdirTemp(upgradeDir, time.Now().UTC().Format("20060102T150405Z")+"-")
		if err != nil {
			return err
		}
		backup, err := upgrade.CopyPinned(target, folder, oldHash)
		if err != nil {
			return err
		}
		previous := filepath.Join(folder, "previous-aevora")
		if err = os.Rename(backup, previous); err != nil {
			return err
		}
		receipt := map[string]any{"schema_version": "aevora.local-upgrade/1", "status": "PREPARED", "project": pr.Name, "target": target, "previous_binary": previous, "previous_sha256": oldHash, "sha256": pin, "previous_version": old, "version": next, "resume_tasks": tasks, "database_restored": false, "model_calls": "NOT_STARTED"}
		writeReceipt := func() error {
			raw, e := json.MarshalIndent(receipt, "", "  ")
			if e != nil {
				return e
			}
			return platform.AtomicLimit(filepath.Join(folder, "receipt.json"), append(raw, '\n'), 65536)
		}
		if err = writeReceipt(); err != nil {
			return err
		}
		// Backup is performed by the current product's trusted CLI, not by a raw WAL copy.
		dbBackup := filepath.Join(folder, "experience.db")
		backupCmd := exec.CommandContext(cmd.Context(), target, "--project", pr.Name, "backup", "--output", dbBackup)
		var backupOut, backupErr upgradeOutputBuffer
		backupCmd.Stdout = &backupOut
		backupCmd.Stderr = &backupErr
		if err = backupCmd.Run(); err != nil {
			receipt["status"] = "BACKUP_FAILED"
			writeReceipt()
			return errors.New("AEVORA_UPGRADE_BACKUP_FAILED; installed binary unchanged")
		}
		receipt["database_backup"] = dbBackup
		if !json.Valid(backupOut.Bytes()) {
			return errors.New("AEVORA_UPGRADE_INVALID_BACKUP_RECEIPT")
		}
		receipt["database_backup_receipt"] = json.RawMessage(backupOut.Bytes())
		if err = writeReceipt(); err != nil {
			return err
		}
		stopped, installed, completed := false, false, false
		originalPort := r.Port
		defer func() {
			if err == nil || completed {
				return
			}
			if !stopped && !installed {
				return
			}
			ctx, cancel := context.WithTimeout(context.Background(), 40*time.Second)
			defer cancel()
			receipt["status"] = "RECOVERY_REQUIRED"
			rollback := func() error {
				if installed {
					if e := service.Action(ctx, serviceDir, r, "stop"); e != nil {
						return e
					}
					if e := checkMemoryReaders(ctx, p, old); e != nil {
						return e
					}
					current, e := upgrade.Digest(target)
					if e != nil || current != pin {
						return upgrade.ErrChanged
					}
					oldStage, e := upgrade.CopyPinned(previous, filepath.Dir(target), oldHash)
					if e != nil {
						return e
					}
					defer os.Remove(oldStage)
					if e = upgrade.Replace(oldStage, target, pin); e != nil {
						return e
					}
				}
				if r.Port != originalPort {
					var e error
					r, e = service.ConfigurePort(ctx, serviceDir, r, originalPort)
					if e != nil {
						return e
					}
				}
				if active {
					if e := service.Action(ctx, serviceDir, r, "start"); e != nil {
						return e
					}
					if e := upgradeReady(ctx, p, r, old); e != nil {
						return e
					}
					for _, name := range tasks {
						t, _, e := local.LoadTask(pr.Name, name)
						if e != nil {
							return e
						}
						recovery := &cobra.Command{}
						recovery.SetContext(ctx)
						if e = authorizeTask(recovery, t, p); e != nil {
							return e
						}
					}
				}
				return nil
			}
			if e := rollback(); e == nil {
				receipt["status"] = "ROLLED_BACK"
			} else {
				receipt["recovery_error"] = e.Error()
			}
			writeReceipt()
			err = &upgradeFailure{state: receipt["status"].(string), receipt: filepath.Join(folder, "receipt.json"), cause: err}
		}()
		if active {
			if err = service.Action(cmd.Context(), serviceDir, r, "stop"); err != nil {
				return err
			}
			stopped = true
		}
		receipt["status"] = "HOST_STOPPED"
		if err = writeReceipt(); err != nil {
			return err
		}
		if err = checkMemoryReaders(cmd.Context(), p, next); err != nil {
			return err
		}
		if err = upgrade.Replace(staged, target, oldHash); err != nil {
			observed, _ := upgrade.Digest(target)
			installed = observed == pin
			return err
		}
		installed = true
		receipt["status"] = "INSTALLED"
		if err = writeReceipt(); err != nil {
			return err
		}
		if active {
			if r.Port != port {
				r, err = service.ConfigurePort(cmd.Context(), serviceDir, r, port)
				if err != nil {
					return err
				}
			}
			if err = service.Action(cmd.Context(), serviceDir, r, "start"); err != nil {
				return err
			}
			if err = upgradeReady(cmd.Context(), p, r, next); err != nil {
				return err
			}
			for _, name := range tasks {
				t, _, e := local.LoadTask(pr.Name, name)
				if e != nil {
					return e
				}
				if err = authorizeTask(cmd, t, p); err != nil {
					return err
				}
			}
			receipt["status"] = "READY"
			status, _ := host.ReadStatus(p)
			receipt["console"] = status.Console
		}
		receipt["client_reconnect_required"] = true
		receipt["receipt"] = filepath.Join(folder, "receipt.json")
		if err = writeReceipt(); err != nil {
			return err
		}
		completed = true
		return output(cmd, receipt)
	}}
	u.Flags().StringVar(&binary, "binary", "", "Absolute path to an explicitly selected native binary")
	u.Flags().StringVar(&pin, "sha256", "", "Trusted SHA256 pin; verified before executing the staged binary")
	u.Flags().StringVar(&target, "target", "", "Existing installed executable; defaults to this executable")
	u.Flags().StringSliceVar(&tasks, "resume-task", nil, "Explicit task aliases to reauthorize after restart; no business requests replayed")
	c.AddCommand(u)
}

func checkCaptureReader(ctx context.Context, p host.Profile, reader int) error {
	if reader >= 2 {
		return nil
	}
	store, err := storage.Open(ctx, p.Database.Path, storage.Options{})
	if err != nil {
		return err
	}
	defer store.Close()
	versioned, err := store.Read().HasVersionedCapture(ctx)
	if err != nil {
		return err
	}
	if versioned {
		return errors.New("AEVORA_UPGRADE_CAPTURE_RECORD_READER_REQUIRED")
	}
	return nil
}

func upgradeReady(ctx context.Context, p host.Profile, r service.Record, version upgrade.Version) error {
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	for ctx.Err() == nil {
		state, e := host.ReadStatus(p)
		unit, uerr := service.Show(ctx, r)
		if e == nil && uerr == nil && state.State == "READY" && state.Version == version.Version && state.Revision == version.Revision && unit["MainPID"] == strconv.Itoa(state.PID) && unit["ActiveState"] == "active" {
			probeCtx, stop := context.WithTimeout(ctx, 5*time.Second)
			_, e = host.Probe(probeCtx, p)
			stop()
			console, cerr := consoleProbe(ctx, p)
			if e == nil && cerr == nil && console["status"] == "READY" {
				return nil
			}
		}
		select {
		case <-ctx.Done():
		case <-time.After(100 * time.Millisecond):
		}
	}
	return errors.New("AEVORA_UPGRADE_READINESS_FAILED")
}

func checkMemoryReaders(ctx context.Context, p host.Profile, v upgrade.Version) error {
	if e := checkCaptureReader(ctx, p, v.CaptureReader); e != nil {
		return e
	}
	return checkTaskReader(ctx, p, v.TaskReader)
}
func checkTaskReader(ctx context.Context, p host.Profile, reader int) error {
	if reader >= 1 {
		return nil
	}
	s, e := storage.Open(ctx, p.Database.Path, storage.Options{})
	if e != nil {
		return e
	}
	defer s.Close()
	exists, e := s.Read().HasTaskMemory(ctx)
	if e != nil {
		return e
	}
	if exists {
		return errors.New("AEVORA_UPGRADE_TASK_MEMORY_READER_REQUIRED")
	}
	return nil
}
