"""
Nawah JD Suggester Agent — Pre-JD Verification + Dynamic JD Generation

Micro-Step 1.1 + 1.2: BEFORE drafting any JD, this agent:
  A. Detects department from input (or requests clarification)
  B. Checks department hiring budget via ERP
  C. If budget=0 → ABORT with denial
  D. If input is too vague → ABORT with 3 clarification questions
  E. Checks Saudization/Nitaqat localization quota
  F. If quota critical → inject MANDATORY local-citizen constraint
  G. Only then → generate professional dynamic JD
"""
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.tools.sourcing_tools import get_sourcing_tools
from core.tools.erp_connector import get_erp_tool

SYSTEM_PROMPT = (
    "أنت خبير صياغة أوصاف وظيفية في نظام نواة.\n"
    "المستخدم سيعطيك وصفاً غامضاً. مهمتك:\n"
    "1. فهم الاحتياج الحقيقي.\n"
    "2. صياغة وصف وظيفي احترافي كامل.\n"
    "3. تحديد: المسمى، المهارات التقنية، المهارات الشخصية، KPIs، المستوى.\n"
    "4. استخدام اتجاهات السوق الحالية.\n"
    "5. تقديم النتيجة كـ JSON مُنسق + تقرير Markdown.\n"
    "6. اكتب بالعربية الفصحى.\n"
)

# Vagueness detection — if input has fewer than this many meaningful words
_MIN_MEANINGFUL_WORDS = 4
# Keywords that help detect a department
_DEPT_KEYWORDS = {
    "it": "IT", "تقنية": "التقنية", "التقنية": "التقنية", "tech": "IT",
    "ai": "الذكاء الاصطناعي", "ذكاء": "الذكاء الاصطناعي", "ml": "الذكاء الاصطناعي",
    "marketing": "التسويق", "تسويق": "التسويق", "التسويق": "التسويق",
    "hr": "موارد بشرية", "موارد": "موارد بشرية",
    "finance": "مالية", "مالية": "مالية", "محاسب": "مالية",
    "engineering": "هندسة", "هندسة": "هندسة", "مهندس": "هندسة",
    "backend": "IT", "frontend": "IT", "fullstack": "IT",
    "data": "IT", "بيانات": "IT", "devops": "IT",
    "مبرمج": "IT", "مطور": "IT", "developer": "IT", "coder": "IT",
    "operations": "عمليات", "عمليات": "عمليات",
}


