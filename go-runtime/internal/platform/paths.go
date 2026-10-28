package platform

import (
	"os"
	"path/filepath"
	"runtime"
)

func ConfigHome() string {
	if v := os.Getenv("XDG_CONFIG_HOME"); v != "" {
		return v
	}
	if runtime.GOOS == "windows" {
		v, _ := os.UserCacheDir()
		return v
	}
	v, _ := os.UserConfigDir()
	return v
}
func DataHome() string {
	if runtime.GOOS == "linux" {
		if v := os.Getenv("XDG_DATA_HOME"); v != "" {
			return v
		}
		home, e := os.UserHomeDir()
		if e != nil {
			return ""
		}
		return filepath.Join(home, ".local", "share")
	}
	if runtime.GOOS == "darwin" {
		home, e := os.UserHomeDir()
		if e != nil {
			return ""
		}
		return filepath.Join(home, "Library", "Application Support")
	}
	home, _ := os.UserCacheDir()
	return home
}
