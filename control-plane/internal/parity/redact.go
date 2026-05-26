package parity

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"unicode/utf8"
)

func RedactedReport(report Report) Report {
	sanitized := report
	sanitized.Cases = make([]CaseResult, len(report.Cases))
	for index, result := range report.Cases {
		sanitized.Cases[index] = result
		sanitized.Cases[index].Legacy = redactEndpoint(result.Legacy)
		sanitized.Cases[index].Shadow = redactEndpoint(result.Shadow)
	}
	return sanitized
}

func redactEndpoint(result EndpointResult) EndpointResult {
	if result.Body == "" {
		return result
	}
	body := result.Body
	result.BodyLength = utf8.RuneCountInString(body)
	sum := sha256.Sum256([]byte(body))
	result.BodySHA256 = hex.EncodeToString(sum[:8])
	result.BodyPreview = fmt.Sprintf("[redacted len=%d sha256=%s]", result.BodyLength, result.BodySHA256)
	result.Body = ""
	return result
}
