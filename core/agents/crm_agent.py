"""
Nawah L3 CRM Agent — Customer Relationship Manager

Handles: CRM_RESOLUTION intent
Manages customer complaints, refund processing, and satisfaction.
Uses CorporateMemory (RAG) for refund policies and ERPWebhookTool
for processing actual refund transactions.
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
from core.tools.erp_connector import get_erp_tool

MAX_FILE_CHARS = 12000

_FALLBACK_PROMPT = "أنت مدير علاقات العملاء في نظام نواة. عالج شكاوى العملاء بتعاطف والتزام."




class CRMAgent(BaseAgent):
    """L3 Executive Agent — Customer Relationship Manager."""
    agent_name = "crm_agent"
    agent_icon = "🤝"

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None
        self.memory = get_corporate_memory()
        self.erp = get_erp_tool()
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

            # Read attached complaint/document
            file_content = ""
            if attachments:
                att = attachments[0]
                fp = att.get("file_path", "") if isinstance(att, dict) else getattr(att, "file_path", "")
                file_content = truncate_prompt(self._read_file(fp), MAX_FILE_CHARS)

            # RAG: Query refund/CRM policies
            policy_context = ""
            policy_chunks = self.memory.query_policy(
                f"سياسة استرداد شكوى عميل تعويض {instruction}", n_results=3
            )
            if policy_chunks:
                policy_context = "\n\n".join(
                    f"📋 سياسة ({c['doc_id']}): {c['text']}" for c in policy_chunks
                )

            # Build prompt
            human_msg = f"شكوى العميل / طلب خدمة العملاء: {instruction}\n\n"
            if policy_context:
                human_msg += f"=== سياسات الاسترداد والتعويض ===\n{policy_context}\n\n"
            if file_content:
                human_msg += f"=== تفاصيل الشكوى المرفقة ===\n{file_content}"

            # ReAct: Generate thought process
            intent = task_payload.get("l1_triage", {}).get("intent", "CRM_RESOLUTION")
            thought = self.generate_thought_process(instruction, human_msg, intent)
            human_msg = f"{thought}\n\n{human_msg}"

            sys_prompt = self.persona.get_system_prompt("crm_agent", _FALLBACK_PROMPT)
            temp = self.persona.get_temperature("crm_agent", 0.3)

            prompt = ChatPromptTemplate.from_messages([
                ("system", sys_prompt), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temp, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)

            # Governance check
            verdict = self.guardrail.check("crm_agent", result)
            if not verdict.compliant:
                feedback = self.guardrail.format_violation_report(verdict)
                result = self.self_reflect(result, feedback, task_id=task_id, intent=intent)

            print(f"🤝 CRMAgent: معالجة شكوى مكتملة — {len(result)} حرف")
            return self._success(task_id, f"🤝 تقرير خدمة العملاء:\n\n{result}")

        except CriticalAPIFailure:
            # Execute ERP refund even in mock mode
            refund = self.erp.process_customer_refund(
                customer_id=f"CUS-{task_id[:6]}",
                amount=250.0,
                reason=instruction[:50]
            )

            mock = (
                f"🤝 [MOCK/SIMULATED - L3 EXECUTIVE DECISION]\n\n"
                f"## تقرير خدمة العملاء — مهمة {task_id[:8]}\n\n"
                f"**شكوى العميل:** {instruction[:120]}\n\n"
                f"### تحليل الشكوى:\n\n"
                f"| المحور | التقييم |\n"
                f"|--------|--------|\n"
                f"| نوع المشكلة | جودة الخدمة |\n"
                f"| الأولوية | عالية |\n"
                f"| مدة العلاقة | عميل مميز |\n\n"
                f"### إجراء ERP — معالجة الاسترداد:\n\n"
                f"| رقم المعاملة | المبلغ | الحالة | طريقة الاسترداد |\n"
                f"|-------------|--------|--------|----------------|\n"
                f"| {refund['transaction_id']} | {refund['amount_sar']} ر.س | "
                f"{'✅ موافقة' if refund['status'] == 'APPROVED' else '⚠️ يتطلب موافقة'} | "
                f"{refund['refund_method']} |\n\n"
                f"### القرار: ✅ استرداد كامل + اعتذار (محاكاة)\n\n"
                f"### مسودة البريد الإلكتروني:\n\n"
                f"---\n"
                f"**الموضوع:** اعتذار وتعويض — رقم المرجع {refund['transaction_id']}\n\n"
                f"عميلنا الكريم،\n\n"
                f"نعتذر بشدة عن التجربة غير المرضية. تم معالجة استرداد بقيمة "
                f"{refund['amount_sar']} ر.س وسيصل خلال {refund['processing_time']}.\n\n"
                f"نقدر ولاءكم ونتعهد بتحسين خدماتنا.\n\n"
                f"مع خالص التقدير،\n"
                f"إدارة علاقات العملاء — نواة\n"
                f"---\n\n"
                f"_⚠️ هذا تحليل محاكاة — التحليل الحقيقي يتطلب مفاتيح API فعّالة._"
            )
            return self._success(task_id, mock)
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ في معالجة شكوى العميل: {e}")
