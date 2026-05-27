package gatewayhttp

import (
	"net/http"
	"strings"
	"time"

	"gaokao-agent/control-plane/internal/contract"
	"gaokao-agent/control-plane/internal/observability"
	"gaokao-agent/control-plane/internal/transport"
)

type Options struct {
	ShadowMode         bool
	RequestTimeout     time.Duration
	BodyLimitBytes     int64
	LogLevel           string
	EnablePanicPath    bool
	PythonBaseURL      string
	UpstreamTimeout    time.Duration
	ShadowProxyEnabled bool
	ShadowProxyRoutes  []string
	UpstreamMaxConns   int
	UpstreamMaxInFlight int
	RateLimitGlobalRPS float64
	RateLimitRouteRPS  float64
	CircuitThreshold   int
	CircuitCooldownSec int
}

func setLogContext(w http.ResponseWriter, ctx observability.LogContext) {
	if lr, ok := w.(*logContextRecorder); ok {
		lr.SetLogContext(ctx)
	}
}

func NewRouter(loaded *contract.Contract, options Options) http.Handler {
	mux := http.NewServeMux()
	mux.Handle("/api/health", withRouteLogContext(HealthHandler(loaded, options.ShadowMode), loaded, "/api/health", "GET"))
	if loaded != nil {
		proxyHandler := newProxyHandler(loaded, options)
		if loaded.HasExactPath("/api/gaokao/chat") {
			mux.Handle("/api/gaokao/chat", withRouteLogContext(proxyHandler, loaded, "/api/gaokao/chat", "POST"))
		}

		proxiedPaths := make(map[string]bool, len(options.ShadowProxyRoutes))
		hasAdminProxy := false
		for _, routeKey := range options.ShadowProxyRoutes {
			parts := strings.SplitN(strings.TrimSpace(routeKey), " ", 2)
			if len(parts) == 2 {
				normalizedPath := strings.TrimRight(parts[1], "/")
				if normalizedPath != "" {
					proxiedPaths[normalizedPath] = true
				}
				if strings.HasPrefix(normalizedPath, "/api/admin/") {
					hasAdminProxy = true
				}
			}
		}

		if hasAdminProxy {
			mux.Handle("/api/admin/", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				path := r.URL.Path
				route, routeExists := loaded.FindMatchingRoute(r.Method, path)
				if routeExists && route.HasLegacyFlag("deprecated_compatibility_alias") {
					ctx := buildDeprecatedLogContext(route, r.Method, path, "DEPRECATED_ROUTE_NOT_PROXIED")
					setLogContext(w, ctx)
					WriteError(w, http.StatusMethodNotAllowed, CodeDeprecatedRouteNotProxied,
						"Deprecated admin GET mutation is not available through the shadow gateway",
						requestIDFromContext(r))
					return
				}
				if routeExists {
					ctx := buildRouteLogContext(route, r.Method, path, options)
					setLogContext(w, ctx)
					proxyHandler.ServeHTTP(w, r)
				} else {
					proxyHandler.ServeHTTP(w, r)
				}
			}))
		}
	}
	if options.EnablePanicPath {
		mux.HandleFunc("/__test/panic", func(w http.ResponseWriter, r *http.Request) {
			panic("test panic")
		})
	}
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		WriteError(w, http.StatusNotFound, CodeRouteNotFound, "Route not found", requestIDFromContext(r))
	})

	var handler http.Handler = mux
	handler = WithBodyLimit(options.BodyLimitBytes, handler)
	handler = WithPanicRecovery(handler)
	handler = WithStructuredLogging(observability.NewLogger(options.LogLevel), handler)
	handler = WithTimeout(options.RequestTimeout, handler)
	handler = WithRequestID(handler)
	if options.RateLimitGlobalRPS > 0 {
		rl := NewRateLimiter(RateLimitConfig{
			GlobalRate:   options.RateLimitGlobalRPS,
			GlobalBurst:  int(options.RateLimitGlobalRPS * 2),
			PerRouteRate: options.RateLimitRouteRPS,
		})
		handler = WithRateLimiter(rl)(handler)
	}
	return handler
}

func withRouteLogContext(h http.Handler, loaded *contract.Contract, pathTemplate, method string) http.Handler {
	route, exists := loaded.FindExactRoute(method, pathTemplate)
	if !exists {
		return h
	}
	ctx := buildRouteLogContext(route, method, pathTemplate, Options{})
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		setLogContext(w, ctx)
		h.ServeHTTP(w, r)
	})
}

func buildRouteLogContext(route contract.Route, method, path string, options Options) observability.LogContext {
	proxyMode := "direct"
	if options.ShadowMode {
		proxyMode = "shadow"
	}
	ctx := observability.LogContext{
		PathTemplate:       route.Path,
		Surface:            route.Surface,
		RouteOwner:         route.Owner,
		ProxyMode:          proxyMode,
		ShadowProxyEnabled: options.ShadowProxyEnabled,
	}
	if route.Surface == "admin" {
		ctx.AuthRequired = observability.BoolPtr(route.Auth != "" && route.Auth != "anonymous")
		ctx.CSRFRequired = observability.BoolPtr(route.CSRF == "required")
		ctx.AuditRequired = observability.BoolPtr(route.Audit)
	}
	return ctx
}

func buildDeprecatedLogContext(route contract.Route, method, path, errorCode string) observability.LogContext {
	ctx := observability.LogContext{
		PathTemplate:       route.Path,
		Surface:            route.Surface,
		RouteOwner:         route.Owner,
		ProxyMode:          "direct",
		ShadowProxyEnabled: true,
		ErrorCode:          observability.StrPtr(errorCode),
		DeprecatedDenied:   observability.BoolPtr(true),
	}
	if route.LegacyExit != nil {
		ctx.SuccessorRoute = observability.StrPtr(route.LegacyExit.TargetPhase)
	}
	if route.Surface == "admin" {
		ctx.AuthRequired = observability.BoolPtr(false)
		ctx.CSRFRequired = observability.BoolPtr(false)
		ctx.AuditRequired = observability.BoolPtr(false)
	}
	return ctx
}

