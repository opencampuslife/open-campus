package gatewayhttp

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"gaokao-agent/control-plane/internal/parity"
)

func TestEvidenceWriterWritesValidJSONL(t *testing.T) {
	dir := t.TempDir()
	ew, err := NewEvidenceWriter(dir)
	if err != nil {
		t.Fatalf("NewEvidenceWriter: %v", err)
	}
	defer ew.Close()
	if !ew.Enabled() {
		t.Fatal("expected writer to be enabled")
	}

	event := ParityEvent{
		Type:          "parity_event",
		Timestamp:     "2026-05-27T12:00:00Z",
		Route:         "POST /api/gaokao/chat",
		Method:        "POST",
		RequestID:     "req_test_001",
		PrimaryStatus: 200,
		ShadowStatus:  200,
		StatusMatch:   true,
		SchemaMatch:   true,
		Result:        "passed",
	}

	if err := ew.WriteParityEvent(event); err != nil {
		t.Fatalf("WriteParityEvent: %v", err)
	}
	ew.Close()

	data, err := os.ReadFile(filepath.Join(dir, evidenceEventsFilename))
	if err != nil {
		t.Fatalf("read events file: %v", err)
	}
	lines := strings.Split(strings.TrimSpace(string(data)), "\n")
	if len(lines) != 1 {
		t.Fatalf("expected 1 line, got %d", len(lines))
	}

	var parsed ParityEvent
	if err := json.Unmarshal([]byte(lines[0]), &parsed); err != nil {
		t.Fatalf("unmarshal event: %v", err)
	}
	if parsed.RequestID != "req_test_001" {
		t.Errorf("expected request_id req_test_001, got %s", parsed.RequestID)
	}
}

func TestEvidenceWriterRedactsSensitiveDiffValues(t *testing.T) {
	dir := t.TempDir()
	ew, err := NewEvidenceWriter(dir)
	if err != nil {
		t.Fatalf("NewEvidenceWriter: %v", err)
	}
	defer ew.Close()

	diffResult := parity.DiffResult{
		Status: "failed",
		Diffs:  []string{"payment amount mismatch", "status mismatch: legacy=200 shadow=500"},
	}
	event := NewParityEvent("POST /api/campus/payment", "POST", "req_002", 200, 500, 50, diffResult)

	if err := ew.WriteParityEvent(event); err != nil {
		t.Fatalf("WriteParityEvent: %v", err)
	}
	ew.Close()

	events, err := ReadParityEvents(ew.EventsPath())
	if err != nil {
		t.Fatalf("ReadParityEvents: %v", err)
	}
	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}
	e := events[0]

	hasRedacted := false
	for _, d := range e.Diffs {
		if d.Path == "[redacted]" {
			hasRedacted = true
			break
		}
	}
	if !hasRedacted {
		t.Errorf("expected sensitive diff to be redacted, got: %v", e.Diffs)
	}

	sensitiveFound := false
	for _, d := range e.Diffs {
		if d.Reason == "payment amount mismatch" && d.Path == "[redacted]" {
			sensitiveFound = true
		}
	}
	if !sensitiveFound {
		t.Errorf("expected 'payment amount mismatch' to be redacted")
	}

	nonSensitiveFound := false
	for _, d := range e.Diffs {
		if d.Reason == "status mismatch: legacy=200 shadow=500" && d.Path != "[redacted]" {
			nonSensitiveFound = true
		}
	}
	if !nonSensitiveFound {
		t.Errorf("expected status mismatch diff to NOT be redacted")
	}
}

func TestEvidenceWriterDisabledPath(t *testing.T) {
	ew, err := NewEvidenceWriter("")
	if err != nil {
		t.Fatalf("NewEvidenceWriter: %v", err)
	}
	if ew.Enabled() {
		t.Fatal("expected writer to be disabled")
	}
	if err := ew.WriteParityEvent(ParityEvent{}); err != nil {
		t.Fatalf("WriteParityEvent should not error when disabled: %v", err)
	}
	if err := ew.Close(); err != nil {
		t.Fatalf("Close should not error when disabled: %v", err)
	}
}

