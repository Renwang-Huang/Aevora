//go:build !linux && !darwin && !windows

package platform

import (
	"context"
	"errors"
	"net"
	"os"
)

var ErrUnsafe = errors.New("AEVORA_PLATFORM_NOT_SUPPORTED")

func PrivateDir(string, bool) error                  { return ErrUnsafe }
func NewPrivateDir(string) error                     { return ErrUnsafe }
func OpenPrivate(string, int) (*os.File, error)      { return nil, ErrUnsafe }
func ReadPrivate(string, int) ([]byte, error)        { return nil, ErrUnsafe }
func Exclusive(string, []byte) error                 { return ErrUnsafe }
func Lock(string) (*os.File, error)                  { return nil, ErrUnsafe }
func LockData(string) (*os.File, error)              { return nil, ErrUnsafe }
func FileIdentity(*os.File) (string, error)          { return "", ErrUnsafe }
func EvidenceStamp(*os.File) (string, error)         { return "", ErrUnsafe }
func EvidenceFlags() int                             { return os.O_RDONLY }
func Atomic(string, []byte) error                    { return ErrUnsafe }
func AtomicLimit(string, []byte, int) error          { return ErrUnsafe }
func SameUser(net.Conn, ...bool) bool                { return false }
func Address(string) string                          { return "" }
func OwnershipHome() string                          { return "" }
func Listen(string) (net.Listener, error)            { return nil, ErrUnsafe }
func Dial(context.Context, string) (net.Conn, error) { return nil, ErrUnsafe }
