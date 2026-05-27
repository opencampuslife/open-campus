package tests

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"gaokao-agent/control-plane/internal/contract"
)

func TestLoadRouteContract(t *testing.T) {
	loaded, err := contract.Load("../../contracts/routes.yaml")
	if err != nil {
		t.Fatalf("load contract: %v", err)
	}
	if got, want := len(loaded.Routes), 115; got != want {
		t.Fatalf("route count = %d, want %d", got, want)
	}
	if got, want := contract.LegacyGapCount(loaded), 0; got != want {
		t.Fatalf("legacy gap count = %d, want %d", got, want)
	}
}

func TestLoadMissingRouteContractFails(t *testing.T) {
	_, err := contract.Load(filepath.Join(t.TempDir(), "missing-routes.yaml"))
	if err == nil {
		t.Fatal("expected missing routes contract to fail")
	}
}

func TestInvalidRouteContractFails(t *testing.T) {
	path := writeTempContract(t, map[string]any{
		"version":       1,
		"frozen_source": "server.py",
		"routes":        []any{"not-a-route"},
	})
	_, err := contract.Load(path)
	if err == nil {
		t.Fatal("expected invalid routes contract to fail")
	}
}

func TestUnknownMethodFails(t *testing.T) {
	loaded := validContract()
	loaded.Routes[0].Method = "TRACE"
	err := contract.Validate(loaded)
	if err == nil || !strings.Contains(err.Error(), "unknown method") {
		t.Fatalf("expected unknown method error, got %v", err)
	}
}

func TestDuplicateRouteFails(t *testing.T) {
	loaded := validContract()
	loaded.Routes = append(loaded.Routes, loaded.Routes[0])
	err := contract.Validate(loaded)
	if err == nil || !strings.Contains(err.Error(), "duplicate route") {
		t.Fatalf("expected duplicate route error, got %v", err)
	}
}

func TestLegacyGapRequiresExit(t *testing.T) {
	loaded := validContract()
	loaded.Routes[0].LegacyFlags = []string{"legacy_policy_gap"}
	loaded.Routes[0].LegacyExit = nil
	err := contract.Validate(loaded)
	if err == nil || !strings.Contains(err.Error(), "legacy_policy_gap requires legacy_exit") {
		t.Fatalf("expected legacy exit error, got %v", err)
	}
}

func validContract() *contract.Contract {
	return &contract.Contract{
		Version:      1,
		FrozenSource: "services/api-gateway/src/server.py",
		Routes: []contract.Route{
			{
				Method:         "GET",
				Path:           "/api/health",
				Owner:          "api-gateway",
				Surface:        "public",
				Visibility:     "public",
				Auth:           "anonymous",
				CSRF:           "none",
				RateLimit:      "default",
				Audit:          false,
				Backend:        "legacy_python",
				MigrationWave:  "phase_1",
				LegacyFlags:    []string{},
				OpenAPIRef:     "contracts/openapi/public.yaml",
				OpenAPI:        "contracts/openapi/public.yaml",
				RequestSchema:  "None",
				ResponseSchema: "LegacyResponse",
			},
		},
	}
}

func writeTempContract(t *testing.T, payload map[string]any) string {
	t.Helper()
	data, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal temp contract: %v", err)
	}
	path := filepath.Join(t.TempDir(), "routes.yaml")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write temp contract: %v", err)
	}
	return path
}
