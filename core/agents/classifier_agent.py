"""
Nawah L2 Classifier Agent — LIVE AI Logic

Handles: FILE_CLASSIFICATION
Strict document categorizer brain: analyzes file content
and assigns structured classification metadata.
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
    "أنت مصنّف مستندات خبير في نظام نواة للأتمتة المؤسسية.\n"
    "قواعد صارمة:\n"
    "1. صنّف المستند إلى إحدى الفئات التالية:\n"
    "   - مالي (فواتير، ميزانيات، تقارير مالية)\n"
    "   - قانوني (عقود، اتفاقيات، لوائح)\n"
    "   - تقني (وثائق تقنية، أكواد، مواصفات)\n"
    "   - إداري (مذكرات، خطابات، تعاميم)\n"
    "   - أكاديمي (أبحاث، أوراق علمية، تقارير دراسية)\n"
    "   - تسويقي (عروض، حملات، تحليل سوق)\n"
    "   - شخصي (سير ذاتية، طلبات، مراسلات شخصية)\n"
    "   - غير محدد (إذا لم ينطبق أي تصنيف)\n"
    "2. حدد مستوى السرية: عام، داخلي، سري، سري للغاية.\n"
    "3. استخرج الكلمات المفتاحية (5-10 كلمات).\n"
    "4. حدد اللغة الرئيسية للمستند.\n"
    "5. قدم ملخصاً من سطرين عن محتوى المستند.\n"
    "6. قدم النتائج بتنسيق منظم وواضح."
)


class ClassifierAgent(BaseAgent):
    """Live L2 Agent — Document classification and metadata extraction."""
    agent_name = "classifier_agent"
    agent_icon = "🏷️"

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
                human_msg += f"محتوى المستند ({file_name}):\n{file_content}"
            else:
                human_msg += f"اسم الملف: {file_name}\n(لم يتم استخراج محتوى نصي — صنّف بناءً على الاسم والسياق)"

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            print(f"🏷️ ClassifierAgent: تصنيف مكتمل — {len(result)} حرف")
            return self._success(task_id, f"🏷️ التصنيف مكتمل ({len(result)} حرف):\n\n{result}")

        except CriticalAPIFailure:
            return self._success(task_id, f"🏷️ [MOCK/SIMULATED - API OFFLINE] تصنيف محاكى للمهمة {task_id[:8]}. سيتم تفعيل محرك التصنيف عند توفر مفاتيح API.")
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ غير متوقع: {e}")
