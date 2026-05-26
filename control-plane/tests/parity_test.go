package tests

import (
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/gatewayhttp"
	"gaokao-agent/control-plane/internal/parity"
)

func TestParityHarnessUnit(t *testing.T) {
	legacy := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.RawQuery {
		case "case=malformed":
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":"invalid_json"}`))
		case "case=policy":
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusForbidden)
			_, _ = w.Write([]byte(`{"error":{"code":"POLICY_BLOCK","message":"blocked"}}`))
		default:
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"answer":"ok","citations":[]}`))
		}
	}))
	defer legacy.Close()

	shadowRouter := gatewayhttp.NewRouter(chatContract(), gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: true,
		ShadowProxyRoutes:  []string{"POST /api/gaokao/chat"},
		PythonBaseURL:      legacy.URL,
		UpstreamTimeout:    time.Second,
	})
	shadow := httptest.NewServer(shadowRouter)
	defer shadow.Close()

	fixture, err := parity.LoadFixture("../../tests/parity/gaokao_chat.yaml")
	if err != nil {
		t.Fatalf("load fixture: %v", err)
	}
	report, err := parity.RunFixture(fixture, legacy.URL, shadow.URL, &http.Client{Timeout: time.Second})
	if err != nil {
		t.Fatalf("run parity: %v", err)
	}
	if report.Summary.Total != len(fixture.Cases) || report.Summary.Failed != 0 {
		t.Fatalf("unexpected parity summary: %+v", report.Summary)
	}
	data, err := parity.MarshalReport(report)
	if err != nil {
		t.Fatalf("marshal parity report: %v", err)
	}
	if strings.Contains(string(data), "请介绍") || strings.Contains(string(data), `"answer":"ok"`) {
		t.Fatalf("expected redacted parity report, got %s", string(data))
	}
}

func TestParityGaokaoChatLive(t *testing.T) {
	legacyBaseURL := os.Getenv("PYTHON_LEGACY_BASE_URL")
	shadowBaseURL := os.Getenv("GO_SHADOW_BASE_URL")
	if legacyBaseURL == "" || shadowBaseURL == "" {
		t.Skip("live parity is optional; set PYTHON_LEGACY_BASE_URL and GO_SHADOW_BASE_URL to run it")
	}
	fixturePath := os.Getenv("PARITY_FIXTURE_PATH")
	if fixturePath == "" {
		fixturePath = "../../tests/parity/gaokao_chat.yaml"
	}
	fixture, err := parity.LoadFixture(fixturePath)
	if err != nil {
		t.Fatalf("load fixture: %v", err)
	}
	report, err := parity.RunFixture(fixture, legacyBaseURL, shadowBaseURL, &http.Client{Timeout: 30 * time.Second})
	if err != nil {
		t.Fatalf("run live parity: %v", err)
	}
	data, err := parity.MarshalReport(report)
	if err != nil {
		t.Fatalf("marshal report: %v", err)
	}
	t.Log(string(data))
	if report.Summary.Failed != 0 {
		t.Fatalf("parity failures: %+v", report.Summary)
	}
}
