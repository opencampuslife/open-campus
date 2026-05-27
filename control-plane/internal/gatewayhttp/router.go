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
	ShadowMode          bool
	RequestTimeout      time.Duration
	BodyLimitBytes      int64
	LogLevel            string
	EnablePanicPath     bool
	PythonBaseURL       string
	UpstreamTimeout     time.Duration
	ShadowProxyEnabled  bool
	ShadowProxyRoutes   []string
	UpstreamMaxConns    int
	UpstreamMaxInFlight int
	RateLimitGlobalRPS  float64
	RateLimitRouteRPS   float64
	CircuitThreshold    int
	CircuitCooldownSec  int
	ShadowSampleRate    float64
	ShadowTimeout       time.Duration
	ShadowAllowUnsafe   bool
	ParityEnabled       bool
	ParityMaxLatencyMs  int64
	EvidenceDir         string
	CanaryHeaderEnabled bool
	CanaryHeaderName    string
	CanaryHeaderValue   string
	CanaryRequireEvidence bool
	CandidateBaseURL    string
	EvidencePassed      bool
	CanaryPercentEnabled bool
	CanaryPercent       int
	CanaryBucketKeyName string
	CanaryPercentRequireEvidence bool
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

	var shadowPool *transport.UpstreamPool
	var shadowDispatcher *ShadowDispatcher
	var parityConfig ParityBridgeConfig
	if options.ShadowSampleRate > 0 && options.PythonBaseURL != "" {
		shadowTimeout := options.ShadowTimeout
		if shadowTimeout <= 0 {
			shadowTimeout = 5 * time.Second
		}
		p, err := transport.NewUpstreamPool(transport.PoolConfig{
			BaseURL:         options.PythonBaseURL,
			MaxConns:        options.UpstreamMaxConns,
			MaxInFlight:     options.UpstreamMaxInFlight,
			RequestTimeout:  shadowTimeout,
			Mode:            "shadow",
		})
		if err == nil {
			shadowPool = p
			shadowDispatcher = NewShadowDispatcher(pool, shadowPool, ShadowConfig{
				Enabled:     true,
				SampleRate:  options.ShadowSampleRate,
				Timeout:     shadowTimeout,
				AllowUnsafe: options.ShadowAllowUnsafe,
			})
			parityConfig = ParityBridgeConfig{
				Enabled:        options.ParityEnabled,
				MaxLatencyMs:   options.ParityMaxLatencyMs,
			}
		}
	}

	evidenceWriter, err := NewEvidenceWriter(options.EvidenceDir)
	if err != nil {
		evidenceWriter, _ = NewEvidenceWriter("")
	}

	var candidatePool *transport.UpstreamPool
	var candidateBreaker *CircuitBreaker
	canaryConfig := CanaryConfig{
		HeaderEnabled:   options.CanaryHeaderEnabled,
		HeaderName:      options.CanaryHeaderName,
		HeaderValue:     options.CanaryHeaderValue,
		RequireEvidence: options.CanaryRequireEvidence,
	}
	if (options.CanaryHeaderEnabled || options.CanaryPercentEnabled) && options.CandidateBaseURL != "" {
		p, err := transport.NewUpstreamPool(transport.PoolConfig{
			BaseURL:         options.CandidateBaseURL,
			MaxConns:        options.UpstreamMaxConns,
			MaxInFlight:     options.UpstreamMaxInFlight,
			RequestTimeout:  options.UpstreamTimeout,
			Mode:            "candidate",
		})
		if err == nil {
			candidatePool = p
			candidateBreaker = NewCircuitBreaker(CircuitBreakerConfig{
				FailureThreshold: threshold,
				CooldownDuration: cooldown,
			})
		}
	}

	pctConfig := PercentageCanaryConfig{
		Enabled:         options.CanaryPercentEnabled,
		Percent:         clampPercent(options.CanaryPercent),
		BucketKeyName:   options.CanaryBucketKeyName,
		RequireEvidence: options.CanaryPercentRequireEvidence,
	}

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

		canaryDecision := DecideCanary(r, canaryConfig, options.EvidencePassed)
		pctDecision := DecidePercentage(r, pctConfig, options.EvidencePassed)
		primaryPool := pool
		primaryBreaker := breaker
		evidenceStatus := "disabled"
		canaryType := ""
		canaryPercent := pctConfig.Percent
		canaryBucket := pctDecision.Bucket

		if canaryDecision.UseCandidate && candidatePool != nil && candidateBreaker != nil {
			primaryPool = candidatePool
			primaryBreaker = candidateBreaker
			canaryType = "header"
		} else if pctDecision.UseCandidate && candidatePool != nil && candidateBreaker != nil {
			primaryPool = candidatePool
			primaryBreaker = candidateBreaker
			canaryType = "percentage"
		}
		if options.EvidencePassed {
			evidenceStatus = "passed"
		}

		canaryCtx := buildCanaryLogContext(route, r.Method, r.URL.Path, options, canaryDecision, pctDecision, evidenceStatus, canaryType, canaryPercent, canaryBucket)
		setLogContext(w, canaryCtx)

		if !primaryBreaker.Allow() {
			ctx := buildErrorLogContext(route, r.Method, r.URL.Path, "UPSTREAM_CIRCUIT_OPEN", 0)
			setLogContext(w, ctx)
			WriteError(w, http.StatusServiceUnavailable, "UPSTREAM_CIRCUIT_OPEN",
				"Upstream temporarily unavailable (circuit open)", requestIDFromContext(r))
			return
		}

		var shadowClone *http.Request
		if shadowDispatcher != nil {
			shadowClone = shadowDispatcher.PrepareShadow(r)
		}

		stripCanaryHeaders(r.Header, options.CanaryHeaderName)
		stripCanaryKeyHeaders(r.Header)
		transport.InjectForwardedHeaders(r, requestIDFromContext(r), "shadow")
		capture := newCaptureResponseWriter(w, 1<<20)
		start := time.Now()
		err := primaryPool.ServeHTTP(capture, r)
		latency := time.Since(start)
		if err != nil {
			primaryBreaker.RecordFailure()
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
		primaryBreaker.RecordSuccess()

		if shadowClone != nil && parityConfig.Enabled {
			reqID := requestIDFromContext(r)
			method := r.Method
			go func() {
				result := shadowDispatcher.DispatchClone(shadowClone, route.Key())
				diffResult := NewParityCompare(capture, &result, route.Key(), parityConfig)
				if evidenceWriter.Enabled() {
					event := NewParityEvent(route.Key(), method, reqID, capture.StatusCode(), result.StatusCode, result.LatencyMs, diffResult)
					evidenceWriter.WriteParityEvent(event)
				}
			}()
		} else if shadowClone != nil {
			go shadowDispatcher.DispatchClone(shadowClone, route.Key())
		}
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

func buildCanaryLogContext(route contract.Route, method, path string, options Options, headerDecision CanaryDecision, pctDecision PercentageCanaryDecision, evidenceStatus string, canaryType string, canaryPercent int, canaryBucket int) observability.LogContext {
	proxyMode := "shadow_proxy"
	primaryUpstream := "legacy"
	canaryRequested := headerDecision.HeaderMatched || pctDecision.UseCandidate
	canaryAllowed := headerDecision.UseCandidate || pctDecision.UseCandidate
	canaryReason := "legacy"
	if headerDecision.UseCandidate {
		proxyMode = "header_canary"
		primaryUpstream = "candidate"
		canaryReason = headerDecision.Reason
	} else if pctDecision.UseCandidate {
		proxyMode = "percentage_canary"
		primaryUpstream = "candidate"
		canaryReason = pctDecision.Reason
	} else if pctConfigIsEnabled(options) && !headerDecision.UseCandidate {
		canaryReason = pctDecision.Reason
	}

	ctx := observability.LogContext{
		PathTemplate:       route.Path,
		Surface:            route.Surface,
		RouteOwner:         route.Owner,
		ProxyMode:          proxyMode,
		ShadowProxyEnabled: options.ShadowProxyEnabled,
		CanaryRequested:    observability.BoolPtr(canaryRequested),
		CanaryAllowed:      observability.BoolPtr(canaryAllowed),
		CanaryReason:       observability.StrPtr(canaryReason),
		PrimaryUpstream:    observability.StrPtr(primaryUpstream),
		EvidenceStatus:     observability.StrPtr(evidenceStatus),
	}
	if canaryType != "" {
		ctx.CanaryType = observability.StrPtr(canaryType)
	}
	if pctConfigIsEnabled(options) {
		ctx.CanaryPercent = observability.IntPtr(canaryPercent)
		ctx.CanaryBucket = observability.IntPtr(canaryBucket)
	}
	return ctx
}

func pctConfigIsEnabled(options Options) bool {
	return options.CanaryPercentEnabled && clampPercent(options.CanaryPercent) > 0
}
