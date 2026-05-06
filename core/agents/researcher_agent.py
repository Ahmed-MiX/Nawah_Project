"""
Nawah L2 Researcher Agent — LIVE AI Logic

Handles: RESEARCH
Expert data gatherer brain: synthesizes comprehensive research
reports from provided context and commander queries.
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
    "أنت باحث أكاديمي ومحلل بيانات متخصص في نظام نواة للأتمتة المؤسسية.\n"
    "قواعد صارمة:\n"
    "1. اجمع وحلل المعلومات المتاحة حول الموضوع المطلوب بعمق.\n"
    "2. قدم بحثاً منظماً بأقسام واضحة: المقدمة، المنهجية، النتائج، الخلاصة.\n"
    "3. اذكر الحقائق والأرقام المستخلصة من المحتوى المقدم فقط.\n"
    "4. لا تختلق مصادر أو إحصائيات غير موجودة في النص.\n"
    "5. قارن بين وجهات النظر المختلفة إن وُجدت.\n"
    "6. حدد الفجوات المعرفية واقترح مجالات بحث إضافية.\n"
    "7. استخدم تنسيق Markdown مع عناوين واضحة وقوائم مرقمة.\n"
    "8. اكتب بأسلوب أكاديمي دقيق بالعربية الفصحى."
)


class ResearcherAgent(BaseAgent):
    """Live L2 Agent — Research synthesis and knowledge analysis."""
    agent_name = "researcher_agent"
    agent_icon = "🔬"

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

            human_msg = f"موضوع البحث / تعليمات القائد: {instruction}\n\n"
            if file_content:
                human_msg += f"المراجع والمصادر المتاحة:\n{file_content}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.4, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            print(f"🔬 ResearcherAgent: بحث مكتمل — {len(result)} حرف")
            return self._success(task_id, f"🔬 البحث مكتمل ({len(result)} حرف):\n\n{result}")

        except CriticalAPIFailure:
            return self._success(task_id, f"🔬 [MOCK/SIMULATED - API OFFLINE] بحث محاكى للمهمة {task_id[:8]}. سيتم تفعيل محرك البحث عند توفر مفاتيح API.")
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ غير متوقع: {e}")
