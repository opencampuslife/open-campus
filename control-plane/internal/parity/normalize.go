package parity

import (
	"encoding/json"
	"strings"
)

var defaultIgnoredHeaders = map[string]struct{}{
	"date":              {},
	"server":            {},
	"content-length":    {},
	"transfer-encoding": {},
	"connection":        {},
	"keep-alive":        {},
	"x-request-id":      {},
	"x-runtime":         {},
	"x-process-time":    {},
}

func NormalizeHeaders(headers map[string]string, ignored []string) map[string]string {
	extraIgnored := make(map[string]struct{}, len(ignored))
	for _, name := range ignored {
		extraIgnored[strings.ToLower(name)] = struct{}{}
	}
	normalized := make(map[string]string)
	for name, value := range headers {
		lower := strings.ToLower(name)
		if _, ok := defaultIgnoredHeaders[lower]; ok {
			continue
		}
		if _, ok := extraIgnored[lower]; ok {
			continue
		}
		normalized[lower] = normalizeHeaderValue(lower, value)
	}
	return normalized
}

func normalizeHeaderValue(name string, value string) string {
	if name == "content-type" {
		return strings.ToLower(strings.TrimSpace(value))
	}
	return strings.TrimSpace(value)
}

func NormalizeBody(body string, mode string) string {
	switch mode {
	case "json_semantic", "exact_or_json_semantic":
		var decoded any
		if err := json.Unmarshal([]byte(body), &decoded); err == nil {
			data, marshalErr := json.Marshal(decoded)
			if marshalErr == nil {
				return string(data)
			}
		}
	}
	return body
}
