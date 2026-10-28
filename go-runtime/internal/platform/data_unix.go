//go:build linux || darwin

package platform

import (
	"fmt"
	"golang.org/x/sys/unix"
	"os"
)

func LockData(path string) (*os.File, error) { return Lock(path) }
func FileIdentity(f *os.File) (string, error) {
	var s unix.Stat_t
	if e := unix.Fstat(int(f.Fd()), &s); e != nil {
		return "", e
	}
	return fmt.Sprintf("sqlite/%x/%x", s.Dev, s.Ino), nil
}

func EvidenceStamp(f *os.File) (string, error) {
	var s unix.Stat_t
	if e := unix.Fstat(int(f.Fd()), &s); e != nil {
		return "", e
	}
	if s.Mode&unix.S_IFMT != unix.S_IFREG || s.Nlink != 1 {
		return "", ErrUnsafe
	}
	return fmt.Sprintf("%d/%d/%d/%v/%v", s.Dev, s.Ino, s.Size, s.Mtim, s.Ctim), nil
}
func EvidenceFlags() int { return os.O_RDONLY | unix.O_NOFOLLOW | unix.O_NONBLOCK }
