package transport

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestProxyForwardsRequestAndHeaders(t *testing.T) {
	received := make(chan *http.Request, 1)
	body := make(chan string, 1)
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data, _ := io.ReadAll(r.Body)
		body <- string(data)
		received <- r
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Connection", "keep-alive")
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(`{"error":"upstream"}`))
	}))
	defer upstream.Close()

	proxy, err := NewPythonProxy(upstream.URL, time.Second, "shadow")
	if err != nil {
		t.Fatalf("new proxy: %v", err)
	}
	request := httptest.NewRequest(http.MethodPost, "/api/gaokao/chat?foo=bar", strings.NewReader(`{"message":"hi"}`))
	request.Host = "shadow.local"
	request.RemoteAddr = "127.0.0.1:8080"
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Authorization", "Bearer token")
	request.Header.Set("Cookie", "sid=1")
	request.Header.Set("Connection", "keep-alive")
	InjectForwardedHeaders(request, "req_123", "shadow")
	recorder := httptest.NewRecorder()

	if err := proxy.ServeHTTP(recorder, request); err != nil {
		t.Fatalf("serve proxy: %v", err)
	}
	if recorder.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusForbidden)
	}
	if recorder.Header().Get("Connection") != "" {
		t.Fatalf("connection header should be stripped, got %q", recorder.Header().Get("Connection"))
	}
	if recorder.Body.String() != `{"error":"upstream"}` {
		t.Fatalf("body = %q", recorder.Body.String())
	}
	gotRequest := <-received
	if gotRequest.Method != http.MethodPost || gotRequest.URL.Path != "/api/gaokao/chat" || gotRequest.URL.RawQuery != "foo=bar" {
		t.Fatalf("unexpected upstream request: %s %s?%s", gotRequest.Method, gotRequest.URL.Path, gotRequest.URL.RawQuery)
	}
	if gotRequest.Header.Get("X-Request-Id") != "req_123" {
		t.Fatalf("request id = %q", gotRequest.Header.Get("X-Request-Id"))
	}
	if gotRequest.Header.Get("X-Gaokao-Gateway-Mode") != "shadow" {
		t.Fatalf("gateway mode = %q", gotRequest.Header.Get("X-Gaokao-Gateway-Mode"))
	}
	if gotRequest.Header.Get("X-Forwarded-Host") != "shadow.local" {
		t.Fatalf("forwarded host = %q", gotRequest.Header.Get("X-Forwarded-Host"))
	}
	if gotRequest.Header.Get("Connection") != "" {
		t.Fatalf("connection header should not be forwarded, got %q", gotRequest.Header.Get("Connection"))
	}
	if got := <-body; got != `{"message":"hi"}` {
		t.Fatalf("upstream body = %q", got)
	}
}

func TestTimeoutClassification(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(50 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	proxy, err := NewPythonProxy(upstream.URL, 10*time.Millisecond, "shadow")
	if err != nil {
		t.Fatalf("new proxy: %v", err)
	}
	request := httptest.NewRequest(http.MethodPost, "/api/gaokao/chat", strings.NewReader(`{}`))
	recorder := httptest.NewRecorder()
	err = proxy.ServeHTTP(recorder, request)
	if !IsTimeoutError(err) {
		t.Fatalf("expected timeout error, got %v", err)
	}
}
