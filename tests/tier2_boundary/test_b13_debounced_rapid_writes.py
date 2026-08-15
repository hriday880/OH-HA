"""
Boundary Test 13: Debounced Queue Under Heavy Concurrency.
Tests high-frequency concurrent note mutations (100+ writes), timer resets, and queue consistency.
"""

from __future__ import annotations

import asyncio
import pytest
from bot.git_sync.engine import DebouncedPushQueue


class TestBoundary13DebouncedRapidWrites:
    """Boundary tests for Feature 13 (Debounced Push Engine)."""

    @pytest.mark.asyncio
    async def test_high_concurrency_100_rapid_writes(self):
        """Test enqueueing 100 writes concurrently batches them without dropping entries."""
        flushed_batches = []

        async def push_handler(count: int):
            flushed_batches.append(count)

        queue = DebouncedPushQueue(debounce_seconds=0.08, push_callback=push_handler)

        async def write_worker(idx: int):
            await queue.enqueue(f"notes/concurrent_{idx}.md")

        # Launch 100 concurrent tasks
        await asyncio.gather(*[write_worker(i) for i in range(100)])

        # Await debounce settling
        await asyncio.sleep(0.15)

        assert sum(flushed_batches) == 100
        assert queue.push_count >= 1

    @pytest.mark.asyncio
    async def test_consecutive_debounce_resets(self):
        """Test continuous incoming writes keep resetting the timer until writes cease."""
        flushed = []

        queue = DebouncedPushQueue(debounce_seconds=0.06, push_callback=lambda c: flushed.append(c))

        # Enqueue with small gaps less than debounce_seconds
        for i in range(4):
            await queue.enqueue(f"stream_{i}.md")
            await asyncio.sleep(0.03)

        assert len(flushed) == 0  # Should not have fired yet because timer kept resetting

        # Now wait for debounce to expire
        await asyncio.sleep(0.1)
        assert len(flushed) == 1
        assert flushed[0] == 4

    @pytest.mark.asyncio
    async def test_concurrent_manual_flush_and_enqueue(self):
        """Test calling flush() while enqueue() is concurrently executing."""
        queue = DebouncedPushQueue(debounce_seconds=0.5)

        async def writer():
            for i in range(10):
                await queue.enqueue(f"n_{i}.md")
                await asyncio.sleep(0.005)

        async def flusher():
            await asyncio.sleep(0.02)
            return await queue.flush()

        w_task = asyncio.create_task(writer())
        f_task = asyncio.create_task(flusher())

        await w_task
        flushed_in_between = await f_task
        remaining = await queue.flush()

        assert flushed_in_between + remaining == 10
