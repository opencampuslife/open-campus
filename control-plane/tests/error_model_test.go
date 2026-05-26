package tests

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"gaokao-agent/control-plane/internal/gatewayhttp"
)

func TestPanicRecoveryReturnsJSON500WithRequestID(t *testing.T) {
	router := gatewayhttp.NewRouter(validContract(), gatewayhttp.Options{
		ShadowMode:      true,
		LogLevel:        "silent",
		EnablePanicPath: true,
	})
	request := httptest.NewRequest(http.MethodGet, "/__test/panic", nil)
	request.Header.Set("X-Request-Id", "req_test")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusInternalServerError)
	}
	if recorder.Header().Get("X-Request-Id") != "req_test" {
		t.Fatalf("request id header = %q", recorder.Header().Get("X-Request-Id"))
	}
	assertErrorCode(t, recorder, gatewayhttp.CodeInternalError)
}

func TestBodyTooLargeReturnsJSON413(t *testing.T) {
	router := gatewayhttp.NewRouter(validContract(), gatewayhttp.Options{
		ShadowMode:     true,
		BodyLimitBytes: 3,
		LogLevel:       "silent",
	})
	request := httptest.NewRequest(http.MethodPost, "/api/health", strings.NewReader("abcd"))
	request.ContentLength = 4
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusRequestEntityTooLarge)
	}
	assertErrorCode(t, recorder, gatewayhttp.CodeRequestTooLarge)
}

func assertErrorCode(t *testing.T, recorder *httptest.ResponseRecorder, code string) {
	t.Helper()
	if contentType := recorder.Header().Get("Content-Type"); !strings.Contains(contentType, "application/json") {
		t.Fatalf("content-type = %q", contentType)
	}
	var envelope gatewayhttp.ErrorEnvelope
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode error response: %v; body=%s", err, recorder.Body.String())
	}
	if envelope.Error.Code != code {
		t.Fatalf("error code = %q, want %q", envelope.Error.Code, code)
	}
	if envelope.Error.RequestID == "" {
		t.Fatal("missing request_id in error response")
	}
}
