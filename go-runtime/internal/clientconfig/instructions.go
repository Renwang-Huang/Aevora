package clientconfig

import (
	"bytes"
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"path/filepath"
)

const instructionBegin = "\n<!-- Aevora managed workflow BEGIN -->\n"
const instructionEnd = "<!-- Aevora managed workflow END -->\n"

// The receipt holds only our public instructions, never the user's AGENTS file.
func instructionEdit(home, state string, remove bool) ([]byte, []byte, string, error) {
	path := filepath.Join(home, "AGENTS.md")
	info, err := os.Lstat(path)
	var raw []byte
	if err == nil {
		if !info.Mode().IsRegular() || info.Size() > 65536 {
			return nil, nil, "", ErrConflict
		}
		raw, err = os.ReadFile(path)
		if err != nil {
			return nil, nil, "", err
		}
	} else if !os.IsNotExist(err) {
		return nil, nil, "", err
	}
	rp := receiptPath(state, home) + ".instructions"
	old, err := platform.ReadPrivate(rp, 16384)
	remaining := raw
	if err == nil {
		if !bytes.HasPrefix(old, []byte(instructionBegin)) || !bytes.HasSuffix(old, []byte(instructionEnd)) || bytes.Count(raw, old) != 1 {
			return nil, nil, "", ErrConflict
		}
		remaining = bytes.Replace(raw, old, nil, 1)
	} else if !os.IsNotExist(err) {
		return nil, nil, "", err
	} else if bytes.Contains(raw, []byte(instructionBegin)) || bytes.Contains(raw, []byte(instructionEnd)) {
		return nil, nil, "", ErrConflict
	}
	block := ""
	if !remove {
		catalog, err := contracts.Files.ReadFile("tools.json")
		if err != nil {
			return nil, nil, "", err
		}
		var data struct {
			Instructions string `json:"instructions"`
		}
		if json.Unmarshal(catalog, &data) != nil || data.Instructions == "" {
			return nil, nil, "", ErrConflict
		}
		block = instructionBegin + "## Aevora workflow (only when its MCP tools are enabled)\n\n" + data.Instructions + "\n" + instructionEnd
	}
	return raw, append(append([]byte{}, remaining...), []byte(block)...), block, nil
}

// Check before editing either the MCP block or the companion instructions.
func CheckInstructions(home, state string, remove bool) error {
	_, _, _, err := instructionEdit(home, state, remove)
	return err
}

func ApplyInstructions(home, state string, remove bool) error {
	if !filepath.IsAbs(home) || !filepath.IsAbs(state) {
		return ErrConflict
	}
	if err := platform.PrivateDir(state, true); err != nil {
		return err
	}
	lock, err := platform.Lock(filepath.Join(state, "instructions.lock"))
	if err != nil {
		return err
	}
	defer lock.Close()
	raw, next, block, err := instructionEdit(home, state, remove)
	if err != nil {
		return err
	}
	current, err := os.ReadFile(filepath.Join(home, "AGENTS.md"))
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if !bytes.Equal(current, raw) {
		return ErrConflict
	}
	if !bytes.Equal(raw, next) {
		if err = writeInstructions(filepath.Join(home, "AGENTS.md"), raw, next); err != nil {
			return err
		}
	}
	rp := receiptPath(state, home) + ".instructions"
	if remove {
		err = os.Remove(rp)
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	return platform.AtomicLimit(rp, []byte(block), 16384)
}

// AGENTS.md is user-authored documentation, often mode 0644/0664. It is not a
// protected Host credential file. Preserve its mode and bytes outside our block.
func writeInstructions(path string, before, next []byte) error {
	mode := os.FileMode(0600)
	info, err := os.Lstat(path)
	if err == nil {
		if !info.Mode().IsRegular() {
			return ErrConflict
		}
		mode = info.Mode().Perm()
	} else if !os.IsNotExist(err) {
		return err
	}
	f, err := os.CreateTemp(filepath.Dir(path), ".aevora-instructions-*")
	if err != nil {
		return err
	}
	name := f.Name()
	defer os.Remove(name)
	defer f.Close()
	if _, err = f.Write(next); err != nil {
		return err
	}
	if err = f.Chmod(mode); err != nil {
		return err
	}
	if err = f.Sync(); err != nil {
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	current, err := os.ReadFile(path)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if !bytes.Equal(current, before) {
		return ErrConflict
	}
	if currentInfo, e := os.Lstat(path); e == nil && !currentInfo.Mode().IsRegular() {
		return ErrConflict
	}
	if err = os.Rename(name, path); err != nil {
		return err
	}
	dir, err := os.Open(filepath.Dir(path))
	if err != nil {
		return err
	}
	defer dir.Close()
	return dir.Sync()
}
