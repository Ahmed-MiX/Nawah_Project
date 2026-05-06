"""
Nawah L2 Math Agent — LIVE AI Logic

Handles: MATH_SOLVING
Expert mathematician brain: step-by-step logical problem solver,
equation analysis, statistical computation.
"""
import os
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.synthesizer import truncate_prompt

MAX_FILE_CHARS = 10000

SYSTEM_PROMPT = (
    "أنت عالم رياضيات خبير في نظام نواة للأتمتة المؤسسية.\n"
    "قواعد صارمة:\n"
    "1. حل المسائل الرياضية خطوة بخطوة مع شرح كل خطوة بالعربية.\n"
    "2. اعرض المعادلات بشكل واضح ومنظم.\n"
    "3. تحقق من صحة الحل بطريقة معاكسة إن أمكن.\n"
    "4. إذا كانت المسألة تحتمل أكثر من حل، اعرض جميع الحلول.\n"
    "5. في الإحصاء: احسب المتوسط والانحراف المعياري والوسيط حسب الحاجة.\n"
    "6. في الجبر: فكّ المعادلات وبسّطها قبل الحل.\n"
    "7. استخدم الرموز الرياضية الصحيحة (×، ÷، √، π، Σ).\n"
    "8. إذا كان النص لا يحتوي على مسألة رياضية، اذكر ذلك صراحة.\n"
    "9. قدم الإجابة النهائية بشكل بارز ومميز."
)


class MathAgent(BaseAgent):
    """Live L2 Agent — Mathematical problem solving and statistical analysis."""
    agent_name = "math_agent"
    agent_icon = "🔢"

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
            if attachments:
                att = attachments[0]
                fp = att.get("file_path", "") if isinstance(att, dict) else getattr(att, "file_path", "")
                file_content = truncate_prompt(self._read_file(fp), MAX_FILE_CHARS)

            human_msg = f"تعليمات القائد: {instruction}\n\n"
            if file_content:
                human_msg += f"المسألة / البيانات:\n{file_content}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            print(f"🔢 MathAgent: حل رياضي مكتمل — {len(result)} حرف")
            return self._success(task_id, f"🔢 الحل الرياضي مكتمل ({len(result)} حرف):\n\n{result}")

        except CriticalAPIFailure:
            return self._success(task_id, f"🔢 [MOCK/SIMULATED - API OFFLINE] حل رياضي محاكى للمهمة {task_id[:8]}. سيتم تفعيل المحرك الحقيقي عند توفر مفاتيح API.")
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ غير متوقع: {e}")
