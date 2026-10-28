package main

import (
	"context"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/cli"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"os"
)

func main() {
	os.Exit(cli.Execute(context.Background(), os.Args[1:], os.Stdin, os.Stdout, os.Stderr, native.Factory()))
}
