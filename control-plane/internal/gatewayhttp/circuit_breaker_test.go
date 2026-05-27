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

func TestTwoCircuitBreakersIndependent(t *testing.T) {
	cfg := CircuitBreakerConfig{
		FailureThreshold: 3,
		CooldownDuration: 100 * time.Millisecond,
	}
	cb1 := NewCircuitBreaker(cfg)
	cb2 := NewCircuitBreaker(cfg)

	for i := 0; i < 3; i++ {
		cb1.RecordFailure()
	}
	if cb1.State() != CircuitOpen {
		t.Fatal("breaker 1 should be open")
	}

	if cb2.State() != CircuitClosed {
		t.Fatal("breaker 2 should still be closed")
	}
	if !cb2.Allow() {
		t.Fatal("breaker 2 should allow requests")
	}

	cb2.RecordFailure()
	cb2.RecordFailure()
	cb2.RecordFailure()
	if cb2.State() != CircuitOpen {
		t.Fatal("breaker 2 should open independently")
	}
	if cb1.State() != CircuitOpen {
		t.Fatal("breaker 1 should remain open")
	}
}

func TestCircuitBreakerFailRecoverFailCycle(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 2,
		CooldownDuration: 50 * time.Millisecond,
		HalfOpenMaxReqs:  1,
	})

	cb.RecordFailure()
	cb.RecordFailure()
	if cb.State() != CircuitOpen {
		t.Fatal("should be open after 2 failures")
	}

	time.Sleep(60 * time.Millisecond)
	if !cb.Allow() {
		t.Fatal("should allow in half-open after cooldown")
	}
	if cb.State() != CircuitHalfOpen {
		t.Fatal("should transition to half-open")
	}

	cb.RecordSuccess()
	if cb.State() != CircuitClosed {
		t.Fatalf("state = %s, want closed after half-open success", cb.StateName())
	}

	cb.RecordFailure()
	cb.RecordFailure()
	if cb.State() != CircuitOpen {
		t.Fatal("should reopen after 2 more failures on fresh cycle")
	}
}

func TestCircuitBreakerRecordSuccessResetsFailureCount(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 10,
		CooldownDuration: 1 * time.Second,
	})
	for i := 0; i < 5; i++ {
		cb.RecordFailure()
	}
	if cb.failureCount.Load() != 5 {
		t.Fatalf("failure count = %d, want 5", cb.failureCount.Load())
	}

	cb.RecordSuccess()
	if cb.failureCount.Load() != 0 {
		t.Fatalf("failure count = %d, want 0 after RecordSuccess", cb.failureCount.Load())
	}
	if cb.State() != CircuitClosed {
		t.Fatalf("state = %s, want closed", cb.StateName())
	}
}

func TestCircuitBreakerConcurrentTransitions(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 50,
		CooldownDuration: 500 * time.Millisecond,
	})

	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 10; j++ {
				cb.Allow()
				cb.RecordFailure()
				cb.State()
				cb.StateName()
				cb.RecordSuccess()
			}
		}()
	}
	wg.Wait()

	s := cb.StateName()
	if s != "closed" && s != "open" && s != "half-open" {
		t.Fatalf("invalid state after concurrent transitions: %s", s)
	}

	stats := cb.Stats()
	if stats.FailureCount < 0 {
		t.Fatal("failure count should not be negative")
	}
}
