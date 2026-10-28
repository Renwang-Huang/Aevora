package storage

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"io"
	"os"
)

func FileDigest(ctx context.Context, path string) (string, error) {
	f, e := platform.OpenPrivate(path, os.O_RDONLY)
	if e != nil {
		return "", e
	}
	defer f.Close()
	return DigestReader(ctx, f, nil)
}

// DigestReader optionally copies into an already exclusively created target.
// A stamp change, cancellation, or oversized artifact refuses the result.
func DigestReader(ctx context.Context, f *os.File, target io.Writer) (string, error) {
	before, e := platform.EvidenceStamp(f)
	if e != nil {
		return "", e
	}
	info, e := f.Stat()
	if e != nil {
		return "", e
	}
	if info.Size() < 1 || info.Size() > 512*1024*1024 {
		return "", ErrReadBudget
	}
	h := sha256.New()
	out := io.Writer(h)
	if target != nil {
		out = io.MultiWriter(target, h)
	}
	buffer := make([]byte, 64*1024)
	var total int64
	for {
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		n, e := f.Read(buffer)
		if n > 0 {
			total += int64(n)
			if total > info.Size() {
				return "", platform.ErrUnsafe
			}
			if _, err := out.Write(buffer[:n]); err != nil {
				return "", err
			}
		}
		if e == io.EOF {
			break
		}
		if e != nil {
			return "", e
		}
	}
	after, e := platform.EvidenceStamp(f)
	if e != nil || before != after || total != info.Size() {
		return "", platform.ErrUnsafe
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
