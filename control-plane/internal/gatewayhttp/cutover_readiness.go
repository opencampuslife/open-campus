package gatewayhttp

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type PhaseReport struct {
	Route                   string  `json:"route"`
	Phase                   string  `json:"phase"`
	Percent                 int     `json:"percent"`
	StartedAt               string  `json:"started_at"`
	EndedAt                 string  `json:"ended_at"`
	Samples                 int     `json:"samples"`
	CandidateRequests       int     `json:"candidate_requests"`
	LegacyRequests          int     `json:"legacy_requests"`
	Candidate5xxRate        float64 `json:"candidate_5xx_rate"`
	Legacy5xxRate           float64 `json:"legacy_5xx_rate"`
	Candidate4xxRate        float64 `json:"candidate_4xx_rate"`
	Legacy4xxRate           float64 `json:"legacy_4xx_rate"`
	CandidateP95Ms          float64 `json:"candidate_p95_ms"`
	LegacyP95Ms             float64 `json:"legacy_p95_ms"`
	CandidateErrorRateDelta float64 `json:"candidate_error_rate_delta"`
	P95LatencyDeltaMs       float64 `json:"p95_latency_delta_ms"`
	PrivacyViolations       int     `json:"privacy_violations"`
	BusinessMatchRate       float64 `json:"business_match_rate"`
	Result                  string  `json:"result"`
}

type ReadinessConfig struct {
	RequiredPhases            []int
	MaxCandidate5xxDelta      float64
	MaxP95LatencyDeltaMs      float64
	ParityGateRequired        bool
	PrivacyGateRequired       bool
	RollbackPlanPath          string
	OwnerApprovalPath         string
	HighRiskRoutes            map[string]bool
	HighRiskBusinessMatchRate float64
	Mode                      string
}

type RouteReadiness struct {
	Route          string         `json:"route"`
	GeneratedAt    string         `json:"generated_at"`
	CurrentMode    string         `json:"current_mode"`
	TargetMode     string         `json:"target_mode"`
	RequiredPhases []int          `json:"required_phases"`
	PhaseResults   map[int]string `json:"phase_results"`
	ParityGate     string         `json:"parity_gate"`
	PrivacyGate    string         `json:"privacy_gate"`
	RollbackPlan   string         `json:"rollback_plan"`
	OwnerApproval  string         `json:"owner_approval"`
	Result         string         `json:"result"`
	Reasons        []string       `json:"reasons,omitempty"`
}

var defaultRequiredPhases = []int{1, 5, 25, 50}

func DefaultReadinessConfig() ReadinessConfig {
	return ReadinessConfig{
		RequiredPhases:            defaultRequiredPhases,
		MaxCandidate5xxDelta:      0.001,
		MaxP95LatencyDeltaMs:      20,
		ParityGateRequired:        true,
		PrivacyGateRequired:       true,
		RollbackPlanPath:          "",
		OwnerApprovalPath:         "",
		HighRiskRoutes:            nil,
		HighRiskBusinessMatchRate: 0.995,
		Mode:                      "strict",
	}
}

const readinessReportFilename = "cutover_readiness_report.json"

func EvaluateRouteReadiness(route string, phaseReports []PhaseReport, paritySummary ParitySummary, gateReport GateReport, config ReadinessConfig) RouteReadiness {
	report := RouteReadiness{
		Route:          route,
		GeneratedAt:    time.Now().UTC().Format(time.RFC3339),
		CurrentMode:    "percent_canary",
		TargetMode:     "go_primary",
		RequiredPhases: config.RequiredPhases,
		PhaseResults:   make(map[int]string),
		ParityGate:     "skipped",
		PrivacyGate:    "skipped",
		RollbackPlan:   "missing",
		OwnerApproval:  "missing",
		Result:         "passed",
		Reasons:        make([]string, 0),
	}

	routeReports := filterPhaseReportsForRoute(phaseReports, route)

	for _, percent := range config.RequiredPhases {
		phaseStatus, found := lookupPhaseStatus(routeReports, percent)
		if !found {
			report.PhaseResults[percent] = "missing"
			report.Reasons = append(report.Reasons, fmt.Sprintf("missing %d_percent phase report", percent))
			continue
		}
		report.PhaseResults[percent] = phaseStatus
		if phaseStatus != "passed" {
			report.Reasons = append(report.Reasons, fmt.Sprintf("%d_percent phase %s", percent, phaseStatus))
		}
	}

	if config.ParityGateRequired {
		report.ParityGate = evaluateParityGate(route, paritySummary, gateReport, config)
		if report.ParityGate != "passed" {
			report.Reasons = append(report.Reasons, fmt.Sprintf("parity gate %s", report.ParityGate))
		}
	}

	if config.PrivacyGateRequired {
		report.PrivacyGate = evaluatePrivacyGate(routeReports, paritySummary, config)
		if report.PrivacyGate != "passed" {
			report.Reasons = append(report.Reasons, fmt.Sprintf("privacy gate %s", report.PrivacyGate))
		}
	}

	if config.RollbackPlanPath != "" {
		report.RollbackPlan = checkFileExists(config.RollbackPlanPath)
	} else {
		report.RollbackPlan = "not_configured"
	}
	if report.RollbackPlan != "exists" && report.RollbackPlan != "not_configured" {
		report.Reasons = append(report.Reasons, "rollback plan missing")
	}

	if config.OwnerApprovalPath != "" {
		report.OwnerApproval = checkFileExists(config.OwnerApprovalPath)
	} else {
		report.OwnerApproval = "not_configured"
	}
	if report.OwnerApproval != "exists" && report.OwnerApproval != "not_configured" {
		report.Reasons = append(report.Reasons, "owner approval missing")
	}

	isHighRisk := config.HighRiskRoutes != nil && config.HighRiskRoutes[route]
	for _, pr := range routeReports {
		if isHighRisk && pr.BusinessMatchRate < config.HighRiskBusinessMatchRate {
			report.Reasons = append(report.Reasons,
				fmt.Sprintf("high-risk route %s: business_match_rate %.3f below threshold %.3f",
					route, pr.BusinessMatchRate, config.HighRiskBusinessMatchRate))
		}

		if pr.CandidateErrorRateDelta > config.MaxCandidate5xxDelta {
			report.Reasons = append(report.Reasons,
				fmt.Sprintf("candidate 5xx delta %.3f exceeds threshold %.3f at %s phase",
					pr.CandidateErrorRateDelta, config.MaxCandidate5xxDelta, pr.Phase))
		}

		if pr.P95LatencyDeltaMs > config.MaxP95LatencyDeltaMs {
			report.Reasons = append(report.Reasons,
				fmt.Sprintf("p95 latency delta %.1fms exceeds threshold %.1fms at %s phase",
					pr.P95LatencyDeltaMs, config.MaxP95LatencyDeltaMs, pr.Phase))
		}

		if pr.PrivacyViolations > 0 {
			report.Reasons = append(report.Reasons,
				fmt.Sprintf("privacy violations %d at %s phase", pr.PrivacyViolations, pr.Phase))
		}
	}

	if len(report.Reasons) > 0 {
		report.Result = "failed"
		if config.Mode == "warn" {
			report.Result = "warned"
		}
	}

	return report
}

