"""
Nawah Base Agent — Abstract Constitution for All L2 Agents

Every L2 agent MUST inherit from BaseAgent and implement the
`process(task_payload) -> dict` method. No exceptions.
"""
from abc import ABC, abstractmethod
from datetime import datetime


class BaseAgent(ABC):
    """
    Abstract base class for all Nawah L2 agents.

    Subclasses MUST implement:
        process(task_payload: dict) -> dict

    The returned dict MUST contain at minimum:
        - status: "completed" | "failed" | "routed"
        - agent: agent name string
        - task_id: from the payload
        - message: human-readable result
        - timestamp: ISO-8601
    """

    # Each subclass sets its own name and icon
    agent_name: str = "base_agent"
    agent_icon: str = "🤖"

    @abstractmethod
    def process(self, task_payload: dict) -> dict:
        """
        Process a Military Task Order.

        Args:
            task_payload: Validated L1 payload dict with task_id,
                          commander_instruction, attachments, l1_triage.

        Returns:
            dict with status, agent, task_id, message, timestamp.
        """
        raise NotImplementedError

    def _success(self, task_id: str, message: str) -> dict:
        """Helper to build a standard success response."""
        return {
            "status": "completed",
            "agent": self.agent_name,
            "task_id": task_id,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }

    def _fail(self, task_id: str, error: str) -> dict:
        """Helper to build a standard failure response."""
        return {
            "status": "failed",
            "agent": self.agent_name,
            "task_id": task_id,
            "message": f"❌ {error}",
            "timestamp": datetime.now().isoformat(),
        }
