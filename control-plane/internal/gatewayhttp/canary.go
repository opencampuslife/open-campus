package gatewayhttp

import (
	"net/http"
	"strings"
)

type CanaryConfig struct {
	HeaderEnabled   bool
	HeaderName      string
	HeaderValue     string
	RequireEvidence bool
}

type CanaryDecision struct {
	UseCandidate   bool
	Reason         string
	HeaderMatched  bool
	EvidencePassed bool
}

func DecideCanary(r *http.Request, config CanaryConfig, evidencePassed bool) CanaryDecision {
	if !config.HeaderEnabled {
		return CanaryDecision{UseCandidate: false, Reason: "canary_disabled"}
	}
	headerValue := r.Header.Get(config.HeaderName)
	if headerValue == "" {
		return CanaryDecision{UseCandidate: false, Reason: "header_missing"}
	}
	if headerValue != config.HeaderValue {
		return CanaryDecision{UseCandidate: false, Reason: "header_mismatch"}
	}
	if config.RequireEvidence && !evidencePassed {
		return CanaryDecision{UseCandidate: false, Reason: "evidence_not_passed", HeaderMatched: true}
	}
	return CanaryDecision{
		UseCandidate:   true,
		Reason:         "header_match",
		HeaderMatched:  true,
		EvidencePassed: !config.RequireEvidence || evidencePassed,
	}
}

func stripCanaryHeaders(header http.Header, headerName string) {
	if strings.TrimSpace(headerName) == "" {
		headerName = "X-Gaokao-Canary"
	}
	header.Del(headerName)
	lower := strings.ToLower(headerName)
	if lower != headerName {
		header.Del(lower)
	}
}
