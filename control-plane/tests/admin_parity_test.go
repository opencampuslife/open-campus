package tests

import (
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/contract"
	"gaokao-agent/control-plane/internal/gatewayhttp"
	"gaokao-agent/control-plane/internal/parity"
)

func adminPostParityContract() *contract.Contract {
	return &contract.Contract{
		Version:      1,
		FrozenSource: "services/api-gateway/src/server.py",
		Routes: []contract.Route{
			{
				Method:        "POST",
				Path:          "/api/admin/ingestion/runs/{run_id}/cancel",
				Owner:         "api-gateway",
				Surface:       "public",
				Visibility:    "public",
				Auth:          "staff",
				CSRF:          "required",
				RateLimit:     "admin_60_per_minute",
				Audit:         true,
				Backend:       "legacy_python",
				MigrationWave: "phase_4",
				LegacyFlags:   []string{},
				OpenAPIRef:    "contracts/openapi/admin.yaml",
				OpenAPI:       "contracts/openapi/admin.yaml",
			},
			{
				Method:        "POST",
				Path:          "/api/admin/staging/docs/{doc_id}/validate",
				Owner:         "api-gateway",
				Surface:       "public",
				Visibility:    "public",
				Auth:          "staff",
				CSRF:          "required",
				RateLimit:     "admin_60_per_minute",
				Audit:         true,
				Backend:       "legacy_python",
				MigrationWave: "phase_4",
				LegacyFlags:   []string{},
				OpenAPIRef:    "contracts/openapi/admin.yaml",
				OpenAPI:       "contracts/openapi/admin.yaml",
			},
			{
				Method:        "POST",
				Path:          "/api/admin/staging/docs/{doc_id}/approve",
				Owner:         "api-gateway",
				Surface:       "public",
				Visibility:    "public",
				Auth:          "staff",
				CSRF:          "required",
				RateLimit:     "admin_60_per_minute",
				Audit:         true,
				Backend:       "legacy_python",
				MigrationWave: "phase_4",
				LegacyFlags:   []string{},
				OpenAPIRef:    "contracts/openapi/admin.yaml",
				OpenAPI:       "contracts/openapi/admin.yaml",
			},
			{
				Method:        "POST",
				Path:          "/api/admin/staging/docs/{doc_id}/reject",
				Owner:         "api-gateway",
				Surface:       "public",
				Visibility:    "public",
				Auth:          "staff",
				CSRF:          "required",
				RateLimit:     "admin_60_per_minute",
				Audit:         true,
				Backend:       "legacy_python",
				MigrationWave: "phase_4",
				LegacyFlags:   []string{},
				OpenAPIRef:    "contracts/openapi/admin.yaml",
				OpenAPI:       "contracts/openapi/admin.yaml",
			},
			{
				Method:        "POST",
				Path:          "/api/admin/staging/docs/{doc_id}/publish",
				Owner:         "api-gateway",
				Surface:       "public",
				Visibility:    "public",
				Auth:          "staff",
				CSRF:          "required",
				RateLimit:     "admin_60_per_minute",
				Audit:         true,
				Backend:       "legacy_python",
				MigrationWave: "phase_4",
				LegacyFlags:   []string{},
				OpenAPIRef:    "contracts/openapi/admin.yaml",
				OpenAPI:       "contracts/openapi/admin.yaml",
			},
		},
	}
}

func adminPostShadowProxyRoutes() []string {
	return []string{
		"POST /api/admin/ingestion/runs/{run_id}/cancel",
		"POST /api/admin/staging/docs/{doc_id}/validate",
		"POST /api/admin/staging/docs/{doc_id}/approve",
		"POST /api/admin/staging/docs/{doc_id}/reject",
		"POST /api/admin/staging/docs/{doc_id}/publish",
	}
}

func TestAdminParityUnit(t *testing.T) {
	legacy := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		requestID := r.Header.Get("X-Request-Id")

		if r.URL.RawQuery == "case=missing-csrf" || (strings.HasPrefix(r.URL.Path, "/api/admin/") && r.Header.Get("X-CSRF-Token") == "") {
			w.WriteHeader(http.StatusForbidden)
			_, _ = w.Write([]byte(`{"error":"csrf_token_required"}`))
			return
		}

		switch {
		case strings.Contains(r.URL.Path, "/cancel"):
			if strings.Contains(r.URL.Path, "run-parity-404") {
				w.WriteHeader(http.StatusBadRequest)
				_, _ = w.Write([]byte(`{"error":"Ingestion run not found"}`))
				return
			}
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"status":"cancelled"}`))

		case strings.Contains(r.URL.Path, "/validate"):
			if requestID == "parity-admin-005" {
				w.WriteHeader(http.StatusBadRequest)
				_, _ = w.Write([]byte(`{"error":"malformed_json"}`))
				return
			}
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"validation_status":"passed","compliance_status":"passed"}`))

		case strings.Contains(r.URL.Path, "/approve"):
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"review_status":"approved","reviewer":"parity-admin-001"}`))

		case strings.Contains(r.URL.Path, "/reject"):
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"review_status":"rejected","reason":"test-reject-reason"}`))

		case strings.Contains(r.URL.Path, "/publish"):
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"review_status":"published","published_at":"2026-05-27T00:00:00Z"}`))

		default:
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{"error":"not_found"}`))
		}
	}))
	defer legacy.Close()

	shadowRouter := gatewayhttp.NewRouter(adminPostParityContract(), gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: true,
		ShadowProxyRoutes:  adminPostShadowProxyRoutes(),
		PythonBaseURL:      legacy.URL,
		UpstreamTimeout:    time.Second,
	})
	shadow := httptest.NewServer(shadowRouter)
	defer shadow.Close()

	fixture, err := parity.LoadFixture("../../tests/parity/admin_post_replacements.yaml")
	if err != nil {
		t.Fatalf("load fixture: %v", err)
	}
	report, err := parity.RunFixture(fixture, legacy.URL, shadow.URL, &http.Client{Timeout: time.Second})
	if err != nil {
		t.Fatalf("run parity: %v", err)
	}
	if report.Summary.Total != len(fixture.Cases) || report.Summary.Failed != 0 {
		t.Fatalf("unexpected parity summary: got total=%d passed=%d failed=%d warned=%d",
			report.Summary.Total, report.Summary.Passed, report.Summary.Failed, report.Summary.Warned)
	}
	_, err = parity.MarshalReport(report)
	if err != nil {
		t.Fatalf("marshal parity report: %v", err)
	}
}

func TestParityAdminPostLive(t *testing.T) {
	legacyBaseURL := os.Getenv("PYTHON_LEGACY_BASE_URL")
	shadowBaseURL := os.Getenv("GO_SHADOW_BASE_URL")
	if legacyBaseURL == "" || shadowBaseURL == "" {
		t.Skip("live parity is optional; set PYTHON_LEGACY_BASE_URL and GO_SHADOW_BASE_URL to run it")
	}
	fixture, err := parity.LoadFixture("../../tests/parity/admin_post_replacements.yaml")
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
