"""
Nawah L2 Researcher Agent — LIVE AI + Web Search (Tavily)

Handles: RESEARCH
Senior Web Researcher with live internet access via Tavily.
Synthesizes comprehensive research reports from web data + provided context.

Tool Integration:
    - IF TAVILY_API_KEY exists → Real web search via TavilySearchResults
    - IF missing → MockSearchTool returns simulated results (zero crashes)
"""
import os
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.synthesizer import truncate_prompt

MAX_FILE_CHARS = 14000
MAX_SEARCH_RESULTS = 5

SYSTEM_PROMPT = (
    "أنت باحث ويب أول ومحلل بيانات متقدم في نظام نواة للأتمتة المؤسسية.\n"
    "لديك أداة بحث على الإنترنت (Web Search Tool).\n\n"
    "قواعد صارمة:\n"
    "1. إذا طلب المستخدم بيانات حية أو أحداث جارية أو تحليل سوقي:\n"
    "   → يجب أن تستخدم أداة البحث أولاً قبل الإجابة.\n"
    "2. ادمج نتائج البحث مع معرفتك لتقديم تقرير شامل.\n"
    "3. اذكر المصادر بوضوح مع روابطها.\n"
    "4. نظّم البحث بأقسام: المقدمة، المنهجية، النتائج، التحليل، الخلاصة.\n"
    "5. ميّز بين الحقائق المؤكدة والتحليلات الاستنتاجية.\n"
    "6. حدد الفجوات المعرفية واقترح مجالات بحث إضافية.\n"
    "7. استخدم تنسيق Markdown مع عناوين، جداول، وقوائم مرقمة.\n"
    "8. اكتب بأسلوب أكاديمي دقيق بالعربية الفصحى.\n"
    "9. إذا كانت نتائج البحث فارغة، اعتمد على المحتوى المقدم فقط.\n"
)


# ============================================================
# TOOL INITIALIZATION — Dynamic Tavily / Mock Fallback
# ============================================================
def _init_search_tool():
    """
    Initialize web search tool with graceful degradation.
    Returns (tool_instance, is_live: bool)
    """
    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()

    if tavily_key:
        try:
            from langchain_tavily import TavilySearch
            tool = TavilySearch(
                max_results=MAX_SEARCH_RESULTS,
                tavily_api_key=tavily_key,
            )
            print("🌐 ResearcherAgent: أداة البحث الحي (Tavily) مُفعّلة")
            return tool, True
        except Exception as e:
            print(f"⚠️ ResearcherAgent: فشل تهيئة Tavily — {e}")

    # Fallback: Mock Search Tool
    print("⚠️ ResearcherAgent: TAVILY_API_KEY غير متوفر — وضع البحث المحاكى")
    return None, False


def _mock_search(query: str) -> str:
    """Returns simulated search results when Tavily is unavailable."""
    return (
        f"📌 **نتائج بحث محاكاة** (TAVILY_API_KEY غير متوفر)\n\n"
        f"**الاستعلام:** {query}\n\n"
        f"1. **[محاكاة]** تقرير حديث يشير إلى تطورات في هذا المجال — "
        f"المصدر: تقارير مؤسسية (2024)\n"
        f"2. **[محاكاة]** دراسة أكاديمية تحلل الاتجاهات الحالية — "
        f"المصدر: مجلة بحثية متخصصة\n"
        f"3. **[محاكاة]** مقال تحليلي حول أفضل الممارسات العالمية — "
        f"المصدر: منصة تقنية رائدة\n\n"
        f"_⚠️ هذه نتائج محاكاة. للحصول على نتائج حقيقية، "
        f"أضف TAVILY_API_KEY في ملف .env_"
    )


class ResearcherAgent(BaseAgent):
    """Live L2 Agent — Web Research with Tavily search integration."""
    agent_name = "researcher_agent"
    agent_icon = "🔬"

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None
        self.search_tool, self.search_live = _init_search_tool()

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

    def _web_search(self, query: str) -> str:
        """Execute web search — live or mock depending on key availability."""
        if self.search_live and self.search_tool:
            try:
                results = self.search_tool.invoke(query)
                if isinstance(results, list):
                    formatted = []
                    for i, r in enumerate(results, 1):
                        title = r.get("title", "بدون عنوان") if isinstance(r, dict) else ""
                        url = r.get("url", "") if isinstance(r, dict) else ""
                        content = r.get("content", str(r)) if isinstance(r, dict) else str(r)
                        formatted.append(
                            f"{i}. **{title}**\n"
                            f"   🔗 {url}\n"
                            f"   {content[:300]}"
                        )
                    search_text = "\n\n".join(formatted)
                    print(f"🌐 Tavily: {len(results)} نتيجة بحث حية")
                    return search_text
                return str(results)
            except Exception as e:
                print(f"⚠️ Tavily search error: {e}")
                return _mock_search(query)
        else:
            return _mock_search(query)

    def process(self, task_payload: dict) -> dict:
        task_id = task_payload.get("task_id", "unknown")
        instruction = task_payload.get("commander_instruction", "")
        attachments = task_payload.get("attachments", [])

        try:
            if not self.router:
                raise CriticalAPIFailure("No API keys available")

            # Read attached files
            file_content = ""
            if attachments:
                att = attachments[0]
                fp = att.get("file_path", "") if isinstance(att, dict) else getattr(att, "file_path", "")
                file_content = truncate_prompt(self._read_file(fp), MAX_FILE_CHARS)

            # Execute web search
            search_results = self._web_search(instruction)

            # Build comprehensive prompt
            human_msg = f"موضوع البحث / تعليمات القائد: {instruction}\n\n"
            if search_results:
                human_msg += f"=== نتائج البحث على الإنترنت ===\n{search_results}\n\n"
            if file_content:
                human_msg += f"=== المراجع والمصادر المرفقة ===\n{file_content}"

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash", temperature=0.4, google_api_key=api_key
                )
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            search_tag = "🌐 بحث حي" if self.search_live else "📋 بحث محاكى"
            print(f"🔬 ResearcherAgent [{search_tag}]: بحث مكتمل — {len(result)} حرف")
            return self._success(task_id, f"🔬 البحث مكتمل [{search_tag}]:\n\n{result}")

        except CriticalAPIFailure:
            # Full mock: simulate both search + analysis
            mock_search = _mock_search(instruction)
            mock = (
                f"🔬 [MOCK/SIMULATED - API OFFLINE]\n\n"
                f"## تقرير بحثي — مهمة {task_id[:8]}\n\n"
                f"**الموضوع:** {instruction[:120]}\n\n"
                f"### نتائج البحث:\n{mock_search}\n\n"
                f"### التحليل والخلاصة:\n\n"
                f"بناءً على المعطيات المتاحة، يُلاحظ أن الموضوع يستدعي "
                f"بحثاً معمقاً يشمل:\n\n"
                f"1. **تحليل الاتجاهات** — مراجعة البيانات التاريخية والحالية.\n"
                f"2. **المقارنة المعيارية** — مقارنة مع أفضل الممارسات العالمية.\n"
                f"3. **التوصيات** — خطة عمل مبنية على الأدلة.\n\n"
                f"_⚠️ هذا تقرير محاكاة — التقرير الحقيقي يتطلب مفاتيح API فعّالة._"
            )
            return self._success(task_id, mock)
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ غير متوقع: {e}")
