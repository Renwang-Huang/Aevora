package storage

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func BenchmarkFTSRecallScaling(b *testing.B) {
	for _, size := range []int{100, 1000, 10000} {
		b.Run(fmt.Sprint(size), func(b *testing.B) {
			ctx := context.Background()
			root := b.TempDir()
			os.Chmod(root, 0700)
			s, e := Open(ctx, filepath.Join(root, "graph.db"), Options{Create: true})
			if e != nil {
				b.Fatal(e)
			}
			defer s.Close()
			if e = s.Write(ctx, func(r *Repository) error {
				for i := 0; i < size; i++ {
					title := "Storage maintenance backup"
					if i == size-1 {
						title = "Native queued instruction"
					}
					if e := r.PutNode(ctx, "Experience", map[string]any{"id": fmt.Sprintf("experience:%05d", i), "title": title, "public_summary": "Synthetic scale fixture"}); e != nil {
						return e
					}
				}
				return nil
			}); e != nil {
				b.Fatal(e)
			}
			if _, _, e = s.Read().Recall(ctx, "Experience", "原生队列", 5, 0); e != nil {
				b.Fatal(e)
			}
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				hits, _, err := s.Read().Recall(ctx, "Experience", "原生队列", 5, 0)
				if err != nil || len(hits) != 1 {
					b.Fatal(hits, err)
				}
			}
		})
	}
}
