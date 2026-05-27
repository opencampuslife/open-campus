package gatewayhttp

import (
	"sync"
	"testing"
	"time"
)

func TestCircuitBreakerClosedAllowsRequests(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 3,
		CooldownDuration: 1 * time.Second,
	})
	for i := 0; i < 10; i++ {
		if !cb.Allow() {
			t.Fatalf("allow %d: closed circuit should allow requests", i)
		}
	}
	if cb.State() != CircuitClosed {
		t.Fatalf("state = %d, want closed", cb.State())
	}
}

func TestCircuitBreakerOpensAfterFailures(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 3,
		CooldownDuration: 500 * time.Millisecond,
	})
	for i := 0; i < 3; i++ {
		cb.RecordFailure()
	}
	if cb.State() != CircuitOpen {
		t.Fatalf("state = %s, want open after %d failures", cb.StateName(), 3)
	}
	if cb.Allow() {
		t.Fatal("open circuit should not allow requests")
	}
}

func TestCircuitBreakerRecordSuccessDoesNotOpen(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 5,
		CooldownDuration: 1 * time.Second,
	})
	for i := 0; i < 3; i++ {
		cb.RecordFailure()
	}
	for i := 0; i < 3; i++ {
		cb.RecordSuccess()
	}
	if cb.State() != CircuitClosed {
		t.Fatalf("state = %s, want closed after success resets", cb.StateName())
	}
	if !cb.Allow() {
		t.Fatal("closed circuit should allow requests")
	}
}

func TestCircuitBreakerHalfOpenProbes(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 2,
		CooldownDuration: 50 * time.Millisecond,
		HalfOpenMaxReqs:  2,
	})
	for i := 0; i < 2; i++ {
		cb.RecordFailure()
	}
	if cb.State() != CircuitOpen {
		t.Fatalf("state = %s, want open", cb.StateName())
	}
	time.Sleep(100 * time.Millisecond)
	if !cb.Allow() {
		t.Fatal("first request should transition to half-open and allow")
	}
	if cb.State() != CircuitHalfOpen {
		t.Fatalf("state = %s, want half-open", cb.StateName())
	}
	if !cb.Allow() {
		t.Fatal("second half-open request should be allowed")
	}
	if cb.Allow() {
		t.Fatal("third half-open request should be rejected (max probes = 2)")
	}
}

func TestCircuitBreakerHalfOpenSuccessCloses(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 2,
		CooldownDuration: 50 * time.Millisecond,
		HalfOpenMaxReqs:  1,
	})
	for i := 0; i < 2; i++ {
		cb.RecordFailure()
	}
	time.Sleep(100 * time.Millisecond)
	cb.Allow()
	if cb.State() != CircuitHalfOpen {
		t.Fatalf("state = %s, want half-open", cb.StateName())
	}
	cb.RecordSuccess()
	if cb.State() != CircuitClosed {
		t.Fatalf("state = %s, want closed after success", cb.StateName())
	}
}

func TestCircuitBreakerHalfOpenFailureReopens(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 2,
		CooldownDuration: 50 * time.Millisecond,
		HalfOpenMaxReqs:  1,
	})
	for i := 0; i < 2; i++ {
		cb.RecordFailure()
	}
	time.Sleep(100 * time.Millisecond)
	cb.Allow()
	cb.RecordFailure()
	if cb.State() != CircuitOpen {
		t.Fatalf("state = %s, want open after half-open failure", cb.StateName())
	}
}

func TestCircuitBreakerStats(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 5,
		CooldownDuration: 10 * time.Second,
	})
	for i := 0; i < 3; i++ {
		cb.RecordFailure()
	}
	stats := cb.Stats()
	if stats.FailureCount != 3 {
		t.Fatalf("failure count = %d, want 3", stats.FailureCount)
	}
	if stats.State != "closed" {
		t.Fatalf("state = %s, want closed", stats.State)
	}
}

func TestCircuitBreakerConcurrentAccess(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 20,
		CooldownDuration: 200 * time.Millisecond,
	})
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 5; j++ {
				cb.Allow()
				cb.RecordFailure()
			}
		}()
	}
	wg.Wait()
	if cb.state.Load() != CircuitOpen {
		t.Fatalf("state = %s, want open after concurrent failures", cb.StateName())
	}
}

func TestCircuitBreakerDefaultConfig(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{})
	for i := 0; i < 5; i++ {
		cb.RecordFailure()
	}
	if cb.State() != CircuitOpen {
		t.Fatalf("default threshold: state = %s, want open", cb.StateName())
	}
}