func newProxyHandler(loaded *contract.Contract, options Options) http.Handler {
	allowlist := make(map[string]struct{}, len(options.ShadowProxyRoutes))
	for _, routeKey := range options.ShadowProxyRoutes {
		allowlist[strings.ToUpper(strings.TrimSpace(routeKey))] = struct{}{}
	}
	var pool *transport.UpstreamPool
	if options.PythonBaseURL != "" {
		p, err := transport.NewUpstreamPool(transport.PoolConfig{
			BaseURL:         options.PythonBaseURL,
			MaxConns:        options.UpstreamMaxConns,
			MaxInFlight:     options.UpstreamMaxInFlight,
			RequestTimeout:  options.UpstreamTimeout,
			Mode:            "shadow",
		})
		if err == nil {
			pool = p
		}
	}
	cooldown := 15 * time.Second
	if options.CircuitCooldownSec > 0 {
		cooldown = time.Duration(options.CircuitCooldownSec) * time.Second
	}
	threshold := options.CircuitThreshold
	if threshold <= 0 {
		threshold = 5
	}
	breaker := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: threshold,
		CooldownDuration: cooldown,
	})
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		route, routeExists := loaded.FindMatchingRoute(r.Method, r.URL.Path)
		if !routeExists {
			if loaded.HasMatchingPath(r.URL.Path) {
				WriteError(w, http.StatusMethodNotAllowed, CodeMethodNotAllowed, "Method not allowed", requestIDFromContext(r))
				return
			}
			WriteError(w, http.StatusNotFound, CodeRouteNotFound, "Route not found", requestIDFromContext(r))
			return
		}
		if !route.IsPublic() || route.HasLegacyFlag("legacy_policy_gap") {
			ctx := buildDisabledLogContext(route, r.Method, r.URL.Path, "PROXY_ROUTE_DISABLED")
			setLogContext(w, ctx)
			WriteError(w, http.StatusNotFound, CodeProxyRouteDisabled, "Proxy route disabled", requestIDFromContext(r))
			return
		}
		if !options.ShadowProxyEnabled {
			ctx := buildDisabledLogContext(route, r.Method, r.URL.Path, "PROXY_ROUTE_DISABLED")
			setLogContext(w, ctx)
			WriteError(w, http.StatusNotFound, CodeProxyRouteDisabled, "Proxy route disabled", requestIDFromContext(r))
			return
		}
		if _, ok := allowlist[strings.ToUpper(route.Key())]; !ok {
			ctx := buildDisabledLogContext(route, r.Method, r.URL.Path, "PROXY_ROUTE_DISABLED")
			setLogContext(w, ctx)
			WriteError(w, http.StatusNotFound, CodeProxyRouteDisabled, "Proxy route disabled", requestIDFromContext(r))
			return
		}
		if pool == nil {
			WriteError(w, http.StatusBadGateway, CodeUpstreamUnavailable, "Upstream unavailable", requestIDFromContext(r))
			return
		}
		if !breaker.Allow() {
			ctx := buildErrorLogContext(route, r.Method, r.URL.Path, "UPSTREAM_CIRCUIT_OPEN", 0)
			setLogContext(w, ctx)
			WriteError(w, http.StatusServiceUnavailable, "UPSTREAM_CIRCUIT_OPEN",
				"Upstream temporarily unavailable (circuit open)", requestIDFromContext(r))
			return
		}
		transport.InjectForwardedHeaders(r, requestIDFromContext(r), "shadow")
		start := time.Now()
		err := pool.ServeHTTP(w, r)
		latency := time.Since(start)
		if err != nil {
			breaker.RecordFailure()
			errorCode := "UPSTREAM_UNAVAILABLE"
			if transport.IsTimeoutError(err) {
				errorCode = "UPSTREAM_TIMEOUT"
			}
			ctx := buildErrorLogContext(route, r.Method, r.URL.Path, errorCode, int(latency.Milliseconds()))
			setLogContext(w, ctx)
			if transport.IsTimeoutError(err) {
				WriteError(w, http.StatusGatewayTimeout, CodeUpstreamTimeout, "Upstream timeout", requestIDFromContext(r))
				return
			}
			WriteError(w, http.StatusBadGateway, CodeUpstreamUnavailable, "Upstream unavailable", requestIDFromContext(r))
			return
		}
		breaker.RecordSuccess()
	})
}

func buildDisabledLogContext(route contract.Route, method, path, errorCode string) observability.LogContext {
	return observability.LogContext{
		PathTemplate:       route.Path,
		Surface:            route.Surface,
		RouteOwner:         route.Owner,
		ProxyMode:          "shadow",
		ShadowProxyEnabled: true,
		ErrorCode:          observability.StrPtr(errorCode),
		DeprecatedDenied:   observability.BoolPtr(false),
	}
}

func buildErrorLogContext(route contract.Route, method, path, errorCode string, latencyMs int) observability.LogContext {
	return observability.LogContext{
		PathTemplate:       route.Path,
		Surface:            route.Surface,
		RouteOwner:         route.Owner,
		ProxyMode:          "shadow",
		ShadowProxyEnabled: true,
		ErrorCode:          observability.StrPtr(errorCode),
		UpstreamLatencyMs:  observability.Int64Ptr(int64(latencyMs)),
	}
}
