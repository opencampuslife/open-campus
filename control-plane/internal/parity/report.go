package parity

import "encoding/json"

func MarshalReport(report Report) ([]byte, error) {
	return json.MarshalIndent(RedactedReport(report), "", "  ")
}
