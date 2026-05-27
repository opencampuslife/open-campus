package gatewayhttp

import (
	"net/http"
	"sync"
	"time"
)

type RateLimitConfig struct {
	GlobalRate    float64
	GlobalBurst   int
	PerRouteRate  float64
	PerRouteBurst int
	CleanupEvery  time.Duration
}

type TokenBucket struct {
	rate       float64
	burst      int
	tokens     float64
	lastRefill time.Time
	mu         sync.Mutex
}

func newTokenBucket(rate float64, burst int) *TokenBucket {
	if burst <= 0 {
		burst = int(rate)
		if burst < 1 {
			burst = 1
		}
	}
	return &TokenBucket{
		rate:       rate,
		burst:      burst,
		tokens:     float64(burst),
		lastRefill: time.Now(),
	}
}

func (tb *TokenBucket) allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()
	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens += elapsed * tb.rate
	if tb.tokens > float64(tb.burst) {
		tb.tokens = float64(tb.burst)
	}
	tb.lastRefill = now
	if tb.tokens >= 1.0 {
		tb.tokens -= 1.0
		return true
	}
	return false
}

type RateLimiter struct {
	global       *TokenBucket
	perRoute     map[string]*TokenBucket
	perRouteRate float64
	perRouteBurst int
	mu           sync.RWMutex
}

func NewRateLimiter(cfg RateLimitConfig) *RateLimiter {
	if cfg.GlobalRate <= 0 {
		cfg.GlobalRate = 100
	}
	if cfg.GlobalBurst <= 0 {
		cfg.GlobalBurst = int(cfg.GlobalRate * 2)
		if cfg.GlobalBurst < 1 {
			cfg.GlobalBurst = 1
		}
	}
	if cfg.PerRouteRate <= 0 {
		cfg.PerRouteRate = cfg.GlobalRate / 10
	}
	if cfg.PerRouteBurst <= 0 {
		cfg.PerRouteBurst = int(cfg.PerRouteRate * 2)
		if cfg.PerRouteBurst < 1 {
			cfg.PerRouteBurst = 1
		}
	}
	if cfg.CleanupEvery <= 0 {
		cfg.CleanupEvery = 5 * time.Minute
	}
	rl := &RateLimiter{
		global:        newTokenBucket(cfg.GlobalRate, cfg.GlobalBurst),
		perRoute:      make(map[string]*TokenBucket),
		perRouteRate:  cfg.PerRouteRate,
		perRouteBurst: cfg.PerRouteBurst,
	}
	go rl.startCleanup(cfg.CleanupEvery)
	return rl
}

func (rl *RateLimiter) Allow(pathTemplate string) bool {
	if !rl.global.allow() {
		return false
	}
	if pathTemplate == "" {
		return true
	}
	rl.mu.RLock()
	bucket, exists := rl.perRoute[pathTemplate]
	rl.mu.RUnlock()
	if !exists {
		rl.mu.Lock()
		bucket, exists = rl.perRoute[pathTemplate]
		if !exists {
			bucket = newTokenBucket(rl.perRouteRate, rl.perRouteBurst)
			rl.perRoute[pathTemplate] = bucket
		}
		rl.mu.Unlock()
	}
	return bucket.allow()
}

func (rl *RateLimiter) startCleanup(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for range ticker.C {
		rl.mu.Lock()
		now := time.Now()
		for path, bucket := range rl.perRoute {
			bucket.mu.Lock()
			if now.Sub(bucket.lastRefill) > 5*interval {
				delete(rl.perRoute, path)
			}
			bucket.mu.Unlock()
		}
		rl.mu.Unlock()
	}
}

func WithRateLimiter(rl *RateLimiter) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			pathTemplate := r.URL.Path
			if lr, ok := w.(*logContextRecorder); ok && lr.logContext.PathTemplate != "" {
				pathTemplate = lr.logContext.PathTemplate
			}
			if !rl.Allow(pathTemplate) {
				WriteError(w, http.StatusTooManyRequests, "RATE_LIMITED",
					"Rate limit exceeded", requestIDFromContext(r))
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

func RateLimitedHandler(rl *RateLimiter, handler http.Handler) http.Handler {
	return WithRateLimiter(rl)(handler)
}
