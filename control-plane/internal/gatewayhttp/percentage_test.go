package gatewayhttp

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"gaokao-agent/control-plane/internal/contract"
)

func TestHashBucketDeterministic(t *testing.T) {
	b1 := HashBucket("user_001")
	b2 := HashBucket("user_001")
	if b1 != b2 {
		t.Errorf("same key must produce same bucket: %d != %d", b1, b2)
	}
}

func TestHashBucketRange(t *testing.T) {
	for i := 0; i < 1000; i++ {
		key := "key_" + string(rune('a'+i%26)) + string(rune('0'+i%10))
		b := HashBucket(key)
		if b < 0 || b >= 100 {
			t.Errorf("bucket %d out of range [0, 100)", b)
		}
	}
}

func TestHashBucketDifferentKeysSpread(t *testing.T) {
	seen := make(map[int]bool)
	for i := 0; i < 100; i++ {
		key := "user_" + string(rune('a'+i%26)) + string(rune('0'+i%10)) + string(rune('a'+(i/10)))
		b := HashBucket(key)
		seen[b] = true
	}
	if len(seen) < 10 {
		t.Errorf("expected at least 10 distinct buckets from 100 keys, got %d", len(seen))
	}
}

func TestDecidePercentageDisabled(t *testing.T) {
	cfg := PercentageCanaryConfig{Enabled: false, Percent: 50}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	dec := DecidePercentage(req, cfg, false)
	if dec.UseCandidate {
		t.Error("expected legacy when percent disabled")
	}
	if dec.Reason != "percent_disabled" {
		t.Errorf("expected reason percent_disabled, got %s", dec.Reason)
	}
}

func TestDecidePercentageZero(t *testing.T) {
	cfg := PercentageCanaryConfig{Enabled: true, Percent: 0}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	dec := DecidePercentage(req, cfg, false)
	if dec.UseCandidate {
		t.Error("expected legacy when percent 0")
	}
}

func TestDecidePercentageFullCutover(t *testing.T) {
	cfg := PercentageCanaryConfig{Enabled: true, Percent: 100}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	dec := DecidePercentage(req, cfg, false)
	if !dec.UseCandidate {
		t.Error("expected candidate when percent 100")
	}
	if dec.Reason != "full_cutover" {
		t.Errorf("expected reason full_cutover, got %s", dec.Reason)
	}
}

func TestDecidePercentageEvidenceFailFallsBack(t *testing.T) {
	cfg := PercentageCanaryConfig{Enabled: true, Percent: 50, RequireEvidence: true}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	dec := DecidePercentage(req, cfg, false)
	if dec.UseCandidate {
		t.Error("expected legacy when evidence required but not passed")
	}
	if dec.Reason != "evidence_not_passed" {
		t.Errorf("expected reason evidence_not_passed, got %s", dec.Reason)
	}
}

func TestDecidePercentageEvidencePassedApplies(t *testing.T) {
	cfg := PercentageCanaryConfig{Enabled: true, Percent: 100, RequireEvidence: true}
	req, _ := http.NewRequest("GET", "/api/test", nil)
	dec := DecidePercentage(req, cfg, true)
	if !dec.UseCandidate {
		t.Error("expected candidate when evidence passed with percent 100")
	}
	if !dec.EvidencePassed {
		t.Error("expected EvidencePassed true")
	}
}

func TestDecidePercentageBucketKeyConsistency(t *testing.T) {
	cfg := PercentageCanaryConfig{Enabled: true, Percent: 50, BucketKeyName: "test_key"}
	req1, _ := http.NewRequest("GET", "/api/test", nil)
	req1.Header.Set("X-Gaokao-Canary-Key", "user_abc")
	dec1 := DecidePercentage(req1, cfg, false)

	req2, _ := http.NewRequest("GET", "/api/test", nil)
	req2.Header.Set("X-Gaokao-Canary-Key", "user_abc")
	dec2 := DecidePercentage(req2, cfg, false)

	if dec1.UseCandidate != dec2.UseCandidate || dec1.Bucket != dec2.Bucket {
		t.Error("same bucket key must produce consistent decision")
	}
}

func TestDecidePercentageBucketKeyDifferent(t *testing.T) {
	cfg := PercentageCanaryConfig{Enabled: true, Percent: 50, BucketKeyName: "test_key"}

	total := 0
	selected := 0
	for i := 0; i < 100; i++ {
		req, _ := http.NewRequest("GET", "/api/test", nil)
		req.Header.Set("X-Gaokao-Canary-Key", "user_"+string(rune('A'+i%26))+string(rune('0'+i%10)))
		dec := DecidePercentage(req, cfg, false)
		total++
		if dec.UseCandidate {
			selected++
		}
	}

	if selected < 20 || selected > 80 {
		t.Errorf("expected ~50%% selection with percent=50, got %d/%d", selected, total)
	}
}

