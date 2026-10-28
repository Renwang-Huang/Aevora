//go:build linux

package platform

import (
	"os"
	"os/user"
	"path/filepath"
	"strconv"
)

// Ownership uses the OS account, not caller-controlled HOME/XDG namespaces.
func OwnershipHome() string {
	u, e := user.LookupId(strconv.Itoa(os.Getuid()))
	if e != nil {
		return ""
	}
	return filepath.Join(u.HomeDir, ".local", "state")
}
