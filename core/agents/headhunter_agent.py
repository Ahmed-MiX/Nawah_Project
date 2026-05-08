"""
Nawah L3 Headhunter Agent — Proactive Executive Talent Acquisition

Unlike passive HR screening, this agent PROACTIVELY:
  1. Generates Dynamic Job Descriptions based on company context
  2. Scans professional networks (LinkedIn/GitHub) for matching talent
  3. Evaluates candidates against dynamic requirements
  4. Drafts personalized outreach messages to pull talent into Nawah's pipeline

Uses: SourcingTools, ComplianceGuardrail, DynamicPersonaManager, ReAct, Episodic Memory
"""
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.memory.rag_engine import get_corporate_memory
from core.memory.persona_manager import get_persona_manager
from core.governance_engine import get_compliance_guardrail
from core.tools.sourcing_tools import get_sourcing_tools

_FALLBACK_PROMPT = (
    "أنت صياد مواهب تنفيذي نخبوي في نظام نواة. "
    "لا تنتظر المتقدمين. تحلل سياق الشركة، تبني متطلبات ديناميكية، "
    "تبحث عن أفضل الكفاءات، وتصيغ رسائل استقطاب لا تُقاوم."
)

SYSTEM_PROMPT = (
    "أنت صياد مواهب تنفيذي نخبوي (Elite Executive Headhunter) في نظام نواة.\n"
    "أنت لا تنتظر المتقدمين. أنت تبادر بالبحث عن أفضل الكفاءات.\n\n"
    "لديك أدوات متقدمة:\n"
    "- generate_dynamic_jd: بناء وصف وظيفي ديناميكي من سياق الشركة.\n"
    "- scan_professional_networks: مسح LinkedIn/GitHub لإيجاد الكفاءات.\n\n"
    "بروتوكول صارم:\n"
    "1. حلل سياق الشركة والاحتياج الفوري.\n"
    "2. بناء وصف وظيفي ديناميكي مُخصص (ليس قوالب ثابتة).\n"
    "3. البحث في الشبكات المهنية عن أفضل الكفاءات المطابقة.\n"
    "4. تقييم كل مرشح ضد المتطلبات الديناميكية.\n"
    "5. صياغة رسائل استقطاب شخصية لأفضل مرشحَين.\n"
    "6. الرسالة يجب أن تكون مقنعة ومهنية ومخصصة لكل مرشح.\n"
    "7. اذكر رابط المقابلة الآلية في نواة في نهاية كل رسالة.\n"
    "8. استخدم تنسيق Markdown مع جداول وقوائم.\n"
    "9. اكتب بالعربية الفصحى بأسلوب تنفيذي راقٍ.\n"
)


