package gatewayhttp

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/contract"
)

func TestDecideCanaryDisabled(t *testing.T) {
	cfg := CanaryConfig{HeaderEnabled: false}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "go-control-plane")
	dec := DecideCanary(req, cfg, false)
	if dec.UseCandidate {
		t.Error("expected legacy when canary disabled")
	}
	if dec.Reason != "canary_disabled" {
		t.Errorf("expected reason canary_disabled, got %s", dec.Reason)
	}
}

func TestDecideCanaryHeaderMissing(t *testing.T) {
	cfg := CanaryConfig{HeaderEnabled: true, HeaderName: "X-Gaokao-Canary", HeaderValue: "go-control-plane"}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	dec := DecideCanary(req, cfg, false)
	if dec.UseCandidate {
		t.Error("expected legacy when header missing")
	}
	if dec.Reason != "header_missing" {
		t.Errorf("expected reason header_missing, got %s", dec.Reason)
	}
}

func TestDecideCanaryHeaderWrongValue(t *testing.T) {
	cfg := CanaryConfig{HeaderEnabled: true, HeaderName: "X-Gaokao-Canary", HeaderValue: "go-control-plane"}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "bad-value")
	dec := DecideCanary(req, cfg, false)
	if dec.UseCandidate {
		t.Error("expected legacy when header value wrong")
	}
	if dec.Reason != "header_mismatch" {
		t.Errorf("expected reason header_mismatch, got %s", dec.Reason)
	}
}

func TestDecideCanaryHeaderCorrectUsesCandidate(t *testing.T) {
	cfg := CanaryConfig{HeaderEnabled: true, HeaderName: "X-Gaokao-Canary", HeaderValue: "go-control-plane"}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "go-control-plane")
	dec := DecideCanary(req, cfg, false)
	if !dec.UseCandidate {
		t.Error("expected candidate when header matches")
	}
	if dec.Reason != "header_match" {
		t.Errorf("expected reason header_match, got %s", dec.Reason)
	}
	if !dec.HeaderMatched {
		t.Error("expected HeaderMatched true")
	}
}

func TestDecideCanaryEvidenceRequiredAndNotPassed(t *testing.T) {
	cfg := CanaryConfig{
		HeaderEnabled:   true,
		HeaderName:      "X-Gaokao-Canary",
		HeaderValue:     "go-control-plane",
		RequireEvidence: true,
	}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "go-control-plane")
	dec := DecideCanary(req, cfg, false)
	if dec.UseCandidate {
		t.Error("expected legacy when evidence not passed")
	}
	if dec.Reason != "evidence_not_passed" {
		t.Errorf("expected reason evidence_not_passed, got %s", dec.Reason)
	}
	if !dec.HeaderMatched {
		t.Error("expected HeaderMatched true even when evidence fails")
	}
}

func TestDecideCanaryEvidenceRequiredAndPassed(t *testing.T) {
	cfg := CanaryConfig{
		HeaderEnabled:   true,
		HeaderName:      "X-Gaokao-Canary",
		HeaderValue:     "go-control-plane",
		RequireEvidence: true,
	}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "go-control-plane")
	dec := DecideCanary(req, cfg, true)
	if !dec.UseCandidate {
		t.Error("expected candidate when header matches and evidence passed")
	}
	if !dec.EvidencePassed {
		t.Error("expected EvidencePassed true")
	}
}

func TestDecideCanaryEvidenceNotRequiredHeaderMatch(t *testing.T) {
	cfg := CanaryConfig{
		HeaderEnabled:   true,
		HeaderName:      "X-Gaokao-Canary",
		HeaderValue:     "go-control-plane",
		RequireEvidence: false,
	}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "go-control-plane")
	dec := DecideCanary(req, cfg, false)
	if !dec.UseCandidate {
		t.Error("expected candidate when header matches and evidence not required")
	}
	if !dec.EvidencePassed {
		t.Error("expected EvidencePassed true when evidence not required")
	}
}

func TestStripCanaryHeadersRemovesHeader(t *testing.T) {
	h := http.Header{}
	h.Set("X-Gaokao-Canary", "go-control-plane")
	h.Set("Content-Type", "application/json")
	stripCanaryHeaders(h, "X-Gaokao-Canary")
	if h.Get("X-Gaokao-Canary") != "" {
		t.Error("expected canary header to be stripped")
	}
	if h.Get("Content-Type") != "application/json" {
		t.Error("expected non-canary header to remain")
	}
}

func TestStripCanaryHeadersCaseInsensitive(t *testing.T) {
	h := http.Header{}
	h.Set("x-gaokao-canary", "go-control-plane")
	h.Set("Content-Type", "application/json")
	stripCanaryHeaders(h, "X-Gaokao-Canary")
	if h.Get("x-gaokao-canary") != "" {
		t.Error("expected lower-case canary header to be stripped")
	}
	if h.Get("Content-Type") != "application/json" {
		t.Error("expected non-canary header to remain")
	}
}

