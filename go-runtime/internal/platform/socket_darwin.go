//go:build darwin

package platform

import (
	"golang.org/x/sys/unix"
	"net"
	"os"
)

func SameUser(c net.Conn, _ ...bool) bool {
	u, ok := c.(*net.UnixConn)
	if !ok {
		return false
	}
	raw, err := u.SyscallConn()
	if err != nil {
		return false
	}
	ok = false
	err = raw.Control(func(fd uintptr) {
		cred, e := unix.GetsockoptXucred(int(fd), unix.SOL_LOCAL, unix.LOCAL_PEERCRED)
		ok = e == nil && cred.Uid == uint32(os.Getuid())
	})
	return err == nil && ok
}
