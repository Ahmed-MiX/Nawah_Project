"""
Nawah Message Bus — Thread-Safe Task Broker (L1 → L2 Bridge)

Uses SQLite for ACID-compliant atomic task state management.
Guarantees no two L2 agents can pull the same task.
"""

import os
import json
import sqlite3
import threading
from datetime import datetime
from enum import Enum

DB_PATH = "nawah_state.db"
OUTBOX_DIR = "nawah_outbox"


class TaskState(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskBroker:
    """Thread-safe task queue backed by SQLite."""

    _lock = threading.Lock()

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        """Get a thread-safe SQLite connection (safe for Streamlit multi-thread)."""
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create the tasks table if it doesn't exist. Migrate schema if needed."""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'PENDING',
                    assigned_to TEXT,
                    dossier TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT,
                    result TEXT
                )
            """)
            # Migration: add result column if table existed before this version
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN result TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            conn.commit()
        finally:
            conn.close()

    def ingest_from_outbox(self):
        """Scan nawah_outbox for new L1 JSONs and register them as PENDING tasks."""
        if not os.path.isdir(OUTBOX_DIR):
            return 0

        conn = self._get_conn()
        ingested = 0
        try:
            for filename in os.listdir(OUTBOX_DIR):
                if not filename.endswith('.json'):
                    continue

                filepath = os.path.join(OUTBOX_DIR, filename)
                task_id = os.path.splitext(filename)[0]

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        dossier = json.load(f)
                except Exception:
                    continue

                # Skip dummy/failed dossiers (the old RateLimited poison)
                complexity = dossier.get("complexity", "")
                if complexity in ("RateLimited", "Error") and "original_context" not in dossier:
                    continue

                now = datetime.now().isoformat()
                # INSERT OR IGNORE = atomic deduplication (no SELECT-then-INSERT race)
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO tasks (task_id, source_file, state, dossier, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (task_id, filename, TaskState.PENDING.value, json.dumps(dossier, ensure_ascii=False), now, now)
                )
                if cursor.rowcount > 0:
                    ingested += 1

            conn.commit()
        finally:
            conn.close()

        return ingested

    def register_task(self, task_id, source_file, dossier):
        """
        Directly register a new task from the L1 pipeline.
        Called by watcher.py / email_watcher.py after saving the JSON.
        """
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO tasks (task_id, source_file, state, dossier, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, source_file, TaskState.PENDING.value, json.dumps(dossier, ensure_ascii=False), now, now)
            )
            conn.commit()
            print(f"📋 TaskBroker: مهمة جديدة مسجلة → {task_id} [PENDING]")
        finally:
            conn.close()

    def pull_next_task(self, agent_id="anonymous"):
        """
        Atomically pull the next PENDING task and lock it as IN_PROGRESS.
        Returns (task_id, dossier_dict) or (None, None) if no tasks available.
        Thread-safe via SQLite BEGIN IMMEDIATE transaction.
        """
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT task_id, dossier FROM tasks WHERE state = ? ORDER BY created_at ASC LIMIT 1",
                    (TaskState.PENDING.value,)
                ).fetchone()

                if not row:
                    conn.rollback()
                    return None, None

                task_id = row["task_id"]
                dossier = json.loads(row["dossier"])
                now = datetime.now().isoformat()

                conn.execute(
                    "UPDATE tasks SET state = ?, assigned_to = ?, updated_at = ? WHERE task_id = ?",
                    (TaskState.IN_PROGRESS.value, agent_id, now, task_id)
                )
                conn.commit()
                return task_id, dossier

            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def complete_task(self, task_id):
        """Mark a task as COMPLETED."""
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE tasks SET state = ?, updated_at = ? WHERE task_id = ?",
                (TaskState.COMPLETED.value, now, task_id)
            )
            conn.commit()
        finally:
            conn.close()

    def update_task_result(self, task_id, status, result_text):
        """
        Store the L2 agent's final output and update task state.

        Args:
            task_id: UUID of the task
            status: 'COMPLETED' or 'FAILED'
            result_text: The AI agent's full response text
        """
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            state = TaskState.COMPLETED.value if status == "COMPLETED" else TaskState.FAILED.value
            conn.execute(
                "UPDATE tasks SET state = ?, result = ?, updated_at = ? WHERE task_id = ?",
                (state, result_text, now, task_id)
            )
            conn.commit()
            print(f"💾 TaskBroker: نتيجة المهمة {task_id[:8]} → {state}")
        finally:
            conn.close()

    def fail_task(self, task_id, error_message=""):
        """Mark a task as FAILED with an error message."""
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE tasks SET state = ?, error_message = ?, updated_at = ? WHERE task_id = ?",
                (TaskState.FAILED.value, error_message, now, task_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_task_state(self, task_id):
        """Get the current state of a task."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT state FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return TaskState(row["state"]) if row else None
        finally:
            conn.close()

    def get_stats(self):
        """Get task counts by state."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT state, COUNT(*) as cnt FROM tasks GROUP BY state").fetchall()
            return {row["state"]: row["cnt"] for row in rows}
        finally:
            conn.close()

    def reset_db(self):
        """Drop all tasks. Used for testing only."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM tasks")
            conn.commit()
        finally:
            conn.close()

    def get_recent_tasks(self, limit=5):
        """Get the most recent tasks with summary info for UI display."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT task_id, state, dossier, created_at, result FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            results = []
            for row in rows:
                try:
                    dossier = json.loads(row["dossier"])
                    intent = dossier.get("intent", "—")
                    complexity = dossier.get("complexity", "—")
                    # Extract from l1_triage if present (new schema)
                    triage = dossier.get("l1_triage", {})
                    if triage:
                        intent = triage.get("intent", intent)
                        complexity = triage.get("complexity", complexity)
                except Exception:
                    intent = "—"
                    complexity = "—"
                results.append({
                    "task_id": row["task_id"][:16] + "...",
                    "state": row["state"],
                    "intent": str(intent)[:40],
                    "complexity": str(complexity),
                    "created_at": row["created_at"][:16],
                    "has_result": bool(row["result"]),
                })
            return results
        finally:
            conn.close()

