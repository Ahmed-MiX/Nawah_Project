"""
Nawah L3 Negotiator Agent — Salary & Benefits Negotiation

Contacts approved candidates, negotiates salary within FinancialHardCap
limits, handles counter-offers, and triggers onboarding upon agreement.
"""
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.memory.persona_manager import get_persona_manager
from core.governance_engine import get_compliance_guardrail
from core.tools.erp_connector import get_erp_tool

_FALLBACK_PROMPT = "أنت مفاوض رواتب محترف في نظام نواة. تفاوض ضمن الحدود المعتمدة."

SYSTEM_PROMPT = (
    "أنت مفاوض رواتب نخبوي في نظام نواة للأتمتة المؤسسية.\n"
    "تتفاوض مع المرشحين المعتمدين على الراتب والمزايا.\n\n"
    "قواعد صارمة:\n"
    "1. لا تتجاوز أبداً الحد المالي المعتمد من المدقق المالي.\n"
    "2. ابدأ بعرض عند 80% من الحد الأقصى للتفاوض.\n"
    "3. إذا طلب المرشح أكثر من الحد → ارفض بأدب واعرض مزايا بديلة.\n"
    "4. المزايا البديلة: تأمين طبي VIP، بدل سكن، بونص سنوي، أسهم.\n"
    "5. عند الاتفاق → أصدر خطاب عرض وظيفي رسمي.\n"
    "6. وثّق كل خطوة تفاوضية في التقرير.\n"
    "7. اكتب بالعربية الفصحى بأسلوب مهني.\n"
)


class NegotiatorAgent(BaseAgent):
    """L3 Executive Agent — Salary & Benefits Negotiator."""
    agent_name = "negotiator_agent"
    agent_icon = "💼"

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None
        self.persona = get_persona_manager()
        self.guardrail = get_compliance_guardrail()
        self.erp = get_erp_tool()

    def process(self, task_payload: dict) -> dict:
        task_id = task_payload.get("task_id", "unknown")
        instruction = task_payload.get("commander_instruction", "")
        intent = task_payload.get("l1_triage", {}).get("intent", "SALARY_NEGOTIATION")
        candidate_name = task_payload.get("candidate_name", "المرشح")
        budget_cap = task_payload.get("budget_cap", 30000)
        seniority = task_payload.get("seniority", "mid")

        try:
            if not self.router:
                raise CriticalAPIFailure("No API keys")

            # Authorize budget via FinancialHardCap
            self.guardrail.financial_cap.authorize_budget(task_id, budget_cap, "finance_agent")

            # ReAct
            thought = self.generate_thought_process(instruction, f"Budget: {budget_cap} SAR", intent)

            human_msg = (
                f"{thought}\n\n"
                f"تفاوض مع المرشح: {candidate_name}\n"
                f"الميزانية المعتمدة: {budget_cap:,.0f} ر.س\n"
                f"المستوى: {seniority}\n"
                f"التعليمات: {instruction}"
            )

            sys_prompt = self.persona.get_system_prompt("negotiator_agent", SYSTEM_PROMPT)
            prompt = ChatPromptTemplate.from_messages([("system", sys_prompt), ("human", "{input}")])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)

            # Governance + Anti-Bias
            verdict = self.guardrail.check("negotiator_agent", result, {
                "task_id": task_id, "salary_offer": budget_cap * 0.8, "seniority": seniority
            })
            if not verdict.compliant:
                feedback = self.guardrail.format_violation_report(verdict)
                result = self.self_reflect(result, feedback, task_id=task_id, intent=intent)

            return self._success(task_id, f"💼 تقرير التفاوض:\n\n{result}")

        except CriticalAPIFailure:
            return self._mock_negotiation(task_id, instruction, candidate_name, budget_cap, seniority)
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ في التفاوض: {e}")

    def _mock_negotiation(self, task_id, instruction, candidate_name, budget_cap, seniority):
        """Full mock negotiation pipeline."""
        # Authorize budget
        self.guardrail.financial_cap.authorize_budget(task_id, budget_cap, "finance_agent")

        initial_offer = int(budget_cap * 0.80)
        counter_offer = int(budget_cap * 0.95)
        final_offer = int(budget_cap * 0.90)

        # Check final offer against hard cap
        approved, reason = self.guardrail.financial_cap.check_offer(task_id, final_offer, seniority)

        # Trigger onboarding on success
        onboard = None
        if approved:
            onboard = self.erp.onboard_new_employee(
                name=candidate_name, job_title="AI Developer",
                department="قسم الذكاء الاصطناعي", salary=final_offer
            )

        mock = (
            f"💼 [L3 EXECUTIVE DECISION — SALARY NEGOTIATION]\n\n"
            f"## تقرير التفاوض — مهمة {task_id[:8]}\n\n"
            f"**المرشح:** {candidate_name}\n"
            f"**الميزانية المعتمدة:** {budget_cap:,.0f} ر.س\n\n"
            f"---\n\n"
            f"### 📊 مراحل التفاوض\n\n"
            f"| المرحلة | العرض (ر.س) | الحالة |\n"
            f"|---------|-----------|--------|\n"
            f"| العرض الأولي | {initial_offer:,.0f} | 📤 مُرسل |\n"
            f"| عرض المرشح المضاد | {counter_offer:,.0f} | 📥 مُستلم |\n"
            f"| العرض النهائي | {final_offer:,.0f} | {'✅ موافقة' if approved else '🚫 مرفوض'} |\n\n"
            f"### 💰 فحص الحد المالي\n"
            f"- {reason}\n\n"
        )

        if approved:
            mock += (
                f"### 🎁 حزمة المزايا\n\n"
                f"| الميزة | التفاصيل |\n"
                f"|--------|----------|\n"
                f"| الراتب الأساسي | {final_offer:,.0f} ر.س |\n"
                f"| بدل سكن | {int(final_offer * 0.25):,.0f} ر.س |\n"
                f"| تأمين طبي | VIP — يشمل العائلة |\n"
                f"| بونص سنوي | حتى 15% من الراتب |\n"
                f"| إجازة سنوية | 25 يوم عمل |\n\n"
            )
            if onboard:
                mock += (
                    f"### 🏭 ERP — تهيئة الموظف الجديد\n\n"
                    f"| البند | التفاصيل |\n"
                    f"|-------|----------|\n"
                    f"| رقم الموظف | {onboard['employee_id']} |\n"
                    f"| البريد المؤسسي | {onboard['provisions']['corporate_email']} |\n"
                    f"| حساب Slack | {onboard['provisions']['slack_account']} |\n"
                    f"| كرت الدخول | {onboard['provisions']['access_card']} |\n"
                    f"| طلب لابتوب | {onboard['provisions']['laptop_request']} |\n\n"
                )

        mock += (
            f"### ✉️ خطاب العرض الوظيفي\n\n---\n"
            f"الأخ الكريم {candidate_name}،\n\n"
            f"يسرنا إبلاغكم بقبولكم في فريق نواة بمسمى AI Developer.\n"
            f"الراتب الشهري: {final_offer:,.0f} ر.س\n\n"
            f"نتطلع لانضمامكم.\n\nمع التقدير،\nإدارة الموارد البشرية — نواة\n---\n\n"
            f"_⚠️ محاكاة — API مطلوب للتفاوض الحقيقي._"
        )
        return self._success(task_id, mock)
