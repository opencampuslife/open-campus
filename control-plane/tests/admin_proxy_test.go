package tests

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/contract"
	"gaokao-agent/control-plane/internal/gatewayhttp"
)

func adminContract() *contract.Contract {
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
				Method:        "GET",
				Path:          "/api/admin/ingestion/runs/{run_id}/cancel",
				Owner:         "api-gateway",
				Surface:       "public",
				Visibility:    "public",
				Auth:          "staff",
				CSRF:          "none",
				RateLimit:     "admin_60_per_minute",
				Audit:         true,
				Backend:       "legacy_python",
				MigrationWave: "phase_4",
				LegacyFlags:   []string{"deprecated_compatibility_alias", "state_changing_get"},
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
			{
				Method:        "GET",
				Path:          "/api/admin/health",
				Owner:         "api-gateway",
				Surface:       "public",
				Visibility:    "public",
				Auth:          "staff",
				CSRF:          "none",
				RateLimit:     "admin_60_per_minute",
				Audit:         false,
				Backend:       "legacy_python",
				MigrationWave: "phase_4",
				LegacyFlags:   []string{},
				OpenAPIRef:    "contracts/openapi/admin.yaml",
				OpenAPI:       "contracts/openapi/admin.yaml",
			},
		},
	}
}

func adminProxyOptions(upstreamURL string, enabled bool, allowlist ...string) gatewayhttp.Options {
	return gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: enabled,
		ShadowProxyRoutes:  allowlist,
		PythonBaseURL:      upstreamURL,
		UpstreamTimeout:    time.Second,
		RequestTimeout:     time.Second,
	}
}

func assertStatusCode(t *testing.T, actual, expected int) {
	t.Helper()
	if actual != expected {
		t.Fatalf("status = %d, want %d", actual, expected)
	}
}

func assertBodyContains(t *testing.T, body, want string) {
	t.Helper()
	if !strings.Contains(body, want) {
		t.Fatalf("body does not contain %q, got: %q", want, body)
	}
}

func assertBodyNotContains(t *testing.T, body, unwanted string) {
	t.Helper()
	if strings.Contains(body, unwanted) {
		t.Fatalf("body contains %q, should not", unwanted)
	}
}

func TestAdminPostCancelAllowlistedIsProxied(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || !strings.Contains(r.URL.Path, "/cancel") {
			t.Fatalf("unexpected upstream request: %s %s", r.Method, r.URL.Path)
		}
		if r.Header.Get("X-Gaokao-Gateway-Mode") != "shadow" {
			t.Fatalf("gateway mode = %q", r.Header.Get("X-Gaokao-Gateway-Mode"))
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"cancelled"}`))
	}))
	defer upstream.Close()

	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		upstream.URL, true,
		"POST /api/admin/ingestion/runs/{run_id}/cancel",
	))
	request := httptest.NewRequest(http.MethodPost, "/api/admin/ingestion/runs/ing_abc123/cancel", strings.NewReader(`{}`))
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-CSRF-Token", "test")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusOK)
	assertBodyContains(t, recorder.Body.String(), `"cancelled"`)
}

func TestAdminPostCancelNotAllowlistedReturnsDisabled(t *testing.T) {
	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		"http://127.0.0.1:8787", true,
		"POST /api/admin/staging/docs/{doc_id}/validate",
	))
	request := httptest.NewRequest(http.MethodPost, "/api/admin/ingestion/runs/ing_abc123/cancel", strings.NewReader(`{}`))
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-CSRF-Token", "test")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusNotFound)
	assertBodyContains(t, recorder.Body.String(), gatewayhttp.CodeProxyRouteDisabled)
}

func TestAdminGetDeprecatedAliasReturns405(t *testing.T) {
	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		"http://127.0.0.1:8787", true,
		"POST /api/admin/ingestion/runs/{run_id}/cancel",
	))
	request := httptest.NewRequest(http.MethodGet, "/api/admin/ingestion/runs/ing_abc123/cancel", nil)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusMethodNotAllowed)
	assertBodyContains(t, recorder.Body.String(), gatewayhttp.CodeDeprecatedRouteNotProxied)
}

func TestAdminGetDeprecatedAliasDeniedWithShadowDisabled(t *testing.T) {
	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		"http://127.0.0.1:8787", false,
		"POST /api/admin/ingestion/runs/{run_id}/cancel",
	))
	request := httptest.NewRequest(http.MethodGet, "/api/admin/ingestion/runs/ing_abc123/cancel", nil)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusMethodNotAllowed)
	assertBodyContains(t, recorder.Body.String(), gatewayhttp.CodeDeprecatedRouteNotProxied)
}

func TestAdminPostUpstream403Passthrough(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(`{"error":"legacy_forbidden"}`))
	}))
	defer upstream.Close()

	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		upstream.URL, true,
		"POST /api/admin/ingestion/runs/{run_id}/cancel",
	))
	request := httptest.NewRequest(http.MethodPost, "/api/admin/ingestion/runs/ing_abc123/cancel", strings.NewReader(`{}`))
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-CSRF-Token", "test")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusForbidden)
	assertBodyContains(t, recorder.Body.String(), `"legacy_forbidden"`)
}

func TestAdminPostUpstream500Passthrough(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"error":"unexpected"}`))
	}))
	defer upstream.Close()

	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		upstream.URL, true,
		"POST /api/admin/ingestion/runs/{run_id}/cancel",
	))
	request := httptest.NewRequest(http.MethodPost, "/api/admin/ingestion/runs/ing_abc123/cancel", strings.NewReader(`{}`))
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-CSRF-Token", "test")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusInternalServerError)
	assertBodyContains(t, recorder.Body.String(), `"unexpected"`)
}