class JDSuggesterAgent(BaseAgent):
    """Converts vague HR requests into professional dynamic JDs with budget pre-check."""
    agent_name = "jd_suggester_agent"
    agent_icon = "📝"

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None
        self.sourcing = get_sourcing_tools()
        self.erp = get_erp_tool()

    def process(self, task_payload: dict) -> dict:
        task_id = task_payload.get("task_id", "unknown")
        instruction = task_payload.get("commander_instruction", "")
        intent = "JD_SUGGESTION"
        explicit_dept = task_payload.get("department", "")

        # ── PRE-JD GATE A: Vagueness Check ──
        vagueness_result = self._check_vagueness(instruction)
        if vagueness_result:
            print(f"📝 JDSuggester: طلب غامض — مطلوب توضيح")
            return self._success(task_id, vagueness_result)

        # ── PRE-JD GATE B: Department Detection ──
        department = explicit_dept or self._detect_department(instruction)
        if not department:
            print(f"📝 JDSuggester: قسم غير محدد — مطلوب توضيح")
            return self._success(task_id, self._ask_department(instruction))

        # ── PRE-JD GATE C: Budget Verification ──
        budget = self.erp.check_department_hiring_budget(department)
        if not budget["can_hire"]:
            print(f"📝 JDSuggester: 🚫 ميزانية توظيف صفرية — {department}")
            return self._success(task_id, self._deny_no_budget(department, budget))

        # ── PRE-JD GATE D: Localization / Saudization Quota ──
        quota = self.erp.check_localization_quota(department)
        localization_constraint = ""
        if quota["must_hire_local"]:
            localization_constraint = (
                f"\n\n🔴 **قيد إلزامي (نطاقات):** يجب أن يكون المرشح مواطناً سعودياً. "
                f"القسم ({department}) في النطاق {quota['nitaqat_band']} — "
                f"نسبة السعودة الحالية {quota['current_saudization_pct']}% "
                f"(المطلوب ≥{quota['required_pct']}%)."
            )
            print(f"📝 JDSuggester: 🔴 نطاقات — قيد السعودة مُفعّل لـ {department}")
        else:
            print(f"📝 JDSuggester: 🟢 نطاقات — لا قيود إلزامية لـ {department}")

        # ── ALL GATES PASSED — Generate JD ──
        print(f"📝 JDSuggester: ✅ جميع البوابات مفتوحة — بدء صياغة الوصف الوظيفي")
        try:
            if not self.router:
                raise CriticalAPIFailure("No API keys")

            thought = self.generate_thought_process(instruction, f"Dept: {department}, Budget: {budget['hiring_budget_sar']}", intent)
            human_msg = (
                f"{thought}\n\n"
                f"القسم: {department} | الميزانية: {budget['hiring_budget_sar']:,.0f} ر.س\n"
                f"المدخل: {instruction}\n\n"
                f"أنشئ وصفاً وظيفياً احترافياً كاملاً."
            )
            prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", "{input}")])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)
            return self._success(task_id, f"📝 الوصف الوظيفي المقترح:\n\n{result}")

        except CriticalAPIFailure:
            return self._mock_suggestion(task_id, instruction, department, budget, quota, localization_constraint)
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ: {e}")

    # ============================================================
    # PRE-JD GATES
    # ============================================================
    def _check_vagueness(self, instruction: str) -> str | None:
        """
        Gate A: Detect if the input is too vague to generate a JD.
        Returns clarification request or None if input is sufficient.
        """
        # Strip noise
        words = [w for w in instruction.split() if len(w) > 1]
        has_role_keyword = any(
            kw in instruction.lower()
            for kw in [
                "developer", "engineer", "manager", "analyst", "designer",
                "مطور", "مهندس", "مدير", "محلل", "مصمم", "مبرمج",
                "lead", "senior", "junior", "قائد", "أخصائي", "خبير",
                "coder", "ai", "data", "backend", "frontend",
            ]
        )

        if len(words) < _MIN_MEANINGFUL_WORDS and not has_role_keyword:
            return (
                f"⚠️ [PRE-JD GATE — طلب غامض]\n\n"
                f"## الطلب غير كافٍ لصياغة وصف وظيفي\n\n"
                f"**المدخل الأصلي:** \"{instruction}\"\n\n"
                f"الطلب غامض جداً ولا يحتوي على معلومات كافية. "
                f"يرجى الإجابة على الأسئلة التالية:\n\n"
                f"1. **ما المسمى الوظيفي المطلوب؟** (مثال: مطور Python، مهندس بيانات)\n"
                f"2. **ما القسم الطالب؟** (مثال: قسم التقنية، قسم التسويق)\n"
                f"3. **ما مستوى الخبرة المطلوب؟** (مبتدئ / متوسط / خبير)\n\n"
                f"**الحالة:** 🔒 معلّق — بانتظار التوضيح\n"
            )
        return None

    def _detect_department(self, instruction: str) -> str:
        """Gate B: Extract department from instruction text."""
        inst_lower = instruction.lower()
        for keyword, dept in _DEPT_KEYWORDS.items():
            if keyword in inst_lower:
                return dept
        return ""

    def _ask_department(self, instruction: str) -> str:
        """Gate B fallback: Ask user to specify department."""
        return (
            f"⚠️ [PRE-JD GATE — قسم غير محدد]\n\n"
            f"## لم يتم تحديد القسم الطالب\n\n"
            f"**المدخل الأصلي:** \"{instruction}\"\n\n"
            f"لا يمكن بدء عملية التوظيف بدون تحديد القسم الطالب "
            f"(لفحص ميزانية التوظيف المعتمدة).\n\n"
            f"**الأقسام المتاحة:**\n"
            f"- التقنية (IT)\n"
            f"- الذكاء الاصطناعي (AI)\n"
            f"- الهندسة\n"
            f"- التسويق\n"
            f"- الموارد البشرية\n"
            f"- المالية\n"
            f"- العمليات\n\n"
            f"**الحالة:** 🔒 معلّق — يرجى تحديد القسم\n"
        )

    def _deny_no_budget(self, department: str, budget: dict) -> str:
        """Gate C: Budget denial response."""
        return (
            f"🚫 [PRE-JD GATE — طلب مرفوض: ميزانية توظيف غير كافية]\n\n"
            f"## طلب التوظيف مرفوض\n\n"
            f"**القسم:** {department}\n"
            f"**ميزانية التوظيف:** {budget['hiring_budget_sar']:,.0f} ر.س\n"
            f"**الوظائف المتاحة:** {budget['open_positions']}\n"
            f"**حالة الميزانية:** {budget['budget_status']}\n\n"
            f"---\n\n"
            f"### ⛔ السبب:\n"
            f"القسم المطلوب ({department}) لا يملك ميزانية توظيف معتمدة. "
            f"لا يمكن لنظام نواة بدء عملية استقطاب أو صياغة وصف وظيفي "
            f"بدون ميزانية مسبقة.\n\n"
            f"### 📋 الإجراء المطلوب:\n"
            f"1. تقديم طلب ميزانية توظيف لمجلس الإدارة.\n"
            f"2. الحصول على موافقة المدير المالي.\n"
            f"3. تحديث سجل الميزانيات في نظام ERP.\n"
            f"4. إعادة إرسال طلب التوظيف بعد الاعتماد.\n\n"
            f"**الحالة:** 🔒 مرفوض — ميزانية غير كافية\n"
        )

    # ============================================================
    # JD GENERATION (post-gates)
    # ============================================================
    def _mock_suggestion(self, task_id: str, vague_input: str, department: str, budget: dict, quota: dict = None, localization_constraint: str = "") -> dict:
        """Generate a professional JD from vague input using sourcing tools."""
        mappings = {
            "coder": ("Senior Software Engineer", "backend"),
            "مبرمج": ("Senior Software Engineer", "backend"),
            "ai": ("AI/ML Engineer", "ai"),
            "ذكاء": ("AI/ML Engineer", "ai"),
            "data": ("Data Engineer", "data"),
            "بيانات": ("Data Engineer", "data"),
            "frontend": ("Senior Frontend Developer", "fullstack"),
            "واجهة": ("Senior Frontend Developer", "fullstack"),
            "lead": ("Technical Lead", "ai"),
            "قائد": ("Technical Lead", "ai"),
            "manager": ("Engineering Manager", "backend"),
            "مدير": ("Engineering Manager", "backend"),
        }

        detected_role = "Senior Software Engineer"
        for keyword, (role, _) in mappings.items():
            if keyword in vague_input.lower():
                detected_role = role
                break

        jd = self.sourcing.generate_dynamic_jd(detected_role, vague_input)
        reqs = jd.get("requirements", {})

        mock = (
            f"📝 [JD SUGGESTER — AUTO-GENERATED]\n\n"
            f"## الوصف الوظيفي المقترح\n\n"
            f"**المدخل الأصلي:** \"{vague_input}\"\n\n"
            f"### ✅ التحقق المسبق\n"
            f"- **القسم:** {department}\n"
            f"- **الميزانية:** {budget['hiring_budget_sar']:,.0f} ر.س ✅\n"
            f"- **الوظائف المتاحة:** {budget['open_positions']} ✅\n"
        )
        if quota:
            mock += (
                f"- **نسبة السعودة:** {quota.get('current_saudization_pct', '?')}% "
                f"({quota.get('nitaqat_band', '?')}) "
                f"{'🔴 قيد إلزامي' if quota.get('must_hire_local') else '🟢 لا قيود'}\n"
            )
        mock += (
            f"\n"
            f"---\n\n"
            f"### 📋 التفاصيل\n\n"
            f"| البند | التفاصيل |\n"
            f"|-------|----------|\n"
            f"| المسمى المقترح | {jd['title']} |\n"
            f"| المجال | {jd['domain']} |\n"
            f"| المستوى | {jd['seniority']} |\n"
            f"| الخبرة المطلوبة | ≥{reqs['min_experience_years']} سنوات |\n"
            f"| الراتب المقترح | {jd['compensation']['salary_range_sar']} ر.س |\n\n"
            f"### 🔧 المهارات التقنية المطلوبة\n"
        )
        for s in reqs.get("required_skills", []):
            mock += f"- ✅ {s}\n"

        mock += f"\n### 🌟 المهارات المفضلة\n"
        for s in reqs.get("preferred_skills", [])[:4]:
            mock += f"- 💡 {s}\n"

        mock += (
            f"\n### 📊 مؤشرات الأداء المقترحة (KPIs)\n"
            f"- إنجاز المشاريع في الوقت المحدد (≥90%)\n"
            f"- جودة الكود (Code Review Pass Rate ≥85%)\n"
            f"- مساهمات مفتوحة المصدر (≥2 شهرياً)\n"
            f"- رضا الفريق (Team NPS ≥70)\n\n"
            f"### 🤝 المهارات الشخصية\n"
            f"- القيادة والتوجيه\n"
            f"- التواصل الفعال\n"
            f"- حل المشكلات\n"
            f"- العمل تحت الضغط\n"
        )
        if localization_constraint:
            mock += f"\n### 🔴 قيود إلزامية (نطاقات)\n{localization_constraint}\n"
        mock += (
            f"\n---\n"
            f"_يمكنك تعديل هذا الوصف الوظيفي ثم إطلاق الاستقطاب التلقائي._"
        )
        return self._success(task_id, mock)
