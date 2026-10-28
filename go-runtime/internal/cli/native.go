package cli

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/codec"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/domain"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/engine"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/host"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/local"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/native"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/platform"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/storage"
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"github.com/google/uuid"
	"github.com/spf13/cobra"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type operationError struct{ status, id, code string }

func (e *operationError) Error() string         { return e.code }
func object(raw string) (map[string]any, error) { return wire.Decode([]byte(raw), wire.MaxMessage) }
func emitOperation(cmd *cobra.Command, response map[string]any) error {
	if response["status"] != "COMPLETED" {
		return &operationError{domain.S(response["status"]), domain.S(response["operation_id"]), domain.S(response["code"])}
	}
	result := response["result"]
	if raw, ok := result.(json.RawMessage); ok {
		value, e := codec.Parse(raw)
		if e != nil {
			return e
		}
		result = value
	}
	return json.NewEncoder(cmd.OutOrStdout()).Encode(map[string]any{"schema_version": "aevora.cli-response/1", "status": "COMPLETED", "operation_id": response["operation_id"], "result": result})
}
func trustedCall(ctx context.Context, p host.Profile, run, operation string, args map[string]any) (map[string]any, error) {
	if p.Database.Kind != "sqlite" {
		return nil, errors.New("AEVORA_NATIVE_CONFIG_REQUIRED")
	}
	response, e := host.ManagementCall(ctx, p, run, operation, args)
	if e == nil {
		return response, nil
	}
	if e.Error() != "AEVORA_HOST_UNAVAILABLE" {
		return nil, e
	}
	if ctx.Err() != nil {
		return nil, ctx.Err()
	}
	owner, e := host.Own(p)
	if e != nil {
		return nil, e
	}
	defer owner.Close()
	s, e := storage.Open(ctx, p.Database.Path, storage.Options{Owner: owner})
	if e != nil {
		return nil, e
	}
	if run == "" {
		run = "host-admin-" + uuid.NewString()
	}
	scope := host.Scope(p, run, false)
	if operation != "query" && operation != "context" {
		scope.Facts = json.RawMessage(`{}`)
		scope.FactsSource = "trusted_host_management"
	}
	r, e := native.NewConfigured(ctx, s, scope, p.Retrieval, p.Reranker)
	if e != nil {
		s.Close()
		return nil, e
	}
	defer r.Close()
	return host.OfflineCall(ctx, p, run, operation, args, r)
}
func addNativeCommands(c *cobra.Command, profilePath *string) {
	var dataDir, factsText string
	var port int
	initCmd := &cobra.Command{Use: "init", Short: "Create a private local SQLite project without external services", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		path := *profilePath
		if path == "" {
			path = host.ProfilePath()
		}
		if !filepath.IsAbs(path) || !filepath.IsAbs(dataDir) {
			return engine.ErrInvalid
		}
		if _, e := os.Lstat(path); !os.IsNotExist(e) {
			return errors.New("AEVORA_PROJECT_ALREADY_EXISTS")
		}
		facts, e := object(factsText)
		if e != nil {
			return e
		}
		if e = domain.NormalizeContext(facts, true); e != nil {
			return e
		}
		if port < 1024 || port > 65535 {
			return engine.ErrInvalid
		}
		if e = platform.PrivateDir(filepath.Dir(path), true); e != nil {
			return e
		}
		if e = platform.PrivateDir(dataDir, true); e != nil {
			return e
		}
		database := filepath.Join(dataDir, "experience.db")
		s, e := storage.Open(cmd.Context(), database, storage.Options{Create: true})
		if e != nil {
			return e
		}
		if e = s.Close(); e != nil {
			return e
		}
		p := host.Profile{Schema: "aevora.host-config/2"}
		p.Database.Kind, p.Database.Path = "sqlite", database
		p.Console.Port = port
		p.Session.Facts, e = codec.Canonical(facts)
		if e != nil {
			return e
		}
		id := host.BackendID(p)
		if len(id) != 64 {
			return platform.ErrUnsafe
		}
		p.Session.Root = filepath.Join(platform.OwnershipHome(), "aevora", "sessions", id[:12])
		if e = platform.PrivateDir(p.Session.Root, true); e != nil {
			return e
		}
		raw, e := json.MarshalIndent(p, "", "  ")
		if e != nil {
			return e
		}
		if e = platform.Exclusive(path, raw); e != nil {
			return e
		}
		return json.NewEncoder(cmd.OutOrStdout()).Encode(map[string]any{"status": "INITIALIZED", "config": path, "database": database, "next_step": "Run aevora serve, then aevora mcp-config. Empty projects require no seed data."})
	}}
	initCmd.Flags().StringVar(&dataDir, "data-dir", host.DefaultDataDir(), "Private Aevora data directory; existing databases are preserved")
	initCmd.Flags().StringVar(&factsText, "facts", "{}", "Host-pinned public facts JSON; missing facts remain unknown")
	initCmd.Flags().IntVar(&port, "port", 17805, "Loopback Console port")
	c.AddCommand(initCmd)
	loadProfile := func() (host.Profile, error) {
		if *profilePath == "" {
			dir, err := os.Getwd()
			if err != nil {
				return host.Profile{}, err
			}
			project, err := local.SelectWorkspace(dir)
			if err != nil {
				return host.Profile{}, err
			}
			*profilePath = project.Profile
		}
		return host.Load(*profilePath)
	}
	invoke := func(cmd *cobra.Command, run, operation string, args map[string]any) error {
		p, e := loadProfile()
		if e != nil {
			return e
		}
		response, e := trustedCall(cmd.Context(), p, run, operation, args)
		if e != nil {
			return e
		}
		return emitOperation(cmd, response)
	}
	workflow := &cobra.Command{Use: "candidate", Short: "Understand a candidate and prepare a new immutable bounded proposal"}
	var policyName, policySource, policyScope, policyState, policyOutput string
	makePolicy := &cobra.Command{Use: "automation-policy", Short: "Create a standing protected policy; preserve any existing file", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		p, err := loadProfile()
		if err != nil {
			return err
		}
		if p.Database.Kind != "sqlite" || !filepath.IsAbs(policyOutput) {
			return engine.ErrInvalid
		}
		source, err := domain.LoadPolicy(policySource)
		if err != nil {
			return err
		}
		scope, err := object(policyScope)
		if err != nil {
			return err
		}
		policy := domain.Map{"schema_version": domain.AutomationPolicyVersion, "policy_id": policyName, "backend_id": host.BackendID(p), "source_policy_sha256": domain.H(source), "scope": scope, "target_state": policyState}
		if err = domain.ValidateAutomationPolicy(policy); err != nil {
			return err
		}
		if err = platform.PrivateDir(filepath.Dir(policyOutput), true); err != nil {
			return err
		}
		raw, err := codec.Canonical(policy)
		if err != nil {
			return err
		}
		if err = platform.Exclusive(policyOutput, raw); err != nil {
			return err
		}
		return output(cmd, map[string]any{"status": "AUTOMATION_POLICY_CREATED", "policy_id": policyName, "target_state": policyState, "policy_sha256": domain.H(policy), "publication": "NO_CANDIDATE_PROCESSED"})
	}}
	for _, flag := range []struct {
		value      *string
		name, help string
	}{
		{&policyName, "name", "Standing policy name"}, {&policySource, "source-policy", "Protected independent-verifier policy"},
		{&policyScope, "scope", "Allowed publication scope JSON"}, {&policyState, "target-state", "ADMITTED_BOUNDED or PUBLISHED"},
		{&policyOutput, "output", "New private automation policy file"},
	} {
		makePolicy.Flags().StringVar(flag.value, flag.name, "", flag.help)
		_ = makePolicy.MarkFlagRequired(flag.name)
	}
	workflow.AddCommand(makePolicy)
	var autoCandidate, autoHead, autoPolicy, autoSourcePolicy, autoRoot, autoPin string
	automate := &cobra.Command{Use: "automate", Short: "Verify and promote under a standing protected project policy", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		return invoke(cmd, "", "candidate-automate", map[string]any{"candidate_id": autoCandidate, "expected_head_sha256": autoHead, "policy_file": autoPolicy, "source_policy_file": autoSourcePolicy, "evidence_root": autoRoot, "receipt_sha256": autoPin})
	}}
	for _, flag := range []struct {
		value      *string
		name, help string
	}{
		{&autoCandidate, "candidate", "Candidate from the protected verifier job"},
		{&autoHead, "expected-head", "Candidate head pinned before the verifier job"},
		{&autoPolicy, "policy", "Standing protected automation policy"},
		{&autoSourcePolicy, "source-policy", "Protected independent-verifier policy"},
		{&autoRoot, "evidence-root", "Independent verifier artifacts"},
		{&autoPin, "receipt-sha256", "Receipt pin delivered by the trusted job"},
	} {
		automate.Flags().StringVar(flag.value, flag.name, "", flag.help)
		_ = automate.MarkFlagRequired(flag.name)
	}
	workflow.AddCommand(automate)
	var observationLimit int
	var observationMode string
	observations := &cobra.Command{Use: "observations QUERY", Short: "Search public untrusted observations as investigative leads", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		return invoke(cmd, "", "search-observations", map[string]any{"query": args[0], "limit": observationLimit, "mode": observationMode})
	}}
	observations.Flags().IntVar(&observationLimit, "limit", 10, "Maximum 20 untrusted observations")
	observations.Flags().StringVar(&observationMode, "mode", "ranked", "ranked (FTS5) or literal (compatibility)")
	c.AddCommand(observations)
	workflow.AddCommand(&cobra.Command{Use: "plan CANDIDATE", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		return invoke(cmd, "", "candidate-plan", map[string]any{"candidate_id": args[0]})
	}})
	var original, derivedKey, conditions, bounds string
	derive := &cobra.Command{Use: "derive", Short: "Create a new untrusted proposal; preserve the original and its provenance", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		declared, err := object(conditions)
		if err != nil {
			return err
		}
		scope, err := object(bounds)
		if err != nil {
			return err
		}
		return invoke(cmd, "", "candidate-derive", map[string]any{"candidate_id": original, "candidate_key": derivedKey, "necessary_conditions": declared, "scope": scope})
	}}
	derive.Flags().StringVar(&original, "from", "", "Original candidate identity")
	derive.Flags().StringVar(&derivedKey, "key", "", "New candidate key; original content is never overwritten")
	derive.Flags().StringVar(&conditions, "conditions", "{}", "Declared necessary conditions JSON; not verified facts")
	derive.Flags().StringVar(&bounds, "scope", "{}", "Declared scope JSON; not publication authority")
	workflow.AddCommand(derive)
	c.AddCommand(workflow)
	var runID, claims, taskQuery, queryDetail string
	var queryLimit int
	query := &cobra.Command{Use: "query", Short: "Record a query using the project's trusted public facts", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		args, e := object(claims)
		if e != nil {
			return e
		}
		return invoke(cmd, runID, "query", map[string]any{"task_context": args, "query": taskQuery, "limit": queryLimit, "detail": queryDetail})
	}}
	query.Flags().StringVar(&runID, "run-id", "", "Authorized Run; omitted uses the active Run or a fresh offline Run")
	query.Flags().StringVar(&claims, "context", "{}", "Public claims JSON; cannot override trusted facts")
	query.Flags().StringVar(&taskQuery, "query", "", "Public task description for relevant recall; required for recommendations")
	query.Flags().IntVar(&queryLimit, "limit", 5, "Maximum relevant experiences, 1..20")
	query.Flags().StringVar(&queryDetail, "detail", "summary", "summary or full; summaries have a 32 KiB budget")
	c.AddCommand(query)
	c.AddCommand(&cobra.Command{Use: "inspect CANDIDATE", Short: "Read the checked candidate lifecycle", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		return invoke(cmd, "", "inspect", map[string]any{"candidate_id": args[0]})
	}})
	var candidate, state, head, key, reason, principal, expires, scope, source string
	review := &cobra.Command{Use: "review", Short: "Perform an explicit trusted candidate review or publication", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		metadata := map[string]any{}
		if scope != "" {
			value, e := object(scope)
			if e != nil {
				return e
			}
			metadata["scope"] = value
		}
		if source != "" {
			metadata["source_id"], metadata["strength"] = source, "BOUNDED_SUPPORT_NOT_CAUSAL"
		}
		end := expires
		if end == "" {
			end = time.Now().Add(10 * time.Minute).UTC().Format(time.RFC3339Nano)
		}
		return invoke(cmd, "", "review", map[string]any{"candidate_id": candidate, "state": state, "expected_head_sha256": head, "event_key": key, "reason": reason, "principal": principal, "expires_at": end, "metadata": metadata})
	}}
	for _, f := range []struct {
		p                 *string
		name, value, help string
	}{{&candidate, "candidate", "", "Candidate identity"}, {&state, "state", "", "Explicit target lifecycle state"}, {&head, "expected-head", "", "Inspected current head SHA256"}, {&key, "event-key", "", "Stable local key; changed requests require another key"}, {&reason, "reason", "", "Bounded public review reason"}, {&principal, "principal", "host-local", "Trusted operator identity"}, {&expires, "expires-at", "", "RFC3339 review lease; preserve it for exact request retries"}, {&scope, "scope", "", "Reviewed scope JSON for bounded admission"}, {&source, "source", "", "Host-verified SourceVerification identity"}} {
		review.Flags().StringVar(f.p, f.name, f.value, f.help)
	}
	c.AddCommand(review)
	var policyFile, evidenceRoot, receiptPin, sourceCandidate string
	verify := &cobra.Command{Use: "source-project", Short: "Verify an independently authorized receipt and pinned project artifacts", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		return invoke(cmd, "", "source-project", map[string]any{"candidate_id": sourceCandidate, "policy_file": policyFile, "evidence_root": evidenceRoot, "receipt_sha256": receiptPin})
	}}
	verify.Flags().StringVar(&sourceCandidate, "candidate", "", "Candidate identity")
	verify.Flags().StringVar(&policyFile, "policy", "", "Protected Host policy file")
	verify.Flags().StringVar(&evidenceRoot, "evidence-root", "", "Ordinary verifier artifact directory")
	verify.Flags().StringVar(&receiptPin, "receipt-sha256", "", "Receipt pin approved independently by Host")
	c.AddCommand(verify)
	c.AddCommand(&cobra.Command{Use: "feedback SOURCE", Short: "Record an observed verified outcome without inferring adoption", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		return invoke(cmd, "", "feedback", map[string]any{"source_id": args[0]})
	}})
	var destination string
	backup := &cobra.Command{Use: "backup", Short: "Write a consistent SQLite backup to a new private file", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		return invoke(cmd, "", "backup", map[string]any{"destination": destination})
	}}
	backup.Flags().StringVar(&destination, "output", "", "New file in an owned private directory")
	c.AddCommand(backup)
	var newRun, newFacts string
	var proposals bool
	openRun := &cobra.Command{Use: "open-run", Short: "Authorize another Run on the active Host", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		p, e := host.Load(*profilePath)
		if e != nil {
			return e
		}
		value, e := object(newFacts)
		if e != nil {
			return e
		}
		response, e := host.ManagementCall(cmd.Context(), p, newRun, "open-run", map[string]any{"public_context": value, "enable_proposals": proposals})
		if e != nil {
			return e
		}
		return emitOperation(cmd, response)
	}}
	openRun.Flags().StringVar(&newRun, "run-id", "", "Distinct trusted Run identity")
	openRun.Flags().StringVar(&newFacts, "facts", "{}", "Host-approved public facts JSON")
	openRun.Flags().BoolVar(&proposals, "enable-proposals", false, "Allow untrusted proposals in this Run")
	c.AddCommand(openRun)
	var operation, requestRun string
	request := &cobra.Command{Use: "host-request", Hidden: true, Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		raw, e := io.ReadAll(io.LimitReader(cmd.InOrStdin(), wire.MaxMessage+1))
		if e != nil || len(raw) > wire.MaxMessage {
			return engine.ErrInvalid
		}
		args, e := wire.Decode(raw, wire.MaxMessage)
		if e != nil {
			return e
		}
		if strings.TrimSpace(operation) == "" {
			return engine.ErrInvalid
		}
		return invoke(cmd, requestRun, operation, args)
	}}
	request.Flags().StringVar(&operation, "operation", "", "Versioned trusted operation")
	request.Flags().StringVar(&requestRun, "run-id", "", "Authorized Run")
	c.AddCommand(request)
}
