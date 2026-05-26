package contract

import (
	"fmt"
	"regexp"
	"strings"
)

var migrationWavePattern = regexp.MustCompile(`^phase_[0-9]+$`)

func Validate(loaded *Contract) error {
	if loaded == nil {
		return fmt.Errorf("contract violation: nil contract")
	}
	if loaded.Version == 0 {
		return fmt.Errorf("contract violation: version is required")
	}
	if strings.TrimSpace(loaded.FrozenSource) == "" {
		return fmt.Errorf("contract violation: frozen_source is required")
	}
	if len(loaded.Routes) == 0 {
		return fmt.Errorf("contract violation: routes must not be empty")
	}
	seen := make(map[string]struct{}, len(loaded.Routes))
	for index, route := range loaded.Routes {
		if err := validateRoute(index, route); err != nil {
			return err
		}
		key := route.Method + " " + route.Path
		if _, ok := seen[key]; ok {
			return fmt.Errorf("contract violation: duplicate route %s", key)
		}
		seen[key] = struct{}{}
	}
	return nil
}

func validateRoute(index int, route Route) error {
	prefix := fmt.Sprintf("contract violation: routes[%d]", index)
	if !knownMethod(route.Method) {
		return fmt.Errorf("%s unknown method %q", prefix, route.Method)
	}
	if !strings.HasPrefix(route.Path, "/") {
		return fmt.Errorf("%s path must start with /", prefix)
	}
	if strings.TrimSpace(route.Owner) == "" {
		return fmt.Errorf("%s owner is required", prefix)
	}
	if route.Surface != "public" && route.Surface != "internal" {
		return fmt.Errorf("%s surface must be public or internal", prefix)
	}
	if route.Visibility != "" && route.Visibility != route.Surface {
		return fmt.Errorf("%s visibility must match surface", prefix)
	}
	if !knownAuth(route.Auth) {
		return fmt.Errorf("%s unknown auth %q", prefix, route.Auth)
	}
	if route.CSRF != "required" && route.CSRF != "none" {
		return fmt.Errorf("%s csrf must be required or none", prefix)
	}
	if strings.TrimSpace(route.RateLimit) == "" {
		return fmt.Errorf("%s rate_limit is required", prefix)
	}
	if !migrationWavePattern.MatchString(route.MigrationWave) {
		return fmt.Errorf("%s migration_wave must match phase_N", prefix)
	}
	if route.OpenAPIRef == "" {
		return fmt.Errorf("%s openapi_ref is required", prefix)
	}
	if route.OpenAPI != "" && route.OpenAPI != route.OpenAPIRef {
		return fmt.Errorf("%s openapi must match openapi_ref", prefix)
	}
	if !knownBackend(route.Backend) {
		return fmt.Errorf("%s unknown backend %q", prefix, route.Backend)
	}
	for _, flag := range route.LegacyFlags {
		if flag != "legacy_policy_gap" && flag != "legacy_contract_alias" && flag != "state_changing_get" && flag != "deprecated_compatibility_alias" {
			return fmt.Errorf("%s unknown legacy flag %q", prefix, flag)
		}
	}
	if route.HasLegacyFlag("legacy_policy_gap") && route.LegacyExit == nil {
		return fmt.Errorf("%s legacy_policy_gap requires legacy_exit", prefix)
	}
	if route.LegacyExit != nil {
		if route.LegacyExit.TargetPhase == "" || route.LegacyExit.AllowedUntil == "" || route.LegacyExit.RequiredFix == "" {
			return fmt.Errorf("%s legacy_exit requires target_phase, allowed_until, and required_fix", prefix)
		}
	}
	return nil
}

func knownMethod(method string) bool {
	switch method {
	case "GET", "POST", "PUT", "PATCH", "DELETE":
		return true
	default:
		return false
	}
}

func knownAuth(auth string) bool {
	switch auth {
	case "anonymous", "session", "staff", "signed_token", "trusted_proxy":
		return true
	default:
		return false
	}
}

func knownBackend(backend string) bool {
	switch backend {
	case "legacy_python", "go_native", "python_capability":
		return true
	default:
		return false
	}
}

func LegacyGapCount(loaded *Contract) int {
	count := 0
	if loaded == nil {
		return count
	}
	for _, route := range loaded.Routes {
		if route.HasLegacyFlag("legacy_policy_gap") {
			count++
		}
	}
	return count
}

func DeprecatedCompatibilityAliasCount(loaded *Contract) int {
	count := 0
	if loaded == nil {
		return count
	}
	for _, route := range loaded.Routes {
		if route.HasLegacyFlag("deprecated_compatibility_alias") {
			count++
		}
	}
	return count
}
