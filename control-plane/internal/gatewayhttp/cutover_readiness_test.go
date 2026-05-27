package gatewayhttp

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func allPhasesPassed(got *PhaseReport) bool { return got.Result == "passed" }

func makeRouteReadinessPhaseReports(route string) []PhaseReport {
	return []PhaseReport{
		{
			Route:                   route,
			Phase:                   "1_percent",
			Percent:                 1,
			Samples:                 3000,
			CandidateRequests:       30,
			LegacyRequests:          2970,
			Candidate5xxRate:        0.0,
			Legacy5xxRate:           0.001,
			CandidateErrorRateDelta: -0.001,
			P95LatencyDeltaMs:       -3,
			CandidateP95Ms:          68,
			LegacyP95Ms:             71,
			PrivacyViolations:       0,
			BusinessMatchRate:       0.998,
			Result:                  "passed",
		},
		{
			Route:                   route,
			Phase:                   "5_percent",
			Percent:                 5,
			Samples:                 5000,
			CandidateRequests:       250,
			LegacyRequests:          4750,
			Candidate5xxRate:        0.0,
			Legacy5xxRate:           0.001,
			CandidateErrorRateDelta: -0.001,
			P95LatencyDeltaMs:       -2,
			CandidateP95Ms:          65,
			LegacyP95Ms:             70,
			PrivacyViolations:       0,
			BusinessMatchRate:       0.997,
			Result:                  "passed",
		},
		{
			Route:                   route,
			Phase:                   "25_percent",
			Percent:                 25,
			Samples:                 12000,
			CandidateRequests:       3000,
			LegacyRequests:          9000,
			Candidate5xxRate:        0.0005,
			Legacy5xxRate:           0.001,
			CandidateErrorRateDelta: -0.0005,
			P95LatencyDeltaMs:       -1,
			CandidateP95Ms:          62,
			LegacyP95Ms:             70,
			PrivacyViolations:       0,
			BusinessMatchRate:       0.996,
			Result:                  "passed",
		},
		{
			Route:                   route,
			Phase:                   "50_percent",
			Percent:                 50,
			Samples:                 20000,
			CandidateRequests:       10000,
			LegacyRequests:          10000,
			Candidate5xxRate:        0.0008,
			Legacy5xxRate:           0.001,
			CandidateErrorRateDelta: -0.0002,
			P95LatencyDeltaMs:       0,
			CandidateP95Ms:          64,
			LegacyP95Ms:             70,
			PrivacyViolations:       0,
			BusinessMatchRate:       0.996,
			Result:                  "passed",
		},
	}
}

func makePassingParitySummary() ParitySummary {
	return ParitySummary{
		Type:        "parity_summary",
		GeneratedAt: "2026-05-27T12:00:00Z",
		Routes: []RouteSummaryEntry{
			{
				Route:             "POST /api/campus/materials/submit",
				Samples:           40000,
				Passed:            39900,
				Failed:            0,
				Warned:            100,
				StatusMatchRate:   0.998,
				SchemaMatchRate:   0.997,
				PassRate:          0.9975,
				PrivacyViolations: 0,
				Result:            "passed",
			},
		},
	}
}

func makePassingGateReport() GateReport {
	return GateReport{
		Type:        "evidence_gate_report",
		GeneratedAt: "2026-05-27T12:00:00Z",
		Mode:        "strict",
		Result:      "passed",
		Summary:     makePassingParitySummary(),
		Conditions: []GateCondition{
			{Route: "POST /api/campus/materials/submit", Condition: "min_samples", Expected: ">= 100", Actual: "40000", Passed: true, Blocking: true},
			{Route: "POST /api/campus/materials/submit", Condition: "status_match_rate", Expected: ">= 0.995", Actual: "0.998", Passed: true, Blocking: true},
			{Route: "POST /api/campus/materials/submit", Condition: "schema_match_rate", Expected: ">= 0.995", Actual: "0.997", Passed: true, Blocking: true},
			{Route: "POST /api/campus/materials/submit", Condition: "pass_rate", Expected: ">= 0.995", Actual: "0.998", Passed: true, Blocking: true},
			{Route: "POST /api/campus/materials/submit", Condition: "privacy_violations", Expected: "<= 0", Actual: "0", Passed: true, Blocking: true},
		},
	}
}