func TestBuildCanaryLogContext(t *testing.T) {
	decision := CanaryDecision{
		UseCandidate:   true,
		Reason:         "header_match",
		HeaderMatched:  true,
		EvidencePassed: true,
	}
	ctx := buildCanaryLogContext(contract.Route{}, "GET", "/api/test", Options{}, decision, PercentageCanaryDecision{}, "passed", "header", 0, 0)

	if ctx.ProxyMode != "header_canary" {
		t.Errorf("expected proxy_mode header_canary, got %s", ctx.ProxyMode)
	}
	if ctx.CanaryRequested == nil || !*ctx.CanaryRequested {
		t.Error("expected CanaryRequested true")
	}
	if ctx.CanaryAllowed == nil || !*ctx.CanaryAllowed {
		t.Error("expected CanaryAllowed true")
	}
	if ctx.CanaryReason == nil || *ctx.CanaryReason != "header_match" {
		t.Errorf("expected CanaryReason header_match, got %v", ctx.CanaryReason)
	}
	if ctx.PrimaryUpstream == nil || *ctx.PrimaryUpstream != "candidate" {
		t.Errorf("expected PrimaryUpstream candidate, got %v", ctx.PrimaryUpstream)
	}
	if ctx.EvidenceStatus == nil || *ctx.EvidenceStatus != "passed" {
		t.Errorf("expected EvidenceStatus passed, got %v", ctx.EvidenceStatus)
	}
}

func TestBuildCanaryLogContextFallsBackToLegacy(t *testing.T) {
	decision := CanaryDecision{
		UseCandidate:  false,
		Reason:        "header_missing",
		HeaderMatched: false,
	}
	ctx := buildCanaryLogContext(contract.Route{}, "GET", "/api/test", Options{}, decision, PercentageCanaryDecision{}, "disabled", "", 0, 0)

	if ctx.ProxyMode != "shadow_proxy" {
		t.Errorf("expected proxy_mode shadow_proxy, got %s", ctx.ProxyMode)
	}
	if ctx.CanaryRequested == nil || *ctx.CanaryRequested {
		t.Error("expected CanaryRequested false")
	}
	if ctx.PrimaryUpstream == nil || *ctx.PrimaryUpstream != "legacy" {
		t.Errorf("expected PrimaryUpstream legacy, got %v", ctx.PrimaryUpstream)
	}
}

func TestRouterCanaryDisabledUsesLegacy(t *testing.T) {
	legacyServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Upstream", "legacy")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer legacyServer.Close()

	candidateServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Upstream", "candidate")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer candidateServer.Close()

	loaded := &contract.Contract{
		Routes: []contract.Route{{
			Method:   "GET",
			Path:     "/api/test",
			Surface:  "public",
		}},
	}

	opts := Options{
		PythonBaseURL:       legacyServer.URL,
		ShadowProxyEnabled:  true,
		ShadowProxyRoutes:   []string{"GET /api/test"},
		UpstreamTimeout:     5 * time.Second,
		UpstreamMaxConns:    10,
		UpstreamMaxInFlight: 10,
		CandidateBaseURL:    candidateServer.URL,
		CanaryHeaderEnabled: false,
		CircuitThreshold:    5,
	}
	router := newProxyHandler(loaded, opts)

	req := httptest.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "go-control-plane")
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if rec.Header().Get("X-Upstream") != "legacy" {
		t.Errorf("expected legacy upstream, got %s", rec.Header().Get("X-Upstream"))
	}
}

func TestRouterCanaryEnabledHeaderMatchUsesCandidate(t *testing.T) {
	legacyServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Upstream", "legacy")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer legacyServer.Close()

	candidateServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Upstream", "candidate")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer candidateServer.Close()

	loaded := &contract.Contract{
		Routes: []contract.Route{{
			Method:   "GET",
			Path:     "/api/test",
			Surface:  "public",
		}},
	}

	opts := Options{
		PythonBaseURL:       legacyServer.URL,
		ShadowProxyEnabled:  true,
		ShadowProxyRoutes:   []string{"GET /api/test"},
		UpstreamTimeout:     5 * time.Second,
		UpstreamMaxConns:    10,
		UpstreamMaxInFlight: 10,
		CandidateBaseURL:    candidateServer.URL,
		CanaryHeaderEnabled: true,
		CanaryHeaderName:    "X-Gaokao-Canary",
		CanaryHeaderValue:   "go-control-plane",
		CircuitThreshold:    5,
	}
	router := newProxyHandler(loaded, opts)

	req := httptest.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "go-control-plane")
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if rec.Header().Get("X-Upstream") != "candidate" {
		t.Errorf("expected candidate upstream, got %s (headers: %v)", rec.Header().Get("X-Upstream"), rec.Header())
	}
}

