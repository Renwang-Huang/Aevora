package capture

import (
	"fmt"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/captureformat"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"os"
	"path/filepath"
	"testing"
)

func TestInvalidFilesConsumeScanBudgetAndCursorStillFindsValidWork(t *testing.T) {
	root := filepath.Join(t.TempDir(), "private")
	dir := filepath.Join(root, "capture-outbox")
	if err := platform.PrivateDir(dir, true); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 40; i++ {
		if err := os.WriteFile(filepath.Join(dir, fmt.Sprintf("%064x.json", i)), []byte("{"), 0600); err != nil {
			t.Fatal(err)
		}
	}
	e, err := captureformat.New("fixture", "session-1", "turn-1", "call-1", "BASH", "JSON_DECODE_ERROR")
	if err != nil {
		t.Fatal(err)
	}
	if _, err = Enqueue(root, e); err != nil {
		t.Fatal(err)
	}
	cursor := ""
	found := false
	for i := 0; i < 42; i++ {
		scan, err := ScanSince(root, 1, cursor)
		if err != nil {
			t.Fatal(err)
		}
		if scan.Scanned != 1 || !scan.Limited {
			t.Fatal("file budget was not enforced", scan)
		}
		if len(scan.Events) > 0 {
			if scan.Events[0].ID != e.ID {
				t.Fatal(scan)
			}
			found = true
			break
		}
		if scan.Last == cursor {
			t.Fatal("bad record pinned the cursor")
		}
		cursor = scan.Last
	}
	if !found {
		t.Fatal("bad records starved a later valid event")
	}
	scan, err := ScanSince(root, 1, e.ID)
	if err != nil || scan.Last != fmt.Sprintf("%064x", 0) {
		t.Fatal("cursor did not wrap", scan, err)
	}
}
