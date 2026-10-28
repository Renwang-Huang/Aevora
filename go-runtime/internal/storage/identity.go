package storage

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"time"
)

// BackendIdentity combines a protected file identity with an immutable database
// UUID, so recycled filesystem inode numbers cannot inherit an old enrollment.
func BackendIdentity(path string) (string, error) {
	f, e := platform.OpenPrivate(path, os.O_RDONLY)
	if e != nil {
		return "", e
	}
	defer f.Close()
	before, e := f.Stat()
	if e != nil {
		return "", e
	}
	physical, e := platform.FileIdentity(f)
	if e != nil {
		return "", e
	}
	db, e := sql.Open("sqlite", dsn(path, "ro"))
	if e != nil {
		return "", e
	}
	defer db.Close()
	db.SetMaxOpenConns(1)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	var uuid string
	if e = db.QueryRowContext(ctx, "SELECT value FROM metadata WHERE key='backend_uuid'").Scan(&uuid); e != nil {
		return "", e
	}
	raw, e := hex.DecodeString(uuid)
	if e != nil || len(raw) != 16 {
		return "", ErrIncompatible
	}
	after, e := os.Lstat(path)
	if e != nil || !os.SameFile(before, after) {
		return "", platform.ErrUnsafe
	}
	h := sha256.Sum256([]byte(physical + "/" + uuid))
	return hex.EncodeToString(h[:]), nil
}
