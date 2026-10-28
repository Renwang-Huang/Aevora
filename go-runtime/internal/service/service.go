// Package service delegates process supervision to the user's OS service manager.
package service

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

var ErrUnavailable = errors.New("AEVORA_USER_SERVICE_UNAVAILABLE")
var ErrConflict = errors.New("AEVORA_SERVICE_CONFIGURATION_CONFLICT")

type Record struct {
	Schema     string `json:"schema_version"`
	Unit       string `json:"unit"`
	Backend    string `json:"backend_id"`
	Profile    string `json:"profile"`
	Executable string `json:"executable"`
	Port       int    `json:"console_port,omitempty"`
}

func unitText(r Record) ([]byte, error) {
	quote := func(s string) string {
		s = strings.ReplaceAll(s, "%", "%%")
		s = strings.ReplaceAll(s, "$", "$$")
		s = strings.ReplaceAll(s, `\`, `\\`)
		s = strings.ReplaceAll(s, `"`, `\"`)
		return `"` + s + `"`
	}
	for _, s := range []string{r.Executable, r.Profile} {
		if !filepath.IsAbs(s) || strings.ContainsAny(s, "\x00\r\n") {
			return nil, ErrConflict
		}
	}
	if r.Port != 0 && (r.Port < 1024 || r.Port > 65535) {
		return nil, ErrConflict
	}
	return []byte("[Unit]\nDescription=Aevora local project Host\nStartLimitIntervalSec=60\nStartLimitBurst=3\n[Service]\nType=exec\nExecStart=" + quote(r.Executable) + " --config " + quote(r.Profile) + " serve --port " + strconv.Itoa(r.Port) + "\nRestart=on-abnormal\nRestartSec=3\nTimeoutStopSec=75\nKillMode=control-group\nUMask=0077\n[Install]\nWantedBy=default.target\n"), nil
}
func Load(dir, backend string) (Record, error) {
	var r Record
	if len(backend) != 64 {
		return r, ErrConflict
	}
	raw, e := platform.ReadPrivate(filepath.Join(dir, "service.json"), 4096)
	if e != nil {
		return r, e
	}
	if json.Unmarshal(raw, &r) != nil || r.Schema != "aevora.user-service/1" || r.Backend != backend || r.Unit != "aevora-"+backend[:24]+".service" {
		return r, ErrConflict
	}
	expected, e := unitText(r)
	if e != nil {
		return r, e
	}
	unit, e := platform.ReadPrivate(filepath.Join(dir, r.Unit), 4096)
	if e != nil || string(unit) != string(expected) {
		return r, ErrConflict
	}
	return r, nil
}
func Install(ctx context.Context, dir, backend, profile, exe string) (Record, error) {
	if len(backend) != 64 {
		return Record{}, ErrConflict
	}
	if e := platform.PrivateDir(dir, true); e != nil {
		return Record{}, e
	}
	lock, e := platform.Lock(filepath.Join(dir, "service.lock"))
	if e != nil {
		return Record{}, e
	}
	defer lock.Close()
	r, e := Load(dir, backend)
	if e == nil {
		if r.Profile != profile || r.Executable != exe {
			return r, ErrConflict
		}
		if e = verify(ctx, dir, r); e != nil {
			return r, e
		}
		if _, e = control(ctx, "link", filepath.Join(dir, r.Unit)); e != nil {
			return r, e
		}
		_, e = control(ctx, "daemon-reload")
		return r, e
	}
	if !os.IsNotExist(e) {
		return r, e
	}
	r = Record{Schema: "aevora.user-service/1", Unit: "aevora-" + backend[:24] + ".service", Backend: backend, Profile: profile, Executable: exe}
	if e = verify(ctx, dir, r); e != nil {
		return r, e
	}
	raw, e := unitText(r)
	if e != nil {
		return r, e
	}
	if e = platform.Exclusive(filepath.Join(dir, r.Unit), raw); e != nil {
		return r, e
	}
	encoded, _ := json.Marshal(r)
	if e = platform.Exclusive(filepath.Join(dir, "service.json"), encoded); e != nil {
		return r, e
	}
	if _, e = control(ctx, "link", filepath.Join(dir, r.Unit)); e != nil {
		return r, e
	}
	_, e = control(ctx, "daemon-reload")
	return r, e
}
func verify(ctx context.Context, dir string, r Record) error {
	s, e := Show(ctx, r)
	if e != nil {
		return e
	}
	fragment := s["FragmentPath"]
	if fragment != "" {
		real, e := filepath.EvalSymlinks(fragment)
		if e != nil || real != filepath.Join(dir, r.Unit) {
			return ErrConflict
		}
	}
	return nil
}
func Show(ctx context.Context, r Record) (map[string]string, error) {
	raw, e := control(ctx, "show", r.Unit, "--no-pager", "--property=FragmentPath,ActiveState,SubState,MainPID,Result")
	if e != nil {
		return nil, e
	}
	out := map[string]string{}
	for _, line := range strings.Split(raw, "\n") {
		if k, v, ok := strings.Cut(line, "="); ok {
			out[k] = v
		}
	}
	return out, nil
}
func Action(ctx context.Context, dir string, r Record, action string) error {
	switch action {
	case "start", "stop", "restart", "enable", "disable":
	default:
		return ErrConflict
	}
	if e := verify(ctx, dir, r); e != nil {
		return e
	}
	_, e := control(ctx, action, r.Unit)
	return e
}

// ConfigurePort preserves the observed Console URL across an explicit upgrade.
// Only our verified service source is edited; autostart remains unchanged.
func ConfigurePort(ctx context.Context, dir string, r Record, port int) (Record, error) {
	lock, err := platform.Lock(filepath.Join(dir, "service.lock"))
	if err != nil {
		return r, err
	}
	defer lock.Close()
	current, err := Load(dir, r.Backend)
	if err != nil || current != r {
		return r, ErrConflict
	}
	if err = verify(ctx, dir, r); err != nil {
		return r, err
	}
	next := r
	next.Port = port
	raw, err := unitText(next)
	if err != nil {
		return r, err
	}
	oldUnit, _ := unitText(r)
	oldRecord, _ := json.Marshal(r)
	newRecord, _ := json.Marshal(next)
	if err = platform.Atomic(filepath.Join(dir, r.Unit), raw); err != nil {
		return r, err
	}
	if err = platform.Atomic(filepath.Join(dir, "service.json"), newRecord); err != nil {
		platform.Atomic(filepath.Join(dir, r.Unit), oldUnit)
		return r, err
	}
	if _, err = control(ctx, "daemon-reload"); err != nil {
		platform.Atomic(filepath.Join(dir, r.Unit), oldUnit)
		platform.Atomic(filepath.Join(dir, "service.json"), oldRecord)
		return r, err
	}
	return next, nil
}
func Remove(ctx context.Context, dir string, r Record) error {
	if e := Action(ctx, dir, r, "stop"); e != nil {
		return e
	}
	if e := Action(ctx, dir, r, "disable"); e != nil {
		return e
	}
	for _, name := range []string{r.Unit, "service.json"} {
		if e := os.Remove(filepath.Join(dir, name)); e != nil {
			return e
		}
	}
	_, e := control(ctx, "daemon-reload")
	return e
}
