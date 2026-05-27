package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"gaokao-agent/control-plane/internal/config"
	"gaokao-agent/control-plane/internal/contract"
	"gaokao-agent/control-plane/internal/gatewayhttp"
)

func main() {
	cfg, err := config.Load(os.Args[1:])
	if err != nil {
		log.Fatalf("load config: %v", err)
	}
	loaded, err := contract.Load(cfg.RoutesContractPath)
	if err != nil {
		log.Fatalf("load routes contract: %v", err)
	}
	router := gatewayhttp.NewRouter(loaded, gatewayhttp.Options{
		ShadowMode:          cfg.ShadowMode,
		RequestTimeout:      cfg.RequestTimeout,
		BodyLimitBytes:      cfg.ProxyBodyLimitBytes,
		LogLevel:            cfg.LogLevel,
		PythonBaseURL:       cfg.PythonBaseURL,
		UpstreamTimeout:     cfg.UpstreamTimeout,
		ShadowProxyEnabled:  cfg.ShadowProxyEnabled,
		ShadowProxyRoutes:   cfg.ShadowProxyRoutes,
		UpstreamMaxConns:    cfg.UpstreamMaxConns,
		UpstreamMaxInFlight: cfg.UpstreamMaxInFlight,
		RateLimitGlobalRPS:  cfg.RateLimitGlobalRPS,
		RateLimitRouteRPS:   cfg.RateLimitRouteRPS,
		CircuitThreshold:    cfg.CircuitThreshold,
		CircuitCooldownSec:  cfg.CircuitCooldownSec,
		ShadowSampleRate:    cfg.ShadowSampleRate,
		ShadowTimeout:       time.Duration(cfg.ShadowTimeoutMs) * time.Millisecond,
		ShadowAllowUnsafe:   cfg.ShadowAllowUnsafe,
		ParityEnabled:       cfg.ParityEnabled,
		ParityMaxLatencyMs:  cfg.ParityMaxLatencyMs,
		EvidenceDir:         cfg.EvidenceDir,
		CanaryHeaderEnabled: cfg.CanaryHeaderEnabled,
		CanaryHeaderName:    cfg.CanaryHeaderName,
		CanaryHeaderValue:   cfg.CanaryHeaderValue,
		CanaryRequireEvidence: cfg.CanaryRequireEvidence,
		CandidateBaseURL:    cfg.CandidateBaseURL,
		EvidencePassed:      cfg.EvidenceMode == "passed",
		CanaryPercentEnabled:         cfg.CanaryPercentEnabled,
		CanaryPercent:                cfg.CanaryPercent,
		CanaryBucketKeyName:          cfg.CanaryBucketKeyName,
		CanaryPercentRequireEvidence: cfg.CanaryPercentRequireEvidence,
	})
	fmt.Printf("gaokao go gateway listening on %s shadow=%v routes=%d\n", cfg.ListenAddr, cfg.ShadowMode, len(loaded.Routes))
	if err := http.ListenAndServe(cfg.ListenAddr, router); err != nil {
		log.Fatalf("gateway stopped: %v", err)
	}
}