func TestAllRequiredPhasesPassedReadinessPass(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	parity := makePassingParitySummary()
	gate := makePassingGateReport()
	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, parity, gate, config)
	if result.Result != "passed" {
		t.Fatalf("result = %s, want passed; reasons: %v", result.Result, result.Reasons)
	}
	for _, percent := range config.RequiredPhases {
		if status, ok := result.PhaseResults[percent]; !ok || status != "passed" {
			t.Errorf("phase %d%%: status = %s, want passed", percent, status)
		}
	}
	if result.ParityGate != "passed" {
		t.Errorf("parity_gate = %s, want passed", result.ParityGate)
	}
}

func TestMissing25PercentPhaseReadinessFail(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	missing := []PhaseReport{
		{Route: route, Phase: "1_percent", Percent: 1, Result: "passed"},
		{Route: route, Phase: "5_percent", Percent: 5, Result: "passed"},
		{Route: route, Phase: "50_percent", Percent: 50, Result: "passed"},
	}
	config := DefaultReadinessConfig()
	parity := makePassingParitySummary()
	gate := makePassingGateReport()

	result := EvaluateRouteReadiness(route, missing, parity, gate, config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed", result.Result)
	}
	if status, ok := result.PhaseResults[25]; !ok || status != "missing" {
		t.Errorf("phase 25%% status = %s, want missing", status)
	}
	found := false
	for _, reason := range result.Reasons {
		if strings.Contains(reason, "missing 25") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected reason about missing 25_percent, got: %v", result.Reasons)
	}
}

func TestFailedPhaseReadinessFail(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	reports := []PhaseReport{
		{Route: route, Phase: "1_percent", Percent: 1, Result: "passed"},
		{Route: route, Phase: "5_percent", Percent: 5, Result: "failed"},
		{Route: route, Phase: "25_percent", Percent: 25, Result: "passed"},
		{Route: route, Phase: "50_percent", Percent: 50, Result: "passed"},
	}
	config := DefaultReadinessConfig()
	parity := makePassingParitySummary()
	gate := makePassingGateReport()

	result := EvaluateRouteReadiness(route, reports, parity, gate, config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed", result.Result)
	}
	found := false
	for _, reason := range result.Reasons {
		if strings.Contains(reason, "5_percent") && strings.Contains(reason, "failed") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected reason about failed 5_percent, got: %v", result.Reasons)
	}
}

func TestParityGateFailedReadinessFail(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	gate := GateReport{
		Type:        "evidence_gate_report",
		GeneratedAt: "2026-05-27T12:00:00Z",
		Mode:        "strict",
		Result:      "failed",
		Summary:     makePassingParitySummary(),
		Conditions: []GateCondition{
			{Route: route, Condition: "status_match_rate", Expected: ">= 0.995", Actual: "0.800", Passed: false, Blocking: true},
		},
		BlockingFailures: []string{"status_match_rate: expected >= 0.995, actual 0.800"},
	}
	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), gate, config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed", result.Result)
	}
	if result.ParityGate != "failed" {
		t.Errorf("parity_gate = %s, want failed", result.ParityGate)
	}
}

func TestPrivacyViolationReadinessFail(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	phaseReports[1].PrivacyViolations = 3
	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed", result.Result)
	}
	if result.PrivacyGate != "failed" {
		t.Errorf("privacy_gate = %s, want failed", result.PrivacyGate)
	}
	found := false
	for _, reason := range result.Reasons {
		if strings.Contains(reason, "privacy") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected privacy violation reason, got: %v", result.Reasons)
	}
}

