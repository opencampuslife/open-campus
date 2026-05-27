package gatewayhttp

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"gaokao-agent/control-plane/internal/parity"
)

type ParityEvent struct {
	Type              string              `json:"type"`
	Timestamp         string              `json:"timestamp"`
	Route             string              `json:"route"`
	Method            string              `json:"method"`
	RequestID         string              `json:"request_id"`
	PrimaryStatus     int                 `json:"primary_status"`
	ShadowStatus      int                 `json:"shadow_status"`
	StatusMatch       bool                `json:"status_match"`
	SchemaMatch       bool                `json:"schema_match"`
	LatencyDeltaMS    int64               `json:"latency_delta_ms"`
	Result            string              `json:"result"`
	Diffs             []ParityEventDiff   `json:"diffs"`
	PrivacyViolations []string            `json:"privacy_violations"`
}

type ParityEventDiff struct {
	Path     string `json:"path"`
	Severity string `json:"severity"`
	Reason   string `json:"reason"`
}

type RouteSummaryEntry struct {
	Route             string  `json:"route"`
	Samples           int     `json:"samples"`
	Passed            int     `json:"passed"`
	Failed            int     `json:"failed"`
	Warned            int     `json:"warned"`
	StatusMatchRate   float64 `json:"status_match_rate"`
	SchemaMatchRate   float64 `json:"schema_match_rate"`
	PassRate          float64 `json:"pass_rate"`
	PrivacyViolations int     `json:"privacy_violations"`
	Result            string  `json:"result"`
}

type ParitySummary struct {
	Type        string              `json:"type"`
	GeneratedAt string              `json:"generated_at"`
	Routes      []RouteSummaryEntry `json:"routes"`
}

type EvidenceGateConfig struct {
	Mode             string
	MinSamples       int
	MinStatusMatch   float64
	MinSchemaMatch   float64
	MinPassRate      float64
	MaxPrivacyViolations int
	CriticalRoutes   []string
	RouteCriticality map[string]bool
}

type GateCondition struct {
	Route     string `json:"route"`
	Condition string `json:"condition"`
	Expected  string `json:"expected"`
	Actual    string `json:"actual"`
	Passed    bool   `json:"passed"`
	Blocking  bool   `json:"blocking"`
}

type GateReport struct {
	Type             string          `json:"type"`
	GeneratedAt      string          `json:"generated_at"`
	Mode             string          `json:"mode"`
	Result           string          `json:"result"`
	Summary          ParitySummary   `json:"summary"`
	Conditions       []GateCondition `json:"conditions"`
	BlockingFailures []string        `json:"blocking_failures"`
}

type EvidenceWriter struct {
	mu       sync.Mutex
	dirpath  string
	eventsPath  string
	file     *os.File
	enabled  bool
}

const (
	evidenceEventsFilename  = "parity_events.jsonl"
	evidenceSummaryFilename = "parity_summary.json"
	evidenceGateFilename    = "evidence_gate_report.json"
)

var sensitiveDiffKeywords = []string{
	"amount", "score", "password", "token", "secret", "phone", "name",
	"id_card", "student_id", "email", "address", "identity", "certificate",
}

func NewEvidenceWriter(dirpath string) (*EvidenceWriter, error) {
	if strings.TrimSpace(dirpath) == "" {
		return &EvidenceWriter{enabled: false}, nil
	}
	absDir, err := filepath.Abs(dirpath)
	if err != nil {
		return &EvidenceWriter{enabled: false}, fmt.Errorf("resolve evidence dir: %w", err)
	}
	if err := os.MkdirAll(absDir, 0755); err != nil {
		return &EvidenceWriter{enabled: false}, fmt.Errorf("create evidence dir: %w", err)
	}
	eventsPath := filepath.Join(absDir, evidenceEventsFilename)
	f, err := os.OpenFile(eventsPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return &EvidenceWriter{enabled: false}, fmt.Errorf("open events file: %w", err)
	}
	return &EvidenceWriter{
		dirpath:    absDir,
		eventsPath: eventsPath,
		file:       f,
		enabled:    true,
	}, nil
}

func (ew *EvidenceWriter) WriteParityEvent(event ParityEvent) error {
	if !ew.enabled || ew.file == nil {
		return nil
	}
	line, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal parity event: %w", err)
	}
	ew.mu.Lock()
	defer ew.mu.Unlock()
	if _, err := ew.file.Write(append(line, '\n')); err != nil {
		return fmt.Errorf("write parity event: %w", err)
	}
	return nil
}

func (ew *EvidenceWriter) WriteSummary(summary ParitySummary) error {
	if !ew.enabled {
		return nil
	}
	path := filepath.Join(ew.dirpath, evidenceSummaryFilename)
	data, err := json.MarshalIndent(summary, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal summary: %w", err)
	}
	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("write summary: %w", err)
	}
	return nil
}

