package gatewayhttp

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/transport"
)

func TestParityStatusMatchPasses(t *testing.T) {
	primaryBody := `{"ok":true,"data":"same"}`
	shadowBody := `{"ok":true,"data":"same"}`

	primary := newTestCapture(primaryBody, http.StatusOK, "application/json")
	shadow := newTestShadowResult(shadowBody, http.StatusOK)

	result := NewParityCompare(primary, shadow, "GET /api/test", ParityBridgeConfig{
		Enabled:        true,
		RequiredFields: []string{"ok"},
	})
	if result.Status != "passed" {
		t.Fatalf("status = %s, want passed", result.Status)
	}
}

func TestParityStatusMismatchFails(t *testing.T) {
	primary := newTestCapture(`{"ok":true}`, http.StatusOK, "application/json")
	shadow := newTestShadowResult(`{"ok":true}`, http.StatusInternalServerError)

	result := NewParityCompare(primary, shadow, "GET /api/test", ParityBridgeConfig{Enabled: true})
	if result.Status != "failed" {
		t.Fatalf("status = %s, want failed on status mismatch", result.Status)
	}
}

func TestParityRequiredFieldMissingFails(t *testing.T) {
	primary := newTestCapture(`{"ok":true,"status":"active"}`, http.StatusOK, "application/json")
	shadow := newTestShadowResult(`{"other":"data"}`, http.StatusOK)

	result := NewParityCompare(primary, shadow, "GET /api/test", ParityBridgeConfig{
		Enabled:        true,
		RequiredFields: []string{"ok", "status"},
	})
	if result.Status != "failed" {
		t.Fatalf("status = %s, want failed (missing required fields)", result.Status)
	}
}

func TestParityShadowErrorFails(t *testing.T) {
	primary := newTestCapture(`{"ok":true}`, http.StatusOK, "application/json")
	shadow := &ShadowResult{
		StatusCode: 0,
		Error:      "connection refused",
	}

	result := NewParityCompare(primary, shadow, "GET /api/test", ParityBridgeConfig{Enabled: true})
	if result.Status != "failed" {
		t.Fatalf("status = %s, want failed on shadow error", result.Status)
	}
}

func TestParityShadowTimeoutFails(t *testing.T) {
	primary := newTestCapture(`{"ok":true}`, http.StatusOK, "application/json")
	shadow := &ShadowResult{
		StatusCode: 0,
		TimedOut:   true,
		Error:      "shadow timeout",
	}

	result := NewParityCompare(primary, shadow, "GET /api/test", ParityBridgeConfig{Enabled: true})
	if result.Status != "failed" {
		t.Fatalf("status = %s, want failed on shadow timeout", result.Status)
	}
}

func TestParityIdenticalBodiesPass(t *testing.T) {
	body := `{"ok":true,"status":"active","data":{"id":1,"name":"test"}}`
	primary := newTestCapture(body, http.StatusOK, "application/json")
	shadow := newTestShadowResult(body, http.StatusOK)

	result := NewParityCompare(primary, shadow, "GET /api/test", ParityBridgeConfig{
		Enabled:        true,
		RequiredFields: []string{"ok", "status", "data"},
	})
	if result.Status != "passed" {
		t.Fatalf("status = %s, want passed for identical bodies", result.Status)
	}
	if len(result.Diffs) > 0 {
		t.Fatalf("diffs = %v, want none", result.Diffs)
	}
}

func TestParityCriticalFieldMissing(t *testing.T) {
	primary := newTestCapture(`{"ok":true,"status":"active"}`, http.StatusOK, "application/json")
	shadow := newTestShadowResult(`{"ok":false}`, http.StatusOK)

	result := NewParityCompare(primary, shadow, "POST /api/campus/payment/submit", ParityBridgeConfig{
		Enabled:        true,
		RequiredFields: []string{"ok", "status"},
	})
	if result.Status != "failed" {
		t.Fatalf("status = %s, want failed (critical field missing)", result.Status)
	}
}

