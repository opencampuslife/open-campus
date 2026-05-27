package gatewayhttp

import (
	"gaokao-agent/control-plane/internal/parity"
)

var defaultParityCriticalFields = []string{
	"ok",
	"error",
	"error.code",
	"status",
}

type ParityBridgeConfig struct {
	Enabled        bool
	IgnoreFields   []string
	IgnoreHeaders  []string
	CriticalFields []string
	RequiredFields []string
	MaxLatencyMs   int64
	ParityLogger   func(route string, result parity.DiffResult)
}

func NewParityCompare(primary *captureResponseWriter, shadow *ShadowResult, routeKey string, config ParityBridgeConfig) parity.DiffResult {
	if !config.Enabled {
		return parity.DiffResult{Status: "passed"}
	}

	parityCase := parity.Case{
		Name:    routeKey,
		Route:   routeKey,
		Expect: parityExpectation(config),
	}

	primaryResult := parity.EndpointResult{
		Status:   primary.StatusCode(),
		Headers:  primary.CapturedHeaders(),
		Body:     string(primary.Body()),
	}
	primaryResult.LatencyMS = 0

	shadowResult := parity.EndpointResult{
		Status:   shadow.StatusCode,
		Headers:  shadow.Headers,
		Body:     string(shadow.Body),
	}
	if shadow.LatencyMs > 0 {
		shadowResult.LatencyMS = shadow.LatencyMs
	}

	if shadow.Error != "" || shadow.TimedOut || shadow.PanicCaught {
		return parity.DiffResult{
			Status: "failed",
			Diffs:  []string{"shadow dispatch error: " + shadow.Error},
		}
	}

	diffResult := parity.CompareCase(parityCase, primaryResult, shadowResult)

	if config.ParityLogger != nil {
		config.ParityLogger(routeKey, diffResult)
	}

	return diffResult
}

func parityExpectation(config ParityBridgeConfig) parity.Expectation {
	requiredFields := config.RequiredFields
	if len(requiredFields) == 0 {
		requiredFields = config.CriticalFields
	}
	if len(requiredFields) == 0 {
		requiredFields = defaultParityCriticalFields
	}

	warnRatio := 0.0
	failRatio := 0.0
	if config.MaxLatencyMs > 0 {
		warnRatio = 0.5
		failRatio = 1.0
	}

	return parity.Expectation{
		Status: parity.StatusExpectation{
			Allowed: []int{200, 201, 204, 301, 302, 400, 401, 403, 404, 422},
		},
		Compare: parity.CompareExpectation{
			Status:        "exact",
			IgnoreHeaders: config.IgnoreHeaders,
			Body: parity.BodyCompareExpectation{
				Mode:           "json_required_fields",
				RequiredFields: requiredFields,
			},
		},
		Latency: parity.LatencyExpectation{
			WarnRatio: warnRatio,
			FailRatio: failRatio,
		},
	}
}