func TestP95LatencyDeltaOverThresholdReadinessFail(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	phaseReports[0].P95LatencyDeltaMs = 35.0
	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed", result.Result)
	}
	found := false
	for _, reason := range result.Reasons {
		if strings.Contains(reason, "p95 latency delta") && strings.Contains(reason, "35") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected p95 latency delta reason, got: %v", result.Reasons)
	}
}

func TestCandidate5xxDeltaOverThresholdReadinessFail(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	phaseReports[2].CandidateErrorRateDelta = 0.005
	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed (candidate 5xx delta = 0.005 > 0.001)", result.Result)
	}
	found := false
	for _, reason := range result.Reasons {
		if strings.Contains(reason, "5xx delta") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected 5xx delta reason, got: %v", result.Reasons)
	}
}

func TestMissingRollbackPlanReadinessFail(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	config := DefaultReadinessConfig()
	config.RollbackPlanPath = "/nonexistent/rollback_plan.md"

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed (missing rollback plan)", result.Result)
	}
	if result.RollbackPlan != "missing" {
		t.Errorf("rollback_plan = %s, want missing", result.RollbackPlan)
	}
	found := false
	for _, reason := range result.Reasons {
		if strings.Contains(reason, "rollback") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected rollback plan reason, got: %v", result.Reasons)
	}
}

func TestMissingOwnerApprovalReadinessFail(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	config := DefaultReadinessConfig()
	config.OwnerApprovalPath = "/nonexistent/owner_approval.json"

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed (missing owner approval)", result.Result)
	}
	if result.OwnerApproval != "missing" {
		t.Errorf("owner_approval = %s, want missing", result.OwnerApproval)
	}
	found := false
	for _, reason := range result.Reasons {
		if strings.Contains(reason, "owner approval") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected owner approval reason, got: %v", result.Reasons)
	}
}

func TestPercent100NotTreatedAsGoPrimaryAutomatically(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := []PhaseReport{
		{Route: route, Phase: "100_percent", Percent: 100, Result: "passed"},
	}
	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.TargetMode != "go_primary" {
		t.Errorf("target_mode = %s, want go_primary", result.TargetMode)
	}

	if result.Result == "passed" {
		t.Fatal("should not pass — required phases 1/5/25/50 are missing even though 100% passed")
	}

	missingCount := 0
	for _, percent := range config.RequiredPhases {
		if status, ok := result.PhaseResults[percent]; ok && status == "missing" {
			missingCount++
		}
	}
	if missingCount != 4 {
		t.Errorf("expected 4 missing phases (1/5/25/50), got %d", missingCount)
	}
}

func TestHighRiskRouteRequiresBusinessMatchRate(t *testing.T) {
	route := "POST /api/campus/payment/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	phaseReports[3].BusinessMatchRate = 0.980
	config := DefaultReadinessConfig()
	config.HighRiskRoutes = map[string]bool{route: true}

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed (high-risk route with low business_match_rate)", result.Result)
	}
	found := false
	for _, reason := range result.Reasons {
		if strings.Contains(reason, "business_match_rate") {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected business_match_rate reason, got: %v", result.Reasons)
	}
}

func TestLowRiskRouteDoesNotRequireBusinessMatchRate(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	phaseReports[0].BusinessMatchRate = 0.8
	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "passed" {
		t.Fatalf("result = %s, want passed (low-risk route, business_match_rate not required); reasons: %v", result.Result, result.Reasons)
	}
}

func TestMalformedPhaseReportFailsClosed(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := []PhaseReport{
		{Route: route, Phase: "1_percent", Percent: 1, Result: "passed"},
		{Route: route, Phase: "5_percent", Percent: 5, Result: ""},
		{Route: route, Phase: "25_percent", Percent: 25, Result: "passed"},
		{Route: route, Phase: "50_percent", Percent: 50, Result: "passed"},
	}
	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed (malformed empty-result phase report)", result.Result)
	}
	if status := result.PhaseResults[5]; status == "passed" {
		t.Errorf("phase 5%%: status = %s, expected non-passed (malformed, empty result)", status)
	}
}

