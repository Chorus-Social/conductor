"""Retry logic with exponential backoff for Conductor."""

import asyncio
import random
import logging
from typing import Callable, TypeVar, Optional
from datetime import datetime, timedelta

from conductor.errors import (
    ConductorError,
    ConsensusTimeoutError,
    NetworkPartitionError,
    VDFComputationError
)

logger = logging.getLogger(__name__)

T = TypeVar('T')

async def exponential_backoff(
    func: Callable,
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (ConductorError,)
) -> T:
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter
        retryable_exceptions: Tuple of exception types to retry on
        
    Returns:
        Result of the function call
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            
            # Check if this exception is retryable
            if not isinstance(e, retryable_exceptions):
                logger.error(f"Non-retryable exception: {e}")
                raise
                
            # Don't retry on the last attempt
            if attempt == max_retries:
                logger.error(f"All {max_retries} retries exhausted for {func.__name__}")
                break
                
            # Calculate delay with exponential backoff
            delay = min(base_delay * (2 ** attempt), max_delay)
            
            # Add jitter to prevent thundering herd
            if jitter:
                jitter_amount = delay * 0.1 * (2 * random.random() - 1)  # +/- 10%
                delay += jitter_amount
                
            logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay:.2f}s: {e}")
            await asyncio.sleep(delay)
            
    # If we get here, all retries failed
    raise last_exception


class CircuitBreaker:
    """Circuit breaker pattern for external dependencies."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: timedelta = timedelta(minutes=1),
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Time to wait before trying half-open state
            expected_exception: Exception type to count as failures
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half_open
        
    async def call(self, func: Callable) -> T:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            
        Returns:
            Result of function execution
            
        Raises:
            Exception if circuit is open or function fails
        """
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
                logger.info("Circuit breaker transitioning to half-open state")
            else:
                raise Exception("Circuit breaker is open")
                
        try:
            result = await func()
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
            
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return datetime.now() - self.last_failure_time > self.timeout
        
    def _on_success(self):
        """Handle successful execution."""
        if self.state == "half_open":
            self.state = "closed"
            self.failure_count = 0
            logger.info("Circuit breaker closed after successful execution")
            
    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


class RateLimiter:
    """Rate limiter with token bucket algorithm."""
    
    def __init__(self, rate: float, capacity: int):
        """
        Initialize rate limiter.
        
        Args:
            rate: Tokens per second
            capacity: Maximum token capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = datetime.now()
        
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from the rate limiter.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False if rate limited
        """
        now = datetime.now()
        time_passed = (now - self.last_update).total_seconds()
        
        # Add tokens based on time passed
        self.tokens = min(
            self.capacity,
            self.tokens + time_passed * self.rate
        )
        self.last_update = now
        
        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        else:
            logger.debug(f"Rate limited: need {tokens} tokens, have {self.tokens}")
            return False
