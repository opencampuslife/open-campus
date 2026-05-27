package transport

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestUpstreamPoolBasicProxy(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:         upstream.URL,
		MaxConns:        10,
		MaxInFlight:     10,
		RequestTimeout:  5 * time.Second,
		Mode:            "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	defer pool.Close()

	req := httptest.NewRequest(http.MethodGet, "/api/gaokao/chat?q=test", strings.NewReader(`{"msg":"hi"}`))
	req.Host = "test.local"
	rec := httptest.NewRecorder()

	err = pool.ServeHTTP(rec, req)
	if err != nil {
		t.Fatalf("serve: %v", err)
	}
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if rec.Body.String() != `{"ok":true}` {
		t.Fatalf("body = %q", rec.Body.String())
	}
}

func TestUpstreamPoolConcurrencyLimit(t *testing.T) {
	blocker := make(chan struct{})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-blocker
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:         upstream.URL,
		MaxConns:        10,
		MaxInFlight:     2,
		RequestTimeout:  1 * time.Second,
		Mode:            "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	defer func() {
		close(blocker)
		pool.Close()
	}()

	errs := make(chan error, 5)
	var wg sync.WaitGroup
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
			rec := httptest.NewRecorder()
			_ = pool.ServeHTTP(rec, req)
		}(i)
	}
	go func() {
		wg.Wait()
		close(errs)
	}()

	stats := pool.Stats()
	if stats.Capacity != 2 {
		t.Fatalf("capacity = %d, want 2", stats.Capacity)
	}
}

func TestUpstreamPoolHealthCheck(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/health" {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{}`))
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL: upstream.URL,
		Mode:    "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	defer pool.Close()

	if err := pool.HealthCheck(context.Background()); err != nil {
		t.Fatalf("health check: %v", err)
	}
}

func TestUpstreamPoolHeaderCopy(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Custom", r.Header.Get("X-Custom"))
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{}`))
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:         upstream.URL,
		RequestTimeout:  5 * time.Second,
		Mode:            "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	defer pool.Close()

	req := httptest.NewRequest(http.MethodPost, "/api/gaokao/chat", strings.NewReader(`{}`))
	req.Header.Set("X-Custom", "hello")
	req.Header.Set("Content-Type", "application/json")
	InjectForwardedHeaders(req, "req_pool_test", "shadow")
	rec := httptest.NewRecorder()

	err = pool.ServeHTTP(rec, req)
	if err != nil {
		t.Fatalf("serve: %v", err)
	}
	if rec.Header().Get("X-Custom") != "hello" {
		t.Fatalf("X-Custom = %q, want hello", rec.Header().Get("X-Custom"))
	}
}

func TestUpstreamPoolTimeout(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:         upstream.URL,
		RequestTimeout:  10 * time.Millisecond,
		Mode:            "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	defer pool.Close()

	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	rec := httptest.NewRecorder()
	err = pool.ServeHTTP(rec, req)
	if !IsTimeoutError(err) {
		t.Fatalf("expected timeout, got %v", err)
	}
}

func TestUpstreamPoolStats(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{}`))
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:         upstream.URL,
		MaxInFlight:     10,
		RequestTimeout:  5 * time.Second,
		Mode:            "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	defer pool.Close()

	for i := 0; i < 5; i++ {
		req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
		rec := httptest.NewRecorder()
		if err := pool.ServeHTTP(rec, req); err != nil {
			t.Fatalf("req %d: %v", i, err)
		}
	}
	stats := pool.Stats()
	if stats.TotalReqs != 5 {
		t.Fatalf("total = %d, want 5", stats.TotalReqs)
	}
	if stats.Closed {
		t.Fatal("pool should not be closed before Close()")
	}
	pool.Close()
	if !pool.Stats().Closed {
		t.Fatal("pool should be closed after Close()")
	}
}