func TestRouterCanaryEnabledHeaderMissingUsesLegacy(t *testing.T) {
	legacyServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Upstream", "legacy")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer legacyServer.Close()

	candidateServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Upstream", "candidate")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer candidateServer.Close()

	loaded := &contract.Contract{
		Routes: []contract.Route{{
			Method:   "GET",
			Path:     "/api/test",
			Surface:  "public",
		}},
	}

	opts := Options{
		PythonBaseURL:       legacyServer.URL,
		ShadowProxyEnabled:  true,
		ShadowProxyRoutes:   []string{"GET /api/test"},
		UpstreamTimeout:     5 * time.Second,
		UpstreamMaxConns:    10,
		UpstreamMaxInFlight: 10,
		CandidateBaseURL:    candidateServer.URL,
		CanaryHeaderEnabled: true,
		CanaryHeaderName:    "X-Gaokao-Canary",
		CanaryHeaderValue:   "go-control-plane",
		CircuitThreshold:    5,
	}
	router := newProxyHandler(loaded, opts)

	req := httptest.NewRequest("GET", "/api/test", nil)
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if rec.Header().Get("X-Upstream") != "legacy" {
		t.Errorf("expected legacy upstream when header missing, got %s", rec.Header().Get("X-Upstream"))
	}
}

func TestRouterCanaryEnabledEvidenceFailBlocksCandidate(t *testing.T) {
	legacyServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Upstream", "legacy")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer legacyServer.Close()

	candidateServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Upstream", "candidate")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer candidateServer.Close()

	loaded := &contract.Contract{
		Routes: []contract.Route{{
			Method:   "GET",
			Path:     "/api/test",
			Surface:  "public",
		}},
	}

	opts := Options{
		PythonBaseURL:         legacyServer.URL,
		ShadowProxyEnabled:    true,
		ShadowProxyRoutes:     []string{"GET /api/test"},
		UpstreamTimeout:       5 * time.Second,
		UpstreamMaxConns:      10,
		UpstreamMaxInFlight:   10,
		CandidateBaseURL:      candidateServer.URL,
		CanaryHeaderEnabled:   true,
		CanaryHeaderName:      "X-Gaokao-Canary",
		CanaryHeaderValue:     "go-control-plane",
		CanaryRequireEvidence: true,
		EvidencePassed:        false,
		CircuitThreshold:      5,
	}
	router := newProxyHandler(loaded, opts)

	req := httptest.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "go-control-plane")
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if rec.Header().Get("X-Upstream") != "legacy" {
		t.Errorf("expected legacy upstream when evidence fails, got %s", rec.Header().Get("X-Upstream"))
	}
}

func TestCanaryHeaderStrippedBeforeUpstream(t *testing.T) {
	var receivedHeaders http.Header
	legacyServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedHeaders = r.Header.Clone()
		w.Header().Set("X-Upstream", "legacy")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"ok":true}`))
	}))
	defer legacyServer.Close()

	loaded := &contract.Contract{
		Routes: []contract.Route{{
			Method:   "GET",
			Path:     "/api/test",
			Surface:  "public",
		}},
	}

	opts := Options{
		PythonBaseURL:       legacyServer.URL,
		ShadowProxyEnabled:  true,
		ShadowProxyRoutes:   []string{"GET /api/test"},
		UpstreamTimeout:     5 * time.Second,
		UpstreamMaxConns:    10,
		UpstreamMaxInFlight: 10,
		CanaryHeaderEnabled: false,
		CanaryHeaderName:    "X-Gaokao-Canary",
		CircuitThreshold:    5,
	}
	router := newProxyHandler(loaded, opts)

	req := httptest.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary", "go-control-plane")
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if receivedHeaders == nil {
		t.Fatal("expected upstream to receive headers")
	}
	if receivedHeaders.Get("X-Gaokao-Canary") != "" {
		t.Error("expected X-Gaokao-Canary header to be stripped before reaching upstream")
	}
	if receivedHeaders.Get("Content-Type") != "application/json" {
		t.Error("expected Content-Type header to be preserved")
	}
}

func TestCanaryModelFieldJSON(t *testing.T) {
	raw := `{"canary_requested":true,"canary_allowed":true,"canary_reason":"header_match","primary_upstream":"candidate","evidence_status":"passed"}`
	var m map[string]any
	if err := json.Unmarshal([]byte(raw), &m); err != nil {
		t.Fatalf("failed to parse canary log: %v", err)
	}
	if v, _ := m["canary_requested"].(bool); !v {
		t.Error("expected canary_requested true")
	}
	if v, _ := m["canary_allowed"].(bool); !v {
		t.Error("expected canary_allowed true")
	}
}
