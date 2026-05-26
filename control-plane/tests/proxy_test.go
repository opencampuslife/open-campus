package tests

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/contract"
	"gaokao-agent/control-plane/internal/gatewayhttp"
)

func TestProxyDisabledReturnsDisabledError(t *testing.T) {
	router := gatewayhttp.NewRouter(chatContract(), gatewayhttp.Options{
		ShadowMode:      true,
		LogLevel:        "silent",
		PythonBaseURL:   "http://127.0.0.1:8787",
		UpstreamTimeout: time.Second,
	})
	request := httptest.NewRequest(http.MethodPost, "/api/gaokao/chat", strings.NewReader(`{"message":"hi"}`))
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusNotFound)
	}
	assertErrorCode(t, recorder, gatewayhttp.CodeProxyRouteDisabled)
}

func TestProxyMethodMismatchReturns405(t *testing.T) {
	router := gatewayhttp.NewRouter(chatContract(), gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: true,
		ShadowProxyRoutes:  []string{"POST /api/gaokao/chat"},
		PythonBaseURL:      "http://127.0.0.1:8787",
		UpstreamTimeout:    time.Second,
	})
	request := httptest.NewRequest(http.MethodGet, "/api/gaokao/chat", nil)
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusMethodNotAllowed {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusMethodNotAllowed)
	}
	assertErrorCode(t, recorder, gatewayhttp.CodeMethodNotAllowed)
}

func TestProxyEnabledForwardsUpstreamResponse(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/gaokao/chat" || r.URL.RawQuery != "x=1" {
			t.Fatalf("unexpected upstream request: %s %s?%s", r.Method, r.URL.Path, r.URL.RawQuery)
		}
		if r.Header.Get("X-Request-Id") == "" {
			t.Fatal("missing request id")
		}
		if r.Header.Get("X-Gaokao-Gateway-Mode") != "shadow" {
			t.Fatalf("gateway mode = %q", r.Header.Get("X-Gaokao-Gateway-Mode"))
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(`{"error":"legacy_forbidden"}`))
	}))
	defer upstream.Close()

	router := gatewayhttp.NewRouter(chatContract(), gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: true,
		ShadowProxyRoutes:  []string{"POST /api/gaokao/chat"},
		PythonBaseURL:      upstream.URL,
		UpstreamTimeout:    time.Second,
	})
	request := httptest.NewRequest(http.MethodPost, "/api/gaokao/chat?x=1", strings.NewReader(`{"message":"hi"}`))
	request.Header.Set("Content-Type", "application/json")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusForbidden)
	}
	if recorder.Body.String() != `{"error":"legacy_forbidden"}` {
		t.Fatalf("body = %q", recorder.Body.String())
	}
}

func TestProxyUnavailableReturns502(t *testing.T) {
	router := gatewayhttp.NewRouter(chatContract(), gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: true,
		ShadowProxyRoutes:  []string{"POST /api/gaokao/chat"},
		PythonBaseURL:      "http://127.0.0.1:1",
		UpstreamTimeout:    50 * time.Millisecond,
	})
	request := httptest.NewRequest(http.MethodPost, "/api/gaokao/chat", strings.NewReader(`{}`))
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusBadGateway)
	}
	assertErrorCode(t, recorder, gatewayhttp.CodeUpstreamUnavailable)
}

func TestProxyTimeoutReturns504(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(80 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	router := gatewayhttp.NewRouter(chatContract(), gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: true,
		ShadowProxyRoutes:  []string{"POST /api/gaokao/chat"},
		PythonBaseURL:      upstream.URL,
		UpstreamTimeout:    10 * time.Millisecond,
	})
	request := httptest.NewRequest(http.MethodPost, "/api/gaokao/chat", strings.NewReader(`{}`))
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusGatewayTimeout {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusGatewayTimeout)
	}
	assertErrorCode(t, recorder, gatewayhttp.CodeUpstreamTimeout)
}

func TestProxyLargeBodyReturns413BeforeUpstream(t *testing.T) {
	upstreamCalled := false
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		upstreamCalled = true
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	router := gatewayhttp.NewRouter(chatContract(), gatewayhttp.Options{
		ShadowMode:         true,
		LogLevel:           "silent",
		ShadowProxyEnabled: true,
		ShadowProxyRoutes:  []string{"POST /api/gaokao/chat"},
		PythonBaseURL:      upstream.URL,
		UpstreamTimeout:    time.Second,
		BodyLimitBytes:     3,
	})
	request := httptest.NewRequest(http.MethodPost, "/api/gaokao/chat", io.NopCloser(strings.NewReader("abcd")))
	request.ContentLength = 4
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusRequestEntityTooLarge)
	}
	if upstreamCalled {
		t.Fatal("upstream should not be called for oversized request")
	}
	assertErrorCode(t, recorder, gatewayhttp.CodeRequestTooLarge)
}

func chatContract() *contract.Contract {
	return &contract.Contract{
		Version:      1,
		FrozenSource: "services/api-gateway/src/server.py",
		Routes: []contract.Route{
			{
				Method:         "POST",
				Path:           "/api/gaokao/chat",
				Owner:          "api-gateway",
				Surface:        "public",
				Visibility:     "public",
				Auth:           "anonymous",
				CSRF:           "none",
				RateLimit:      "chat_30_per_minute",
				Audit:          true,
				Backend:        "legacy_python",
				MigrationWave:  "phase_2",
				LegacyFlags:    []string{},
				OpenAPIRef:     "contracts/openapi/public.yaml",
				OpenAPI:        "contracts/openapi/public.yaml",
				RequestSchema:  "LegacyJsonRequest",
				ResponseSchema: "LegacyResponse",
			},
		},
	}
}
