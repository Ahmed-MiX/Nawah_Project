"""
Nawah Shared Memory — Agent Workspace (L2 Collaboration Whiteboard)

Provides a per-task workspace where multiple L2 agents can read/write
intermediate findings without data loss or race conditions.
"""

import threading
from datetime import datetime


class AgentWorkspace:
    """
    Per-task shared memory for L2 agent collaboration.
    Thread-safe whiteboard where agents can drop and read notes.
    """

    def __init__(self, task_id, dossier):
        """
        Initialize workspace for a specific task.

        Args:
            task_id: Unique task identifier from the message bus
            dossier: The L1 Unified Context Bag (dict)
        """
        self.task_id = task_id
        self.dossier = dossier
        self._notes = []
        self._lock = threading.Lock()
        self.created_at = datetime.now().isoformat()

    @property
    def task_summary(self):
        return self.dossier.get("task_summary", "")

    @property
    def intent(self):
        return self.dossier.get("intent", "")

    @property
    def original_context(self):
        return self.dossier.get("original_context", "")

    @property
    def attachments(self):
        return self.dossier.get("attachments_metadata", [])

    @property
    def complexity(self):
        return self.dossier.get("complexity", "Unknown")

    @property
    def agents_needed(self):
        return self.dossier.get("agents_needed", [])

    def write_note(self, agent_name, content):
        """
        Write a note to the shared whiteboard. Thread-safe.

        Args:
            agent_name: Name/role of the writing agent (e.g., "محلل مالي")
            content: The note content (findings, analysis, etc.)
        """
        with self._lock:
            note = {
                "agent": agent_name,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            self._notes.append(note)
            return len(self._notes)

    def read_all_notes(self):
        """Read all notes from the whiteboard. Thread-safe."""
        with self._lock:
            return list(self._notes)

    def read_notes_by_agent(self, agent_name):
        """Read notes from a specific agent."""
        with self._lock:
            return [n for n in self._notes if n["agent"] == agent_name]

    def get_latest_note(self):
        """Get the most recent note."""
        with self._lock:
            return self._notes[-1] if self._notes else None

    def note_count(self):
        """Get total number of notes."""
        with self._lock:
            return len(self._notes)

    def to_dict(self):
        """Serialize workspace state for persistence or debugging."""
        with self._lock:
            return {
                "task_id": self.task_id,
                "dossier_summary": self.task_summary,
                "intent": self.intent,
                "complexity": self.complexity,
                "agents_needed": self.agents_needed,
                "attachments_count": len(self.attachments),
                "notes": list(self._notes),
                "created_at": self.created_at
            }


class WorkspaceManager:
    """
    Manages active workspaces across all in-flight tasks.
    Thread-safe registry for workspace creation and retrieval.
    """

    def __init__(self):
        self._workspaces = {}
        self._lock = threading.Lock()

    def create_workspace(self, task_id, dossier):
        """Create a new workspace for a task."""
        with self._lock:
            ws = AgentWorkspace(task_id, dossier)
            self._workspaces[task_id] = ws
            return ws

    def get_workspace(self, task_id):
        """Retrieve an existing workspace."""
        with self._lock:
            return self._workspaces.get(task_id)

    def remove_workspace(self, task_id):
        """Remove a completed workspace."""
        with self._lock:
            return self._workspaces.pop(task_id, None)

    def active_count(self):
        """Count active workspaces."""
        with self._lock:
            return len(self._workspaces)

    def list_active(self):
        """List all active task IDs."""
        with self._lock:
            return list(self._workspaces.keys())
