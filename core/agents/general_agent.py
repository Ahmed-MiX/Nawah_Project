"""
Nawah L2 General Agent — LIVE AI Logic

Handles: UNKNOWN / fallback intents
Intelligent general-purpose assistant for ambiguous
or uncategorized requests.
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
    "أنت المساعد الذكي العام في نظام نواة للأتمتة المؤسسية.\n"
    "قواعد صارمة:\n"
    "1. أنت الوكيل الاحتياطي — تتعامل مع أي طلب لم يتمكن وكيل متخصص من معالجته.\n"
    "2. افهم نية المستخدم بدقة وقدم أفضل إجابة ممكنة.\n"
    "3. إذا كان الطلب غامضاً، اطرح أسئلة توضيحية.\n"
    "4. كن شاملاً ومفيداً في إجاباتك.\n"
    "5. استخدم تنسيق Markdown لتحسين القراءة.\n"
    "6. اكتب بالعربية الفصحى بأسلوب مهني ومحترف.\n"
    "7. إذا كان المحتوى خارج قدراتك، اعترف بذلك بصراحة.\n"
    "8. قدم توصيات للوكيل المتخصص المناسب إن أمكن."
)


class GeneralAgent(BaseAgent):
    """Live L2 Agent — General-purpose intelligent assistant (fallback)."""
    agent_name = "general_agent"
    agent_icon = "🤖"

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

            human_msg = f"طلب المستخدم: {instruction}\n\n"
            if file_content:
                human_msg += f"محتوى مرفق:\n{file_content}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            print(f"🤖 GeneralAgent: معالجة مكتملة — {len(result)} حرف")
            return self._success(task_id, f"🤖 المعالجة مكتملة ({len(result)} حرف):\n\n{result}")

        except CriticalAPIFailure:
            return self._success(task_id, f"🤖 [MOCK/SIMULATED - API OFFLINE] الوكيل العام استلم المهمة {task_id[:8]} بنجاح. جاهز للتنفيذ عند توفر مفاتيح API.")
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ غير متوقع: {e}")
