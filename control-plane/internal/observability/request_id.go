package observability

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
)

const RequestIDHeader = "X-Request-Id"

func RequestIDFrom(r *http.Request) string {
	if value := r.Header.Get(RequestIDHeader); value != "" {
		return value
	}
	return NewRequestID()
}

func NewRequestID() string {
	var bytes [12]byte
	if _, err := rand.Read(bytes[:]); err != nil {
		return "req_fallback"
	}
	return "req_" + hex.EncodeToString(bytes[:])
}
