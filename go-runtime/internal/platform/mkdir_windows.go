//go:build windows

package platform

import (
	"golang.org/x/sys/windows"
	"path/filepath"
	"unsafe"
)

func NewPrivateDir(path string) error {
	if !filepath.IsAbs(path) {
		return ErrUnsafe
	}
	p, e := windows.UTF16PtrFromString(path)
	if e != nil {
		return e
	}
	sd, e := descriptor(true)
	if e != nil {
		return e
	}
	sa := &windows.SecurityAttributes{Length: uint32(unsafe.Sizeof(windows.SecurityAttributes{})), SecurityDescriptor: sd}
	if e = windows.CreateDirectory(p, sa); e != nil {
		return e
	}
	return PrivateDir(path, false)
}
