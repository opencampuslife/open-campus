package parity

type Fixture struct {
	Cases []Case `json:"cases"`
}

type Case struct {
	Name     string            `json:"name"`
	Category string            `json:"category"`
	Source   string            `json:"source"`
	Route    string            `json:"route"`
	Method   string            `json:"method"`
	Path     string            `json:"path"`
	Headers  map[string]string `json:"headers"`
	Body     string            `json:"body"`
	BodyJSON map[string]any    `json:"body_json"`
	Privacy  PrivacyMetadata   `json:"privacy"`
	Expect   Expectation       `json:"expect"`
}

type PrivacyMetadata struct {
	Sanitized   bool   `json:"sanitized"`
	ContainsPII bool   `json:"contains_pii"`
	ReviewedBy  string `json:"reviewed_by"`
}

type Expectation struct {
	Status  StatusExpectation  `json:"status"`
	Compare CompareExpectation `json:"compare"`
	Latency LatencyExpectation `json:"latency"`
}

type StatusExpectation struct {
	Allowed []int `json:"allowed"`
}

type CompareExpectation struct {
	Status        string                 `json:"status"`
	Body          BodyCompareExpectation `json:"body"`
	Headers       map[string]string      `json:"headers"`
	IgnoreHeaders []string               `json:"ignore_headers"`
}

type BodyCompareExpectation struct {
	Mode           string   `json:"mode"`
	RequiredFields []string `json:"required_fields"`
}

type LatencyExpectation struct {
	WarnRatio float64 `json:"warn_ratio"`
	FailRatio float64 `json:"fail_ratio"`
}

type Report struct {
	Summary Summary      `json:"summary"`
	Cases   []CaseResult `json:"cases"`
}

type Summary struct {
	Total  int `json:"total"`
	Passed int `json:"passed"`
	Failed int `json:"failed"`
	Warned int `json:"warned"`
}

type CaseResult struct {
	Name   string         `json:"name"`
	Status string         `json:"status"`
	Legacy EndpointResult `json:"legacy"`
	Shadow EndpointResult `json:"shadow"`
	Diffs  []string       `json:"diffs"`
}

type EndpointResult struct {
	Status      int               `json:"status"`
	LatencyMS   int64             `json:"latency_ms"`
	Headers     map[string]string `json:"headers"`
	Body        string            `json:"body,omitempty"`
	BodyLength  int               `json:"body_length,omitempty"`
	BodySHA256  string            `json:"body_sha256,omitempty"`
	BodyPreview string            `json:"body_preview,omitempty"`
}
