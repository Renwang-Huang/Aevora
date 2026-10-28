package domain

import (
	"crypto/sha256"
	"encoding/hex"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// EvidenceFiles uses Go's traversal-resistant directory capability. Source
// artifacts are bytes, never imports, shell commands, or executable plugins.
type EvidenceFiles struct {
	root  *os.Root
	total int64
}

func OpenEvidence(path string) (*EvidenceFiles, error) {
	if !filepath.IsAbs(path) || filepath.Clean(path) != path {
		return nil, ErrInvalid
	}
	resolved, e := filepath.EvalSymlinks(path)
	if e != nil || resolved != path {
		return nil, ErrInvalid
	}
	root, e := os.OpenRoot(path)
	if e != nil {
		return nil, e
	}
	return &EvidenceFiles{root: root}, nil
}
func (e *EvidenceFiles) Close() error { return e.root.Close() }
func (e *EvidenceFiles) unlinked(relative string) error {
	if relative == "" || strings.ContainsAny(relative, "\\\x00") || strings.HasPrefix(relative, "/") {
		return ErrInvalid
	}
	parts := strings.Split(relative, "/")
	for i, part := range parts {
		if part == "" || part == "." || part == ".." {
			return ErrInvalid
		}
		p, err := e.root.Lstat(strings.Join(parts[:i+1], "/"))
		if err != nil {
			return err
		}
		if p.Mode()&os.ModeSymlink != 0 || (i < len(parts)-1 && !p.IsDir()) {
			return ErrInvalid
		}
	}
	return nil
}
func (e *EvidenceFiles) Read(relative string, limit int64, pin string) ([]byte, error) {
	if err := e.unlinked(relative); err != nil {
		return nil, err
	}
	f, err := e.root.OpenFile(relative, platform.EvidenceFlags(), 0)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	before, err := platform.EvidenceStamp(f)
	if err != nil {
		return nil, err
	}
	info, err := f.Stat()
	if err != nil || info.Size() > limit {
		return nil, ErrInvalid
	}
	raw, err := io.ReadAll(io.LimitReader(f, limit+1))
	if err != nil || int64(len(raw)) > limit {
		return nil, ErrInvalid
	}
	after, err := platform.EvidenceStamp(f)
	if err != nil || before != after {
		return nil, ErrInvalid
	}
	if err = e.unlinked(relative); err != nil {
		return nil, err
	}
	e.total += int64(len(raw))
	if e.total > 256*1024*1024 {
		return nil, ErrInvalid
	}
	if pin != "" {
		if !shaPattern.MatchString(pin) {
			return nil, ErrInvalid
		}
		s := sha256.Sum256(raw)
		if hex.EncodeToString(s[:]) != pin {
			return nil, ErrConflict
		}
	}
	return raw, nil
}
