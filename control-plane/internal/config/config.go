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
}

func Load(args []string) (Config, error) {
	defaultTimeout := int(envInt("REQUEST_TIMEOUT_MS", 5000))
	defaultBodyLimit := int64(envInt("BODY_LIMIT_BYTES", 10*1024*1024))
	defaultProxyBodyLimit := int64(envInt("PROXY_BODY_LIMIT_BYTES", int(defaultBodyLimit)))
	defaultUpstreamTimeout := int(envInt("UPSTREAM_TIMEOUT_MS", defaultTimeout))
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
	if err := flags.Parse(args); err != nil {
		return Config{}, err
	}
	cfg.RequestTimeout = time.Duration(*timeoutMS) * time.Millisecond
	cfg.UpstreamTimeout = time.Duration(*upstreamTimeoutMS) * time.Millisecond
	cfg.ShadowProxyRoutes = parseRouteAllowlist(*shadowProxyRoutes)
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
