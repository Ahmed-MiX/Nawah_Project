"""
Nawah Dynamic Persona Manager — Agent Training Without Code Changes

Loads agent personas (system prompts, constraints, temperatures) from
`nawah_personas.json`. Allows the Commander to dynamically train and
customize agents by editing a single JSON file.
"""
import os
import json
from typing import Optional

_PERSONAS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "nawah_personas.json"
)


class DynamicPersonaManager:
    """
    Loads and serves agent personas from nawah_personas.json.

    Usage:
        pm = get_persona_manager()
        prompt = pm.get_system_prompt("legal_agent")
        constraints = pm.get_constraints("legal_agent")
        temp = pm.get_temperature("legal_agent")
    """

    def __init__(self, personas_path: str = None):
        self.path = personas_path or _PERSONAS_FILE
        self.data = {}
        self.global_constraints = []
        self._load()

    def _load(self):
        """Load personas from JSON file."""
        if not os.path.exists(self.path):
            print(f"⚠️ PersonaManager: ملف التدريب غير موجود — {self.path}")
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            self.data = raw.get("agents", {})
            self.global_constraints = raw.get("global_constraints", [])
            agent_count = len(self.data)
            constraint_count = sum(len(a.get("constraints", [])) for a in self.data.values())
            print(
                f"🧬 PersonaManager: تم تحميل {agent_count} شخصية "
                f"و {constraint_count} قيد حوكمة "
                f"+ {len(self.global_constraints)} قيد عام"
            )
        except Exception as e:
            print(f"⚠️ PersonaManager: فشل تحميل الشخصيات — {e}")

    def reload(self):
        """Hot-reload personas from disk (no restart needed)."""
        self._load()
        print("🔄 PersonaManager: تم إعادة تحميل الشخصيات")

    def get_system_prompt(self, agent_name: str, fallback: str = "") -> str:
        """Get system prompt for an agent. Returns fallback if not found."""
        agent = self.data.get(agent_name, {})
        return agent.get("system_prompt", fallback)

    def get_constraints(self, agent_name: str) -> list[str]:
        """Get governance constraints for an agent (agent-specific + global)."""
        agent = self.data.get(agent_name, {})
        agent_constraints = agent.get("constraints", [])
        return self.global_constraints + agent_constraints

    def get_temperature(self, agent_name: str, fallback: float = 0.3) -> float:
        """Get LLM temperature for an agent."""
        agent = self.data.get(agent_name, {})
        return agent.get("temperature", fallback)

    def get_display_name(self, agent_name: str) -> str:
        """Get Arabic display name for an agent."""
        agent = self.data.get(agent_name, {})
        return agent.get("display_name", agent_name)

    def get_all_agent_names(self) -> list[str]:
        """List all configured agent names."""
        return list(self.data.keys())

    def get_stats(self) -> dict:
        """Return persona manager statistics."""
        return {
            "agents_configured": len(self.data),
            "global_constraints": len(self.global_constraints),
            "total_constraints": sum(
                len(a.get("constraints", [])) for a in self.data.values()
            ) + len(self.global_constraints),
            "file": self.path,
        }


# ============================================================
# Singleton
# ============================================================
_persona_manager = None


def get_persona_manager() -> DynamicPersonaManager:
    """Get or create the singleton DynamicPersonaManager instance."""
    global _persona_manager
    if _persona_manager is None:
        _persona_manager = DynamicPersonaManager()
    return _persona_manager