func TestCaptureDoesNotAlterClientResponse(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true,"data":"client-response"}`))
	}))
	defer upstream.Close()

	primaryPool, _ := transport.NewUpstreamPool(transport.PoolConfig{
		BaseURL:        upstream.URL,
		RequestTimeout: 5 * time.Second,
		Mode:           "shadow",
	})
	defer primaryPool.Close()

	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	clientRec := httptest.NewRecorder()

	capture := newCaptureResponseWriter(clientRec, 1<<20)
	err := primaryPool.ServeHTTP(capture, req)
	if err != nil {
		t.Fatalf("serve error: %v", err)
	}

	if clientRec.Code != http.StatusOK {
		t.Fatalf("client status = %d, want 200", clientRec.Code)
	}
	if clientRec.Body.String() != `{"ok":true,"data":"client-response"}` {
		t.Fatalf("client body = %q, want original", clientRec.Body.String())
	}

	captured := capture.Body()
	if string(captured) != `{"ok":true,"data":"client-response"}` {
		t.Fatalf("captured body = %q, want same as client", string(captured))
	}
}

func TestParityCompareEndToEnd(t *testing.T) {
	primaryServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true,"data":"primary-value"}`))
	}))
	defer primaryServer.Close()

	shadowServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true,"data":"shadow-value"}`))
	}))
	defer shadowServer.Close()

	primaryPool, _ := transport.NewUpstreamPool(transport.PoolConfig{
		BaseURL:        primaryServer.URL,
		RequestTimeout: 5 * time.Second,
		Mode:           "shadow",
	})
	defer primaryPool.Close()

	shadowPool, _ := transport.NewUpstreamPool(transport.PoolConfig{
		BaseURL:        shadowServer.URL,
		RequestTimeout: 5 * time.Second,
		Mode:           "shadow",
	})
	defer shadowPool.Close()

	sd := NewShadowDispatcher(primaryPool, shadowPool, ShadowConfig{
		Enabled:    true,
		SampleRate: 1,
		Timeout:    5 * time.Second,
	})

	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	capture := newCaptureResponseWriter(httptest.NewRecorder(), 1<<20)

	err := primaryPool.ServeHTTP(capture, req)
	if err != nil {
		t.Fatalf("primary error: %v", err)
	}

	clone := sd.PrepareShadow(req)
	if clone == nil {
		t.Fatal("expected clone")
	}

	shadowResult := sd.DispatchClone(clone, "GET /api/test")
	if shadowResult.Error != "" {
		t.Fatalf("shadow error: %s", shadowResult.Error)
	}

	parityResult := NewParityCompare(capture, &shadowResult, "GET /api/test", ParityBridgeConfig{
		Enabled:        true,
		RequiredFields: []string{"ok", "data"},
	})
	if parityResult.Status != "passed" {
		t.Fatalf("parity status = %s, want passed (same structure, different values ok for required_fields)", parityResult.Status)
	}
}

func TestParityDisabledConfig(t *testing.T) {
	primary := newTestCapture(`{"ok":true}`, http.StatusOK, "application/json")
	shadow := newTestShadowResult(`{"ok":true}`, http.StatusOK)

	result := NewParityCompare(primary, shadow, "GET /api/test", ParityBridgeConfig{Enabled: false})
	if result.Status != "passed" {
		t.Fatalf("disabled parity should not report failure, got %s", result.Status)
	}
}

func newTestCapture(body string, status int, contentType string) *captureResponseWriter {
	rec := httptest.NewRecorder()
	capture := newCaptureResponseWriter(rec, 1<<20)
	capture.Header().Set("Content-Type", contentType)
	capture.WriteHeader(status)
	capture.Write([]byte(body))
	return capture
}

func newTestShadowResult(body string, status int) *ShadowResult {
	return &ShadowResult{
		StatusCode: status,
		Headers: map[string]string{
			"content-type": "application/json",
		},
		Body: []byte(body),
	}
}