func TestParitySummaryAggregatesPassFailWarnCorrectly(t *testing.T) {
	events := []ParityEvent{
		{Route: "POST /api/gaokao/chat", Result: "passed", StatusMatch: true, SchemaMatch: true},
		{Route: "POST /api/gaokao/chat", Result: "passed", StatusMatch: true, SchemaMatch: true},
		{Route: "POST /api/gaokao/chat", Result: "failed", StatusMatch: false, SchemaMatch: false},
		{Route: "POST /api/gaokao/chat", Result: "warned", StatusMatch: true, SchemaMatch: true},
		{Route: "GET /api/health", Result: "passed", StatusMatch: true, SchemaMatch: true},
	}

	summary := BuildParitySummary(events)

	if len(summary.Routes) != 2 {
		t.Fatalf("expected 2 routes, got %d", len(summary.Routes))
	}

	for _, entry := range summary.Routes {
		switch entry.Route {
		case "POST /api/gaokao/chat":
			if entry.Samples != 4 {
				t.Errorf("expected 4 samples, got %d", entry.Samples)
			}
			if entry.Passed != 2 {
				t.Errorf("expected 2 passed, got %d", entry.Passed)
			}
			if entry.Failed != 1 {
				t.Errorf("expected 1 failed, got %d", entry.Failed)
			}
			if entry.Warned != 1 {
				t.Errorf("expected 1 warned, got %d", entry.Warned)
			}
			if entry.StatusMatchRate != 0.75 {
				t.Errorf("expected status_match_rate 0.75, got %.2f", entry.StatusMatchRate)
			}
			if entry.PassRate != 0.5 {
				t.Errorf("expected pass_rate 0.5, got %.2f", entry.PassRate)
			}
		case "GET /api/health":
			if entry.Samples != 1 {
				t.Errorf("expected 1 sample, got %d", entry.Samples)
			}
			if entry.Passed != 1 {
				t.Errorf("expected 1 passed, got %d", entry.Passed)
			}
		}
	}
}

func TestParitySummaryStatusMatchRateComputed(t *testing.T) {
	events := []ParityEvent{
		{Route: "POST /api/test", Result: "passed", StatusMatch: true, SchemaMatch: true},
		{Route: "POST /api/test", Result: "passed", StatusMatch: true, SchemaMatch: true},
		{Route: "POST /api/test", Result: "failed", StatusMatch: false, SchemaMatch: false},
	}

	summary := BuildParitySummary(events)
	if len(summary.Routes) != 1 {
		t.Fatalf("expected 1 route")
	}

	entry := summary.Routes[0]

	expected := 2.0 / 3.0
	if entry.StatusMatchRate != expected {
		t.Errorf("expected status_match_rate %f, got %f", expected, entry.StatusMatchRate)
	}
}

func TestParitySummaryBusinessMatchRateComputed(t *testing.T) {
	events := []ParityEvent{
		{Route: "POST /api/test", Result: "passed", StatusMatch: true, SchemaMatch: true},
		{Route: "POST /api/test", Result: "passed", StatusMatch: true, SchemaMatch: false},
		{Route: "POST /api/test", Result: "passed", StatusMatch: true, SchemaMatch: true},
	}

	summary := BuildParitySummary(events)
	if len(summary.Routes) != 1 {
		t.Fatalf("expected 1 route")
	}

	entry := summary.Routes[0]
	expected := 2.0 / 3.0
	if entry.SchemaMatchRate != expected {
		t.Errorf("expected schema_match_rate %f, got %f", expected, entry.SchemaMatchRate)
	}
}

func TestEvidenceGatePrivacyViolationMakesGateFail(t *testing.T) {
	summary := ParitySummary{
		Routes: []RouteSummaryEntry{
			{
				Route:             "POST /api/gaokao/chat",
				Samples:           200,
				Passed:            200,
				StatusMatchRate:   1.0,
				SchemaMatchRate:   1.0,
				PassRate:          1.0,
				PrivacyViolations: 1,
			},
		},
	}

	config := EvidenceGateConfig{
		Mode:                  "strict",
		MinSamples:            100,
		MinStatusMatch:        0.99,
		MinSchemaMatch:        0.99,
		MinPassRate:           0.99,
		MaxPrivacyViolations:  0,
	}

	report := BuildGateReport(summary, config)
	if report.Result != "failed" {
		t.Errorf("expected result 'failed' in strict mode with privacy violation, got '%s'", report.Result)
	}

	hasPrivacyFail := false
	for _, f := range report.BlockingFailures {
		if strings.Contains(f, "privacy_violations") {
			hasPrivacyFail = true
		}
	}
	if !hasPrivacyFail {
		t.Errorf("expected blocking failure for privacy_violations")
	}
}