func TestAdminPostMissingCsrfPassthroughToPython(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-CSRF-Token") != "" {
			t.Fatal("Go should not add CSRF token - passthrough only")
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"cancelled"}`))
	}))
	defer upstream.Close()

	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		upstream.URL, true,
		"POST /api/admin/ingestion/runs/{run_id}/cancel",
	))
	request := httptest.NewRequest(http.MethodPost, "/api/admin/ingestion/runs/ing_abc123/cancel", strings.NewReader(`{}`))
	request.Header.Set("Content-Type", "application/json")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusOK)
}

func TestAdminUnknownRouteReturns404(t *testing.T) {
	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		"http://127.0.0.1:8787", true,
		"POST /api/admin/ingestion/runs/{run_id}/cancel",
	))
	request := httptest.NewRequest(http.MethodPost, "/api/admin/nonexistent/route", strings.NewReader(`{}`))
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusNotFound)
}

func TestAdminHealthGetNotAllowlistedByDefault(t *testing.T) {
	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		"http://127.0.0.1:8787", true,
		"POST /api/admin/ingestion/runs/{run_id}/cancel",
	))
	request := httptest.NewRequest(http.MethodGet, "/api/admin/health", nil)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusNotFound)
	assertBodyContains(t, recorder.Body.String(), gatewayhttp.CodeProxyRouteDisabled)
}

func TestAdminPostValidateAllowlistedIsProxied(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || !strings.Contains(r.URL.Path, "/validate") {
			t.Fatalf("unexpected upstream request: %s %s", r.Method, r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"validation_status":"passed"}`))
	}))
	defer upstream.Close()

	router := gatewayhttp.NewRouter(adminContract(), adminProxyOptions(
		upstream.URL, true,
		"POST /api/admin/staging/docs/{doc_id}/validate",
	))
	request := httptest.NewRequest(http.MethodPost, "/api/admin/staging/docs/std_abc123/validate", strings.NewReader(`{}`))
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-CSRF-Token", "test")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusOK)
	assertBodyContains(t, recorder.Body.String(), `"passed"`)
}

func TestAdminProxyUpstreamUnavailableReturns502(t *testing.T) {
	router := gatewayhttp.NewRouter(adminContract(), gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: true,
		ShadowProxyRoutes:  []string{"POST /api/admin/ingestion/runs/{run_id}/cancel"},
		PythonBaseURL:      "http://127.0.0.1:1",
		UpstreamTimeout:    50 * time.Millisecond,
	})
	request := httptest.NewRequest(http.MethodPost, "/api/admin/ingestion/runs/ing_abc123/cancel", strings.NewReader(`{}`))
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-CSRF-Token", "test")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusBadGateway)
	assertBodyContains(t, recorder.Body.String(), gatewayhttp.CodeUpstreamUnavailable)
}

func TestAdminProxyLargeBodyReturns413(t *testing.T) {
	upstreamCalled := false
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		upstreamCalled = true
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	router := gatewayhttp.NewRouter(adminContract(), gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: true,
		ShadowProxyRoutes:  []string{"POST /api/admin/ingestion/runs/{run_id}/cancel"},
		PythonBaseURL:      upstream.URL,
		UpstreamTimeout:    time.Second,
		BodyLimitBytes:     3,
	})
	request := httptest.NewRequest(http.MethodPost, "/api/admin/ingestion/runs/ing_abc123/cancel", io.NopCloser(strings.NewReader("abcd")))
	request.ContentLength = 4
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-CSRF-Token", "test")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	assertStatusCode(t, recorder.Code, http.StatusRequestEntityTooLarge)
	if upstreamCalled {
		t.Fatal("upstream should not be called for oversized request")
	}
}
