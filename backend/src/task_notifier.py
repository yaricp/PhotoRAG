"""
Shared async result notifier for Huey model tasks.

WHY THIS EXISTS
--------------
Huey runs model tasks in separate worker processes and stores results in
task_results.db (a SQLite file).  The pipeline coroutines that submit those
tasks need to block until the result is ready.

The naive approach — a per-task sleep/poll loop — scales poorly: 50 photos
× 4 model tasks each = 200 concurrent sleep loops hitting SQLite every
second.  It also blocks the event loop if the poll is synchronous.

This module replaces all of that with ONE background coroutine per event loop
that does a single batched SELECT for all currently-waiting task IDs in one
round-trip, then resolves the matching asyncio.Futures.

HOW IT WORKS
------------
1. A caller awaits  get_notifier().wait_for_result(task_id).
2. That creates an asyncio.Future bound to the current event loop, stores it
   in  _pending[loop_id][task_id], and awaits it.
3. A background poll coroutine (_poll_loop) wakes every TASK_RESULT_POLL_INTERVAL
   seconds, fetches results for ALL pending task IDs in one SELECT, and calls
   future.set_result() / future.set_exception() for any that are ready.
4. The awaiting coroutine unblocks and returns the raw JSON string.

MULTIPLE EVENT LOOPS
--------------------
This process contains three independent event loops:
  • uvicorn      — FastAPI request handlers + AI agent
  • observer     — watchdog daemon thread (asyncio.run_coroutine_threadsafe)
  • folder scan  — asyncio.run() called from a Huey worker process

asyncio.Future objects are bound to the loop that created them — resolving a
future from a different loop is undefined / thread-unsafe.  To avoid this,
_pending and _poll_tasks are dicts keyed by id(loop).  Each loop that calls
wait_for_result() gets its own isolated Future dict and its own poll task.
The poll loop is started lazily on the first call within that loop.

USAGE
-----
    from src.task_notifier import get_notifier

    raw_json = await get_notifier().wait_for_result(task_id, timeout=600.0)

No explicit start() call is needed.
"""

import asyncio
import json
import os
import sqlite3
import time

from loguru import logger

from src.config import Database_Settings, TaskQueue_Settings

_ERROR_KEY = "__error__"


