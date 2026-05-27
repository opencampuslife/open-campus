package gatewayhttp

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/transport"
)

func TestShadowDisabledPrepareReturnsNil(t *testing.T) {
	sd := NewShadowDispatcher(nil, nil, ShadowConfig{Enabled: false})
	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	clone := sd.PrepareShadow(req)
	if clone != nil {
		t.Fatal("PrepareShadow should return nil when disabled")
	}
}

func TestShadowSampleRateZeroNeverDispatches(t *testing.T) {
	sd := NewShadowDispatcher(nil, nil, ShadowConfig{Enabled: true, SampleRate: 0})
	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	for i := 0; i < 50; i++ {
		if clone := sd.PrepareShadow(req); clone != nil {
			t.Fatal("sample rate 0 should never produce a clone")
		}
	}
}

func TestShadowSampleRateOneAlwaysDispatches(t *testing.T) {
	sd := NewShadowDispatcher(nil, nil, ShadowConfig{Enabled: true, SampleRate: 1})
	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	for i := 0; i < 20; i++ {
		if clone := sd.PrepareShadow(req); clone == nil {
			t.Fatal("sample rate 1 should always produce a clone")
		}
	}
}

func TestShadowUnsafeMethodBlocked(t *testing.T) {
	sd := NewShadowDispatcher(nil, nil, ShadowConfig{Enabled: true, SampleRate: 1, AllowUnsafe: false})
	req := httptest.NewRequest(http.MethodPost, "/api/test", strings.NewReader("body"))
	clone := sd.PrepareShadow(req)
	if clone != nil {
		t.Fatal("POST should be blocked when AllowUnsafe=false")
	}
}

func TestShadowUnsafeMethodAllowed(t *testing.T) {
	sd := NewShadowDispatcher(nil, nil, ShadowConfig{Enabled: true, SampleRate: 1, AllowUnsafe: true})
	req := httptest.NewRequest(http.MethodPost, "/api/test", strings.NewReader("body"))
	clone := sd.PrepareShadow(req)
	if clone == nil {
		t.Fatal("POST should be allowed when AllowUnsafe=true")
	}
	if clone.Body == nil {
		t.Fatal("clone should have a body")
	}
}

func TestShadowSafeMethodAlwaysDispatches(t *testing.T) {
	sd := NewShadowDispatcher(nil, nil, ShadowConfig{Enabled: true, SampleRate: 1, AllowUnsafe: false})
	for _, method := range []string{http.MethodGet, http.MethodHead} {
		req := httptest.NewRequest(method, "/api/test", nil)
		clone := sd.PrepareShadow(req)
		if clone == nil {
			t.Fatalf("%s should be dispatched (safe method)", method)
		}
	}
}

func TestShadowClonePreservesBodyForPrimary(t *testing.T) {
	sd := NewShadowDispatcher(nil, nil, ShadowConfig{Enabled: true, SampleRate: 1, AllowUnsafe: true})
	req := httptest.NewRequest(http.MethodPost, "/api/test", strings.NewReader("primary-body"))
	clone := sd.PrepareShadow(req)
	if clone == nil {
		t.Fatal("expected clone")
	}

	cloneBytes, err := io.ReadAll(clone.Body)
	if err != nil {
		t.Fatalf("clone read: %v", err)
	}
	if string(cloneBytes) != "primary-body" {
		t.Fatalf("clone body = %q, want primary-body", string(cloneBytes))
	}

	primaryBytes, err := io.ReadAll(req.Body)
	if err != nil {
		t.Fatalf("primary read: %v", err)
	}
	if string(primaryBytes) != "primary-body" {
		t.Fatalf("primary body = %q, want primary-body", string(primaryBytes))
	}
}

