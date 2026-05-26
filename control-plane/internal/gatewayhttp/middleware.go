package gatewayhttp

import (
	"context"
	"net/http"
	"time"

	"gaokao-agent/control-plane/internal/observability"
)

type contextKey string

const requestIDKey contextKey = "request_id"

type logContextRecorder struct {
	http.ResponseWriter
	status     int
	logContext observability.LogContext
}

func (recorder *logContextRecorder) WriteHeader(status int) {
	recorder.status = status
	recorder.ResponseWriter.WriteHeader(status)
}

func (recorder *logContextRecorder) SetLogContext(ctx observability.LogContext) {
	recorder.logContext = ctx
}

func requestIDFromContext(r *http.Request) string {
	value, _ := r.Context().Value(requestIDKey).(string)
	return value
}

func WithRequestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestID := observability.RequestIDFrom(r)
		w.Header().Set(observability.RequestIDHeader, requestID)
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), requestIDKey, requestID)))
	})
}

func WithPanicRecovery(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if recovered := recover(); recovered != nil {
				WriteError(w, http.StatusInternalServerError, CodeInternalError, "Internal server error", requestIDFromContext(r))
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func WithBodyLimit(limitBytes int64, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if limitBytes > 0 {
			r.Body = http.MaxBytesReader(w, r.Body, limitBytes)
			if r.ContentLength > limitBytes {
				WriteError(w, http.StatusRequestEntityTooLarge, CodeRequestTooLarge, "Request body too large", requestIDFromContext(r))
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

func WithTimeout(timeout time.Duration, next http.Handler) http.Handler {
	if timeout <= 0 {
		return next
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), timeout)
		defer cancel()
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func WithStructuredLogging(logger observability.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		recorder := &logContextRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(recorder, r)
		logger.RequestWithContext(r, recorder.status, time.Since(start), requestIDFromContext(r), recorder.logContext)
	})
}
