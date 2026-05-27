package gatewayhttp

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/observability"
)

func TestRateLimiterAllowsWithinLimit(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:   100,
		GlobalBurst:  100,
		PerRouteRate: 100,
		PerRouteBurst: 100,
	})
	for i := 0; i < 100; i++ {
		if !rl.Allow("/api/gaokao/chat") {
			t.Fatalf("allow %d: should pass within burst limit", i)
		}
	}
}

func TestRateLimiterBlocksAfterBurst(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:   10,
		GlobalBurst:  5,
		PerRouteRate: 10,
	})
	allowed := 0
	for i := 0; i < 100; i++ {
		if rl.Allow("/api/gaokao/chat") {
			allowed++
		}
	}
	if allowed > 5 {
		t.Fatalf("allowed = %d, want <= 5 (burst limit)", allowed)
	}
}

func TestRateLimiterPerRouteIsolation(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:   20,
		GlobalBurst:  20,
		PerRouteRate: 2,
		PerRouteBurst: 2,
	})
	if !rl.Allow("/api/chat") {
		t.Fatal("first /api/chat should pass")
	}
	if !rl.Allow("/api/chat") {
		t.Fatal("second /api/chat should pass")
	}
	if rl.Allow("/api/chat") {
		t.Fatal("third /api/chat should be rate limited")
	}
	if !rl.Allow("/api/handoff") {
		t.Fatal("/api/handoff should pass (different route)")
	}
}

func TestRateLimiterMiddleware(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:   100,
		GlobalBurst:  10,
		PerRouteRate: 100,
	})
	called := false
	handler := WithRateLimiter(rl)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
		w.WriteHeader(http.StatusOK)
	}))
	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	rec := httptest.NewRecorder()
	recorder := &logContextRecorder{ResponseWriter: rec, status: http.StatusOK}
	handler.ServeHTTP(recorder, req)
	if !called {
		t.Fatal("handler should be called within rate limit")
	}
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
}

func TestRateLimiterMiddlewareBlocks(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate: 100,
		GlobalBurst: 1,
	})
	handler := WithRateLimiter(rl)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	req := httptest.NewRequest(http.MethodGet, "/api/test", nil)
	rec1 := httptest.NewRecorder()
	handler.ServeHTTP(&logContextRecorder{ResponseWriter: rec1, status: http.StatusOK}, req)
	if rec1.Code != http.StatusOK {
		t.Fatalf("first request: status = %d", rec1.Code)
	}
	rec2 := httptest.NewRecorder()
	handler.ServeHTTP(&logContextRecorder{ResponseWriter: rec2, status: http.StatusOK}, req)
	if rec2.Code != http.StatusTooManyRequests {
		t.Fatalf("second request: status = %d, want 429", rec2.Code)
	}
}

func TestRateLimiterRefill(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:   100,
		GlobalBurst:  1,
		PerRouteRate: 100,
	})
	if !rl.Allow("/api/test") {
		t.Fatal("first allow should pass")
	}
	if rl.Allow("/api/test") {
		t.Fatal("exhausted burst should block")
	}
	time.Sleep(20 * time.Millisecond)
	if !rl.Allow("/api/test") {
		t.Fatal("after refill should allow one token")
	}
}

func TestRateLimiterConcurrent(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:   1000,
		GlobalBurst:  100,
		PerRouteRate: 1000,
	})
	var wg sync.WaitGroup
	allowed := make(chan bool, 100)
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			allowed <- rl.Allow("/api/concurrent")
		}()
	}
	wg.Wait()
	close(allowed)
	count := 0
	for ok := range allowed {
		if ok {
			count++
		}
	}
	if count < 90 {
		t.Fatalf("concurrent allowed = %d, want >= 90", count)
	}
}

func TestRateLimiterEmptyPathTemplate(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate: 100,
		GlobalBurst: 10,
	})
	if !rl.Allow("") {
		t.Fatal("empty path should pass global check only")
	}
}

func TestRateLimiterWithLogContextRecorder(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:   100,
		GlobalBurst:  10,
		PerRouteRate: 100,
	})
	handler := WithRateLimiter(rl)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	req := httptest.NewRequest(http.MethodGet, "/api/specific", nil)
	rec := &logContextRecorder{
		ResponseWriter: httptest.NewRecorder(),
		status:         http.StatusOK,
		logContext:     observability.LogContext{PathTemplate: "/api/specific"},
	}
	handler.ServeHTTP(rec, req)
	if rec.status != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.status)
	}
}

func TestRateLimiterMiddlewareOrdering(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate: 1,
		GlobalBurst: 1,
	})

	innerHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := WithBodyLimit(5, innerHandler)
	handler = WithRateLimiter(rl)(handler)

	rec1 := &logContextRecorder{
		ResponseWriter: httptest.NewRecorder(),
		status:         http.StatusOK,
	}
	req1 := httptest.NewRequest(http.MethodGet, "/api/test", strings.NewReader("hi"))
	handler.ServeHTTP(rec1, req1)
	if rec1.status != http.StatusOK {
		t.Fatalf("first request: status = %d, want 200", rec1.status)
	}

	req2 := httptest.NewRequest(http.MethodGet, "/api/test", strings.NewReader("hi"))
	rec2 := httptest.NewRecorder()
	handler.ServeHTTP(rec2, req2)
	if rec2.Code != http.StatusTooManyRequests {
		t.Fatalf("second request: status = %d, want 429 (rate limited before body limit)", rec2.Code)
	}
}

func TestGlobalLimitBlocksAllRoutes(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:   0.1,
		GlobalBurst:  1,
		PerRouteRate: 100,
		PerRouteBurst: 100,
	})

	if !rl.Allow("/api/chat") {
		t.Fatal("first request should pass (global burst)")
	}

	if rl.Allow("/api/chat") {
		t.Fatal("same route blocked: global exhausted")
	}
	if rl.Allow("/api/handoff") {
		t.Fatal("different route blocked: global exhausted")
	}
	if rl.Allow("/api/campus") {
		t.Fatal("third route blocked: global exhausted")
	}
}

func TestConcurrentBurstNeverExceeded(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:   0.01,
		GlobalBurst:  5,
		PerRouteRate: 100,
		PerRouteBurst: 100,
	})

	var wg sync.WaitGroup
	var mu sync.Mutex
	var successCount int

	for i := 0; i < 200; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if rl.Allow("/api/test") {
				mu.Lock()
				successCount++
				mu.Unlock()
			}
		}()
	}
	wg.Wait()

	if successCount > 6 {
		t.Fatalf("concurrent successes = %d, want <= 6 (burst=5 + tiny refill)", successCount)
	}
	if successCount < 5 {
		t.Fatalf("concurrent successes = %d, want >= 5 (burst should be fully consumed)", successCount)
	}
}

func TestRateLimiterCleanupDoesNotCrash(t *testing.T) {
	rl := NewRateLimiter(RateLimitConfig{
		GlobalRate:  100,
		GlobalBurst: 100,
		CleanupEvery: 5 * time.Millisecond,
	})

	rl.Allow("/api/chat")
	time.Sleep(100 * time.Millisecond)

	if !rl.Allow("/api/chat") {
		t.Fatal("should allow after cleanup cycle (bucket recreated)")
	}
}
