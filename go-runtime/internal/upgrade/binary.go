// Package upgrade stages an explicitly selected, checksum-pinned native binary.
// It does not discover releases, download programs or execute an unverified file.
package upgrade

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"time"
)

var ErrInvalid = errors.New("AEVORA_UPGRADE_INVALID_BINARY_OR_CHECKSUM")
var ErrChanged = errors.New("AEVORA_UPGRADE_TARGET_CHANGED")

const maxBinary = 128 * 1024 * 1024

type Version struct {
	Product       string `json:"product"`
	Version       string `json:"version"`
	Revision      string `json:"revision"`
	OS            string `json:"os"`
	Arch          string `json:"arch"`
	Storage       int    `json:"storage_schema"`
	CaptureReader int    `json:"capture_record_reader,omitempty"`
	TaskReader    int    `json:"task_memory_reader,omitempty"`
}

func Digest(path string) (string, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return "", err
	}
	if !info.Mode().IsRegular() || info.Size() < 1 || info.Size() > maxBinary {
		return "", ErrInvalid
	}
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	n, err := io.Copy(h, io.LimitReader(f, maxBinary+1))
	if err != nil || n > maxBinary {
		return "", ErrInvalid
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// CopyPinned puts verified bytes in the destination filesystem before execution.
func CopyPinned(source, dir, pin string) (string, error) {
	if !regexp.MustCompile(`^[0-9a-f]{64}$`).MatchString(pin) {
		return "", ErrInvalid
	}
	info, err := os.Lstat(source)
	if err != nil {
		return "", err
	}
	if !info.Mode().IsRegular() || info.Size() < 1 || info.Size() > maxBinary {
		return "", ErrInvalid
	}
	in, err := os.Open(source)
	if err != nil {
		return "", err
	}
	defer in.Close()
	out, err := os.CreateTemp(dir, ".aevora-upgrade-*")
	if err != nil {
		return "", err
	}
	name := out.Name()
	ok := false
	defer func() {
		out.Close()
		if !ok {
			os.Remove(name)
		}
	}()
	h := sha256.New()
	n, err := io.Copy(io.MultiWriter(out, h), io.LimitReader(in, maxBinary+1))
	if err != nil || n != info.Size() || n > maxBinary || hex.EncodeToString(h.Sum(nil)) != pin {
		return "", ErrInvalid
	}
	if err = out.Chmod(0700); err != nil {
		return "", err
	}
	if err = out.Sync(); err != nil {
		return "", err
	}
	if err = out.Close(); err != nil {
		return "", err
	}
	ok = true
	return name, nil
}

type bounded struct{ raw []byte }

func (b *bounded) Write(p []byte) (int, error) {
	if len(b.raw)+len(p) > 65536 {
		return 0, ErrInvalid
	}
	b.raw = append(b.raw, p...)
	return len(p), nil
}
func ReadVersion(ctx context.Context, path string) (Version, error) {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	c := exec.CommandContext(ctx, path, "version", "--json")
	var out, stderr bounded
	c.Stdout = &out
	c.Stderr = &stderr
	var v Version
	if err := c.Run(); err != nil {
		return v, ErrInvalid
	}
	if json.Unmarshal(out.raw, &v) != nil || v.Product != "Aevora" || v.Version == "" || v.OS == "" || v.Arch == "" {
		return v, ErrInvalid
	}
	return v, nil
}

// Replace refuses to overwrite a concurrent user edit. The verified staging
// file and target must be in the same directory for atomic rename on Linux.
func Replace(staged, target, expected string) error {
	if filepath.Clean(filepath.Dir(staged)) != filepath.Clean(filepath.Dir(target)) {
		return ErrInvalid
	}
	digest, err := Digest(target)
	if err != nil {
		return err
	}
	if digest != expected {
		return ErrChanged
	}
	info, err := os.Lstat(target)
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() || info.Mode().Perm()&0022 != 0 {
		return ErrInvalid
	}
	if err = os.Chmod(staged, info.Mode().Perm()); err != nil {
		return err
	}
	if err = os.Rename(staged, target); err != nil {
		return err
	}
	dir, err := os.Open(filepath.Dir(target))
	if err != nil {
		return err
	}
	defer dir.Close()
	return dir.Sync()
}
