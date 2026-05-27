package gatewayhttp

import (
	"bytes"
	"net/http"
	"strings"
	"sync"
)

type captureResponseWriter struct {
	http.ResponseWriter
	status      int
	wroteHeader bool
	buf         bytes.Buffer
	limit       int64
	total       int64
	headers     map[string]string
	mu          sync.Mutex
}

func newCaptureResponseWriter(w http.ResponseWriter, limit int64) *captureResponseWriter {
	if limit <= 0 {
		limit = 1 << 20
	}
	return &captureResponseWriter{
		ResponseWriter: w,
		status:         http.StatusOK,
		limit:          limit,
		headers:        make(map[string]string),
	}
}

func (crw *captureResponseWriter) WriteHeader(status int) {
	crw.mu.Lock()
	defer crw.mu.Unlock()
	if crw.wroteHeader {
		return
	}
	crw.status = status
	crw.wroteHeader = true
	for name, values := range crw.Header() {
		crw.headers[strings.ToLower(name)] = strings.Join(values, ", ")
	}
	crw.ResponseWriter.WriteHeader(status)
}

func (crw *captureResponseWriter) Write(data []byte) (int, error) {
	if !crw.wroteHeader {
		crw.WriteHeader(http.StatusOK)
	}
	n, err := crw.ResponseWriter.Write(data)
	if n > 0 && crw.total < crw.limit {
		remaining := crw.limit - crw.total
		if int64(n) > remaining {
			crw.buf.Write(data[:remaining])
		} else {
			crw.buf.Write(data[:n])
		}
	}
	crw.total += int64(n)
	return n, err
}

func (crw *captureResponseWriter) Body() []byte {
	return crw.buf.Bytes()
}

func (crw *captureResponseWriter) StatusCode() int {
	return crw.status
}

func (crw *captureResponseWriter) CapturedHeaders() map[string]string {
	crw.mu.Lock()
	defer crw.mu.Unlock()
	result := make(map[string]string, len(crw.headers))
	for k, v := range crw.headers {
		result[k] = v
	}
	return result
}

func (crw *captureResponseWriter) BodyTruncated() bool {
	return crw.total > crw.limit
}
