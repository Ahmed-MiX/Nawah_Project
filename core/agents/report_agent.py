"""
Nawah L2 Report Agent — LIVE AI Logic

Handles: REPORT_GENERATION
Executive business analyst brain: transforms raw data into
structured markdown reports with tables and executive summaries.
"""
import os
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.synthesizer import truncate_prompt

MAX_FILE_CHARS = 14000

SYSTEM_PROMPT = (
    "أنت محلل أعمال تنفيذي متخصص في إعداد التقارير المؤسسية في نظام نواة.\n"
    "قواعد صارمة:\n"
    "1. حوّل البيانات الخام إلى تقرير تنفيذي منظم بالعربية الفصحى.\n"
    "2. ابدأ دائماً بملخص تنفيذي (Executive Summary) لا يتجاوز 3 أسطر.\n"
    "3. استخدم جداول Markdown لعرض البيانات الرقمية والمقارنات.\n"
    "4. قسّم التقرير إلى أقسام واضحة بعناوين (##).\n"
    "5. أضف قسم 'النتائج الرئيسية' مع نقاط مرقمة.\n"
    "6. أضف قسم 'التوصيات' مع إجراءات محددة وقابلة للتنفيذ.\n"
    "7. إذا توفرت أرقام، احسب النسب المئوية ومعدلات التغيير.\n"
    "8. استخدم رموزاً بصرية (📊 📈 📉 ⚠️ ✅) لتحسين القراءة.\n"
    "9. التقرير يجب أن يكون جاهزاً للعرض على الإدارة العليا مباشرة."
)


class ReportAgent(BaseAgent):
    """Live L2 Agent — Executive business report generation."""
    agent_name = "report_agent"
    agent_icon = "📝"

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None

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

            file_content = ""
            file_name = "N/A"
            if attachments:
                att = attachments[0]
                fp = att.get("file_path", "") if isinstance(att, dict) else getattr(att, "file_path", "")
                file_name = att.get("file_name", "N/A") if isinstance(att, dict) else getattr(att, "file_name", "N/A")
                file_content = truncate_prompt(self._read_file(fp), MAX_FILE_CHARS)

            human_msg = f"تعليمات القائد: {instruction}\n\n"
            if file_content:
                human_msg += f"البيانات المصدرية ({file_name}):\n{file_content}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            print(f"📝 ReportAgent: تقرير مكتمل — {len(result)} حرف")
            return self._success(task_id, f"📝 التقرير التنفيذي مكتمل ({len(result)} حرف):\n\n{result}")

        except CriticalAPIFailure:
            return self._success(task_id, f"📝 [MOCK/SIMULATED - API OFFLINE] تقرير محاكى للمهمة {task_id[:8]}. سيتم تفعيل محرك التقارير عند توفر مفاتيح API.")
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ غير متوقع: {e}")
