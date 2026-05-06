"""
Nawah L2 Analyst Agent — LIVE AI Logic

Handles: TEXT_SUMMARIZATION, DATA_EXTRACTION, DOCUMENT_REVIEW
Reads the source file, combines with commander instruction,
invokes Gemini via LLMFailoverRouter, and returns the AI analysis.
"""
import os
import traceback
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.synthesizer import truncate_prompt

load_dotenv()

MAX_FILE_CHARS = 12000

ANALYST_SYSTEM_PROMPT = (
    "أنت محلل بيانات متخصص في نظام نواة للأتمتة المؤسسية.\n"
    "مهمتك هي تحليل المحتوى المُقدم وتنفيذ تعليمات القائد بدقة.\n"
    "قواعد صارمة:\n"
    "1. اكتب تحليلك بالعربية الفصحى.\n"
    "2. كن دقيقاً ومفصلاً.\n"
    "3. استخرج النقاط الرئيسية والتوصيات.\n"
    "4. لا تختلق معلومات غير موجودة في النص.\n"
    "5. إذا كان المحتوى غير واضح، اذكر ذلك صراحة."
)


class AnalystAgent(BaseAgent):
    """
    Live L2 Agent — Performs real AI analysis on documents.
    Uses Gemini via LLMFailoverRouter for API key resilience.
    """
    agent_name = "analyst_agent"
    agent_icon = "📊"

    def __init__(self):
        self.router = LLMFailoverRouter()

    def _read_file_content(self, file_path: str) -> str:
        """
        Extract text from any supported file format.
        Supports: PDF (fitz), DOCX (python-docx), TXT/CSV (UTF-8).
        Falls back gracefully on unsupported or corrupted files.
        """
        if not file_path or not os.path.exists(file_path):
            return ""

        ext = os.path.splitext(file_path)[1].lower()

        # PDF — extract via PyMuPDF (fitz)
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(file_path)
                if doc.is_encrypted:
                    doc.close()
                    return "[المستند مشفر ومحمي بكلمة مرور — تعذر استخراج النص]"
                pages = []
                for page in doc:
                    pages.append(page.get_text())
                doc.close()
                text = "\n\n".join(pages).strip()
                if not text:
                    return "[مستند PDF بدون نص قابل للاستخراج — قد يحتوي على صور فقط]"
                return text
            except Exception as e:
                return f"[فشل استخراج النص من PDF: {e}]"

        # DOCX — extract via python-docx
        if ext == ".docx":
            try:
                from docx import Document
                doc = Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                text = "\n".join(paragraphs)
                return text if text else "[مستند DOCX فارغ]"
            except ImportError:
                return "[مكتبة python-docx غير متوفرة — تعذر قراءة ملف DOCX]"
            except Exception as e:
                return f"[فشل استخراج النص من DOCX: {e}]"

        # Text files — UTF-8 with BOM strip
        if ext in (".txt", ".csv", ".md", ".json", ".xml", ".html"):
            try:
                with open(file_path, "r", encoding="utf-8-sig") as f:
                    return f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, "r", encoding="windows-1256", errors="replace") as f:
                        return f.read()
                except Exception:
                    return "[تعذر فك تشفير الملف النصي]"
            except Exception as e:
                return f"[فشل قراءة الملف: {e}]"

        # Unsupported binary format — return metadata only
        try:
            size = os.path.getsize(file_path)
            return f"[ملف ثنائي غير مدعوم ({ext}) — الحجم: {size} بايت]"
        except Exception:
            return "[تعذر قراءة الملف]"

    def process(self, task_payload: dict) -> dict:
        """
        Execute real AI analysis on the task.

        1. Extract file content and commander instruction
        2. Build analysis prompt
        3. Invoke Gemini via failover router
        4. Return structured result
        """
        task_id = task_payload.get("task_id", "unknown")
        instruction = task_payload.get("commander_instruction", "")
        attachments = task_payload.get("attachments", [])

        try:
            # Read file content if attachment exists
            file_content = ""
            file_name = "N/A"
            if attachments:
                att = attachments[0]
                # Handle both Pydantic objects and dicts
                if hasattr(att, "file_path"):
                    file_path = att.file_path
                    file_name = att.file_name
                else:
                    file_path = att.get("file_path", "")
                    file_name = att.get("file_name", "N/A")

                file_content = self._read_file_content(file_path)

            if not file_content and not instruction:
                return self._fail(task_id, "لا يوجد محتوى للتحليل — لا ملف ولا تعليمات.")

            # Truncate to prevent token exhaustion
            file_content = truncate_prompt(file_content, MAX_FILE_CHARS)

            # Build prompt
            human_msg = f"تعليمات القائد: {instruction}\n\n"
            if file_content:
                human_msg += f"محتوى الملف ({file_name}):\n{file_content}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", ANALYST_SYSTEM_PROMPT),
                ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    temperature=0.3,
                    google_api_key=api_key,
                )
                chain = prompt | llm
                response = chain.invoke({"input": human_msg})
                return response.content

            # Execute through failover router
            analysis_result = self.router.execute(call_with_key)

            print(f"🧠 AnalystAgent: تحليل حقيقي مكتمل — {len(analysis_result)} حرف")

            return self._success(task_id, f"📊 التحليل مكتمل ({len(analysis_result)} حرف):\n\n{analysis_result}")

        except CriticalAPIFailure as e:
            print(f"⚠️ AnalystAgent: API غير متاح — تفعيل الوضع المحاكى — {e}")
            return self._success(task_id, f"📊 [MOCK/SIMULATED - API OFFLINE] تحليل محاكى للمهمة {task_id[:8]}. سيتم تفعيل التحليل الحقيقي عند توفر مفاتيح API.")

        except Exception as e:
            print(f"⚠️ AnalystAgent: خطأ غير متوقع — تفعيل الوضع المحاكى — {e}")
            traceback.print_exc()
            return self._success(task_id, f"📊 [MOCK/SIMULATED - ERROR] تحليل محاكى للمهمة {task_id[:8]}. خطأ: {str(e)[:100]}")
