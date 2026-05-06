"""
Nawah L2 Vision Agent — LIVE AI Logic

Handles: IMAGE_ANALYSIS
Analyzes extracted image descriptions/text context from L1 vision module.
Provides deep visual content interpretation and insights.
"""
import os
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.synthesizer import truncate_prompt

MAX_FILE_CHARS = 12000

SYSTEM_PROMPT = (
    "أنت محلل صور ومحتوى بصري خبير في نظام نواة للأتمتة المؤسسية.\n"
    "قواعد صارمة:\n"
    "1. حلل الوصف البصري أو النص المستخرج من الصورة بعمق.\n"
    "2. حدد العناصر الرئيسية: نصوص، أرقام، رسوم بيانية، جداول، شعارات.\n"
    "3. استنتج السياق والغرض من المحتوى البصري.\n"
    "4. إذا كان المحتوى يتضمن رسماً بيانياً، استخلص البيانات والاتجاهات.\n"
    "5. إذا كان المحتوى يتضمن مستنداً ممسوحاً ضوئياً، أعد كتابة النص بوضوح.\n"
    "6. قدم ملخصاً تنفيذياً للمحتوى البصري في النهاية.\n"
    "7. اكتب تحليلك بالعربية الفصحى مع الحفاظ على المصطلحات التقنية."
)


class VisionAgent(BaseAgent):
    """Live L2 Agent — Visual content analysis and interpretation."""
    agent_name = "vision_agent"
    agent_icon = "📷"

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
                human_msg += f"المحتوى البصري المستخرج ({file_name}):\n{file_content}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            print(f"📷 VisionAgent: تحليل بصري مكتمل — {len(result)} حرف")
            return self._success(task_id, f"📷 التحليل البصري مكتمل ({len(result)} حرف):\n\n{result}")

        except CriticalAPIFailure:
            return self._success(task_id, f"📷 [MOCK/SIMULATED - API OFFLINE] تحليل بصري محاكى للمهمة {task_id[:8]}. سيتم تفعيل التحليل الحقيقي عند توفر مفاتيح API.")
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ غير متوقع: {e}")