func (ew *EvidenceWriter) WriteGateReport(report GateReport) error {
	if !ew.enabled {
		return nil
	}
	path := filepath.Join(ew.dirpath, evidenceGateFilename)
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal gate report: %w", err)
	}
	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("write gate report: %w", err)
	}
	return nil
}

func (ew *EvidenceWriter) Close() error {
	if ew.file != nil {
		return ew.file.Close()
	}
	return nil
}

func (ew *EvidenceWriter) Enabled() bool {
	return ew.enabled
}

func (ew *EvidenceWriter) EventsPath() string {
	return ew.eventsPath
}

func NewParityEvent(routeKey, method, requestID string, primaryStatus, shadowStatus int, shadowLatency int64, diffResult parity.DiffResult) ParityEvent {
	event := ParityEvent{
		Type:              "parity_event",
		Timestamp:         time.Now().UTC().Format(time.RFC3339),
		Route:             routeKey,
		Method:            method,
		RequestID:         requestID,
		PrimaryStatus:     primaryStatus,
		ShadowStatus:      shadowStatus,
		StatusMatch:       primaryStatus == shadowStatus,
		SchemaMatch:       !hasRequiredFieldMissing(diffResult.Diffs),
		LatencyDeltaMS:    shadowLatency,
		Result:            diffResult.Status,
		Diffs:             redactDiffsForEvidence(diffResult.Diffs),
		PrivacyViolations: checkPrivacyViolations(diffResult.Diffs),
	}
	return event
}

func hasRequiredFieldMissing(diffs []string) bool {
	for _, d := range diffs {
		if strings.Contains(d, "required field missing") {
			return true
		}
	}
	return false
}

func redactDiffsForEvidence(diffs []string) []ParityEventDiff {
	result := make([]ParityEventDiff, 0, len(diffs))
	for _, d := range diffs {
		entry := ParityEventDiff{
			Severity: classifyDiffSeverity(d),
			Reason:   d,
		}
		if hasSensitiveContent(d) {
			entry.Path = "[redacted]"
		} else {
			entry.Path = extractDiffPath(d)
		}
		result = append(result, entry)
	}
	return result
}

func classifyDiffSeverity(diff string) string {
	if strings.Contains(diff, "required field") || strings.Contains(diff, "status mismatch") {
		return "critical"
	}
	if strings.Contains(diff, "error") || strings.Contains(diff, "shadow dispatch") || strings.Contains(diff, "timeout") {
		return "critical"
	}
	return "warning"
}

func hasSensitiveContent(diff string) bool {
	lower := strings.ToLower(diff)
	for _, kw := range sensitiveDiffKeywords {
		if strings.Contains(lower, kw) && !strings.Contains(lower, "status") {
			return true
		}
	}
	return false
}

func extractDiffPath(diff string) string {
	return ""
}

func checkPrivacyViolations(diffs []string) []string {
	violations := make([]string, 0)
	for _, d := range diffs {
		if hasSensitiveContent(d) {
			violations = append(violations, "sensitive value in diff")
			break
		}
	}
	return violations
}

func ReadParityEvents(filepath string) ([]ParityEvent, error) {
	f, err := os.Open(filepath)
	if err != nil {
		return nil, fmt.Errorf("open events file: %w", err)
	}
	defer f.Close()

	var events []ParityEvent
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 0, 1024*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var event ParityEvent
		if err := json.Unmarshal([]byte(line), &event); err != nil {
			continue
		}
		events = append(events, event)
	}
	return events, scanner.Err()
}

func BuildParitySummary(events []ParityEvent) ParitySummary {
	routeData := make(map[string]*struct {
		samples           int
		passed            int
		failed            int
		warned            int
		statusMatches     int
		schemaMatches     int
		privacyViolations int
	})

	for _, e := range events {
		rd, ok := routeData[e.Route]
		if !ok {
			rd = new(struct {
				samples           int
				passed            int
				failed            int
				warned            int
				statusMatches     int
				schemaMatches     int
				privacyViolations int
			})
			routeData[e.Route] = rd
		}
		rd.samples++
		if e.StatusMatch {
			rd.statusMatches++
		}
		if e.SchemaMatch {
			rd.schemaMatches++
		}
		if len(e.PrivacyViolations) > 0 {
			rd.privacyViolations++
		}
		switch e.Result {
		case "passed":
			rd.passed++
		case "failed":
			rd.failed++
		case "warned":
			rd.warned++
		}
	}

	entries := make([]RouteSummaryEntry, 0, len(routeData))
	for route, rd := range routeData {
		entry := RouteSummaryEntry{
			Route:             route,
			Samples:           rd.samples,
			Passed:            rd.passed,
			Failed:            rd.failed,
			Warned:            rd.warned,
			StatusMatchRate:   safeRatio(rd.statusMatches, rd.samples),
			SchemaMatchRate:   safeRatio(rd.schemaMatches, rd.samples),
			PassRate:          safeRatio(rd.passed, rd.samples),
			PrivacyViolations: rd.privacyViolations,
			Result:            "passed",
		}
		if rd.failed > 0 {
			entry.Result = "failed"
		} else if rd.warned > 0 {
			entry.Result = "warned"
		}
		entries = append(entries, entry)
	}
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].Route < entries[j].Route
	})

	return ParitySummary{
		Type:        "parity_summary",
		GeneratedAt: time.Now().UTC().Format(time.RFC3339),
		Routes:      entries,
	}
}