func TestReadinessReportWritesMachineReadableJSON(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	config := DefaultReadinessConfig()
	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)

	dir := t.TempDir()
	if err := WriteReadinessReport(result, dir); err != nil {
		t.Fatalf("WriteReadinessReport: %v", err)
	}

	path := filepath.Join(dir, readinessReportFilename)
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read report: %v", err)
	}

	var parsed RouteReadiness
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("unmarshal report: %v", err)
	}
	if parsed.Route != route {
		t.Errorf("route = %s, want %s", parsed.Route, route)
	}
	if parsed.TargetMode != "go_primary" {
		t.Errorf("target_mode = %s, want go_primary", parsed.TargetMode)
	}
	if parsed.Result != "passed" {
		t.Errorf("result = %s, want passed", parsed.Result)
	}
	if len(parsed.RequiredPhases) != 4 {
		t.Errorf("got %d required phases, want 4", len(parsed.RequiredPhases))
	}
	if len(parsed.PhaseResults) != 4 {
		t.Errorf("got %d phase results, want 4", len(parsed.PhaseResults))
	}
	if parsed.ParityGate != "passed" {
		t.Errorf("parity_gate = %s, want passed", parsed.ParityGate)
	}
}

func TestReadinessConfigWarnMode(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	phaseReports[0].CandidateErrorRateDelta = 0.005
	phaseReports[0].P95LatencyDeltaMs = 50
	config := DefaultReadinessConfig()
	config.Mode = "warn"

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "warned" {
		t.Fatalf("result = %s, want warned (warn mode)", result.Result)
	}
	if len(result.Reasons) == 0 {
		t.Fatal("expected non-empty reasons in warn mode")
	}
}

func TestParitySummaryPrivacyViolationInSummary(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	summary := makePassingParitySummary()
	summary.Routes[0].PrivacyViolations = 5

	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, summary, makePassingGateReport(), config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed (privacy violations in summary)", result.Result)
	}
}

func TestParityGateWarnedInStrictMode(t *testing.T) {
	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	gate := GateReport{
		Type:        "evidence_gate_report",
		GeneratedAt: "2026-05-27T12:00:00Z",
		Mode:        "strict",
		Result:      "warned",
		Summary:     makePassingParitySummary(),
	}

	config := DefaultReadinessConfig()
	config.Mode = "strict"

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), gate, config)
	if result.Result != "failed" {
		t.Fatalf("result = %s, want failed (warned parity gate in strict mode)", result.Result)
	}
	if result.ParityGate != "failed" {
		t.Errorf("parity_gate = %s, want failed", result.ParityGate)
	}
}

func TestRollbackPlanExistsInTempDir(t *testing.T) {
	dir := t.TempDir()

	rollbackPath := filepath.Join(dir, "rollback_plan.md")
	if err := os.WriteFile(rollbackPath, []byte("# Rollback Plan"), 0644); err != nil {
		t.Fatal(err)
	}
	approvalPath := filepath.Join(dir, "owner_approval.json")
	if err := os.WriteFile(approvalPath, []byte(`{"approved":true}`), 0644); err != nil {
		t.Fatal(err)
	}

	route := "POST /api/campus/materials/submit"
	phaseReports := makeRouteReadinessPhaseReports(route)
	config := DefaultReadinessConfig()
	config.RollbackPlanPath = rollbackPath
	config.OwnerApprovalPath = approvalPath

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "passed" {
		t.Fatalf("result = %s, want passed; reasons: %v", result.Result, result.Reasons)
	}
	if result.RollbackPlan != "exists" {
		t.Errorf("rollback_plan = %s, want exists", result.RollbackPlan)
	}
	if result.OwnerApproval != "exists" {
		t.Errorf("owner_approval = %s, want exists", result.OwnerApproval)
	}
}

