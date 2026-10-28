package host

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"io"
	"path/filepath"
	"regexp"
	"time"
)

var directoryID = regexp.MustCompile(`^s-[0-9a-f]{16}$`)

func Bridge(ctx context.Context, root string, input io.Reader, output io.Writer) error {
	return BridgeRun(ctx, root, "", input, output)
}
func BridgeRun(ctx context.Context, root, selectedRun string, input io.Reader, output io.Writer) error {
	selector := filepath.Join(root, "current.json")
	if selectedRun != "" {
		if !validID.MatchString(selectedRun) {
			return wire.ErrInvalid
		}
		selector = runSelector(root, selectedRun)
	}
	raw, e := platform.ReadPrivate(selector, 4096)
	if e != nil {
		return errors.New("SESSION_NOT_STARTED")
	}
	v, e := wire.Decode(raw, 4096)
	if e != nil || len(v) != 3 || v["schema_version"] != "aevora.local-session/1" {
		return wire.ErrInvalid
	}
	dir, _ := v["directory"].(string)
	run, _ := v["run_id"].(string)
	if !directoryID.MatchString(dir) || !validID.MatchString(run) {
		return wire.ErrInvalid
	}
	if selectedRun != "" && run != selectedRun {
		return wire.ErrInvalid
	}
	folder := filepath.Join(root, dir)
	raw, e = platform.ReadPrivate(filepath.Join(folder, "grant.json"), 4096)
	if e != nil {
		return errors.New("AEVORA_GRANT_UNAVAILABLE")
	}
	grant, e := wire.Decode(raw, 4096)
	if e != nil || grant["run_id"] != run {
		return wire.ErrInvalid
	}
	serverDirectory := dir
	if grant["schema_version"] == "aevora.runtime-grant/1" && len(grant) == 4 {
	} else if grant["schema_version"] == "aevora.runtime-grant/2" && len(grant) == 5 {
		serverDirectory, _ = grant["server_directory"].(string)
		if !directoryID.MatchString(serverDirectory) {
			return wire.ErrInvalid
		}
	} else {
		return wire.ErrInvalid
	}
	socket, _ := grant["socket"].(string)
	token, _ := grant["token"].(string)
	if socket != platform.Address(filepath.Join(root, serverDirectory)) || len(token) != 64 {
		return wire.ErrInvalid
	}
	return bridgeConnection(ctx, socket, run, token, input, output)
}

// BridgeGrant reads a Host-created scoped connector capability. Namespaced
// consumers can receive just this file and a socket, without a session root.
// The server still independently verifies the Run/token and kernel peer.
func BridgeGrant(ctx context.Context, path string, input io.Reader, output io.Writer) error {
	raw, e := platform.ReadPrivate(path, 4096)
	if e != nil {
		return errors.New("AEVORA_GRANT_UNAVAILABLE")
	}
	grant, e := wire.Decode(raw, 4096)
	if e != nil || !exactKeys(grant, "schema_version", "run_id", "token", "socket") || grant["schema_version"] != "aevora.connector-grant/1" {
		return wire.ErrInvalid
	}
	socket, _ := grant["socket"].(string)
	run, _ := grant["run_id"].(string)
	token, _ := grant["token"].(string)
	if !validID.MatchString(run) || len(token) != 64 || socket == "" {
		return wire.ErrInvalid
	}
	return bridgeConnection(ctx, socket, run, token, input, output)
}
func bridgeConnection(ctx context.Context, socket, run, token string, input io.Reader, output io.Writer) error {
	c, e := platform.Dial(ctx, socket)
	if e != nil {
		return errors.New("AEVORA_HOST_UNAVAILABLE")
	}
	defer c.Close()
	if !platform.SameUser(c, false) {
		return errors.New("AEVORA_HOST_IDENTITY_INVALID")
	}
	c.SetDeadline(time.Now().Add(10 * time.Second))
	auth, _ := json.Marshal(map[string]any{"schema_version": "aevora.runtime-auth/1", "token": token, "run_id": run, "nonce": random()})
	auth = append(auth, '\n')
	if _, e = c.Write(auth); e != nil {
		return e
	}
	r := bufio.NewReader(c)
	raw, e := wire.Line(r, 4096)
	if e != nil {
		return errors.New("AEVORA_AUTHENTICATION_FAILED")
	}
	ready, e := wire.Decode(raw, 4096)
	if e != nil || ready["status"] != "READY" {
		return errors.New("AEVORA_AUTHENTICATION_FAILED")
	}
	c.SetDeadline(time.Time{})
	done := make(chan error, 2)
	go func() { _, e := io.Copy(c, input); done <- e }()
	go func() { _, e := io.Copy(output, r); done <- e }()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case e := <-done:
		return e
	}
}
