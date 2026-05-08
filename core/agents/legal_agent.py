"""
Nawah L3 Legal Agent — Corporate Legal Counsel

Handles: LEGAL_REVIEW intent
Reviews contracts, agreements, and legal documents against corporate
policies stored in RAG memory. Issues APPROVAL or FLAG decisions.
"""
import os
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.synthesizer import truncate_prompt
from core.memory.rag_engine import get_corporate_memory
from core.memory.persona_manager import get_persona_manager
from core.governance_engine import get_compliance_guardrail

MAX_FILE_CHARS = 12000

# Fallback prompt if persona file is missing
_FALLBACK_PROMPT = (
    "أنت المستشار القانوني الأول في نظام نواة. "
    "راجع العقود والوثائق القانونية بدقة."
)




class LegalAgent(BaseAgent):
    """L3 Executive Agent — Corporate Legal Counsel."""
    agent_name = "legal_agent"
    agent_icon = "⚖️"

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None
        self.memory = get_corporate_memory()
        self.persona = get_persona_manager()
        self.guardrail = get_compliance_guardrail()

    def _read_file(self, file_path):
        if not file_path or not os.path.exists(file_path):
            return ""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(file_path)
                text = "\n\n".join(p.get_text() for p in doc)
                doc.close()
                return text.strip()
            except Exception:
                return ""
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                return f.read()
        except Exception:
            return ""

    def process(self, task_payload: dict) -> dict:
        task_id = task_payload.get("task_id", "unknown")
        instruction = task_payload.get("commander_instruction", "")
        attachments = task_payload.get("attachments", [])

        try:
            if not self.router:
                raise CriticalAPIFailure("No API keys available")

            # Read attached document
            file_content = ""
            if attachments:
                att = attachments[0]
                fp = att.get("file_path", "") if isinstance(att, dict) else getattr(att, "file_path", "")
                file_content = truncate_prompt(self._read_file(fp), MAX_FILE_CHARS)

            # Query RAG memory for relevant policies
            policy_context = ""
            policy_chunks = self.memory.query_policy(
                f"سياسة قانونية عقود {instruction}", n_results=3
            )
            if policy_chunks:
                policy_context = "\n\n".join(
                    f"📋 سياسة ({c['doc_id']}): {c['text']}" for c in policy_chunks
                )

            # Build prompt with document + policies
            human_msg = f"طلب المراجعة القانونية: {instruction}\n\n"
            if policy_context:
                human_msg += f"=== السياسات المؤسسية ذات الصلة ===\n{policy_context}\n\n"
            if file_content:
                human_msg += f"=== محتوى الوثيقة للمراجعة ===\n{file_content}"
            else:
                human_msg += "(لا يوجد ملف مرفق — المراجعة على أساس النص فقط)"

            # ReAct: Generate thought process
            intent = task_payload.get("l1_triage", {}).get("intent", "LEGAL_REVIEW")
            thought = self.generate_thought_process(instruction, human_msg, intent)
            human_msg = f"{thought}\n\n{human_msg}"

            sys_prompt = self.persona.get_system_prompt("legal_agent", _FALLBACK_PROMPT)
            temp = self.persona.get_temperature("legal_agent", 0.2)

            prompt = ChatPromptTemplate.from_messages([
                ("system", sys_prompt), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temp, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)

            # Governance check
            verdict = self.guardrail.check("legal_agent", result)
            if not verdict.compliant:
                feedback = self.guardrail.format_violation_report(verdict)
                result = self.self_reflect(result, feedback, task_id=task_id, intent=intent)

            print(f"⚖️ LegalAgent: مراجعة قانونية مكتملة — {len(result)} حرف")
            return self._success(task_id, f"⚖️ المراجعة القانونية مكتملة:\n\n{result}")

        except CriticalAPIFailure:
            mock = (
                f"⚖️ [MOCK/SIMULATED - L3 EXECUTIVE DECISION]\n\n"
                f"## تقرير المراجعة القانونية — مهمة {task_id[:8]}\n\n"
                f"**الطلب:** {instruction[:100]}\n\n"
                f"### القرار: ⚠️ تحفظ قانوني (محاكاة)\n\n"
                f"| البند | الحالة | الملاحظة |\n"
                f"|-------|--------|----------|\n"
                f"| بند المدة والإنهاء | ⚠️ تحفظ | يحتاج تحديد مدة واضحة |\n"
                f"| بند التعويضات | ✅ مقبول | متوافق مع السياسة |\n"
                f"| بند السرية | ✅ مقبول | بنود قياسية |\n\n"
                f"**التوصية:** يُرجى مراجعة بند الإنهاء قبل التوقيع.\n\n"
                f"_⚠️ هذا تحليل محاكاة — التحليل الحقيقي يتطلب مفاتيح API فعّالة._"
            )
            return self._success(task_id, mock)
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ في المراجعة القانونية: {e}")