func TestWriteReadinessReportsForMultipleRoutes(t *testing.T) {
	dir := t.TempDir()
	reports := []RouteReadiness{
		{
			Route:         "POST /api/campus/materials/submit",
			GeneratedAt:   "2026-05-27T12:00:00Z",
			TargetMode:    "go_primary",
			Result:        "passed",
			PhaseResults:  map[int]string{1: "passed", 5: "passed", 25: "passed", 50: "passed"},
			RequiredPhases: []int{1, 5, 25, 50},
		},
		{
			Route:         "POST /api/campus/payment/submit",
			GeneratedAt:   "2026-05-27T12:00:00Z",
			TargetMode:    "go_primary",
			Result:        "failed",
			PhaseResults:  map[int]string{1: "passed", 5: "missing"},
			RequiredPhases: []int{1, 5, 25, 50},
			Reasons:       []string{"missing 25_percent phase report"},
		},
	}

	if err := WriteReadinessReports(reports, dir); err != nil {
		t.Fatalf("WriteReadinessReports: %v", err)
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 2 {
		t.Fatalf("expected 2 report files, got %d", len(entries))
	}

	for _, entry := range entries {
		data, err := os.ReadFile(filepath.Join(dir, entry.Name()))
		if err != nil {
			t.Fatal(err)
		}
		var parsed RouteReadiness
		if err := json.Unmarshal(data, &parsed); err != nil {
			t.Fatalf("unmarshal %s: %v", entry.Name(), err)
		}
		if parsed.Route == "" {
			t.Errorf("empty route in %s", entry.Name())
		}
	}
}

func TestDefaultConfigValues(t *testing.T) {
	config := DefaultReadinessConfig()
	if len(config.RequiredPhases) != 4 {
		t.Errorf("expected 4 required phases, got %d", len(config.RequiredPhases))
	}
	if config.RequiredPhases[0] != 1 {
		t.Errorf("phase 0 = %d, want 1", config.RequiredPhases[0])
	}
	if config.MaxCandidate5xxDelta != 0.001 {
		t.Errorf("MaxCandidate5xxDelta = %f, want 0.001", config.MaxCandidate5xxDelta)
	}
	if config.MaxP95LatencyDeltaMs != 20 {
		t.Errorf("MaxP95LatencyDeltaMs = %f, want 20", config.MaxP95LatencyDeltaMs)
	}
	if config.Mode != "strict" {
		t.Errorf("Mode = %s, want strict", config.Mode)
	}
	if config.HighRiskBusinessMatchRate != 0.995 {
		t.Errorf("HighRiskBusinessMatchRate = %f, want 0.995", config.HighRiskBusinessMatchRate)
	}
}

func TestPhaseReportEmptyRouteMatchesAnyRoute(t *testing.T) {
	route := "POST /api/some/endpoint"
	phaseReports := []PhaseReport{
		{Route: "", Phase: "1_percent", Percent: 1, Result: "passed"},
		{Route: "", Phase: "5_percent", Percent: 5, Result: "passed"},
		{Route: "", Phase: "25_percent", Percent: 25, Result: "passed"},
		{Route: "", Phase: "50_percent", Percent: 50, Result: "passed"},
	}
	config := DefaultReadinessConfig()

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "passed" {
		t.Fatalf("result = %s, want passed (empty route matches all); reasons: %v", result.Result, result.Reasons)
	}
}

func TestEmptyConfigFailsClosed(t *testing.T) {
	route := "POST /api/test/endpoint"
	phaseReports := makeRouteReadinessPhaseReports(route)

	config := ReadinessConfig{}
	config.RequiredPhases = defaultRequiredPhases
	config.Mode = "strict"

	result := EvaluateRouteReadiness(route, phaseReports, makePassingParitySummary(), makePassingGateReport(), config)
	if result.Result != "passed" {
		t.Fatalf("result = %s; reasons: %v", result.Result, result.Reasons)
	}
	if result.RollbackPlan != "not_configured" {
		t.Errorf("rollback_plan = %s, want not_configured", result.RollbackPlan)
	}
	if result.OwnerApproval != "not_configured" {
		t.Errorf("owner_approval = %s, want not_configured", result.OwnerApproval)
	}
}
