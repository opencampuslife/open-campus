package tests

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/contract"
	"gaokao-agent/control-plane/internal/gatewayhttp"
)

func TestHealthResponse(t *testing.T) {
	loaded, err := contract.Load("../../contracts/routes.yaml")
	if err != nil {
		t.Fatalf("load contract: %v", err)
	}
	router := gatewayhttp.NewRouter(loaded, gatewayhttp.Options{
		ShadowMode:     true,
		RequestTimeout: time.Second,
		BodyLimitBytes: 1024,
		LogLevel:       "silent",
	})
	request := httptest.NewRequest(http.MethodGet, "/api/health", nil)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", recorder.Code, recorder.Body.String())
	}
	if recorder.Header().Get("X-Request-Id") == "" {
		t.Fatal("missing X-Request-Id header")
	}
	var body gatewayhttp.HealthResponse
	if err := json.Unmarshal(recorder.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode health response: %v", err)
	}
	if body.Status != "ok" || body.Service != "gaokao-gateway" || body.Mode != "shadow" {
		t.Fatalf("unexpected health response: %+v", body)
	}
	if !body.RoutesContractLoaded || body.RouteCount != 118 || body.LegacyGapCount != 0 || body.DeprecatedCompatibilityAliases != 5 {
		t.Fatalf("unexpected contract counters: %+v", body)
	}
}

func TestHealthMethodNotAllowed(t *testing.T) {
	router := gatewayhttp.NewRouter(validContract(), gatewayhttp.Options{ShadowMode: true, LogLevel: "silent"})
	request := httptest.NewRequest(http.MethodPost, "/api/health", nil)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusMethodNotAllowed {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusMethodNotAllowed)
	}
	assertErrorCode(t, recorder, gatewayhttp.CodeMethodNotAllowed)
}

func TestUnknownRouteReturnsJSON404(t *testing.T) {
	router := gatewayhttp.NewRouter(validContract(), gatewayhttp.Options{ShadowMode: true, LogLevel: "silent"})
	request := httptest.NewRequest(http.MethodGet, "/api/unknown", nil)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusNotFound)
	}
	assertErrorCode(t, recorder, gatewayhttp.CodeRouteNotFound)
}
