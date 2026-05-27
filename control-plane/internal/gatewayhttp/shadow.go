package gatewayhttp

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/binary"
	"io"
	"net/http"
	"strings"
	"time"

	"gaokao-agent/control-plane/internal/transport"
)

var safeMethods = map[string]struct{}{
	http.MethodGet:  {},
	http.MethodHead: {},
}

var shadowStripHeaders = [...]string{
	"authorization",
	"cookie",
	"set-cookie",
	"x-csrf-token",
	"x-auth-token",
	"proxy-authorization",
}

type ShadowConfig struct {
	Enabled            bool
	SampleRate         float64
	Timeout            time.Duration
	AllowUnsafe        bool
	MaxShadowBodyBytes int64
}

type ShadowDispatcher struct {
	primaryPool *transport.UpstreamPool
	shadowPool  *transport.UpstreamPool
	config      ShadowConfig
}

type ShadowResult struct {
	Route        string
	StatusCode   int
	LatencyMs    int64
	Error        string
	TimedOut     bool
	PanicCaught  bool
	Skipped      bool
	SkipReason   string
	DispatchedAt time.Time
	Body         []byte
	Headers      map[string]string
}

func NewShadowDispatcher(primaryPool, shadowPool *transport.UpstreamPool, config ShadowConfig) *ShadowDispatcher {
	if config.Timeout <= 0 {
		config.Timeout = 5 * time.Second
	}
	if config.SampleRate < 0 {
		config.SampleRate = 0
	}
	if config.SampleRate > 1 {
		config.SampleRate = 1
	}
	if config.MaxShadowBodyBytes <= 0 {
		config.MaxShadowBodyBytes = 1 << 20
	}
	return &ShadowDispatcher{
		primaryPool: primaryPool,
		shadowPool:  shadowPool,
		config:      config,
	}
}

func (sd *ShadowDispatcher) PrepareShadow(r *http.Request) *http.Request {
	if !sd.config.Enabled {
		return nil
	}
	if sd.config.SampleRate < 1 && !sd.shouldSample() {
		return nil
	}
	if !sd.config.AllowUnsafe && !sd.isSafeMethod(r.Method) {
		return nil
	}

	clone := r.Clone(r.Context())

	if r.Body != nil && r.Body != http.NoBody {
		bodyBytes, err := io.ReadAll(r.Body)
		r.Body.Close()
		if err != nil {
			return nil
		}
		r.Body = io.NopCloser(bytes.NewReader(bodyBytes))
		clone.Body = io.NopCloser(bytes.NewReader(bodyBytes))
	}

	return clone
}

func (sd *ShadowDispatcher) DispatchClone(clone *http.Request, routeKey string) ShadowResult {
	result := ShadowResult{
		Route:        routeKey,
		DispatchedAt: time.Now(),
	}

	sd.sanitizeHeaders(clone)

	ctx, cancel := context.WithTimeout(context.Background(), sd.config.Timeout)
	defer cancel()
	clone = clone.WithContext(ctx)

	start := time.Now()

	var innerResult ShadowResult
	done := make(chan struct{})
	go func() {
		defer close(done)
		defer func() {
			if rec := recover(); rec != nil {
				innerResult.PanicCaught = true
				innerResult.Error = "shadow dispatch panic recovered"
			}
		}()

		resp, doErr := sd.shadowPool.DoRequest(clone)
		if doErr != nil {
			innerResult.Error = doErr.Error()
			if transport.IsTimeoutError(doErr) || ctx.Err() == context.DeadlineExceeded {
				innerResult.TimedOut = true
			}
			return
		}
		defer resp.Body.Close()

		var bodyBuf bytes.Buffer
		limitedBody := io.LimitReader(resp.Body, sd.config.MaxShadowBodyBytes)
		io.Copy(&bodyBuf, limitedBody)
		innerResult.Body = bodyBuf.Bytes()

		innerResult.Headers = make(map[string]string, len(resp.Header))
		for name, values := range resp.Header {
			innerResult.Headers[strings.ToLower(name)] = strings.Join(values, ", ")
		}
		innerResult.StatusCode = resp.StatusCode
	}()

	select {
	case <-done:
		result.LatencyMs = time.Since(start).Milliseconds()
		result.StatusCode = innerResult.StatusCode
		result.Body = innerResult.Body
		result.Headers = innerResult.Headers
		result.Error = innerResult.Error
		result.TimedOut = innerResult.TimedOut
		result.PanicCaught = innerResult.PanicCaught
	case <-ctx.Done():
		result.TimedOut = true
		result.Error = "shadow timeout"
		result.LatencyMs = time.Since(start).Milliseconds()
	}

	return result
}

func (sd *ShadowDispatcher) shouldSample() bool {
	var b [8]byte
	_, err := rand.Read(b[:])
	if err != nil {
		return false
	}
	return float64(binary.BigEndian.Uint64(b[:]))/float64(^uint64(0)) < sd.config.SampleRate
}

func (sd *ShadowDispatcher) isSafeMethod(method string) bool {
	_, ok := safeMethods[method]
	return ok
}

func (sd *ShadowDispatcher) sanitizeHeaders(req *http.Request) {
	for _, header := range shadowStripHeaders {
		req.Header.Del(header)
	}
	for key := range req.Header {
		if strings.HasPrefix(strings.ToLower(key), "x-shadow") {
			req.Header.Del(key)
		}
	}
	req.Header.Set("X-Shadow-Mode", "true")
}
