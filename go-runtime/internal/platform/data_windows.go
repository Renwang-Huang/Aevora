//go:build windows

package platform

import (
	"errors"
	"fmt"
	"golang.org/x/sys/windows"
	"os"
)

// Lock a byte outside SQLite's documented lock region and all valid DB pages.
// Locking the database header would deny SQLite's own independent handle reads.
func LockData(path string) (*os.File, error) {
	f, e := OpenPrivate(path, os.O_RDWR)
	if e != nil {
		return nil, e
	}
	o := &windows.Overlapped{Offset: 0xfffffffe, OffsetHigh: 0x7fffffff}
	if e = windows.LockFileEx(windows.Handle(f.Fd()), windows.LOCKFILE_EXCLUSIVE_LOCK|windows.LOCKFILE_FAIL_IMMEDIATELY, 0, 1, 0, o); e != nil {
		f.Close()
		return nil, errors.New("AEVORA_BACKEND_ALREADY_OWNED")
	}
	return f, nil
}
func FileIdentity(f *os.File) (string, error) {
	var i windows.ByHandleFileInformation
	if e := windows.GetFileInformationByHandle(windows.Handle(f.Fd()), &i); e != nil {
		return "", e
	}
	return fmt.Sprintf("sqlite/%x/%x/%x", i.VolumeSerialNumber, i.FileIndexHigh, i.FileIndexLow), nil
}

func EvidenceStamp(f *os.File) (string, error) {
	var i windows.ByHandleFileInformation
	if e := windows.GetFileInformationByHandle(windows.Handle(f.Fd()), &i); e != nil {
		return "", e
	}
	if i.FileAttributes&(windows.FILE_ATTRIBUTE_REPARSE_POINT|windows.FILE_ATTRIBUTE_DIRECTORY) != 0 || i.NumberOfLinks != 1 {
		return "", ErrUnsafe
	}
	return fmt.Sprintf("%x/%x/%x/%x/%x/%v/%v", i.VolumeSerialNumber, i.FileIndexHigh, i.FileIndexLow, i.FileSizeHigh, i.FileSizeLow, i.LastWriteTime, i.CreationTime), nil
}
func EvidenceFlags() int { return os.O_RDONLY }
