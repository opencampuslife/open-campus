package observability

import (
	"encoding/json"
	"log"
	"net/http"
	"time"
)

type Logger struct {
	level string
}

func NewLogger(level string) Logger {
	if level == "" {
		level = "info"
	}
	return Logger{level: level}
}

type LogContext struct {
	PathTemplate       string
	Surface            string
	RouteOwner         string
	UpstreamStatus     *int
	UpstreamLatencyMs  *int64
	ProxyMode          string
	ShadowProxyEnabled bool
	ErrorCode          *string
	AuthRequired       *bool
	CSRFRequired       *bool
	AuditRequired      *bool
	DeprecatedDenied   *bool
	SuccessorRoute     *string
	CanaryRequested    *bool
	CanaryAllowed      *bool
	CanaryReason       *string
	PrimaryUpstream    *string
	EvidenceStatus     *string
	CanaryType         *string
	CanaryPercent      *int
	CanaryBucket       *int
}

func BoolPtr(v bool) *bool       { return &v }
func IntPtr(v int) *int          { return &v }
func Int64Ptr(v int64) *int64    { return &v }
func StrPtr(v string) *string    { return &v }

func (logger Logger) Request(r *http.Request, status int, duration time.Duration, requestID string) {
	logger.RequestWithContext(r, status, duration, requestID, LogContext{})
}

func (logger Logger) RequestWithContext(r *http.Request, status int, duration time.Duration, requestID string, ctx LogContext) {
	if logger.level == "silent" {
		return
	}
	payload := map[string]any{
		"event":                "http_request",
		"method":               r.Method,
		"path":                 r.URL.Path,
		"status":               status,
		"duration_ms":          duration.Milliseconds(),
		"request_id":           requestID,
		"path_template":        ctx.PathTemplate,
		"surface":              ctx.Surface,
		"route_owner":          ctx.RouteOwner,
		"proxy_mode":           ctx.ProxyMode,
		"shadow_proxy_enabled": ctx.ShadowProxyEnabled,
	}
	if ctx.UpstreamStatus != nil {
		payload["upstream_status"] = *ctx.UpstreamStatus
	}
	if ctx.UpstreamLatencyMs != nil {
		payload["upstream_latency_ms"] = *ctx.UpstreamLatencyMs
	}
	if ctx.ErrorCode != nil {
		payload["error_code"] = *ctx.ErrorCode
	}
	if ctx.AuthRequired != nil {
		payload["auth_required"] = *ctx.AuthRequired
	}
	if ctx.CSRFRequired != nil {
		payload["csrf_required"] = *ctx.CSRFRequired
	}
	if ctx.AuditRequired != nil {
		payload["audit_required"] = *ctx.AuditRequired
	}
	if ctx.DeprecatedDenied != nil {
		payload["deprecated_route_denied"] = *ctx.DeprecatedDenied
	}
	if ctx.SuccessorRoute != nil {
		payload["successor_route"] = *ctx.SuccessorRoute
	}
	if ctx.CanaryRequested != nil {
		payload["canary_requested"] = *ctx.CanaryRequested
	}
	if ctx.CanaryAllowed != nil {
		payload["canary_allowed"] = *ctx.CanaryAllowed
	}
	if ctx.CanaryReason != nil {
		payload["canary_reason"] = *ctx.CanaryReason
	}
	if ctx.PrimaryUpstream != nil {
		payload["primary_upstream"] = *ctx.PrimaryUpstream
	}
	if ctx.EvidenceStatus != nil {
		payload["evidence_status"] = *ctx.EvidenceStatus
	}
	if ctx.CanaryType != nil {
		payload["canary_type"] = *ctx.CanaryType
	}
	if ctx.CanaryPercent != nil {
		payload["canary_percent"] = *ctx.CanaryPercent
	}
	if ctx.CanaryBucket != nil {
		payload["canary_bucket"] = *ctx.CanaryBucket
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return
	}
	log.Println(string(data))
}
