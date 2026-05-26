package gatewayhttp

import (
	"encoding/json"
	"net/http"
)

const (
	CodeRouteNotFound             = "ROUTE_NOT_FOUND"
	CodeMethodNotAllowed          = "METHOD_NOT_ALLOWED"
	CodeRequestTooLarge           = "REQUEST_TOO_LARGE"
	CodeInternalError             = "INTERNAL_ERROR"
	CodeContractViolation         = "CONTRACT_VIOLATION"
	CodeProxyRouteDisabled        = "PROXY_ROUTE_DISABLED"
	CodeUpstreamUnavailable       = "UPSTREAM_UNAVAILABLE"
	CodeUpstreamTimeout           = "UPSTREAM_TIMEOUT"
	CodeDeprecatedRouteNotProxied = "DEPRECATED_ROUTE_NOT_PROXIED"
)

type ErrorEnvelope struct {
	Error ErrorBody `json:"error"`
}

type ErrorBody struct {
	Code      string `json:"code"`
	Message   string `json:"message"`
	RequestID string `json:"request_id"`
}

func WriteJSON(w http.ResponseWriter, status int, payload any) {
	body, err := json.Marshal(payload)
	if err != nil {
		status = http.StatusInternalServerError
		body = []byte(`{"error":{"code":"INTERNAL_ERROR","message":"failed to encode response","request_id":""}}`)
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write(body)
}

func WriteError(w http.ResponseWriter, status int, code string, message string, requestID string) {
	WriteJSON(w, status, ErrorEnvelope{
		Error: ErrorBody{
			Code:      code,
			Message:   message,
			RequestID: requestID,
		},
	})
}
