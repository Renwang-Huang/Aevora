package domain

import (
	"encoding/json"
	"github.com/Renwang-Huang/Aevora/go-runtime/contracts"
	"github.com/google/jsonschema-go/jsonschema"
)

// Fact registration is release-controlled. Descriptions and structural
// validation never give caller claims the authority of Host observations.
var factCatalog Map
var factSchemas map[string]*jsonschema.Resolved
var facts map[string]bool

func init() {
	raw, err := contracts.Files.ReadFile("facts.json")
	if err != nil {
		panic(err)
	}
	if err = json.Unmarshal(raw, &factCatalog); err != nil {
		panic(err)
	}
	if factCatalog["schema_version"] != "aevora.fact-catalog/1" {
		panic("unsupported fact catalog")
	}
	facts, factSchemas = map[string]bool{}, map[string]*jsonschema.Resolved{}
	for key, value := range M(M(factCatalog["context_schema"])["properties"]) {
		var schema jsonschema.Schema
		raw, err := json.Marshal(value)
		if err != nil {
			panic(err)
		}
		if err = json.Unmarshal(raw, &schema); err != nil {
			panic(err)
		}
		resolved, err := schema.Resolve(nil)
		if err != nil {
			panic(err)
		}
		facts[key], factSchemas[key] = true, resolved
	}
}

func FactCatalog() Map {
	raw, _ := json.Marshal(factCatalog)
	var out Map
	json.Unmarshal(raw, &out)
	return out
}

func supportCoverage(premises map[string]bool) map[string]bool {
	out := union(premises)
	matched := false
	domains := M(factCatalog["domains"])
	for _, value := range domains {
		domain := M(value)
		for _, key := range A(domain["fact_keys"]) {
			if premises[S(key)] {
				matched = true
				for _, required := range A(domain["support_context_keys"]) {
					out[S(required)] = true
				}
				break
			}
		}
	}
	if !matched {
		for _, required := range A(M(domains[S(factCatalog["default_domain"])])["support_context_keys"]) {
			out[S(required)] = true
		}
	}
	return out
}

func validateFact(key string, value any) error {
	if FactState(Map{key: value}, key) != "KNOWN" {
		return nil
	}
	if schema := factSchemas[key]; schema != nil {
		// The schema library accepts standard JSON numbers, not codec tokens.
		raw, err := json.Marshal(value)
		if err != nil {
			return ErrInvalid
		}
		var instance any
		if json.Unmarshal(raw, &instance) != nil || schema.Validate(instance) != nil {
			return ErrInvalid
		}
	}
	return nil
}
