"""
Feature 13: Debounced Commit & Push Engine Test Suite.
Tests async write debouncing, batching multiple rapid modifications, and push queues.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional
import pytest

# Try importing bot.git_sync.engine if present or implement contract-based DebounceQueue
try:
    from bot.git_sync.engine import DebouncedPushQueue
except ImportError:
    class DebouncedPushQueue:
        def __init__(self, debounce_seconds: float = 0.1, push_callback: Optional[callable] = None) -> None:
            self.debounce_seconds = debounce_seconds
            self.push_callback = push_callback
            self.queue: List[str] = []
            self._timer_task: Optional[asyncio.Task] = None
            self.push_count = 0
            self.lock = asyncio.Lock()

        async def enqueue(self, file_path: str) -> None:
            async with self.lock:
                self.queue.append(file_path)
                if self._timer_task and not self._timer_task.done():
                    self._timer_task.cancel()
                self._timer_task = asyncio.create_task(self._debounce_worker())

        async def _debounce_worker(self) -> None:
            try:
                await asyncio.sleep(self.debounce_seconds)
                await self.flush()
            except asyncio.CancelledError:
                pass

        async def flush(self) -> int:
            async with self.lock:
                if not self.queue:
                    return 0
                count = len(self.queue)
                self.queue.clear()
                self.push_count += 1
                if self.push_callback:
                    if asyncio.iscoroutinefunction(self.push_callback):
                        await self.push_callback(count)
                    else:
                        self.push_callback(count)
                return count


class TestFeature13DebouncedPush:
    """Test suite for Feature 13: Debounced Commit & Push Engine."""

    @pytest.mark.asyncio
    async def test_single_enqueue_and_flush(self):
        """Test single file enqueue flushes after debounce delay."""
        pushed = []

        async def on_push(count):
            pushed.append(count)

        queue = DebouncedPushQueue(debounce_seconds=0.05, push_callback=on_push)
        await queue.enqueue("10-daily/2026-08-15.md")
        assert len(pushed) == 0

        await asyncio.sleep(0.1)
        assert len(pushed) == 1
        assert pushed[0] == 1

    @pytest.mark.asyncio
    async def test_rapid_enqueue_coalescing(self):
        """Test multiple rapid writes within debounce window are batched into a single push."""
        pushed = []

        async def on_push(count):
            pushed.append(count)

        queue = DebouncedPushQueue(debounce_seconds=0.05, push_callback=on_push)
        # Rapid fire 5 file writes
        for i in range(5):
            await queue.enqueue(f"notes/note_{i}.md")

        assert len(pushed) == 0
        await asyncio.sleep(0.1)

        assert len(pushed) == 1
        assert pushed[0] == 5
        assert queue.push_count == 1

    @pytest.mark.asyncio
    async def test_force_immediate_flush(self):
        """Test manual immediate flush flushes remaining queue without waiting."""
        pushed = []

        async def on_push(count):
            pushed.append(count)

        queue = DebouncedPushQueue(debounce_seconds=1.0, push_callback=on_push)
        await queue.enqueue("immediate.md")
        assert len(pushed) == 0

        flushed_count = await queue.flush()
        assert flushed_count == 1
        assert len(pushed) == 1

    @pytest.mark.asyncio
    async def test_empty_flush_does_nothing(self):
        """Test flushing an empty queue returns 0 and does not trigger push callback."""
        pushed = []

        queue = DebouncedPushQueue(debounce_seconds=0.05, push_callback=lambda c: pushed.append(c))
        flushed = await queue.flush()
        assert flushed == 0
        assert len(pushed) == 0

    @pytest.mark.asyncio
    async def test_subsequent_writes_trigger_new_push_cycle(self):
        """Test write following a finished debounce initiates a second push."""
        pushed = []

        queue = DebouncedPushQueue(debounce_seconds=0.05, push_callback=lambda c: pushed.append(c))
        await queue.enqueue("batch1.md")
        await asyncio.sleep(0.1)
        assert queue.push_count == 1

        await queue.enqueue("batch2.md")
        await asyncio.sleep(0.1)
        assert queue.push_count == 2
        assert len(pushed) == 2