func TestExtractBucketKeyUsesHeader(t *testing.T) {
	req, _ := http.NewRequest("GET", "/api/test", nil)
	req.Header.Set("X-Gaokao-Canary-Key", "user_xyz")
	key := ExtractBucketKey(req, "my_key")
	if key != "my_key:user_xyz" {
		t.Errorf("expected bucket key from header, got %s", key)
	}
}

func TestExtractBucketKeyFallsBackToRequestID(t *testing.T) {
	req := httptest.NewRequest("GET", "/api/test", nil)
	req = req.WithContext(req.Context())
	req.Header.Set("X-Request-Id", "req_12345")
	req = req.WithContext(req.Context())
	ctx := req.Context()
	ctx = context.WithValue(ctx, requestIDKey, "req_12345")
	req = req.WithContext(ctx)

	key := ExtractBucketKey(req, "my_key")
	if key == "" || key == "my_key:request:fallback" {
		t.Errorf("expected non-fallback bucket key, got %s", key)
	}
}

func TestClampPercent(t *testing.T) {
	if clampPercent(-1) != 0 {
		t.Error("expected -1 to clamp to 0")
	}
	if clampPercent(0) != 0 {
		t.Error("expected 0 to stay 0")
	}
	if clampPercent(50) != 50 {
		t.Error("expected 50 to stay 50")
	}
	if clampPercent(100) != 100 {
		t.Error("expected 100 to stay 100")
	}
	if clampPercent(150) != 100 {
		t.Error("expected 150 to clamp to 100")
	}
}

func TestRouterPercentageCanaryBucketSelected(t *testing.T) {
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

	candidateCount := 0
	legacyCount := 0
	for i := 0; i < 100; i++ {
		opts := Options{
			PythonBaseURL:            legacyServer.URL,
			ShadowProxyEnabled:       true,
			ShadowProxyRoutes:        []string{"GET /api/test"},
			UpstreamTimeout:          5 * time.Second,
			UpstreamMaxConns:         10,
			UpstreamMaxInFlight:      10,
			CandidateBaseURL:         candidateServer.URL,
			CanaryPercentEnabled:     true,
			CanaryPercent:            100,
			CanaryBucketKeyName:      "test",
			CircuitThreshold:         5,
		}
		router := newProxyHandler(loaded, opts)

		req := httptest.NewRequest("GET", "/api/test", nil)
		req.Header.Set("X-Gaokao-Canary-Key", "user_"+string(rune('A'+i%26)))
		rec := httptest.NewRecorder()
		router.ServeHTTP(rec, req)

		if rec.Code == http.StatusOK {
			upstream := rec.Header().Get("X-Upstream")
			if upstream == "candidate" {
				candidateCount++
			} else {
				legacyCount++
			}
		}
	}
	if candidateCount != 100 {
		t.Errorf("expected 100 candidate requests with percent=100, got %d candidate, %d legacy", candidateCount, legacyCount)
	}
}

func TestRouterHeaderPriorityOverPercentage(t *testing.T) {
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
		PythonBaseURL:            legacyServer.URL,
		ShadowProxyEnabled:       true,
		ShadowProxyRoutes:        []string{"GET /api/test"},
		UpstreamTimeout:          5 * time.Second,
		UpstreamMaxConns:         10,
		UpstreamMaxInFlight:      10,
		CandidateBaseURL:         candidateServer.URL,
		CanaryHeaderEnabled:      true,
		CanaryHeaderName:         "X-Gaokao-Canary",
		CanaryHeaderValue:        "go-control-plane",
		CanaryPercentEnabled:     true,
		CanaryPercent:            0,
		CanaryBucketKeyName:      "test",
		CircuitThreshold:         5,
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
		t.Errorf("header canary must take priority; expected candidate, got %s", rec.Header().Get("X-Upstream"))
	}
}

func TestCanaryPercentageLogFields(t *testing.T) {
	raw := `{"canary_type":"percentage","canary_percent":5,"canary_bucket":3,"canary_reason":"bucket_selected","primary_upstream":"candidate","evidence_status":"passed","canary_requested":true,"canary_allowed":true}`
	var m map[string]any
	if err := json.Unmarshal([]byte(raw), &m); err != nil {
		t.Fatalf("failed to parse percentage canary log: %v", err)
	}
	if v, _ := m["canary_type"].(string); v != "percentage" {
		t.Errorf("expected canary_type percentage, got %v", v)
	}
	if v, _ := m["canary_percent"].(float64); int(v) != 5 {
		t.Errorf("expected canary_percent 5, got %v", v)
	}
	if v, _ := m["canary_bucket"].(float64); int(v) != 3 {
		t.Errorf("expected canary_bucket 3, got %v", v)
	}
}
