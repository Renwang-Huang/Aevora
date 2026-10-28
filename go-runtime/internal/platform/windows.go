//go:build windows

package platform

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"github.com/Microsoft/go-winio"
	"golang.org/x/sys/windows"
	"io"
	"net"
	"os"
	"path/filepath"
	"unsafe"
)

var ErrUnsafe = errors.New("AEVORA_UNSAFE_HOST_STATE")

func OwnershipHome() string {
	path, e := windows.KnownFolderPath(windows.FOLDERID_LocalAppData, 0)
	if e != nil {
		return ""
	}
	return path
}

func userSID() (*windows.SID, error) {
	u, e := windows.GetCurrentProcessToken().GetTokenUser()
	if e != nil {
		return nil, e
	}
	return u.User.Sid, nil
}
func descriptor(directory bool) (*windows.SECURITY_DESCRIPTOR, error) {
	sid, e := userSID()
	if e != nil {
		return nil, e
	}
	inherit := ""
	if directory {
		inherit = "OICI"
	}
	return windows.SecurityDescriptorFromString("O:" + sid.String() + "D:P(A;" + inherit + ";FA;;;" + sid.String() + ")")
}

func secureHandle(h windows.Handle, directory bool) error {
	var info windows.ByHandleFileInformation
	if windows.GetFileInformationByHandle(h, &info) != nil || info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 {
		return ErrUnsafe
	}
	if directory != (info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY != 0) || (!directory && info.NumberOfLinks != 1) {
		return ErrUnsafe
	}
	sd, e := windows.GetSecurityInfo(h, windows.SE_FILE_OBJECT, windows.OWNER_SECURITY_INFORMATION|windows.DACL_SECURITY_INFORMATION)
	if e != nil {
		return ErrUnsafe
	}
	owner, _, e := sd.Owner()
	if e != nil {
		return ErrUnsafe
	}
	current, e := userSID()
	if e != nil || !owner.Equals(current) {
		return ErrUnsafe
	}
	acl, _, e := sd.DACL()
	if e != nil || acl == nil || acl.AceCount != 1 {
		return ErrUnsafe
	}
	var ace *windows.ACCESS_ALLOWED_ACE
	if windows.GetAce(acl, 0, &ace) != nil || ace.Header.AceType != windows.ACCESS_ALLOWED_ACE_TYPE {
		return ErrUnsafe
	}
	sid := (*windows.SID)(unsafe.Pointer(&ace.SidStart))
	const all = windows.ACCESS_MASK(0x1f01ff)
	if !sid.Equals(current) || ace.Mask&all != all {
		return ErrUnsafe
	}
	return nil
}

func openHandle(path string, access, creation uint32, sd *windows.SECURITY_DESCRIPTOR) (windows.Handle, error) {
	p, e := windows.UTF16PtrFromString(path)
	if e != nil {
		return 0, e
	}
	var sa *windows.SecurityAttributes
	if sd != nil {
		sa = &windows.SecurityAttributes{Length: uint32(unsafe.Sizeof(windows.SecurityAttributes{})), SecurityDescriptor: sd}
	}
	return windows.CreateFile(p, access, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE, sa, creation, windows.FILE_FLAG_OPEN_REPARSE_POINT|windows.FILE_FLAG_BACKUP_SEMANTICS, 0)
}