class HeadhunterAgent(BaseAgent):
    """L3 Executive Agent — Proactive Talent Headhunter."""
    agent_name = "headhunter_agent"
    agent_icon = "🎯"

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None
        self.memory = get_corporate_memory()
        self.sourcing = get_sourcing_tools()
        self.persona = get_persona_manager()
        self.guardrail = get_compliance_guardrail()

    def process(self, task_payload: dict) -> dict:
        task_id = task_payload.get("task_id", "unknown")
        instruction = task_payload.get("commander_instruction", "")
        intent = task_payload.get("l1_triage", {}).get("intent", "PROACTIVE_SOURCING")
        # UI-dictated parameters (strict obedience)
        source = task_payload.get("source", "AUTO")
        max_candidates = task_payload.get("max_candidates", 3)

        try:
            if not self.router:
                raise CriticalAPIFailure("No API keys available")

            # ── STEP 1: Extract role + context from instruction ──
            role_title, company_context = self._parse_instruction(instruction)

            # ── STEP 2: Generate Dynamic JD ──
            dynamic_jd = self.sourcing.generate_dynamic_jd(role_title, company_context)

            # ── STEP 3: Dual-Sourcing Strategy (obeys UI source param) ──
            sourcing_result = self.sourcing.execute_dual_sourcing_strategy(
                dynamic_jd.get("keywords", [role_title]), max_results=max_candidates, source=source
            )
            candidates = sourcing_result["final_candidates"]

            # ── STEP 4: Build prompt with all sourcing data ──
            jd_text = self._format_jd(dynamic_jd)
            candidates_text = self._format_candidates(candidates)

            human_msg = (
                f"طلب استقطاب: {instruction}\n\n"
                f"=== الوصف الوظيفي الديناميكي ===\n{jd_text}\n\n"
                f"=== المرشحون المكتشفون ===\n{candidates_text}\n\n"
                f"المطلوب: قيّم المرشحين وصِغ رسائل استقطاب مخصصة لأفضل اثنين."
            )

            # ReAct thought process
            thought = self.generate_thought_process(instruction, human_msg, intent)
            human_msg = f"{thought}\n\n{human_msg}"

            sys_prompt = self.persona.get_system_prompt("headhunter_agent", SYSTEM_PROMPT)
            temp = self.persona.get_temperature("headhunter_agent", 0.4)

            prompt = ChatPromptTemplate.from_messages([
                ("system", sys_prompt), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temp, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)

            # Governance check
            verdict = self.guardrail.check("headhunter_agent", result)
            if not verdict.compliant:
                feedback = self.guardrail.format_violation_report(verdict)
                result = self.self_reflect(result, feedback, task_id=task_id, intent=intent)

            print(f"🎯 HeadhunterAgent: استقطاب مكتمل — {len(result)} حرف")
            return self._success(task_id, f"🎯 تقرير الاستقطاب:\n\n{result}")

        except CriticalAPIFailure:
            return self._mock_headhunt(task_id, instruction, source, max_candidates)
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ في الاستقطاب: {e}")

    def _parse_instruction(self, instruction: str) -> tuple:
        """Extract role title and company context from free-text instruction."""
        # Simple heuristic: first part is the role, rest is context
        parts = instruction.split(".", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

        # Try splitting on common Arabic connectors
        for sep in ["—", "-", "،", ","]:
            parts = instruction.split(sep, 1)
            if len(parts) == 2 and len(parts[0]) < 80:
                return parts[0].strip(), parts[1].strip()

        return instruction[:60], instruction

    def _format_jd(self, jd: dict) -> str:
        reqs = jd.get("requirements", {})
        comp = jd.get("compensation", {})
        return (
            f"**المسمى:** {jd['title']}\n"
            f"**المجال:** {jd['domain']} | **الأولوية:** {jd['urgency']} | **المستوى:** {jd['seniority']}\n"
            f"**الحد الأدنى للخبرة:** {reqs.get('min_experience_years', 3)} سنوات\n"
            f"**المهارات المطلوبة:** {', '.join(reqs.get('required_skills', []))}\n"
            f"**المهارات المفضلة:** {', '.join(reqs.get('preferred_skills', []))}\n"
            f"**الراتب:** {comp.get('salary_range_sar', 'غير محدد')} ر.س\n"
            f"**نظام العمل:** {jd.get('work_arrangement', 'حضوري')}\n"
            f"**سياق الشركة:** {jd.get('company_context_summary', '')}"
        )

    def _format_candidates(self, candidates: list) -> str:
        lines = []
        for i, c in enumerate(candidates, 1):
            lines.append(
                f"### المرشح {i}: {c['name']}\n"
                f"- **العنوان:** {c['headline']}\n"
                f"- **الملخص:** {c['summary']}\n"
                f"- **المنصة:** {c['platform']}\n"
                f"- **الرابط:** {c['url']}\n"
                f"- **نسبة التطابق:** {c['match_score']}%\n"
            )
        return "\n".join(lines)

    def _mock_headhunt(self, task_id: str, instruction: str, source: str = "AUTO", max_candidates: int = 3) -> dict:
        """Full mock pipeline with Dynamic JD + Dual-Sourcing + Outreach."""
        role_title, company_context = self._parse_instruction(instruction)

        # Step 1: Dynamic JD
        jd = self.sourcing.generate_dynamic_jd(role_title, company_context)
        reqs = jd.get("requirements", {})

        # Step 2: Dual-Sourcing (obeys UI source)
        sourcing_result = self.sourcing.execute_dual_sourcing_strategy(
            jd.get("keywords", []), max_results=max_candidates, source=source
        )
        candidates = sourcing_result["final_candidates"]
        strategy = sourcing_result["strategy"]

        # Step 3: Build report
        mock = (
            f"🎯 [L3 EXECUTIVE DECISION — PROACTIVE HEADHUNT]\n\n"
            f"## تقرير الاستقطاب الاستباقي — مهمة {task_id[:8]}\n\n"
            f"**الطلب:** {instruction[:120]}\n\n"
            f"---\n\n"
            f"### 📋 الوصف الوظيفي الديناميكي\n\n"
            f"| البند | التفاصيل |\n"
            f"|-------|----------|\n"
            f"| المسمى | {jd['title']} |\n"
            f"| المجال | {jd['domain']} |\n"
            f"| الأولوية | {jd['urgency']} |\n"
            f"| الخبرة المطلوبة | ≥{reqs.get('min_experience_years', 3)} سنوات |\n"
            f"| المهارات | {', '.join(reqs.get('required_skills', [])[:5])} |\n"
            f"| الراتب | {jd.get('compensation', {}).get('salary_range_sar', 'غير محدد')} ر.س |\n"
            f"| نظام العمل | {jd.get('work_arrangement', 'حضوري')} |\n\n"
            f"---\n\n"
            f"### 🔍 استراتيجية الاستقطاب: {strategy}\n"
            f"- **داخلي (ATS):** {len(sourcing_result['internal_candidates'])} مرشح\n"
            f"- **خارجي (LinkedIn/GitHub):** {len(sourcing_result['external_candidates'])} مرشح\n"
            f"- **التوفير:** {sourcing_result['cost_savings']}\n\n"
            f"### 🔍 المرشحون المكتشفون ({len(candidates)} ملف شخصي)\n\n"
        )

        for i, c in enumerate(candidates, 1):
            mock += (
                f"#### المرشح {i}: {c['name']} ({c['match_score']}% تطابق)\n"
                f"- **{c['headline']}**\n"
                f"- {c['summary'][:150]}\n"
                f"- 🔗 [{c['platform']}]({c['url']})\n\n"
            )

        # Step 4: Outreach messages for top 2
        mock += "---\n\n### ✉️ رسائل الاستقطاب المخصصة\n\n"

        for c in candidates[:2]:
            mock += (
                f"#### رسالة إلى: {c['name']}\n\n"
                f"---\n"
                f"الأخ/الأخت الكريم/ة {c['name']}،\n\n"
                f"لفت انتباهنا ملفك المهني المتميز على {c['platform']}، "
                f"وتحديداً خبرتك في مجال {jd['domain']}. "
                f"نحن في نواة نبحث عن {jd['title']} للانضمام لفريقنا "
                f"في مرحلة {'حرجة وعاجلة' if jd['urgency'] == 'critical' else 'نمو متسارع'}.\n\n"
                f"**لماذا نواة؟**\n"
                f"- راتب تنافسي: {jd.get('compensation', {}).get('salary_range_sar', '')} ر.س\n"
                f"- {jd.get('work_arrangement', 'بيئة عمل مرنة')}\n"
                f"- فريق تقني نخبوي يعمل على أحدث تقنيات الذكاء الاصطناعي\n\n"
                f"**الخطوة التالية:**\n"
                f"يمكنك إجراء مقابلة تقنية آلية فورية عبر نظام نواة الذكي:\n"
                f"🔗 `nawah.ai/interview/{task_id[:8]}`\n\n"
                f"في انتظار ردكم الكريم.\n\n"
                f"مع خالص التقدير،\n"
                f"فريق استقطاب المواهب — نواة\n"
                f"---\n\n"
            )

        mock += "_⚠️ هذا تقرير محاكاة — البحث الحقيقي يتطلب مفاتيح API فعّالة._"
        return self._success(task_id, mock)
