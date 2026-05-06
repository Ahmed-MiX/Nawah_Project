"""
Nawah L2 Translator Agent — LIVE AI Logic

Handles: TRANSLATION
Reads source file, combines with commander instruction,
invokes Gemini for professional contextual translation.
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
    "أنت مترجم محترف متخصص في نظام نواة للأتمتة المؤسسية.\n"
    "قواعد صارمة:\n"
    "1. إذا كان النص المصدر بالعربية، ترجمه إلى الإنجليزية الاحترافية.\n"
    "2. إذا كان النص المصدر بالإنجليزية أو أي لغة أخرى، ترجمه إلى العربية الفصحى.\n"
    "3. حافظ على المصطلحات التقنية والأسماء كما هي بين قوسين.\n"
    "4. حافظ على تنسيق النص الأصلي (قوائم، عناوين، فقرات).\n"
    "5. الترجمة يجب أن تكون سياقية ودقيقة، وليست حرفية.\n"
    "6. إذا وُجدت تعليمات محددة من القائد، اتبعها بدقة.\n"
    "7. قدّم الترجمة مباشرة دون مقدمات أو شروحات إضافية."
)


class TranslatorAgent(BaseAgent):
    """Live L2 Agent — Professional contextual translation via Gemini."""
    agent_name = "translator_agent"
    agent_icon = "🌐"

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
                human_msg += f"النص المطلوب ترجمته:\n{file_content}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            print(f"🌐 TranslatorAgent: ترجمة مكتملة — {len(result)} حرف")
            return self._success(task_id, f"🌐 الترجمة مكتملة ({len(result)} حرف):\n\n{result}")

        except CriticalAPIFailure:
            return self._success(task_id, f"🌐 [MOCK/SIMULATED - API OFFLINE] ترجمة محاكاة للمهمة {task_id[:8]}. سيتم تفعيل محرك الترجمة عند توفر مفاتيح API.")
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ غير متوقع: {e}")
