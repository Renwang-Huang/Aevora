package taskcapture

import (
	"path/filepath"
	"regexp"
	"strings"

	"mvdan.cc/sh/v3/syntax"
)

var pythonCommand = regexp.MustCompile(`^python(3(\.[0-9]{1,2})?)?$`)

// CheckAction classifies an invocation, not the executable's identity or the
// tests that actually ran. Unknown options stay unknown; argv is never stored.
func CheckAction(argv []string) string {
	if len(argv) < 2 {
		if len(argv) == 1 && (filepath.Base(argv[0]) == "pytest" || filepath.Base(argv[0]) == "py.test") {
			return "PYTEST"
		}
		return "COMMAND"
	}
	args := argv[1:]
	switch name := filepath.Base(argv[0]); {
	case name == "go":
		if args[0] == "-C" && len(args) >= 3 {
			args = args[2:]
		} else if strings.HasPrefix(args[0], "-C=") && len(args[0]) > 3 {
			args = args[1:]
		}
		if len(args) > 0 && args[0] == "test" {
			return "GO_TEST"
		}
	case name == "pytest" || name == "py.test":
		return "PYTEST"
	case pythonCommand.MatchString(name):
		for len(args) > 0 && (args[0] == "-I" || args[0] == "-B" || args[0] == "-E" || args[0] == "-s" || args[0] == "-u") {
			args = args[1:]
		}
		if len(args) >= 2 && args[0] == "-m" && args[1] == "pytest" {
			return "PYTEST"
		}
	case name == "npm":
		for len(args) > 0 {
			a := args[0]
			if (a == "--prefix" || a == "--workspace" || a == "-w") && len(args) >= 2 && args[1] != "" && !strings.HasPrefix(args[1], "-") {
				args = args[2:]
			} else if (strings.HasPrefix(a, "--prefix=") || strings.HasPrefix(a, "--workspace=")) && !strings.HasSuffix(a, "=") {
				args = args[1:]
			} else {
				break
			}
		}
		if len(args) > 0 && (args[0] == "test" || len(args) >= 2 && args[0] == "run" && args[1] == "test") {
			return "NPM_TEST"
		}
	}
	return "COMMAND"
}

// commandAction parses one literal simple command without expanding or running
// shell input. A chain, pipeline, substitution, redirect or negation has a
// different result meaning and must not be labelled as a successful check.
func commandAction(command string) string {
	argv := literalCommand(command)
	if len(argv) == 3 && (argv[0] == "sh" || argv[0] == "/bin/sh" || argv[0] == "bash" || argv[0] == "/bin/bash") && (argv[1] == "-lc" || argv[1] == "-c") {
		argv = literalCommand(argv[2])
	}
	return CheckAction(argv)
}

func literalCommand(command string) []string {
	if len(command) > 16384 {
		return nil
	}
	f, err := syntax.NewParser(syntax.Variant(syntax.LangPOSIX)).Parse(strings.NewReader(command), "")
	if err != nil || len(f.Stmts) != 1 {
		return nil
	}
	stmt := f.Stmts[0]
	call, ok := stmt.Cmd.(*syntax.CallExpr)
	if !ok || stmt.Background || stmt.Negated || stmt.Coprocess || len(stmt.Redirs) != 0 || len(call.Assigns) != 0 || len(call.Args) > 256 {
		return nil
	}
	argv := []string{}
	for _, word := range call.Args {
		value, ok := literalParts(word.Parts)
		if !ok {
			return nil
		}
		argv = append(argv, value)
	}
	return argv
}

func literalParts(parts []syntax.WordPart) (string, bool) {
	var b strings.Builder
	for _, part := range parts {
		switch p := part.(type) {
		case *syntax.Lit:
			if strings.ContainsAny(p.Value, "\\*?[") {
				return "", false
			}
			b.WriteString(p.Value)
		case *syntax.SglQuoted:
			if p.Dollar {
				return "", false
			}
			b.WriteString(p.Value)
		case *syntax.DblQuoted:
			value, ok := literalParts(p.Parts)
			if !ok || p.Dollar {
				return "", false
			}
			b.WriteString(value)
		default:
			return "", false
		}
	}
	return b.String(), true
}