func TestShadowHeadersStrippedFromClone(t *testing.T) {
	var receivedHeaders http.Header
	shadowServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedHeaders = r.Header.Clone()
		w.WriteHeader(http.StatusOK)
	}))
	defer shadowServer.Close()

	primaryPool, _ := transport.NewUpstreamPool(transport.PoolConfig{
		BaseURL:        shadowServer.URL,
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
	req.Header.Set("Authorization", "Bearer secret-token")
	req.Header.Set("Cookie", "session=abc123")
	req.Header.Set("X-Csrf-Token", "csrf-secret")
	req.Header.Set("X-Auth-Token", "auth-secret")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	clone := sd.PrepareShadow(req)
	if clone == nil {
		t.Fatal("expected clone")
	}

	result := sd.DispatchClone(clone, "/api/test")
	if result.Error != "" {
		t.Fatalf("dispatch error: %s", result.Error)
	}
	if result.StatusCode != 200 {
		t.Fatalf("shadow status = %d, want 200", result.StatusCode)
	}

	if receivedHeaders.Get("Authorization") != "" {
		t.Fatal("Authorization header should be stripped")
	}
	if receivedHeaders.Get("Cookie") != "" {
		t.Fatal("Cookie header should be stripped")
	}
	if receivedHeaders.Get("X-Csrf-Token") != "" {
		t.Fatal("X-Csrf-Token header should be stripped")
	}
	if receivedHeaders.Get("X-Auth-Token") != "" {
		t.Fatal("X-Auth-Token header should be stripped")
	}
	if receivedHeaders.Get("Content-Type") != "application/json" {
		t.Fatal("Content-Type header should be preserved")
	}
	if receivedHeaders.Get("X-Shadow-Mode") != "true" {
		t.Fatal("X-Shadow-Mode should be set to true")
	}
}

func TestShadowFailureDoesNotAffectPrimary(t *testing.T) {
	primaryServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("primary-response"))
	}))
	defer primaryServer.Close()

	primaryPool, _ := transport.NewUpstreamPool(transport.PoolConfig{
		BaseURL:        primaryServer.URL,
		RequestTimeout: 5 * time.Second,
		Mode:           "shadow",
	})
	defer primaryPool.Close()

	primaryStart := time.Now()
	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	rec := httptest.NewRecorder()
	err := primaryPool.ServeHTTP(rec, req)
	primaryLatency := time.Since(primaryStart)

	if err != nil {
		t.Fatalf("primary error: %v", err)
	}
	if rec.Code != 200 {
		t.Fatalf("primary status = %d, want 200", rec.Code)
	}
	if rec.Body.String() != "primary-response" {
		t.Fatalf("primary body = %q", rec.Body.String())
	}
	if primaryLatency > 500*time.Millisecond {
		t.Fatalf("primary took too long: %v (max 500ms)", primaryLatency)
	}
}

func TestShadowDispatchCloneSuccess(t *testing.T) {
	shadowServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(10 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer shadowServer.Close()

	primaryPool, _ := transport.NewUpstreamPool(transport.PoolConfig{
		BaseURL:        shadowServer.URL,
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
	clone := sd.PrepareShadow(req)
	if clone == nil {
		t.Fatal("expected clone")
	}

	result := sd.DispatchClone(clone, "/api/test")
	if result.Error != "" {
		t.Fatalf("dispatch error: %s", result.Error)
	}
	if result.StatusCode != 200 {
		t.Fatalf("shadow status = %d, want 200", result.StatusCode)
	}
	if result.LatencyMs <= 0 {
		t.Fatal("latency should be positive")
	}
	if result.TimedOut {
		t.Fatal("should not time out")
	}
}

func TestShadowDispatchCloneTimeout(t *testing.T) {
	shadowServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer shadowServer.Close()

	primaryPool, _ := transport.NewUpstreamPool(transport.PoolConfig{
		BaseURL:        shadowServer.URL,
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
		Timeout:    10 * time.Millisecond,
	})

	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	clone := sd.PrepareShadow(req)
	if clone == nil {
		t.Fatal("expected clone")
	}

	result := sd.DispatchClone(clone, "/api/test")
	if !result.TimedOut {
		t.Fatal("should time out")
	}
}

func TestShadowDispatchClonePanicRecovery(t *testing.T) {
	// Force panic by using a nil pool
	sd := &ShadowDispatcher{
		primaryPool: nil,
		shadowPool:  nil,
		config: ShadowConfig{
			Enabled:    true,
			SampleRate: 1,
			Timeout:    5 * time.Second,
		},
	}

	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	clone := sd.PrepareShadow(req)
	result := sd.DispatchClone(clone, "/api/test")
	if !result.PanicCaught {
		t.Fatal("should recover from nil pool panic")
	}
}
