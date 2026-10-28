package transfer

import (
	"context"
	"encoding/hex"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"os"
)

func validPin(pin string) bool {
	b, e := hex.DecodeString(pin)
	return e == nil && len(b) == 32 && len(pin) == 64
}
func Restore(ctx context.Context, source, pin, target string) (Map, error) {
	if !validPin(pin) {
		return nil, domain.ErrInvalid
	}
	if e := freshTarget(target); e != nil {
		return nil, e
	}
	for _, suffix := range []string{"-wal", "-shm", "-journal"} {
		if _, e := os.Lstat(source + suffix); !os.IsNotExist(e) {
			return nil, platform.ErrUnsafe
		}
	}
	f, e := platform.OpenPrivate(source, os.O_RDONLY)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	out, e := platform.OpenPrivate(target, os.O_WRONLY|os.O_CREATE|os.O_EXCL)
	if e != nil {
		return nil, e
	}
	hash, e := storage.DigestReader(ctx, f, out)
	syncErr := out.Sync()
	closeErr := out.Close()
	if e != nil {
		return nil, e
	}
	if syncErr != nil {
		return nil, syncErr
	}
	if closeErr != nil {
		return nil, closeErr
	}
	if hash != pin {
		return nil, domain.ErrConflict
	}
	s, e := storage.Open(ctx, target, storage.Options{})
	if e != nil {
		return nil, e
	}
	defer s.Close()
	receipt, e := Audit(ctx, s, nil)
	if e != nil {
		return nil, e
	}
	receipt["backup_sha256"], receipt["target_database"], receipt["logical_schema"], receipt["run_authority"] = pin, target, storage.LogicalSchema, "NEW_BACKEND_AND_NEW_RUN_REQUIRED"
	raw, e := codec.Canonical(receipt)
	if e != nil {
		return nil, e
	}
	if e = platform.Exclusive(target+".receipt.json", raw); e != nil {
		return nil, e
	}
	return receipt, nil
}
