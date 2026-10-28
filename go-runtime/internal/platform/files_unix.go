//go:build linux || darwin

package platform

import (
	"errors"
	"golang.org/x/sys/unix"
	"io"
	"os"
	"path/filepath"
)

var ErrUnsafe = errors.New("AEVORA_UNSAFE_HOST_STATE")

func PrivateDir(path string, create bool) error {
	if !filepath.IsAbs(path) {
		return ErrUnsafe
	}
	if create {
		if err := os.MkdirAll(path, 0700); err != nil {
			return err
		}
	}
	fi, err := os.Lstat(path)
	if err != nil {
		return err
	}
	fd, err := unix.Open(path, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		return ErrUnsafe
	}
	defer unix.Close(fd)
	var st unix.Stat_t
	if unix.Fstat(fd, &st) != nil || st.Uid != uint32(os.Getuid()) || fi.Mode().Perm() != 0700 || !fi.IsDir() {
		return ErrUnsafe
	}
	return nil
}

func OpenPrivate(path string, flags int) (*os.File, error) {
	if err := PrivateDir(filepath.Dir(path), false); err != nil {
		return nil, err
	}
	fd, err := unix.Open(path, flags|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC, 0600)
	if err != nil {
		return nil, err
	}
	var st unix.Stat_t
	if unix.Fstat(fd, &st) != nil || st.Mode&unix.S_IFMT != unix.S_IFREG || st.Mode&0777 != 0600 || st.Uid != uint32(os.Getuid()) || st.Nlink != 1 {
		unix.Close(fd)
		return nil, ErrUnsafe
	}
	return os.NewFile(uintptr(fd), path), nil
}

func ReadPrivate(path string, max int) ([]byte, error) {
	f, err := OpenPrivate(path, os.O_RDONLY)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	before, err := f.Stat()
	if err != nil || before.Size() < 1 || before.Size() > int64(max) {
		return nil, ErrUnsafe
	}
	b, err := io.ReadAll(io.LimitReader(f, int64(max)+1))
	if err != nil {
		return nil, err
	}
	after, err := f.Stat()
	if err != nil || len(b) != int(before.Size()) || before.Size() != after.Size() || before.ModTime() != after.ModTime() {
		return nil, ErrUnsafe
	}
	return b, nil
}

func Exclusive(path string, raw []byte) error {
	f, err := OpenPrivate(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL)
	if err != nil {
		return err
	}
	_, e := f.Write(raw)
	if e == nil {
		e = f.Sync()
	}
	closeErr := f.Close()
	if e != nil {
		return e
	}
	return closeErr
}

func Lock(path string) (*os.File, error) {
	f, err := OpenPrivate(path, os.O_RDWR|os.O_CREATE)
	if err != nil {
		return nil, err
	}
	if err = unix.Flock(int(f.Fd()), unix.LOCK_EX|unix.LOCK_NB); err != nil {
		f.Close()
		return nil, errors.New("AEVORA_BACKEND_ALREADY_OWNED")
	}
	return f, nil
}

func Atomic(path string, raw []byte) error {
	return AtomicLimit(path, raw, 4096)
}
func AtomicLimit(path string, raw []byte, limit int) error {
	if len(raw) > limit {
		return ErrUnsafe
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), ".selector-")
	if err != nil {
		return err
	}
	name := tmp.Name()
	defer os.Remove(name)
	if _, err = tmp.Write(raw); err == nil {
		err = tmp.Sync()
	}
	if e := tmp.Close(); err == nil {
		err = e
	}
	if err != nil {
		return err
	}
	if _, err = os.Lstat(path); err == nil {
		f, e := OpenPrivate(path, os.O_RDONLY)
		if e != nil {
			return e
		}
		st, e := f.Stat()
		f.Close()
		if e != nil || st.Size() > int64(limit) {
			return ErrUnsafe
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	if err = os.Rename(name, path); err != nil {
		return err
	}
	d, err := os.Open(filepath.Dir(path))
	if err != nil {
		return err
	}
	defer d.Close()
	return d.Sync()
}
