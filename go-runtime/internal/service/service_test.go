package service

import (
	"strings"
	"testing"
)

func TestServiceTemplateBindsExactExecutableAndAvoidsImplicitAutostart(t *testing.T) {
	r := Record{Executable: "/home/user/应用 % $/aevora", Profile: "/private/profile space.json"}
	raw, e := unitText(r)
	if e != nil {
		t.Fatal(e)
	}
	v := string(raw)
	for _, want := range []string{"%%", "$$", "--port 0", "Restart=on-abnormal", "StartLimitBurst=3", "TimeoutStopSec=75", "UMask=0077"} {
		if !strings.Contains(v, want) {
			t.Fatal("missing bounded service policy", want)
		}
	}
	r.Profile = "/tmp/bad\nExecStart=/another"
	if _, e = unitText(r); e == nil {
		t.Fatal("unit directive injection accepted")
	}
}

func TestPinnedConsolePortIsPreservedInServiceTemplate(t *testing.T) {
	r := Record{Executable: "/home/user/aevora", Profile: "/private/host.json", Port: 34289}
	raw, err := unitText(r)
	if err != nil || !strings.Contains(string(raw), "--port 34289") {
		t.Fatal("console port lost", err)
	}
	r.Port = 80
	if _, err = unitText(r); err == nil {
		t.Fatal("invalid console port accepted")
	}
}
