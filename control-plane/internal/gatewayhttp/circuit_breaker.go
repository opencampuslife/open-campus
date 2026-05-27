package gatewayhttp

import (
	"sync"
	"sync/atomic"
	"time"
)

const (
	CircuitClosed   int32 = 0
	CircuitOpen     int32 = 1
	CircuitHalfOpen int32 = 2
)

type CircuitBreakerConfig struct {
	FailureThreshold int
	CooldownDuration time.Duration
	HalfOpenMaxReqs  int
}

type CircuitBreaker struct {
	state               atomic.Int32
	failureCount        atomic.Int32
	halfOpenCount       atomic.Int32
	failureThreshold    int
	cooldownDuration    time.Duration
	halfOpenMaxReqs     int
	lastFailureTime     atomic.Value
	lastStateChangeTime atomic.Value
	mu                  sync.Mutex
}

func NewCircuitBreaker(cfg CircuitBreakerConfig) *CircuitBreaker {
	if cfg.FailureThreshold <= 0 {
		cfg.FailureThreshold = 5
	}
	if cfg.CooldownDuration <= 0 {
		cfg.CooldownDuration = 15 * time.Second
	}
	if cfg.HalfOpenMaxReqs <= 0 {
		cfg.HalfOpenMaxReqs = 3
	}
	cb := &CircuitBreaker{
		failureThreshold: cfg.FailureThreshold,
		cooldownDuration: cfg.CooldownDuration,
		halfOpenMaxReqs:  cfg.HalfOpenMaxReqs,
	}
	cb.state.Store(CircuitClosed)
	cb.lastFailureTime.Store(time.Time{})
	cb.lastStateChangeTime.Store(time.Now())
	return cb
}

func (cb *CircuitBreaker) Allow() bool {
	state := cb.state.Load()
	switch state {
	case CircuitClosed:
		return true
	case CircuitOpen:
		if time.Since(cb.lastStateChangeTime.Load().(time.Time)) >= cb.cooldownDuration {
			cb.transitionTo(CircuitHalfOpen)
			return cb.tryHalfOpen()
		}
		return false
	case CircuitHalfOpen:
		return cb.tryHalfOpen()
	}
	return false
}

func (cb *CircuitBreaker) RecordSuccess() {
	state := cb.state.Load()
	if state == CircuitHalfOpen {
		cb.halfOpenCount.Add(-1)
		if cb.halfOpenCount.Load() <= 0 {
			cb.transitionTo(CircuitClosed)
		}
	}
	cb.failureCount.Store(0)
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.lastFailureTime.Store(time.Now())
	count := cb.failureCount.Add(1)
	if count >= int32(cb.failureThreshold) {
		cb.transitionTo(CircuitOpen)
	}
}

func (cb *CircuitBreaker) transitionTo(newState int32) {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	oldState := cb.state.Swap(newState)
	if oldState != newState {
		cb.lastStateChangeTime.Store(time.Now())
	}
	if newState == CircuitClosed {
		cb.failureCount.Store(0)
	}
	if newState == CircuitHalfOpen {
		cb.halfOpenCount.Store(int32(cb.halfOpenMaxReqs))
	} else {
		cb.halfOpenCount.Store(0)
	}
}

func (cb *CircuitBreaker) tryHalfOpen() bool {
	current := cb.halfOpenCount.Load()
	if current <= 0 {
		return false
	}
	if cb.halfOpenCount.CompareAndSwap(current, current-1) {
		return true
	}
	return false
}

func (cb *CircuitBreaker) State() int32 {
	return cb.state.Load()
}

func (cb *CircuitBreaker) StateName() string {
	switch cb.state.Load() {
	case CircuitClosed:
		return "closed"
	case CircuitOpen:
		return "open"
	case CircuitHalfOpen:
		return "half-open"
	}
	return "unknown"
}

func (cb *CircuitBreaker) Stats() CircuitBreakerStats {
	return CircuitBreakerStats{
		State:         cb.StateName(),
		FailureCount:  cb.failureCount.Load(),
		LastStateTime: cb.lastStateChangeTime.Load().(time.Time),
	}
}

type CircuitBreakerStats struct {
	State         string
	FailureCount  int32
	LastStateTime time.Time
}