func TestUpstreamPoolCloseRejectsRequests(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:         upstream.URL,
		RequestTimeout:  5 * time.Second,
		Mode:            "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	pool.Close()

	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	rec := httptest.NewRecorder()
	err = pool.ServeHTTP(rec, req)
	if err == nil {
		t.Fatal("expected error after close")
	}
	stats := pool.Stats()
	if stats.TotalErrs < 1 {
		t.Fatalf("total_errors = %d, want >= 1", stats.TotalErrs)
	}
}

func TestUpstreamPoolLargeBody(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		w.Header().Set("Content-Length", "0")
		w.WriteHeader(http.StatusOK)
		if len(body) != 1024 {
			t.Errorf("upstream body size = %d", len(body))
		}
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:         upstream.URL,
		RequestTimeout:  5 * time.Second,
		Mode:            "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	defer pool.Close()

	bigBody := strings.Repeat("x", 1024)
	req := httptest.NewRequest(http.MethodPost, "/api/test", strings.NewReader(bigBody))
	req.Header.Set("Content-Type", "text/plain")
	rec := httptest.NewRecorder()
	if err := pool.ServeHTTP(rec, req); err != nil {
		t.Fatalf("serve: %v", err)
	}
}

func TestUpstreamPoolConcurrentCloseAndServe(t *testing.T) {
	blocker := make(chan struct{})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-blocker
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:        upstream.URL,
		MaxInFlight:    10,
		RequestTimeout: 5 * time.Second,
		Mode:           "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}

	var wg sync.WaitGroup
	for i := 0; i < 3; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
			rec := httptest.NewRecorder()
			err := pool.ServeHTTP(rec, req)
			if err != nil && err.Error() != "upstream pool closed" {
				t.Errorf("unexpected error: %v", err)
			}
		}()
	}

	time.Sleep(10 * time.Millisecond)
	pool.Close()
	close(blocker)
	wg.Wait()

	if !pool.isClosed() {
		t.Fatal("pool should be closed")
	}
}

func TestUpstreamPoolDoubleCloseIsSafe(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:        upstream.URL,
		RequestTimeout: 5 * time.Second,
		Mode:           "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}

	pool.Close()
	pool.Close()

	if !pool.isClosed() {
		t.Fatal("pool should be closed after double Close()")
	}
	if pool.Stats().Closed != true {
		t.Fatal("Stats().Closed should be true")
	}
}

func TestUpstreamPoolAcquireReleaseConcurrency(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:        upstream.URL,
		MaxInFlight:    5,
		RequestTimeout: 5 * time.Second,
		Mode:           "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	defer pool.Close()

	ctx := context.Background()
	var wg sync.WaitGroup

	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := pool.Acquire(ctx); err != nil {
				return
			}
			time.Sleep(1 * time.Millisecond)
			pool.Release()
		}()
	}

	wg.Wait()

	stats := pool.Stats()
	if stats.InFlight != 0 {
		t.Fatalf("in-flight = %d, want 0 after all releases", stats.InFlight)
	}
}

func TestUpstreamPoolStatsUnderConcurrency(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{}`))
	}))
	defer upstream.Close()

	pool, err := NewUpstreamPool(PoolConfig{
		BaseURL:        upstream.URL,
		MaxInFlight:    20,
		RequestTimeout: 5 * time.Second,
		Mode:           "shadow",
	})
	if err != nil {
		t.Fatalf("new pool: %v", err)
	}
	defer pool.Close()

	var wg sync.WaitGroup
	totalReqs := 50

	for i := 0; i < totalReqs; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
			rec := httptest.NewRecorder()
			if err := pool.ServeHTTP(rec, req); err != nil {
				t.Errorf("unexpected error: %v", err)
			}
		}()
	}

	wg.Wait()

	stats := pool.Stats()
	if stats.TotalReqs != int64(totalReqs) {
		t.Fatalf("total requests = %d, want %d", stats.TotalReqs, totalReqs)
	}
	if stats.TotalErrs > 0 {
		t.Fatalf("total errors = %d, want 0", stats.TotalErrs)
	}
	if stats.Capacity != 20 {
		t.Fatalf("capacity = %d, want 20", stats.Capacity)
	}
}
