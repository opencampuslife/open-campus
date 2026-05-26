package parity

import (
	"fmt"
	"strings"
)

type DiffResult struct {
	Status string
	Diffs  []string
}

func CompareCase(parityCase Case, legacy EndpointResult, shadow EndpointResult) DiffResult {
	diffs := make([]string, 0)
	diffs = append(diffs, compareAllowedStatus(parityCase.Expect.Status.Allowed, legacy, shadow)...)
	diffs = append(diffs, compareStatus(parityCase.Expect.Compare.Status, legacy, shadow)...)
	diffs = append(diffs, compareHeaders(parityCase.Expect.Compare.Headers, parityCase.Expect.Compare.IgnoreHeaders, legacy, shadow)...)
	diffs = append(diffs, compareBody(parityCase.Expect.Compare.Body, legacy, shadow)...)
	status := parityStatus(parityCase.Expect.Latency, legacy, shadow, len(diffs) == 0)
	if status != "passed" && len(diffs) == 0 {
		diffs = append(diffs, fmt.Sprintf("latency ratio exceeded: legacy=%dms shadow=%dms", legacy.LatencyMS, shadow.LatencyMS))
	}
	return DiffResult{Status: status, Diffs: diffs}
}

func compareAllowedStatus(allowed []int, legacy EndpointResult, shadow EndpointResult) []string {
	if len(allowed) == 0 {
		return nil
	}
	okLegacy := containsInt(allowed, legacy.Status)
	okShadow := containsInt(allowed, shadow.Status)
	diffs := make([]string, 0)
	if !okLegacy {
		diffs = append(diffs, fmt.Sprintf("legacy status %d not in allowed set", legacy.Status))
	}
	if !okShadow {
		diffs = append(diffs, fmt.Sprintf("shadow status %d not in allowed set", shadow.Status))
	}
	return diffs
}

func compareStatus(mode string, legacy EndpointResult, shadow EndpointResult) []string {
	if mode == "" || mode == "exact" {
		if legacy.Status != shadow.Status {
			return []string{fmt.Sprintf("status mismatch: legacy=%d shadow=%d", legacy.Status, shadow.Status)}
		}
	}
	return nil
}

func compareHeaders(expectations map[string]string, ignored []string, legacy EndpointResult, shadow EndpointResult) []string {
	legacyHeaders := NormalizeHeaders(legacy.Headers, ignored)
	shadowHeaders := NormalizeHeaders(shadow.Headers, ignored)
	diffs := make([]string, 0)
	for name, mode := range expectations {
		lower := strings.ToLower(name)
		legacyValue, legacyOK := legacyHeaders[lower]
		shadowValue, shadowOK := shadowHeaders[lower]
		if legacyOK != shadowOK {
			diffs = append(diffs, fmt.Sprintf("header presence mismatch for %s", lower))
			continue
		}
		if !legacyOK {
			continue
		}
		switch mode {
		case "compatible":
			if !headerCompatible(lower, legacyValue, shadowValue) {
				diffs = append(diffs, fmt.Sprintf("header mismatch for %s: legacy=%q shadow=%q", lower, legacyValue, shadowValue))
			}
		default:
			if legacyValue != shadowValue {
				diffs = append(diffs, fmt.Sprintf("header mismatch for %s: legacy=%q shadow=%q", lower, legacyValue, shadowValue))
			}
		}
	}
	return diffs
}

func headerCompatible(name string, legacyValue string, shadowValue string) bool {
	if name == "content-type" {
		return strings.HasPrefix(legacyValue, "application/json") && strings.HasPrefix(shadowValue, "application/json") ||
			legacyValue == shadowValue
	}
	return legacyValue == shadowValue
}

func compareBody(expectation BodyCompareExpectation, legacy EndpointResult, shadow EndpointResult) []string {
	switch expectation.Mode {
	case "", "exact":
		if legacy.Body != shadow.Body {
			return []string{"body mismatch"}
		}
	case "json_semantic", "exact_or_json_semantic":
		if NormalizeBody(legacy.Body, expectation.Mode) != NormalizeBody(shadow.Body, expectation.Mode) {
			return []string{"body mismatch"}
		}
	case "json_required_fields":
		return compareJSONRequiredFields(expectation.RequiredFields, legacy, shadow)
	case "status_only":
		return nil
	default:
		if legacy.Body != shadow.Body {
			return []string{"body mismatch"}
		}
	}
	return nil
}

func compareJSONRequiredFields(requiredFields []string, legacy EndpointResult, shadow EndpointResult) []string {
	legacyJSON, legacyErr := decodeJSONObject(legacy.Body)
	shadowJSON, shadowErr := decodeJSONObject(shadow.Body)
	if legacyErr != nil || shadowErr != nil {
		return []string{"body mismatch"}
	}
	diffs := make([]string, 0)
	for _, field := range requiredFields {
		legacyValue, legacyOK := lookupJSONField(legacyJSON, field)
		shadowValue, shadowOK := lookupJSONField(shadowJSON, field)
		if !legacyOK || !shadowOK {
			diffs = append(diffs, fmt.Sprintf("required field missing: %s", field))
			continue
		}
		if legacyValue == nil || shadowValue == nil {
			diffs = append(diffs, fmt.Sprintf("required field empty: %s", field))
		}
	}
	return diffs
}

func parityStatus(latency LatencyExpectation, legacy EndpointResult, shadow EndpointResult, diffsEmpty bool) string {
	if !diffsEmpty {
		return "failed"
	}
	if legacy.LatencyMS <= 0 || shadow.LatencyMS <= 0 || latency.WarnRatio == 0 {
		return "passed"
	}
	ratio := float64(shadow.LatencyMS) / float64(legacy.LatencyMS)
	if latency.FailRatio > 0 && ratio > latency.FailRatio {
		return "failed"
	}
	if ratio > latency.WarnRatio {
		return "warned"
	}
	return "passed"
}

func containsInt(values []int, target int) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
