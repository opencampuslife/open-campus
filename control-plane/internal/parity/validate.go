package parity

import (
	"fmt"
	"strings"
)

var (
	allowedCategories = map[string]struct{}{
		"deterministic_error":      {},
		"deterministic_policy":     {},
		"nondeterministic_success": {},
	}
	allowedSources = map[string]struct{}{
		"handcrafted":            {},
		"sanitized_real_traffic": {},
	}
	allowedBodyCompareModes = map[string]struct{}{
		"":                       {},
		"exact":                  {},
		"json_semantic":          {},
		"exact_or_json_semantic": {},
		"status_only":            {},
		"json_required_fields":   {},
	}
)

func ValidateFixture(fixture *Fixture) error {
	if fixture == nil {
		return fmt.Errorf("fixture is required")
	}
	if len(fixture.Cases) == 0 {
		return fmt.Errorf("fixture must contain at least one case")
	}
	seenNames := make(map[string]struct{}, len(fixture.Cases))
	for index, parityCase := range fixture.Cases {
		if err := ValidateCase(parityCase); err != nil {
			return fmt.Errorf("case[%d] %s: %w", index, parityCase.Name, err)
		}
		if _, exists := seenNames[parityCase.Name]; exists {
			return fmt.Errorf("duplicate case name %q", parityCase.Name)
		}
		seenNames[parityCase.Name] = struct{}{}
	}
	return nil
}

func ValidateCase(parityCase Case) error {
	if strings.TrimSpace(parityCase.Name) == "" {
		return fmt.Errorf("name is required")
	}
	if !containsKey(allowedCategories, parityCase.Category) {
		return fmt.Errorf("unsupported category %q", parityCase.Category)
	}
	if !containsKey(allowedSources, parityCase.Source) {
		return fmt.Errorf("unsupported source %q", parityCase.Source)
	}
	if strings.TrimSpace(parityCase.Method) == "" {
		return fmt.Errorf("method is required")
	}
	if strings.TrimSpace(parityCase.Path) == "" {
		return fmt.Errorf("path is required")
	}
	if strings.TrimSpace(parityCase.Route) == "" {
		return fmt.Errorf("route is required")
	}
	if strings.TrimSpace(parityCase.ReviewedRoute()) != parityCase.Route {
		return fmt.Errorf("route must equal %s %s", strings.ToUpper(strings.TrimSpace(parityCase.Method)), strings.TrimSpace(parityCase.PathWithoutQuery()))
	}
	if parityCase.Body != "" && parityCase.BodyJSON != nil {
		return fmt.Errorf("body and body_json are mutually exclusive")
	}
	if !parityCase.Privacy.Sanitized {
		return fmt.Errorf("privacy.sanitized must be true")
	}
	if parityCase.Privacy.ContainsPII {
		return fmt.Errorf("privacy.contains_pii must be false")
	}
	if strings.TrimSpace(parityCase.Privacy.ReviewedBy) == "" {
		return fmt.Errorf("privacy.reviewed_by is required")
	}
	if parityCase.Source == "sanitized_real_traffic" && !parityCase.Privacy.Sanitized {
		return fmt.Errorf("sanitized_real_traffic case must set privacy.sanitized=true")
	}
	if len(parityCase.Expect.Status.Allowed) == 0 {
		return fmt.Errorf("expect.status.allowed must not be empty")
	}
	if !containsKey(allowedBodyCompareModes, parityCase.Expect.Compare.Body.Mode) {
		return fmt.Errorf("unsupported body compare mode %q", parityCase.Expect.Compare.Body.Mode)
	}
	if parityCase.Expect.Compare.Body.Mode == "json_required_fields" && len(parityCase.Expect.Compare.Body.RequiredFields) == 0 {
		return fmt.Errorf("json_required_fields requires at least one required field")
	}
	return nil
}

func containsKey(values map[string]struct{}, target string) bool {
	_, ok := values[target]
	return ok
}

func (parityCase Case) ReviewedRoute() string {
	return strings.ToUpper(strings.TrimSpace(parityCase.Method)) + " " + parityCase.PathWithoutQuery()
}

func (parityCase Case) PathWithoutQuery() string {
	path := strings.TrimSpace(parityCase.Path)
	if index := strings.Index(path, "?"); index >= 0 {
		return path[:index]
	}
	return path
}
