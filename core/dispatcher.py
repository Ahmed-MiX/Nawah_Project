"""
Nawah L2 Dispatcher — OOP Agent Router (Full Fleet)

All agents inherit from BaseAgent and implement process().
Each agent is a separate file in core/agents/.
The Dispatcher reads l1_triage.recommended_agent and routes accordingly.
"""
from datetime import datetime
from core.base_agent import BaseAgent

# Import ALL live agents from the fleet
from core.agents.vision_agent import VisionAgent
from core.agents.analyst_agent import AnalystAgent
from core.agents.math_agent import MathAgent
from core.agents.translator_agent import TranslatorAgent
from core.agents.code_agent import CodeAgent
from core.agents.researcher_agent import ResearcherAgent
from core.agents.report_agent import ReportAgent
from core.agents.email_agent import EmailAgent
from core.agents.classifier_agent import ClassifierAgent
from core.agents.general_agent import GeneralAgent


# ============================================================
# AGENT REGISTRY — Maps names to class instances
# ============================================================
AGENT_REGISTRY: dict[str, BaseAgent] = {
    "vision_agent": VisionAgent(),
    "analyst_agent": AnalystAgent(),
    "math_agent": MathAgent(),
    "translator_agent": TranslatorAgent(),
    "code_agent": CodeAgent(),
    "researcher_agent": ResearcherAgent(),
    "report_agent": ReportAgent(),
    "email_agent": EmailAgent(),
    "classifier_agent": ClassifierAgent(),
    "general_agent": GeneralAgent(),
}

_FALLBACK = GeneralAgent()


# ============================================================
# L2 DISPATCHER
# ============================================================
class L2Dispatcher:
    """
    Routes Military Task Orders to the appropriate L2 agent class.
    All agents inherit from BaseAgent and implement process().
    """

    def dispatch(self, task_payload: dict) -> dict:
        task_id = task_payload.get("task_id", "unknown")
        triage = task_payload.get("l1_triage", {})
        raw_agent = triage.get("recommended_agent", "general_agent")
        raw_intent = triage.get("intent", "UNKNOWN")

        # Coerce Pydantic enums to plain strings
        agent_name = raw_agent.value if hasattr(raw_agent, 'value') else str(raw_agent)
        intent = raw_intent.value if hasattr(raw_intent, 'value') else str(raw_intent)

        # Resolve agent instance
        agent = AGENT_REGISTRY.get(agent_name, _FALLBACK)

        if agent_name not in AGENT_REGISTRY:
            print(f"⚠️ L2 Dispatcher: وكيل غير معروف '{agent_name}' → تحويل للوكيل العام")

        # Verify inheritance
        assert isinstance(agent, BaseAgent), f"Agent {agent_name} does not inherit from BaseAgent!"

        # Execute
        try:
            result = agent.process(task_payload)
            print(f"🚦 L2 DISPATCH: [{intent}] → {agent.__class__.__name__}({agent_name}) → ✅ {result['message'][:80]}")
            return result
        except Exception as e:
            print(f"🚦 L2 DISPATCH: [{intent}] → {agent_name} → ❌ ERROR: {e}")
            return {
                "status": "failed",
                "agent": agent_name,
                "task_id": task_id,
                "message": f"❌ فشل التوجيه: {e}",
                "timestamp": datetime.now().isoformat(),
            }