func TestEvidenceGateCriticalRouteInsufficientSamplesFails(t *testing.T) {
	summary := ParitySummary{
		Routes: []RouteSummaryEntry{
			{
				Route:             "POST /api/gaokao/chat",
				Samples:           50,
				Passed:            50,
				StatusMatchRate:   1.0,
				SchemaMatchRate:   1.0,
				PassRate:          1.0,
				PrivacyViolations: 0,
			},
		},
	}

	config := EvidenceGateConfig{
		Mode:                 "strict",
		MinSamples:           100,
		MinStatusMatch:       0.99,
		MinSchemaMatch:       0.99,
		MinPassRate:          0.99,
		MaxPrivacyViolations: 0,
	}

	report := BuildGateReport(summary, config)
	if report.Result != "failed" {
		t.Errorf("expected result 'failed' in strict mode, got '%s'", report.Result)
	}
}

func TestEvidenceGateInsufficientSamplesWarnsInNonBlockingMode(t *testing.T) {
	summary := ParitySummary{
		Routes: []RouteSummaryEntry{
			{
				Route:             "POST /api/gaokao/chat",
				Samples:           50,
				Passed:            50,
				StatusMatchRate:   1.0,
				SchemaMatchRate:   1.0,
				PassRate:          1.0,
				PrivacyViolations: 0,
			},
		},
	}

	config := EvidenceGateConfig{
		Mode:                 "warn",
		MinSamples:           100,
		MinStatusMatch:       0.99,
		MinSchemaMatch:       0.99,
		MinPassRate:          0.99,
		MaxPrivacyViolations: 0,
	}

	report := BuildGateReport(summary, config)
	if report.Result != "warned" {
		t.Errorf("expected result 'warned' in warn mode, got '%s'", report.Result)
	}
}

func TestEvidenceGateFailedParityEventMakesGateFail(t *testing.T) {
	summary := ParitySummary{
		Routes: []RouteSummaryEntry{
			{
				Route:             "POST /api/gaokao/chat",
				Samples:           200,
				Passed:            198,
				Failed:            2,
				StatusMatchRate:   0.99,
				SchemaMatchRate:   0.99,
				PassRate:          0.99,
				PrivacyViolations: 0,
			},
		},
	}

	config := EvidenceGateConfig{
		Mode:                 "strict",
		MinSamples:           100,
		MinStatusMatch:       0.995,
		MinSchemaMatch:       0.995,
		MinPassRate:          0.995,
		MaxPrivacyViolations: 0,
	}

	report := BuildGateReport(summary, config)
	if report.Result != "failed" {
		t.Errorf("expected result 'failed' in strict mode, got '%s'", report.Result)
	}
}

func TestEvidenceGateCleanSummaryPassesGate(t *testing.T) {
	summary := ParitySummary{
		Routes: []RouteSummaryEntry{
			{
				Route:             "POST /api/gaokao/chat",
				Samples:           1000,
				Passed:            1000,
				StatusMatchRate:   1.0,
				SchemaMatchRate:   1.0,
				PassRate:          1.0,
				PrivacyViolations: 0,
			},
		},
	}

	config := EvidenceGateConfig{
		Mode:                 "strict",
		MinSamples:           100,
		MinStatusMatch:       0.995,
		MinSchemaMatch:       0.995,
		MinPassRate:          0.995,
		MaxPrivacyViolations: 0,
	}

	report := BuildGateReport(summary, config)
	if report.Result != "passed" {
		t.Errorf("expected result 'passed', got '%s'", report.Result)
	}
	if len(report.BlockingFailures) != 0 {
		t.Errorf("expected 0 blocking failures, got %d", len(report.BlockingFailures))
	}
}

func TestEvidenceGateOffMode(t *testing.T) {
	summary := ParitySummary{
		Routes: []RouteSummaryEntry{
			{
				Route:             "POST /api/gaokao/chat",
				Samples:           0,
				Passed:            0,
				StatusMatchRate:   0,
				SchemaMatchRate:   0,
				PassRate:          0,
				PrivacyViolations: 5,
			},
		},
	}

	config := EvidenceGateConfig{Mode: "off"}

	report := BuildGateReport(summary, config)
	if report.Result != "disabled" {
		t.Errorf("expected result 'disabled', got '%s'", report.Result)
	}
}