func safeRatio(numerator, denominator int) float64 {
	if denominator == 0 {
		return 0
	}
	return float64(numerator) / float64(denominator)
}

func BuildGateReport(summary ParitySummary, config EvidenceGateConfig) GateReport {
	report := GateReport{
		Type:        "evidence_gate_report",
		GeneratedAt: time.Now().UTC().Format(time.RFC3339),
		Mode:        config.Mode,
		Result:      "passed",
		Summary:     summary,
		Conditions:  make([]GateCondition, 0),
		BlockingFailures: make([]string, 0),
	}

	if config.Mode == "" || config.Mode == "off" {
		report.Result = "disabled"
		return report
	}

	for _, entry := range summary.Routes {
		isCritical := config.RouteCriticality[entry.Route] || containsString(config.CriticalRoutes, entry.Route)
		if len(config.CriticalRoutes) == 0 {
			isCritical = true
		}
		report.Conditions = append(report.Conditions,
			evaluateMinSamples(entry, config.MinSamples, isCritical),
			evaluateStatusMatchRate(entry, config.MinStatusMatch, isCritical),
			evaluateSchemaMatchRate(entry, config.MinSchemaMatch, isCritical),
			evaluatePassRate(entry, config.MinPassRate, isCritical),
			evaluatePrivacyViolations(entry, config.MaxPrivacyViolations, isCritical),
		)
	}

	for _, cond := range report.Conditions {
		if !cond.Passed && cond.Blocking {
			report.BlockingFailures = append(report.BlockingFailures,
				fmt.Sprintf("%s: %s (expected: %s, actual: %s)", cond.Route, cond.Condition, cond.Expected, cond.Actual))
		}
	}

	if len(report.BlockingFailures) > 0 {
		if config.Mode == "strict" {
			report.Result = "failed"
		} else {
			report.Result = "warned"
		}
	}

	return report
}

func evaluateMinSamples(entry RouteSummaryEntry, minSamples int, blocking bool) GateCondition {
	passed := entry.Samples >= minSamples
	cond := GateCondition{
		Route:     entry.Route,
		Condition: "min_samples",
		Expected:  fmt.Sprintf(">= %d", minSamples),
		Actual:    fmt.Sprintf("%d", entry.Samples),
		Passed:    passed,
		Blocking:  blocking,
	}
	return cond
}

func evaluateStatusMatchRate(entry RouteSummaryEntry, threshold float64, blocking bool) GateCondition {
	passed := entry.StatusMatchRate >= threshold
	cond := GateCondition{
		Route:     entry.Route,
		Condition: "status_match_rate",
		Expected:  fmt.Sprintf(">= %.3f", threshold),
		Actual:    fmt.Sprintf("%.3f", entry.StatusMatchRate),
		Passed:    passed,
		Blocking:  blocking,
	}
	return cond
}

func evaluateSchemaMatchRate(entry RouteSummaryEntry, threshold float64, blocking bool) GateCondition {
	passed := entry.SchemaMatchRate >= threshold
	cond := GateCondition{
		Route:     entry.Route,
		Condition: "schema_match_rate",
		Expected:  fmt.Sprintf(">= %.3f", threshold),
		Actual:    fmt.Sprintf("%.3f", entry.SchemaMatchRate),
		Passed:    passed,
		Blocking:  blocking,
	}
	return cond
}

func evaluatePassRate(entry RouteSummaryEntry, threshold float64, blocking bool) GateCondition {
	passed := entry.PassRate >= threshold
	cond := GateCondition{
		Route:     entry.Route,
		Condition: "pass_rate",
		Expected:  fmt.Sprintf(">= %.3f", threshold),
		Actual:    fmt.Sprintf("%.3f", entry.PassRate),
		Passed:    passed,
		Blocking:  blocking,
	}
	return cond
}

func evaluatePrivacyViolations(entry RouteSummaryEntry, maxAllowed int, blocking bool) GateCondition {
	passed := entry.PrivacyViolations <= maxAllowed
	cond := GateCondition{
		Route:     entry.Route,
		Condition: "privacy_violations",
		Expected:  fmt.Sprintf("<= %d", maxAllowed),
		Actual:    fmt.Sprintf("%d", entry.PrivacyViolations),
		Passed:    passed,
		Blocking:  blocking,
	}
	return cond
}

func containsString(slice []string, target string) bool {
	for _, s := range slice {
		if s == target {
			return true
		}
	}
	return false
}
