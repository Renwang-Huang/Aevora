package capture

import (
	"github.com/Renwang-Huang/Aevora/go-runtime/internal/wire"
	"strings"
)

// memoryEcho identifies complete public Aevora response shapes. It is only a
// de-duplication hint; it does not authenticate the caller or its contents.
// Mixed output is intentionally retained when it cannot be classified safely.
func memoryEcho(value any) bool {
	if text, ok := value.(string); ok {
		decoded, err := wire.Decode([]byte(text), MaxInput)
		if err != nil {
			return false
		}
		return memoryEcho(decoded)
	}
	object, ok := value.(map[string]any)
	if !ok {
		return false
	}
	if object["schema_version"] == "aevora.cli-response/1" && object["status"] == "COMPLETED" {
		return memoryEcho(object["result"])
	}
	_, observations := object["observations"].([]any)
	if object["authority"] == "UNTRUSTED_OBSERVATIONS_ONLY" && observations {
		return true
	}
	_, sources := object["sources"].([]any)
	if object["authority"] == "UNTRUSTED_SOURCES_ONLY" && sources {
		return true
	}
	_, candidates := object["candidates"].([]any)
	query, _ := object["query_id"].(string)
	version, _ := object["mcp_version"].(string)
	if candidates && strings.HasPrefix(query, "query:") && strings.HasPrefix(version, "aevora.mcp/") && object["context_authority"] == "TRUSTED_PINNED_PUBLIC_FACTS_ONLY" {
		return true
	}
	disclosure, _ := object["disclosure"].(string)
	experience, _ := object["experience_id"].(string)
	if strings.HasPrefix(disclosure, "PUBLIC_ALLOWLIST_PROJECTION;") && strings.HasPrefix(experience, "experience:") {
		return true
	}
	candidate, _ := object["candidate"].(map[string]any)
	head, _ := object["head"].(map[string]any)
	id, _ := candidate["id"].(string)
	return strings.HasPrefix(id, "candidate:") && head["candidate_id"] == id && candidate["body"] != nil
}
