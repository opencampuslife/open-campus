package transport

import (
	"context"
	"errors"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type PythonProxy struct {
	baseURL *url.URL
	client  *http.Client
	mode    string
}

func NewPythonProxy(rawBaseURL string, timeout time.Duration, mode string) (*PythonProxy, error) {
	parsed, err := url.Parse(rawBaseURL)
	if err != nil {
		return nil, err
	}
	if mode == "" {
		mode = "shadow"
	}
	return &PythonProxy{
		baseURL: parsed,
		client:  &http.Client{Timeout: timeout},
		mode:    mode,
	}, nil
}

func (proxy *PythonProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) error {
	upstreamReq, err := proxy.buildRequest(r)
	if err != nil {
		return err
	}
	resp, err := proxy.client.Do(upstreamReq)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	copyResponseHeaders(w.Header(), resp.Header)
	w.WriteHeader(resp.StatusCode)
	_, copyErr := io.Copy(w, resp.Body)
	return copyErr
}

func (proxy *PythonProxy) buildRequest(r *http.Request) (*http.Request, error) {
	upstreamURL := *proxy.baseURL
	upstreamURL.Path = r.URL.Path
	upstreamURL.RawQuery = r.URL.RawQuery
	upstreamReq, err := http.NewRequestWithContext(r.Context(), r.Method, upstreamURL.String(), r.Body)
	if err != nil {
		return nil, err
	}
	copyRequestHeaders(upstreamReq.Header, r.Header)
	upstreamReq.Host = proxy.baseURL.Host
	return upstreamReq, nil
}

func copyRequestHeaders(dst http.Header, src http.Header) {
	for name, values := range src {
		if isHopByHopHeader(name) {
			continue
		}
		dst[name] = append([]string(nil), values...)
	}
}

func copyResponseHeaders(dst http.Header, src http.Header) {
	for name, values := range src {
		if isHopByHopHeader(name) {
			continue
		}
		dst[name] = append([]string(nil), values...)
	}
}

func InjectForwardedHeaders(r *http.Request, requestID string, mode string) {
	if mode == "" {
		mode = "shadow"
	}
	if requestID != "" {
		r.Header.Set("X-Request-Id", requestID)
	}
	r.Header.Set("X-Forwarded-Host", r.Host)
	r.Header.Set("X-Forwarded-Proto", forwardedProto(r))
	r.Header.Set("X-Forwarded-For", forwardedFor(r))
	r.Header.Set("X-Gaokao-Gateway-Mode", mode)
}

func forwardedProto(r *http.Request) string {
	if value := r.Header.Get("X-Forwarded-Proto"); value != "" {
		return value
	}
	if r.TLS != nil {
		return "https"
	}
	return "http"
}

func forwardedFor(r *http.Request) string {
	if existing := r.Header.Get("X-Forwarded-For"); existing != "" {
		return existing + ", " + remoteHost(r.RemoteAddr)
	}
	return remoteHost(r.RemoteAddr)
}

func remoteHost(remoteAddr string) string {
	host, _, err := net.SplitHostPort(remoteAddr)
	if err == nil {
		return host
	}
	return remoteAddr
}

func isHopByHopHeader(name string) bool {
	switch strings.ToLower(name) {
	case "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade":
		return true
	default:
		return false
	}
}

func IsTimeoutError(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return true
	}
	var netErr net.Error
	return errors.As(err, &netErr) && netErr.Timeout()
}
