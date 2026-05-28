"""Tests for the sliding-window rate limiter (ADR 9)."""

from __future__ import annotations

import pytest

from taskchampion_mcp.rate_limiter import RateLimiter, RateLimitError


class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = RateLimiter(ops_per_minute=5, ops_per_hour=100, creates_per_hour=10)
        for _ in range(5):
            rl.check_and_record()

    def test_blocks_over_minute_limit(self):
        rl = RateLimiter(ops_per_minute=3, ops_per_hour=100, creates_per_hour=10)
        for _ in range(3):
            rl.check_and_record()
        with pytest.raises(RateLimitError, match="ops_per_minute"):
            rl.check_and_record()

    def test_blocks_over_hour_limit(self):
        rl = RateLimiter(ops_per_minute=1000, ops_per_hour=5, creates_per_hour=100)
        for _ in range(5):
            rl.check_and_record()
        with pytest.raises(RateLimitError, match="ops_per_hour"):
            rl.check_and_record()

    def test_create_limit_separate(self):
        rl = RateLimiter(ops_per_minute=100, ops_per_hour=100, creates_per_hour=2)
        rl.check_and_record(is_create=True)
        rl.check_and_record(is_create=True)
        with pytest.raises(RateLimitError, match="creates_per_hour"):
            rl.check_and_record(is_create=True)
        rl.check_and_record(is_create=False)

    def test_status_reflects_capacity(self):
        rl = RateLimiter(ops_per_minute=10, ops_per_hour=100, creates_per_hour=5)
        status = rl.status()
        assert status["ops_per_minute_remaining"] == 10
        assert status["ops_per_hour_remaining"] == 100
        assert status["creates_per_hour_remaining"] == 5

        rl.check_and_record(is_create=True)
        status = rl.status()
        assert status["ops_per_minute_remaining"] == 9
        assert status["ops_per_hour_remaining"] == 99
        assert status["creates_per_hour_remaining"] == 4

    def test_error_attributes(self):
        rl = RateLimiter(ops_per_minute=1, ops_per_hour=100, creates_per_hour=100)
        rl.check_and_record()
        with pytest.raises(RateLimitError) as exc_info:
            rl.check_and_record()
        assert exc_info.value.bucket == "ops_per_minute"
        assert exc_info.value.limit == 1
        assert exc_info.value.window_seconds == 60
