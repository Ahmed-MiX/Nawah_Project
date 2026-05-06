"""
Nawah L2 Email Agent — LIVE AI Logic

Handles: EMAIL_RESPONSE
Professional corporate communicator brain: drafts polished
email replies based on context and commander instructions.
"""
import os
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.synthesizer import truncate_prompt

MAX_FILE_CHARS = 8000

SYSTEM_PROMPT = (
    "أنت متخصص في المراسلات المؤسسية الرسمية في نظام نواة.\n"
    "قواعد صارمة:\n"
    "1. صغ رداً بريدياً احترافياً بالعربية الفصحى.\n"
    "2. ابدأ بتحية مناسبة (السلام عليكم ورحمة الله وبركاته).\n"
    "3. حافظ على نبرة رسمية ومهنية ومحترمة.\n"
    "4. أجب على جميع النقاط المذكورة في البريد الأصلي.\n"
    "5. كن مختصراً ودقيقاً — لا إطالة غير مبررة.\n"
    "6. أضف خاتمة مهنية مناسبة (مع فائق التقدير والاحترام).\n"
    "7. إذا تطلب الأمر إرفاق مستندات، اذكر ذلك صراحة.\n"
    "8. إذا كانت التعليمات تحدد لهجة معينة (ودية/حازمة)، التزم بها.\n"
    "9. لا تضف معلومات غير موجودة في السياق المقدم."
)


class EmailAgent(BaseAgent):
    """Live L2 Agent — Professional email drafting and corporate communication."""
    agent_name = "email_agent"
    agent_icon = "📧"

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None

    def _read_file(self, file_path):
        if not file_path or not os.path.exists(file_path):
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
                human_msg += f"البريد الأصلي / السياق:\n{file_content}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            print(f"📧 EmailAgent: رد بريدي مكتمل — {len(result)} حرف")
            return self._success(task_id, f"📧 الرد البريدي مكتمل ({len(result)} حرف):\n\n{result}")

        except CriticalAPIFailure:
            return self._success(task_id, f"📧 [MOCK/SIMULATED - API OFFLINE] رد بريدي محاكى للمهمة {task_id[:8]}. سيتم تفعيل محرك البريد عند توفر مفاتيح API.")
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ غير متوقع: {e}")
