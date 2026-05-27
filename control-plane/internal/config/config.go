package config

import (
	"flag"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	ListenAddr          string
	RoutesContractPath  string
	PythonBaseURL       string
	RequestTimeout      time.Duration
	BodyLimitBytes      int64
	ProxyBodyLimitBytes int64
	UpstreamTimeout     time.Duration
	ShadowMode          bool
	ShadowProxyEnabled  bool
	ShadowProxyRoutes   []string
	LogLevel            string
	UpstreamMaxConns    int
	UpstreamMaxInFlight int
	RateLimitGlobalRPS  float64
	RateLimitRouteRPS   float64
	CircuitThreshold    int
	CircuitCooldownSec  int
	ShadowSampleRate    float64
	ShadowTimeoutMs     int
	ShadowAllowUnsafe   bool
	ParityEnabled       bool
	ParityMaxLatencyMs  int64
	EvidenceDir         string
	EvidenceMode        string
	CanaryHeaderEnabled bool
	CanaryHeaderName    string
	CanaryHeaderValue   string
	CanaryRequireEvidence bool
	CandidateBaseURL    string
	CanaryPercentEnabled bool
	CanaryPercent       int
	CanaryBucketKeyName string
	CanaryPercentRequireEvidence bool
}

func Load(args []string) (Config, error) {
	defaultTimeout := int(envInt("REQUEST_TIMEOUT_MS", 5000))
	defaultBodyLimit := int64(envInt("BODY_LIMIT_BYTES", 10*1024*1024))
	defaultProxyBodyLimit := int64(envInt("PROXY_BODY_LIMIT_BYTES", int(defaultBodyLimit)))
	defaultUpstreamTimeout := int(envInt("UPSTREAM_TIMEOUT_MS", defaultTimeout))
	defaultMaxConns := int(envInt("UPSTREAM_MAX_CONNS", 512))
	defaultMaxInFlight := int(envInt("UPSTREAM_MAX_IN_FLIGHT", defaultMaxConns))
	defaultRateLimit := float64(envInt("RATE_LIMIT_GLOBAL_RPS", 100))
	defaultRouteRateLimit := float64(envInt("RATE_LIMIT_ROUTE_RPS", 10))
	defaultCircuitThreshold := int(envInt("CIRCUIT_FAILURE_THRESHOLD", 5))
	defaultCircuitCooldown := int(envInt("CIRCUIT_COOLDOWN_SEC", 15))
	defaultShadowSampleRate := float64(envInt("SHADOW_SAMPLE_RATE_PCT", 0)) / 100.0
	defaultShadowTimeoutMs := int(envInt("SHADOW_TIMEOUT_MS", 5000))
	defaultParityMaxLatencyMs := int64(envInt("PARITY_MAX_LATENCY_MS", 200))
	flags := flag.NewFlagSet("gaokao-gateway", flag.ContinueOnError)
	cfg := Config{}
	flags.StringVar(&cfg.ListenAddr, "listen", envString("LISTEN_ADDR", ":8788"), "gateway listen address")
	flags.StringVar(&cfg.RoutesContractPath, "routes", envString("ROUTES_CONTRACT_PATH", "contracts/routes.yaml"), "route contract path")
	flags.StringVar(&cfg.PythonBaseURL, "python-base-url", envString("PYTHON_GATEWAY_BASE_URL", "http://localhost:8787"), "legacy Python gateway base URL")
	timeoutMS := flags.Int("request-timeout-ms", defaultTimeout, "request timeout in milliseconds")
	flags.Int64Var(&cfg.BodyLimitBytes, "body-limit-bytes", defaultBodyLimit, "maximum request body size")
	flags.Int64Var(&cfg.ProxyBodyLimitBytes, "proxy-body-limit-bytes", defaultProxyBodyLimit, "maximum proxy request body size")
	upstreamTimeoutMS := flags.Int("upstream-timeout-ms", defaultUpstreamTimeout, "upstream timeout in milliseconds")
	flags.BoolVar(&cfg.ShadowMode, "shadow-mode", envBool("SHADOW_MODE", true), "run without production traffic ownership")
	flags.BoolVar(&cfg.ShadowProxyEnabled, "shadow-proxy-enabled", envBool("SHADOW_PROXY_ENABLED", false), "enable explicitly allowed shadow proxy routes")
	shadowProxyRoutes := flags.String("shadow-proxy-routes", envString("SHADOW_PROXY_ROUTES", ""), "comma-separated METHOD /path shadow proxy allowlist")
	flags.StringVar(&cfg.LogLevel, "log-level", envString("LOG_LEVEL", "info"), "log level")
	flags.IntVar(&cfg.UpstreamMaxConns, "upstream-max-conns", defaultMaxConns, "max connections to upstream")
	flags.IntVar(&cfg.UpstreamMaxInFlight, "upstream-max-in-flight", defaultMaxInFlight, "max concurrent in-flight upstream requests")
	fastRateLimit := flags.Float64("rate-limit-rps", defaultRateLimit, "global rate limit requests per second")
	fastRouteRate := flags.Float64("rate-limit-route-rps", defaultRouteRateLimit, "per-route rate limit requests per second")
	flags.IntVar(&cfg.CircuitThreshold, "circuit-failure-threshold", defaultCircuitThreshold, "consecutive failures before circuit opens")
	flags.IntVar(&cfg.CircuitCooldownSec, "circuit-cooldown-sec", defaultCircuitCooldown, "seconds before circuit half-opens")
	flags.Float64Var(&cfg.ShadowSampleRate, "shadow-sample-rate", defaultShadowSampleRate, "shadow request sample rate (0-1)")
	shadowTimeout := flags.Int("shadow-timeout-ms", defaultShadowTimeoutMs, "shadow request timeout in milliseconds")
	flags.BoolVar(&cfg.ShadowAllowUnsafe, "shadow-allow-unsafe", envBool("SHADOW_ALLOW_UNSAFE", false), "allow shadowing unsafe methods (POST/PUT/DELETE)")
	flags.BoolVar(&cfg.ParityEnabled, "parity-enabled", envBool("PARITY_ENABLED", false), "enable parity comparison between primary and shadow")
	flags.Int64Var(&cfg.ParityMaxLatencyMs, "parity-max-latency-ms", defaultParityMaxLatencyMs, "max allowed shadow latency ms for parity pass")
	flags.StringVar(&cfg.EvidenceDir, "evidence-dir", envString("EVIDENCE_DIR", "../evidence/control-plane"), "directory for parity evidence files")
	flags.StringVar(&cfg.EvidenceMode, "evidence-mode", envString("EVIDENCE_MODE", "warn"), "evidence gate mode: strict, warn, or off")
	flags.BoolVar(&cfg.CanaryHeaderEnabled, "canary-header-enabled", envBool("CANARY_HEADER_ENABLED", false), "enable header-based canary routing")
	flags.StringVar(&cfg.CanaryHeaderName, "canary-header-name", envString("CANARY_HEADER_NAME", "X-Gaokao-Canary"), "canary header name")
	flags.StringVar(&cfg.CanaryHeaderValue, "canary-header-value", envString("CANARY_HEADER_VALUE", "go-control-plane"), "canary header expected value")
	flags.BoolVar(&cfg.CanaryRequireEvidence, "canary-require-evidence", envBool("CANARY_REQUIRE_EVIDENCE", true), "require evidence gate passed before allowing canary")
	flags.StringVar(&cfg.CandidateBaseURL, "canary-upstream", envString("CANDIDATE_UPSTREAM", ""), "candidate upstream base URL for canary traffic")
	flags.BoolVar(&cfg.CanaryPercentEnabled, "canary-percent-enabled", envBool("CANARY_PERCENT_ENABLED", false), "enable percentage-based canary routing")
	flags.IntVar(&cfg.CanaryPercent, "canary-percent", envInt("CANARY_PERCENT", 0), "percentage of traffic to route to candidate (0-100)")
	flags.StringVar(&cfg.CanaryBucketKeyName, "canary-bucket-key", envString("CANARY_BUCKET_KEY", "request_id"), "bucket key name for deterministic hashing")
	flags.BoolVar(&cfg.CanaryPercentRequireEvidence, "canary-percent-require-evidence", envBool("CANARY_PERCENT_REQUIRE_EVIDENCE", true), "require evidence gate passed before allowing percentage canary")
	if err := flags.Parse(args); err != nil {
		return Config{}, err
	}
	cfg.RequestTimeout = time.Duration(*timeoutMS) * time.Millisecond
	cfg.UpstreamTimeout = time.Duration(*upstreamTimeoutMS) * time.Millisecond
	cfg.ShadowProxyRoutes = parseRouteAllowlist(*shadowProxyRoutes)
	cfg.RateLimitGlobalRPS = *fastRateLimit
	cfg.RateLimitRouteRPS = *fastRouteRate
	cfg.ShadowTimeoutMs = *shadowTimeout
	return cfg, nil
}

func parseRouteAllowlist(raw string) []string {
	if strings.TrimSpace(raw) == "" {
		return nil
	}
	chunks := strings.Split(raw, ",")
	routes := make([]string, 0, len(chunks))
	for _, chunk := range chunks {
		value := strings.TrimSpace(chunk)
		if value == "" {
			continue
		}
		routes = append(routes, value)
	}
	return routes
}

func envString(name string, fallback string) string {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	return value
}

func envBool(name string, fallback bool) bool {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	parsed, err := strconv.ParseBool(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func envInt(name string, fallback int) int {
	value := os.Getenv(name)
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}
