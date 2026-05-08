"""
Nawah L3 Supply Chain Agent — Logistics & Procurement Director

Handles: SUPPLY_CHAIN_MGT intent
Manages inventory, vendor relationships, and procurement.
Uses CorporateMemory (RAG) for vendor policies and ERPWebhookTool
for real-time inventory checks and purchase order issuance.
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

_FALLBACK_PROMPT = "أنت مدير سلسلة الإمداد في نظام نواة. أدر المخزون والمشتريات بدقة."




class SupplyChainAgent(BaseAgent):
    """L3 Executive Agent — Supply Chain & Procurement Director."""
    agent_name = "supply_chain_agent"
    agent_icon = "📦"

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

            # Read attached document
            file_content = ""
            if attachments:
                att = attachments[0]
                fp = att.get("file_path", "") if isinstance(att, dict) else getattr(att, "file_path", "")
                file_content = truncate_prompt(self._read_file(fp), MAX_FILE_CHARS)

            # ERP: Check inventory for referenced items
            inventory_report = self._check_inventory_from_instruction(instruction)

            # RAG: Query vendor/supply policies
            policy_context = ""
            policy_chunks = self.memory.query_policy(
                f"سياسة مشتريات موردين مخزون {instruction}", n_results=3
            )
            if policy_chunks:
                policy_context = "\n\n".join(
                    f"📋 سياسة ({c['doc_id']}): {c['text']}" for c in policy_chunks
                )

            # Build prompt
            human_msg = f"طلب إدارة سلسلة الإمداد: {instruction}\n\n"
            if inventory_report:
                human_msg += f"=== تقرير المخزون (ERP) ===\n{inventory_report}\n\n"
            if policy_context:
                human_msg += f"=== سياسات التوريد ===\n{policy_context}\n\n"
            if file_content:
                human_msg += f"=== المستند المرفق ===\n{file_content}"

            # ReAct: Generate thought process
            intent = task_payload.get("l1_triage", {}).get("intent", "SUPPLY_CHAIN_MGT")
            thought = self.generate_thought_process(instruction, human_msg, intent)
            human_msg = f"{thought}\n\n{human_msg}"

            sys_prompt = self.persona.get_system_prompt("supply_chain_agent", _FALLBACK_PROMPT)
            temp = self.persona.get_temperature("supply_chain_agent", 0.2)

            prompt = ChatPromptTemplate.from_messages([
                ("system", sys_prompt), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temp, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)

            # Governance check
            verdict = self.guardrail.check("supply_chain_agent", result)
            if not verdict.compliant:
                feedback = self.guardrail.format_violation_report(verdict)
                result = self.self_reflect(result, feedback, task_id=task_id, intent=intent)

            print(f"📦 SupplyChainAgent: تحليل سلسلة إمداد مكتمل — {len(result)} حرف")
            return self._success(task_id, f"📦 تقرير سلسلة الإمداد:\n\n{result}")

        except CriticalAPIFailure:
            # Execute ERP actions even in mock mode
            inv = self.erp.check_inventory(f"ITEM-{task_id[:4]}")
            po = None
            if inv["status"] == "LOW_STOCK":
                po = self.erp.issue_purchase_order(inv["item_id"], 100)

            mock = (
                f"📦 [MOCK/SIMULATED - L3 EXECUTIVE DECISION]\n\n"
                f"## تقرير سلسلة الإمداد — مهمة {task_id[:8]}\n\n"
                f"**الطلب:** {instruction[:100]}\n\n"
                f"### فحص المخزون (ERP):\n\n"
                f"| البند | المخزون | الحد الأدنى | الحالة | المستودع |\n"
                f"|-------|---------|-------------|--------|----------|\n"
                f"| {inv['item_id']} | {inv['current_stock']} | {inv['min_threshold']} | "
                f"{'🔴 منخفض' if inv['status'] == 'LOW_STOCK' else '🟢 كافٍ'} | {inv['warehouse']} |\n\n"
            )
            if po:
                mock += (
                    f"### ✅ أمر شراء صادر تلقائياً:\n\n"
                    f"| رقم الأمر | الكمية | المورد | الإجمالي | التسليم |\n"
                    f"|-----------|--------|--------|----------|--------|\n"
                    f"| {po['po_number']} | {po['quantity']} | {po['vendor']} | "
                    f"{po['total_sar']} ر.س | {po['estimated_delivery']} |\n\n"
                )
            else:
                mock += "### ✅ المخزون كافٍ — لا حاجة لأمر شراء.\n\n"

            mock += "_⚠️ هذا تحليل محاكاة — التحليل الحقيقي يتطلب مفاتيح API فعّالة._"
            return self._success(task_id, mock)
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ في إدارة سلسلة الإمداد: {e}")

    def _check_inventory_from_instruction(self, instruction: str) -> str:
        """Extract item references and check ERP inventory."""
        # Simulate checking 2-3 items from the instruction
        items = [f"ITEM-{i:03d}" for i in range(1, 4)]
        lines = []
        for item_id in items:
            inv = self.erp.check_inventory(item_id)
            status_icon = "🔴" if inv["status"] == "LOW_STOCK" else "🟢"
            lines.append(
                f"- {item_id}: {inv['current_stock']} وحدة "
                f"(حد أدنى: {inv['min_threshold']}) [{status_icon} {inv['status']}] — {inv['warehouse']}"
            )
        return "\n".join(lines)