func PrivateDir(path string, create bool) error {
	if !filepath.IsAbs(path) {
		return ErrUnsafe
	}
	if create {
		if e := os.MkdirAll(filepath.Dir(path), 0700); e != nil {
			return e
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
		if e = windows.CreateDirectory(p, sa); e != nil && e != windows.ERROR_ALREADY_EXISTS {
			return e
		}
	}
	h, e := openHandle(path, windows.READ_CONTROL|windows.FILE_READ_ATTRIBUTES, windows.OPEN_EXISTING, nil)
	if e != nil {
		return e
	}
	defer windows.CloseHandle(h)
	return secureHandle(h, true)
}

func OpenPrivate(path string, flags int) (*os.File, error) {
	if e := PrivateDir(filepath.Dir(path), false); e != nil {
		return nil, e
	}
	access := uint32(windows.READ_CONTROL | windows.FILE_READ_ATTRIBUTES)
	if flags&os.O_WRONLY != 0 {
		access |= windows.GENERIC_WRITE
	} else if flags&os.O_RDWR != 0 {
		access |= windows.GENERIC_READ | windows.GENERIC_WRITE
	} else {
		access |= windows.GENERIC_READ
	}
	creation := uint32(windows.OPEN_EXISTING)
	if flags&os.O_CREATE != 0 {
		creation = windows.OPEN_ALWAYS
	}
	if flags&os.O_EXCL != 0 {
		creation = windows.CREATE_NEW
	}
	sd, e := descriptor(false)
	if e != nil {
		return nil, e
	}
	h, e := openHandle(path, access, creation, sd)
	if e != nil {
		return nil, &os.PathError{Op: "open", Path: path, Err: e}
	}
	if e = secureHandle(h, false); e != nil {
		windows.CloseHandle(h)
		return nil, e
	}
	return os.NewFile(uintptr(h), path), nil
}

func ReadPrivate(path string, maximum int) ([]byte, error) {
	f, e := OpenPrivate(path, os.O_RDONLY)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	before, e := f.Stat()
	if e != nil || before.Size() < 1 || before.Size() > int64(maximum) {
		return nil, ErrUnsafe
	}
	raw, e := io.ReadAll(io.LimitReader(f, int64(maximum)+1))
	if e != nil {
		return nil, e
	}
	after, e := f.Stat()
	if e != nil || before.Size() != after.Size() || before.ModTime() != after.ModTime() || len(raw) != int(before.Size()) {
		return nil, ErrUnsafe
	}
	return raw, nil
}
func Exclusive(path string, raw []byte) error {
	f, e := OpenPrivate(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL)
	if e != nil {
		return e
	}
	_, e = f.Write(raw)
	if e == nil {
		e = f.Sync()
	}
	if c := f.Close(); e == nil {
		e = c
	}
	return e
}
func Lock(path string) (*os.File, error) {
	f, e := OpenPrivate(path, os.O_RDWR|os.O_CREATE)
	if e != nil {
		return nil, e
	}
	if e = windows.LockFileEx(windows.Handle(f.Fd()), windows.LOCKFILE_EXCLUSIVE_LOCK|windows.LOCKFILE_FAIL_IMMEDIATELY, 0, 1, 0, &windows.Overlapped{}); e != nil {
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
	var nonce [16]byte
	if _, e := rand.Read(nonce[:]); e != nil {
		return e
	}
	temporary := filepath.Join(filepath.Dir(path), ".selector-"+hex.EncodeToString(nonce[:]))
	if e := Exclusive(temporary, raw); e != nil {
		return e
	}
	defer os.Remove(temporary)
	if _, e := os.Lstat(path); e == nil {
		f, e := OpenPrivate(path, os.O_RDONLY)
		if e != nil {
			return e
		}
		st, e := f.Stat()
		f.Close()
		if e != nil || st.Size() > int64(limit) {
			return ErrUnsafe
		}
	} else if !os.IsNotExist(e) {
		return e
	}
	from, e := windows.UTF16PtrFromString(temporary)
	if e != nil {
		return e
	}
	to, e := windows.UTF16PtrFromString(path)
	if e != nil {
		return e
	}
	return windows.MoveFileEx(from, to, windows.MOVEFILE_REPLACE_EXISTING|windows.MOVEFILE_WRITE_THROUGH)
}

func Address(folder string) string {
	sum := sha256.Sum256([]byte(filepath.Clean(folder)))
	return `\\.\pipe\aevora-` + hex.EncodeToString(sum[:16])
}
func Listen(address string) (net.Listener, error) {
	sid, e := userSID()
	if e != nil {
		return nil, e
	}
	return winio.ListenPipe(address, &winio.PipeConfig{SecurityDescriptor: "D:P(A;;GA;;;" + sid.String() + ")", InputBufferSize: 262144, OutputBufferSize: 262144})
}
func Dial(ctx context.Context, address string) (net.Conn, error) {
	return winio.DialPipeContext(ctx, address)
}

func SameUser(c net.Conn, server ...bool) bool {
	f, ok := c.(interface{ Fd() uintptr })
	if !ok {
		return false
	}
	var pid uint32
	var e error
	if len(server) > 0 && server[0] {
		e = windows.GetNamedPipeClientProcessId(windows.Handle(f.Fd()), &pid)
	} else {
		e = windows.GetNamedPipeServerProcessId(windows.Handle(f.Fd()), &pid)
	}
	if e != nil {
		return false
	}
	process, e := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, pid)
	if e != nil {
		return false
	}
	defer windows.CloseHandle(process)
	var token windows.Token
	if windows.OpenProcessToken(process, windows.TOKEN_QUERY, &token) != nil {
		return false
	}
	defer token.Close()
	user, e := token.GetTokenUser()
	if e != nil {
		return false
	}
	current, e := userSID()
	if e != nil || !user.User.Sid.Equals(current) {
		return false
	}
	ours, e := windows.GetCurrentProcessToken().GetTokenGroups()
	if e != nil {
		return false
	}
	theirs, e := token.GetTokenGroups()
	if e != nil {
		return false
	}
	for _, a := range ours.AllGroups() {
		if a.Attributes&windows.SE_GROUP_LOGON_ID != windows.SE_GROUP_LOGON_ID {
			continue
		}
		for _, b := range theirs.AllGroups() {
			if b.Attributes&windows.SE_GROUP_LOGON_ID == windows.SE_GROUP_LOGON_ID && a.Sid.Equals(b.Sid) {
				return true
			}
		}
	}
	return false
}
