"""
Nawah L2/L3 Dispatcher — OOP Agent Router (Full Fleet + L3 Executive Swarm)

All agents inherit from BaseAgent and implement process().
Each agent is a separate file in core/agents/.
The Dispatcher reads l1_triage.recommended_agent and routes accordingly.

L2 Fleet: 10 specialized agents (Analyst, Translator, Code, Math, etc.)
L3 Executive Swarm: 8 decision-making agents (Legal, Finance, HR, Supply Chain, CRM,
    Headhunter, Negotiator, JD Suggester) with RAG memory and ERP tool integration.
"""
from datetime import datetime
from core.base_agent import BaseAgent

# Import ALL L2 live agents from the fleet
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

# Import L3 Executive Swarm agents (5 agents)
from core.agents.legal_agent import LegalAgent
from core.agents.finance_agent import FinanceAgent
from core.agents.hr_agent import HRAgent
from core.agents.supply_chain_agent import SupplyChainAgent
from core.agents.crm_agent import CRMAgent
from core.agents.headhunter_agent import HeadhunterAgent
from core.agents.negotiator_agent import NegotiatorAgent
from core.agents.jd_suggester_agent import JDSuggesterAgent


# ============================================================
# AGENT REGISTRY — Maps names to class instances (L2 + L3)
# ============================================================
AGENT_REGISTRY: dict[str, BaseAgent] = {
    # === L2 Fleet ===
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
    # === L3 Executive Swarm ===
    "legal_agent": LegalAgent(),
    "finance_agent": FinanceAgent(),
    "hr_agent": HRAgent(),
    "supply_chain_agent": SupplyChainAgent(),
    "crm_agent": CRMAgent(),
    "headhunter_agent": HeadhunterAgent(),
    "negotiator_agent": NegotiatorAgent(),
    "jd_suggester_agent": JDSuggesterAgent(),
}

_FALLBACK = GeneralAgent()


# ============================================================
# L2/L3 DISPATCHER
# ============================================================
class L2Dispatcher:
    """
    Routes Military Task Orders to the appropriate L2/L3 agent class.
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

        # Determine layer tag for logging
        l3_agents = {"legal_agent", "finance_agent", "hr_agent", "supply_chain_agent", "crm_agent", "headhunter_agent", "negotiator_agent", "jd_suggester_agent"}
        layer = "L3" if agent_name in l3_agents else "L2"

        # Execute
        try:
            result = agent.process(task_payload)
            print(f"🚦 {layer} DISPATCH: [{intent}] → {agent.__class__.__name__}({agent_name}) → ✅ {result['message'][:80]}")
            return result
        except Exception as e:
            print(f"🚦 {layer} DISPATCH: [{intent}] → {agent_name} → ❌ ERROR: {e}")
            return {
                "status": "failed",
                "agent": agent_name,
                "task_id": task_id,
                "message": f"❌ فشل التوجيه: {e}",
                "timestamp": datetime.now().isoformat(),
            }