class TaskResultNotifier:
    """
    Singleton notifier that bridges Huey task results back to async callers.

    Internal state is partitioned by event loop ID so that multiple loops
    (uvicorn, observer thread, folder-scanner asyncio.run) can share the same
    singleton without their Futures or poll tasks interfering with each other.
    """

    def __init__(self) -> None:
        # loop_id → {task_id: Future}  — one dict per active event loop
        self._pending: dict[int, dict[str, asyncio.Future]] = {}
        # loop_id → asyncio.Task       — one poll coroutine per active event loop
        self._poll_tasks: dict[int, asyncio.Task] = {}
        self._settings = TaskQueue_Settings()
        # Absolute path so it stays valid regardless of CWD changes
        self._db_path = os.path.abspath(Database_Settings().TASK_RESULTS_DATABASE_NAME)

    # ------------------------------------------------------------------
    # Internal: per-loop lifecycle
    # ------------------------------------------------------------------

    def _ensure_running(self, loop: asyncio.AbstractEventLoop) -> dict[str, asyncio.Future]:
        """
        Ensure a poll task is running on *loop* and return that loop's pending dict.

        Called from wait_for_result() which is already running on *loop*, so
        asyncio.create_task() correctly schedules the poll coroutine on *loop*.
        If the poll task died (e.g. unhandled exception), it is restarted here.
        """
        loop_id = id(loop)

        if loop_id not in self._pending:
            self._pending[loop_id] = {}

        task = self._poll_tasks.get(loop_id)
        if task is None or task.done():
            pending = self._pending[loop_id]
            self._poll_tasks[loop_id] = asyncio.create_task(
                self._poll_loop(loop_id, pending),
                name=f"task-result-notifier-{loop_id}",
            )
            logger.info(f"[notifier] Poll loop started (loop={loop_id}, db={self._db_path})")

        return self._pending[loop_id]

    def stop_all(self) -> None:
        """Cancel every poll task across all loops. Call once during app shutdown."""
        for task in self._poll_tasks.values():
            if not task.done():
                task.cancel()
        logger.info(f"[notifier] Stopped {len(self._poll_tasks)} poll loop(s)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def wait_for_result(self, task_id: str, timeout: float | None = None) -> str:
        """
        Suspend the caller until the Huey task identified by *task_id* finishes.

        The method registers a Future in the current loop's pending dict, then
        awaits it.  The background poll loop resolves the Future once the result
        row appears in task_results.db.

        Returns:
            Raw result string from Huey (typically JSON).
        Raises:
            asyncio.TimeoutError  — result did not arrive within *timeout* seconds.
            RuntimeError          — the Huey task stored an error payload.
        """
        if timeout is None:
            timeout = self._settings.TASK_RESULT_TIMEOUT

        loop = asyncio.get_running_loop()
        pending = self._ensure_running(loop)

        fut: asyncio.Future[str] = loop.create_future()
        pending[task_id] = fut

        try:
            async with asyncio.timeout(timeout):
                return await fut
        except asyncio.TimeoutError:
            logger.error(f"[notifier] Task {task_id} timed out after {timeout}s")
            raise
        finally:
            pending.pop(task_id, None)
            if not fut.done():
                fut.cancel()

    # ------------------------------------------------------------------
    # Internal: poll loop (one instance per event loop)
    # ------------------------------------------------------------------

    async def _poll_loop(
        self,
        loop_id: int,
        pending: dict[str, asyncio.Future],
    ) -> None:
        """
        Background coroutine (one per event loop) that drives result delivery.

        Each iteration calls _poll_once() which issues a single batched SELECT
        for all currently-waiting task IDs and resolves their Futures.
        Exceptions from _poll_once() are logged but do not kill the loop.
        The loop exits cleanly on CancelledError (triggered by stop_all()).
        """
        interval = self._settings.TASK_RESULT_POLL_INTERVAL
        log_every = self._settings.TASK_RESULT_LOG_INTERVAL
        pending_since: dict[str, float] = {}
        last_heartbeat: dict[str, float] = {}

        logger.info(f"[notifier] Poll loop running (loop={loop_id})")
        try:
            while True:
                await asyncio.sleep(interval)
                try:
                    await self._poll_once(pending, pending_since, last_heartbeat, log_every)
                except Exception as exc:
                    logger.error(
                        f"[notifier] Poll iteration failed (loop={loop_id}): {exc}",
                        exc_info=True,
                    )
        except asyncio.CancelledError:
            pass
        finally:
            self._poll_tasks.pop(loop_id, None)
            self._pending.pop(loop_id, None)
            logger.info(f"[notifier] Poll loop exited (loop={loop_id})")

    async def _poll_once(
        self,
        pending: dict[str, asyncio.Future],
        pending_since: dict[str, float],
        last_heartbeat: dict[str, float],
        log_every: float,
    ) -> None:
        if not pending:
            return

        task_ids = list(pending.keys())
        batch = await asyncio.to_thread(self._fetch_batch, task_ids)
        now = time.monotonic()

        for task_id, raw in batch.items():
            fut = pending.get(task_id)
            if fut is None or fut.done():
                pending_since.pop(task_id, None)
                last_heartbeat.pop(task_id, None)
                continue

            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and _ERROR_KEY in parsed:
                    fut.set_exception(RuntimeError(parsed[_ERROR_KEY]))
                else:
                    fut.set_result(raw)
            except Exception as exc:
                if not fut.done():
                    fut.set_exception(exc)

            pending_since.pop(task_id, None)
            last_heartbeat.pop(task_id, None)

        # Heartbeat logging for tasks still waiting
        for task_id in task_ids:
            if task_id in batch:
                continue
            started = pending_since.setdefault(task_id, now)
            elapsed = now - started
            last = last_heartbeat.get(task_id, started)
            if elapsed > 0 and (now - last) >= log_every:
                logger.info(f"[notifier] Still waiting for task {task_id} ({elapsed:.0f}s elapsed)")
                last_heartbeat[task_id] = now

    def _fetch_batch(self, task_ids: list[str]) -> dict[str, str]:
        """
        Synchronous SQLite query for a batch of task IDs.

        Returns only the IDs that have a result row — missing IDs simply don't
        appear in the returned dict and will be retried next poll interval.
        Runs via asyncio.to_thread() so it never blocks the event loop.
        """
        if not task_ids:
            return {}
        placeholders = ",".join("?" * len(task_ids))
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                f"SELECT task_id, result FROM results WHERE task_id IN ({placeholders})",
                task_ids,
            ).fetchall()
        finally:
            conn.close()
        return {row[0]: row[1] for row in rows}


# Module-level singleton
_notifier = TaskResultNotifier()


def get_notifier() -> TaskResultNotifier:
    return _notifier
