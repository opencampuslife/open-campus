package gatewayhttp

import (
	"net/http"

	"gaokao-agent/control-plane/internal/contract"
)

type HealthResponse struct {
	Status                         string `json:"status"`
	Service                        string `json:"service"`
	Mode                           string `json:"mode"`
	RoutesContractLoaded           bool   `json:"routes_contract_loaded"`
	RouteCount                     int    `json:"route_count"`
	LegacyGapCount                 int    `json:"legacy_gap_count"`
	DeprecatedCompatibilityAliases int    `json:"deprecated_compatibility_alias_count"`
}

func HealthHandler(loaded *contract.Contract, shadowMode bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			WriteError(w, http.StatusMethodNotAllowed, CodeMethodNotAllowed, "Method not allowed", requestIDFromContext(r))
			return
		}
		routeCount := 0
		if loaded != nil {
			routeCount = len(loaded.Routes)
		}
		mode := "active"
		if shadowMode {
			mode = "shadow"
		}
		WriteJSON(w, http.StatusOK, HealthResponse{
			Status:                         "ok",
			Service:                        "gaokao-gateway",
			Mode:                           mode,
			RoutesContractLoaded:           loaded != nil,
			RouteCount:                     routeCount,
			LegacyGapCount:                 contract.LegacyGapCount(loaded),
			DeprecatedCompatibilityAliases: contract.DeprecatedCompatibilityAliasCount(loaded),
		})
	}
}
