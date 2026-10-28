//go:build linux || darwin

package platform

import (
	"os"
	"path/filepath"
)

func NewPrivateDir(path string) error {
	if !filepath.IsAbs(path) {
		return ErrUnsafe
	}
	if e := os.Mkdir(path, 0700); e != nil {
		return e
	}
	return PrivateDir(path, false)
}
