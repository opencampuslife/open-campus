package transport

import (
	"context"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"sync"
	"sync/atomic"
	"time"
)

type PoolConfig struct {
	BaseURL           string
	MaxConns          int
	MaxIdleConns      int
	IdleConnTimeout   time.Duration
	RequestTimeout    time.Duration
	MaxInFlight       int
	Mode              string
}

type UpstreamPool struct {
	baseURL     *url.URL
	client      *http.Client
	mode        string
	sem         chan struct{}
	inFlight    atomic.Int64
	totalReqs   atomic.Int64
	totalErrs   atomic.Int64
	mu          sync.RWMutex
	closed      bool
}

func NewUpstreamPool(cfg PoolConfig) (*UpstreamPool, error) {
	parsed, err := url.Parse(cfg.BaseURL)
	if err != nil {
		return nil, fmt.Errorf("parse upstream base URL: %w", err)
	}
	if cfg.MaxConns <= 0 {
		cfg.MaxConns = 512
	}
	if cfg.MaxIdleConns <= 0 {
		cfg.MaxIdleConns = 64
	}
	if cfg.IdleConnTimeout <= 0 {
		cfg.IdleConnTimeout = 90 * time.Second
	}
	if cfg.RequestTimeout <= 0 {
		cfg.RequestTimeout = 30 * time.Second
	}
	if cfg.MaxInFlight <= 0 {
		cfg.MaxInFlight = cfg.MaxConns
	}
	if cfg.Mode == "" {
		cfg.Mode = "shadow"
	}
	transport := &http.Transport{
		Proxy: http.ProxyFromEnvironment,
		DialContext: (&net.Dialer{
			Timeout:   5 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
		MaxIdleConns:        cfg.MaxIdleConns,
		MaxConnsPerHost:     cfg.MaxConns,
		MaxIdleConnsPerHost: cfg.MaxIdleConns,
		IdleConnTimeout:     cfg.IdleConnTimeout,
	}
	return &UpstreamPool{
		baseURL: parsed,
		client: &http.Client{
			Transport: transport,
			Timeout:   cfg.RequestTimeout,
		},
		mode: cfg.Mode,
		sem:  make(chan struct{}, cfg.MaxInFlight),
	}, nil
}

func (pool *UpstreamPool) Acquire(ctx context.Context) error {
	if pool.isClosed() {
		return fmt.Errorf("upstream pool closed")
	}
	select {
	case pool.sem <- struct{}{}:
		pool.inFlight.Add(1)
		return nil
	case <-ctx.Done():
		pool.totalErrs.Add(1)
		return ctx.Err()
	}
}

func (pool *UpstreamPool) Release() {
	pool.inFlight.Add(-1)
	select {
	case <-pool.sem:
	default:
	}
}

func (pool *UpstreamPool) ServeHTTP(w http.ResponseWriter, r *http.Request) error {
	if pool.isClosed() {
		pool.totalErrs.Add(1)
		return fmt.Errorf("upstream pool closed")
	}
	pool.totalReqs.Add(1)
	upstreamReq, err := pool.buildRequest(r)
	if err != nil {
		pool.totalErrs.Add(1)
		return err
	}
	resp, err := pool.client.Do(upstreamReq)
	if err != nil {
		pool.totalErrs.Add(1)
		return err
	}
	defer resp.Body.Close()
	copyResponseHeaders(w.Header(), resp.Header)
	w.WriteHeader(resp.StatusCode)
	_, copyErr := io.Copy(w, resp.Body)
	if copyErr != nil {
		pool.totalErrs.Add(1)
	}
	return copyErr
}

func (pool *UpstreamPool) buildRequest(r *http.Request) (*http.Request, error) {
	upstreamURL := *pool.baseURL
	upstreamURL.Path = r.URL.Path
	upstreamURL.RawQuery = r.URL.RawQuery
	upstreamReq, err := http.NewRequestWithContext(r.Context(), r.Method, upstreamURL.String(), r.Body)
	if err != nil {
		return nil, err
	}
	copyRequestHeaders(upstreamReq.Header, r.Header)
	upstreamReq.Host = pool.baseURL.Host
	return upstreamReq, nil
}

func (pool *UpstreamPool) Stats() PoolStats {
	return PoolStats{
		InFlight:  pool.inFlight.Load(),
		TotalReqs: pool.totalReqs.Load(),
		TotalErrs: pool.totalErrs.Load(),
		Capacity:  cap(pool.sem),
		Closed:    pool.isClosed(),
	}
}

type PoolStats struct {
	InFlight  int64
	TotalReqs int64
	TotalErrs int64
	Capacity  int
	Closed    bool
}

func (pool *UpstreamPool) HealthCheck(ctx context.Context) error {
	healthURL := *pool.baseURL
	healthURL.Path = "/api/health"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, healthURL.String(), nil)
	if err != nil {
		return err
	}
	resp, err := pool.client.Do(req)
	if err != nil {
		return err
	}
	resp.Body.Close()
	if resp.StatusCode >= 500 {
		return fmt.Errorf("upstream health check failed: status %d", resp.StatusCode)
	}
	return nil
}

func (pool *UpstreamPool) Close() {
	pool.mu.Lock()
	defer pool.mu.Unlock()
	if pool.closed {
		return
	}
	pool.closed = true
	close(pool.sem)
	pool.client.Transport.(*http.Transport).CloseIdleConnections()
}

func (pool *UpstreamPool) isClosed() bool {
	pool.mu.RLock()
	defer pool.mu.RUnlock()
	return pool.closed
}
