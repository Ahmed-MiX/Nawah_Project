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
    """L3 Executive Agent — Salary & Benefits Negotiator with Deadlock Breaker."""
    agent_name = "negotiator_agent"
    agent_icon = "💼"

    MAX_TURNS = 3  # Deadlock after 3 counter-offers

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None
        self.persona = get_persona_manager()
        self.guardrail = get_compliance_guardrail()
        self.erp = get_erp_tool()
        # Stateful negotiation memory
        self.turn_count = 0
        self.negotiation_history = []
        self.deadlock_reached = False
        self.salary_range = None
        self.current_offer = 0

    def process(self, task_payload: dict) -> dict:
        task_id = task_payload.get("task_id", "unknown")
        instruction = task_payload.get("commander_instruction", "")
        intent = task_payload.get("l1_triage", {}).get("intent", "SALARY_NEGOTIATION")
        candidate_name = task_payload.get("candidate_name", "المرشح")
        budget_cap = task_payload.get("budget_cap", 30000)
        seniority = task_payload.get("seniority", "mid")
        job_id = task_payload.get("job_id", "JD-AI-001")

        try:
            if not self.router:
                raise CriticalAPIFailure("No API keys")

            # Fetch salary range FIRST (Finance Hard-Lock)
            self.salary_range = self.erp.get_approved_salary_range(job_id)
            max_salary = self.salary_range["salary_max"]
            budget_cap = min(budget_cap, max_salary)

            # Authorize budget via FinancialHardCap
            self.guardrail.financial_cap.authorize_budget(task_id, budget_cap, "finance_agent")

            # ReAct
            thought = self.generate_thought_process(instruction, f"Budget: {budget_cap} SAR", intent)

            human_msg = (
                f"{thought}\n\n"
                f"تفاوض مع المرشح: {candidate_name}\n"
                f"الميزانية المعتمدة: {budget_cap:,.0f} ر.س\n"
                f"الحد الأقصى المطلق: {max_salary:,.0f} ر.س (لا يمكن تجاوزه)\n"
                f"المستوى: {seniority}\n"
                f"التعليمات: {instruction}"
            )

            sys_prompt = self.persona.get_system_prompt("negotiator_agent", SYSTEM_PROMPT)
            prompt = ChatPromptTemplate.from_messages([("system", sys_prompt), ("human", "{input}")])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)

            verdict = self.guardrail.check("negotiator_agent", result, {
                "task_id": task_id, "salary_offer": budget_cap * 0.8, "seniority": seniority
            })
            if not verdict.compliant:
                feedback = self.guardrail.format_violation_report(verdict)
                result = self.self_reflect(result, feedback, task_id=task_id, intent=intent)

            return self._success(task_id, f"💼 تقرير التفاوض:\n\n{result}")

        except CriticalAPIFailure:
            return self._mock_negotiation(task_id, instruction, candidate_name, budget_cap, seniority, job_id)
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ في التفاوض: {e}")

    # ============================================================
    # INTERACTIVE NEGOTIATION (multi-turn with deadlock breaker)
    # ============================================================
    def negotiate(self, candidate_demand: int, job_id: str = "JD-AI-001") -> dict:
        """
        Single negotiation turn. Call repeatedly to simulate multi-turn.
        Returns: {"status": "COUNTER"|"ACCEPTED"|"DEADLOCK", "offer": int, ...}
        """
        # Fetch salary range if not yet loaded
        if not self.salary_range:
            self.salary_range = self.erp.get_approved_salary_range(job_id)

        max_salary = self.salary_range["salary_max"]
        min_salary = self.salary_range["salary_min"]

        # Check deadlock
        if self.deadlock_reached:
            return {
                "status": "DEADLOCK",
                "turn": self.turn_count,
                "message": "DEADLOCK REACHED: Offer Withdrawn. Negotiation terminated.",
                "offer": 0,
            }

        self.turn_count += 1
        self.negotiation_history.append({
            "turn": self.turn_count,
            "candidate_demand": candidate_demand,
        })

        # Finance Hard-Lock: NEVER exceed max
        if candidate_demand <= max_salary:
            # Candidate within range → accept
            final = min(candidate_demand, max_salary)
            self.current_offer = final
            print(f"💼 Negotiation Turn {self.turn_count}: طلب {candidate_demand:,} ≤ حد {max_salary:,} → ✅ ACCEPTED")
            return {
                "status": "ACCEPTED",
                "turn": self.turn_count,
                "offer": final,
                "message": f"✅ تم قبول العرض: {final:,} ر.س",
                "within_budget": True,
            }

        # Candidate demands above max
        if self.turn_count >= self.MAX_TURNS:
            # DEADLOCK — 3 turns exhausted
            self.deadlock_reached = True
            print(f"💼 Negotiation Turn {self.turn_count}: ⛔ DEADLOCK — {self.MAX_TURNS} turns exhausted")
            return {
                "status": "DEADLOCK",
                "turn": self.turn_count,
                "offer": 0,
                "message": "DEADLOCK REACHED: Offer Withdrawn. Negotiation terminated.",
                "candidate_last_demand": candidate_demand,
                "max_allowed": max_salary,
            }

        # Counter-offer: escalate gradually but NEVER exceed max
        escalation = [0.80, 0.90, 0.95]
        pct = escalation[min(self.turn_count - 1, len(escalation) - 1)]
        counter = int(max_salary * pct)
        self.current_offer = counter

        print(
            f"💼 Negotiation Turn {self.turn_count}: طلب {candidate_demand:,} > حد {max_salary:,} "
            f"→ عرض مضاد {counter:,} ({pct*100:.0f}%)"
        )
        return {
            "status": "COUNTER",
            "turn": self.turn_count,
            "offer": counter,
            "message": (
                f"عرض مضاد: {counter:,} ر.س + مزايا إضافية (تأمين VIP، بدل سكن {int(counter*0.25):,} ر.س). "
                f"الحد الأقصى المعتمد: {max_salary:,} ر.س. لا يمكن تجاوزه."
            ),
            "max_allowed": max_salary,
            "candidate_demand": candidate_demand,
        }

    def _mock_negotiation(self, task_id, instruction, candidate_name, budget_cap, seniority, job_id="JD-AI-001"):
        """Full mock negotiation pipeline with Finance Hard-Lock."""
        # Fetch salary range
        salary_range = self.erp.get_approved_salary_range(job_id)
        max_salary = salary_range["salary_max"]
        budget_cap = min(budget_cap, max_salary)

        # Authorize budget
        self.guardrail.financial_cap.authorize_budget(task_id, budget_cap, "finance_agent")

        initial_offer = int(max_salary * 0.80)
        counter_offer = int(max_salary * 0.95)
        final_offer = int(max_salary * 0.90)

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
            f"**الميزانية المعتمدة:** {budget_cap:,.0f} ر.س\n"
            f"**الحد الأقصى (ERP):** {max_salary:,} ر.س\n\n"
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