func filterPhaseReportsForRoute(reports []PhaseReport, route string) []PhaseReport {
	filtered := make([]PhaseReport, 0)
	for _, r := range reports {
		if r.Route == route || r.Route == "" {
			filtered = append(filtered, r)
		}
	}
	return filtered
}

func lookupPhaseStatus(reports []PhaseReport, percent int) (string, bool) {
	for _, r := range reports {
		if r.Percent == percent {
			return r.Result, true
		}
	}
	return "", false
}

func evaluateParityGate(route string, summary ParitySummary, gateReport GateReport, config ReadinessConfig) string {
	if gateReport.Result == "disabled" || gateReport.Result == "" {
		return "skipped"
	}
	if gateReport.Result == "failed" {
		return "failed"
	}
	if gateReport.Result == "warned" && config.Mode == "strict" {
		return "failed"
	}
	if gateReport.Result == "warned" && config.Mode == "warn" {
		return "warned"
	}
	for _, entry := range summary.Routes {
		if entry.Route == route {
			if entry.Result == "failed" {
				return "failed"
			}
			if entry.Result == "warned" && config.Mode == "strict" {
				return "failed"
			}
		}
	}
	return "passed"
}

func evaluatePrivacyGate(reports []PhaseReport, summary ParitySummary, config ReadinessConfig) string {
	for _, pr := range reports {
		if pr.PrivacyViolations > 0 {
			return "failed"
		}
	}
	for _, entry := range summary.Routes {
		if entry.PrivacyViolations > 0 {
			return "failed"
		}
	}
	return "passed"
}

func checkFileExists(path string) string {
	if strings.TrimSpace(path) == "" {
		return "missing"
	}
	info, err := os.Stat(path)
	if err != nil {
		return "missing"
	}
	if info.IsDir() {
		return "exists"
	}
	if info.Size() > 0 {
		return "exists"
	}
	return "empty"
}

func WriteReadinessReport(report RouteReadiness, outputDir string) error {
	if outputDir == "" {
		return fmt.Errorf("output directory is empty")
	}
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("create output directory: %w", err)
	}
	path := filepath.Join(outputDir, readinessReportFilename)
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal readiness report: %w", err)
	}
	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("write readiness report: %w", err)
	}
	return nil
}

func WriteReadinessReports(reports []RouteReadiness, outputDir string) error {
	if outputDir == "" {
		return fmt.Errorf("output directory is empty")
	}
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("create output directory: %w", err)
	}
	for _, report := range reports {
		path := filepath.Join(outputDir, fmt.Sprintf("cutover_readiness_%s.json", sanitizeRouteFilename(report.Route)))
		data, err := json.MarshalIndent(report, "", "  ")
		if err != nil {
			return fmt.Errorf("marshal readiness report for %s: %w", report.Route, err)
		}
		if err := os.WriteFile(path, data, 0644); err != nil {
			return fmt.Errorf("write readiness report for %s: %w", report.Route, err)
		}
	}
	return nil
}

func sanitizeRouteFilename(route string) string {
	r := strings.NewReplacer("/", "_", " ", "_", "{", "", "}", "")
	return strings.ToLower(r.Replace(route))
}

func EvaluateAllRoutesFromEvidence(evidenceDir string, config ReadinessConfig) ([]RouteReadiness, error) {
	eventsPath := filepath.Join(evidenceDir, evidenceEventsFilename)
	events, err := ReadParityEvents(eventsPath)
	if err != nil {
		return nil, fmt.Errorf("read parity events: %w", err)
	}
	summary := BuildParitySummary(events)
	gateConfig := EvidenceGateConfig{
		Mode:             config.Mode,
		MinSamples:       100,
		MinStatusMatch:   0.995,
		MinSchemaMatch:   0.995,
		MinPassRate:      0.995,
		MaxPrivacyViolations: 0,
	}
	gateReport := BuildGateReport(summary, gateConfig)

	routeSet := make(map[string]bool)
	for _, event := range events {
		routeSet[event.Route] = true
	}

	var allReports []RouteReadiness
	for route := range routeSet {
		report := EvaluateRouteReadiness(route, nil, summary, gateReport, config)
		allReports = append(allReports, report)
	}
	return allReports, nil
}
