"""
Nawah Sourcing Tools v2.0 — Dynamic JD + Dual-Sourcing Strategy

Advanced HR sourcing capabilities:
  - Dynamic Job Description generation based on company context
  - Dual-Sourcing: Internal ATS Archive FIRST → External (LinkedIn/GitHub) ONLY if needed
  - Backwards-compatible: scan_professional_networks delegates to dual-sourcing
"""
import re
import random
from datetime import datetime

# Try importing Tavily for real web search
try:
    from langchain_tavily import TavilySearch
    import os
    _tavily_key = os.getenv("TAVILY_API_KEY", "")
    TAVILY_AVAILABLE = bool(_tavily_key)
except ImportError:
    TAVILY_AVAILABLE = False


# ============================================================
# DYNAMIC SKILLS & REQUIREMENTS DATABASE
# ============================================================
_TECH_DOMAINS = {
    "ai": {
        "core": ["Python", "TensorFlow", "PyTorch", "LangChain", "Machine Learning", "Deep Learning"],
        "preferred": ["ChromaDB", "FastAPI", "Docker", "Kubernetes", "MLOps", "HuggingFace"],
        "leadership": ["Team Leadership", "System Design", "Architecture", "Mentoring", "Agile"],
    },
    "backend": {
        "core": ["Python", "Java", "Node.js", "PostgreSQL", "REST APIs", "Microservices"],
        "preferred": ["Redis", "Kafka", "gRPC", "GraphQL", "AWS", "Terraform"],
        "leadership": ["System Architecture", "Code Review", "CI/CD", "DevOps", "Mentoring"],
    },
    "fullstack": {
        "core": ["React", "TypeScript", "Node.js", "PostgreSQL", "REST APIs", "Git"],
        "preferred": ["Next.js", "Docker", "Redis", "Tailwind CSS", "Vite"],
        "leadership": ["UI/UX Sense", "Product Thinking", "Agile", "Team Leadership"],
    },
    "data": {
        "core": ["Python", "SQL", "Pandas", "Apache Spark", "ETL", "Data Modeling"],
        "preferred": ["Airflow", "dbt", "Snowflake", "Power BI", "Kafka"],
        "leadership": ["Data Strategy", "Governance", "Team Leadership", "Stakeholder Management"],
    },
}

_URGENCY_MAP = {
    "critical": {"exp_multiplier": 0.7, "salary_boost": 1.3, "flexibility": "عمل عن بعد كامل متاح"},
    "high": {"exp_multiplier": 0.85, "salary_boost": 1.15, "flexibility": "نظام هجين مرن"},
    "normal": {"exp_multiplier": 1.0, "salary_boost": 1.0, "flexibility": "حضوري مع مرونة"},
}

# ============================================================
# INTERNAL ATS (Applicant Tracking System) MOCK DATABASE
# ============================================================
_INTERNAL_ATS = [
    {
        "name": "م. سلطان العمري",
        "headline": "AI Engineer (Internal) | Python | LangChain | 5 Years",
        "summary": "موظف سابق في قسم التقنية. خبرة 5 سنوات في Python وتطوير أنظمة ML. "
                   "ترك الشركة قبل 8 أشهر لظروف شخصية. تقييمه الداخلي: ممتاز.",
        "url": "internal://ats/sultan-alomari",
        "platform": "Internal ATS",
        "match_score": 93,
        "source": "internal",
        "previous_rating": "A",
    },
    {
        "name": "م. لمى الحربي",
        "headline": "Data Scientist (Internal Applicant) | ML | Pandas | 4 Years",
        "summary": "تقدمت لوظيفة سابقة قبل 6 أشهر ولم تُوظف لعدم توفر ميزانية. "
                   "خبرة 4 سنوات في تحليل البيانات وتعلم الآلة. سعودية.",
        "url": "internal://ats/lama-alharbi",
        "platform": "Internal ATS",
        "match_score": 88,
        "source": "internal",
        "previous_rating": "B+",
    },
    {
        "name": "م. عبدالرحمن السبيعي",
        "headline": "Full-Stack Developer (Internal Pool) | React | Node | 3 Years",
        "summary": "متدرب سابق تحول لدوام جزئي. خبرة 3 سنوات في React و Node.js. "
                   "أنهى مشروع التحول الرقمي الداخلي بنجاح. سعودي.",
        "url": "internal://ats/abdulrahman-alsubaie",
        "platform": "Internal ATS",
        "match_score": 80,
        "source": "internal",
        "previous_rating": "B",
    },
    {
        "name": "م. هدى القرني",
        "headline": "Backend Engineer (Internal Archive) | Java | Spring | Python | 6 Years",
        "summary": "مهندسة خلفية بخبرة 6 سنوات. تقدمت لعدة وظائف تقنية. "
                   "حاصلة على AWS Solutions Architect. خبرة في Python و AI automation. سعودية.",
        "url": "internal://ats/huda-alqarni",
        "platform": "Internal ATS",
        "match_score": 85,
        "source": "internal",
        "previous_rating": "A-",
    },
    {
        "name": "م. تركي الغامدي",
        "headline": "AI/ML Engineer (Internal Pool) | Python | LangChain | TensorFlow | 4 Years",
        "summary": "مهندس ذكاء اصطناعي سابق في قسم الابتكار. خبرة 4 سنوات في Python و LangChain. "
                   "ترك لإكمال الماجستير وعاد للتقديم. سعودي. تقييم ممتاز.",
        "url": "internal://ats/turki-alghamdi",
        "platform": "Internal ATS",
        "match_score": 91,
        "source": "internal",
        "previous_rating": "A",
    },
    {
        "name": "م. سارة الزهراني",
        "headline": "NLP Researcher (Internal Archive) | Python | AI | Deep Learning | 5 Years",
        "summary": "باحثة في معالجة اللغة الطبيعية. خبرة 5 سنوات في Python و AI و LangChain. "
                   "نشرت 3 أوراق بحثية. تقدمت لوظيفة AI Lead سابقاً. سعودية.",
        "url": "internal://ats/sara-alzahrani",
        "platform": "Internal ATS",
        "match_score": 90,
        "source": "internal",
        "previous_rating": "A",
    },
    {
        "name": "م. ماجد الدوسري",
        "headline": "DevOps + AI Ops (Internal Pool) | Python | Docker | MLOps | 3 Years",
        "summary": "مهندس بنية تحتية لأنظمة الذكاء الاصطناعي. خبرة في Python و MLOps و Kubernetes. "
                   "ساهم في بناء بنية CI/CD لمشاريع AI داخلية. سعودي.",
        "url": "internal://ats/majed-aldossari",
        "platform": "Internal ATS",
        "match_score": 82,
        "source": "internal",
        "previous_rating": "B+",
    },
]


class SourcingTools:
    """Advanced HR sourcing tools with Dual-Sourcing Strategy."""

    def __init__(self):
        print("🔍 SourcingTools: أدوات الاستقطاب جاهزة (Dual-Sourcing v2.0)")

    def generate_dynamic_jd(self, role_title: str, company_context: str) -> dict:
        """Generate a Dynamic Job Description based on real-time company context."""
        title_lower = role_title.lower()
        domain = "ai"
        if any(k in title_lower for k in ["backend", "server", "api"]):
            domain = "backend"
        elif any(k in title_lower for k in ["fullstack", "frontend", "react"]):
            domain = "fullstack"
        elif any(k in title_lower for k in ["data", "analytics", "bi"]):
            domain = "data"

        ctx_lower = company_context.lower()
        urgency = "normal"
        if any(k in ctx_lower for k in ["urgent", "crisis", "عاجل", "أزمة", "critical"]):
            urgency = "critical"
        elif any(k in ctx_lower for k in ["fast", "growing", "نمو", "سريع", "high priority"]):
            urgency = "high"

        is_senior = any(k in title_lower for k in ["senior", "lead", "head", "director", "كبير", "رئيس"])
        is_executive = any(k in title_lower for k in ["vp", "director", "head", "cto", "مدير"])
        high_budget = any(k in ctx_lower for k in ["high budget", "ميزانية عالية", "competitive", "premium"])

        urgency_config = _URGENCY_MAP[urgency]
        skills = _TECH_DOMAINS[domain]

        base_exp = 7 if is_executive else (5 if is_senior else 3)
        min_exp = max(2, int(base_exp * urgency_config["exp_multiplier"]))

        base_salary_min = 20000 if is_executive else (15000 if is_senior else 10000)
        base_salary_max = 45000 if is_executive else (30000 if is_senior else 20000)
        salary_min = int(base_salary_min * urgency_config["salary_boost"])
        salary_max = int(base_salary_max * urgency_config["salary_boost"])

        required_skills = skills["core"][:4] if urgency == "critical" else skills["core"]
        if is_senior or is_executive:
            required_skills += skills["leadership"][:2]

        jd = {
            "action": "DYNAMIC_JD_GENERATED",
            "title": role_title,
            "domain": domain,
            "urgency": urgency,
            "seniority": "executive" if is_executive else ("senior" if is_senior else "mid"),
            "company_context_summary": company_context[:200],
            "requirements": {
                "min_experience_years": min_exp,
                "required_skills": required_skills,
                "preferred_skills": skills["preferred"],
                "leadership_skills": skills["leadership"] if is_senior else [],
                "education": "بكالوريوس أو ماجستير في علوم الحاسب أو ما يعادلها",
                "certifications_preferred": True,
            },
            "compensation": {
                "salary_range_sar": f"{salary_min:,} - {salary_max:,}",
                "signing_bonus": high_budget,
                "equity": is_executive and high_budget,
            },
            "work_arrangement": urgency_config["flexibility"],
            "keywords": required_skills[:5] + [role_title, domain],
            "timestamp": datetime.now().isoformat(),
        }

        print(
            f"🔍 DynamicJD: {role_title} | {domain} | {urgency} | "
            f"exp≥{min_exp}y | {salary_min:,}-{salary_max:,} SAR"
        )
        return jd

    # ============================================================
    # DUAL-SOURCING STRATEGY (Core Innovation)
    # ============================================================
    def execute_dual_sourcing_strategy(
        self, keywords: list[str], max_results: int = 3,
        must_be_local: bool = False, source: str = "AUTO"
    ) -> dict:
        """
        Dual-Sourcing: Internal ATS Archive FIRST → External ONLY if needed.

        Source modes (UI-dictated):
          - AUTO: Internal first, external if <2 internal
          - EMAIL_ONLY: Only scan company inbox (NO external)
          - LINKEDIN: Only external networks
          - BOTH: Internal + External always

        Args:
            keywords: Skills and role keywords to search for.
            max_results: Number of profiles to return.
            must_be_local: If True, prioritize local (Saudi) candidates.

        Returns:
            Dict with internal_candidates, external_candidates,
            sourcing_strategy used, and cost_savings.
        """
        source = source.upper()

        if source == "EMAIL_ONLY":
            # UI says EMAIL_ONLY — respect it absolutely
            internal = self.scan_company_inbox(keywords, max_results)
            print(f"🔍 EMAIL_ONLY: {len(internal)} مرشحين من البريد")
            return {
                "strategy": "EMAIL_ONLY",
                "internal_candidates": internal,
                "external_candidates": [],
                "external_search_triggered": False,
                "final_candidates": internal[:max_results],
                "cost_savings": "~5,000 ر.س",
                "total_found": len(internal),
            }

        if source == "LINKEDIN":
            # UI says external only
            external = self.scan_professional_networks(keywords, max_results)
            print(f"🔍 LINKEDIN_ONLY: {len(external)} مرشحين خارجيين")
            return {
                "strategy": "LINKEDIN_ONLY",
                "internal_candidates": [],
                "external_candidates": external,
                "external_search_triggered": True,
                "final_candidates": external[:max_results],
                "cost_savings": "0 ر.س",
                "total_found": len(external),
            }

        # AUTO or BOTH: Internal ATS first
        internal = self._search_internal_ats(keywords, must_be_local)
        print(f"🔍 ATS-داخلي: {len(internal)} مرشحين في الأرشيف الداخلي")

        external = []
        strategy = "INTERNAL_ONLY"
        external_triggered = False

        # Go external if BOTH, or AUTO with <2 internal
        if source == "BOTH" or (source == "AUTO" and len(internal) < 2):
            if source == "AUTO":
                print(f"🔍 ATS-داخلي: أقل من 2 مرشح — تفعيل البحث الخارجي")
            external = self.scan_professional_networks(keywords, max_results)
            strategy = "DUAL_SOURCING"
            external_triggered = True
        else:
            print(f"🔍 ATS-داخلي: ≥2 مرشح داخلي — لا حاجة للبحث الخارجي 💰")

        all_candidates = internal + external
        all_candidates.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        final = all_candidates[:max_results]

        return {
            "strategy": strategy,
            "internal_candidates": internal,
            "external_candidates": external,
            "external_search_triggered": external_triggered,
            "final_candidates": final,
            "cost_savings": "~3,000 ر.س" if not external_triggered else "0 ر.س",
            "total_found": len(all_candidates),
        }

    def _search_internal_ats(self, keywords: list[str], must_be_local: bool = False) -> list[dict]:
        """Search the internal ATS archive for matching candidates."""
        results = []
        for candidate in _INTERNAL_ATS:
            # Score based on keyword match
            text = f"{candidate['headline']} {candidate['summary']}".lower()
            hits = sum(1 for k in keywords if k.lower() in text)
            if hits > 0:
                c = dict(candidate)  # Copy
                c["match_score"] = min(99, c["match_score"] + hits * 2)
                results.append(c)

        # Filter for local candidates if required
        if must_be_local:
            results = [c for c in results if "سعودي" in c.get("summary", "")]

        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results

    # ============================================================
    # EXTERNAL SEARCH (LinkedIn/GitHub)
    # ============================================================
    def scan_professional_networks(self, keywords: list[str], max_results: int = 3) -> list[dict]:
        """
        Scan LinkedIn/GitHub for matching talent using Tavily search or mock.
        Now part of the dual-sourcing strategy (called only when needed).
        """
        query = " ".join(keywords[:5]) + " site:linkedin.com OR site:github.com"

        if TAVILY_AVAILABLE:
            try:
                return self._tavily_scan(query, max_results)
            except Exception as e:
                print(f"⚠️ Tavily scan failed: {e} — switching to mock")

        return self._mock_external_scan(keywords, max_results)

    def _tavily_scan(self, query: str, max_results: int) -> list[dict]:
        """Real Tavily-powered professional network scan."""
        tool = TavilySearch(max_results=max_results * 2)
        raw_results = tool.invoke({"query": query})

        profiles = []
        if isinstance(raw_results, list):
            for r in raw_results[:max_results]:
                url = r.get("url", "")
                if "linkedin" in url or "github" in url:
                    profiles.append({
                        "name": self._extract_name(r.get("content", "")),
                        "headline": r.get("content", "")[:120],
                        "summary": r.get("content", "")[:300],
                        "url": url,
                        "platform": "LinkedIn" if "linkedin" in url else "GitHub",
                        "match_score": random.randint(75, 95),
                        "source": "external",
                    })

        if not profiles:
            profiles = self._mock_external_scan(query.split()[:3], max_results)

        print(f"🔍 NetworkScan (Tavily): {len(profiles)} ملفات شخصية")
        return profiles

    def _mock_external_scan(self, keywords: list[str], max_results: int) -> list[dict]:
        """Sophisticated mock scan returning realistic Saudi/MENA profiles."""
        mock_profiles = [
            {
                "name": "م. خالد الشهري",
                "headline": "Senior AI Engineer @ Aramco Digital | Python | LangChain | MLOps",
                "summary": "مهندس ذكاء اصطناعي بخبرة 6 سنوات في بناء أنظمة ML للقطاع النفطي. "
                           "قاد فريقاً من 8 مهندسين في مشروع أتمتة خطوط الإنتاج. "
                           "حاصل على ماجستير من KAUST في تعلم الآلة.",
                "url": "https://linkedin.com/in/khalid-alshehri-ai",
                "platform": "LinkedIn",
                "match_score": 92,
                "source": "external",
            },
            {
                "name": "د. نورة القحطاني",
                "headline": "Lead ML Researcher @ SDAIA | PhD NLP | Former Google AI",
                "summary": "باحثة في معالجة اللغة الطبيعية العربية بخبرة 8 سنوات. "
                           "نشرت 12 ورقة بحثية في مؤتمرات ACL و NeurIPS. "
                           "قادت مشروع النموذج اللغوي العربي الكبير في سدايا.",
                "url": "https://linkedin.com/in/noura-alqahtani-ml",
                "platform": "LinkedIn",
                "match_score": 95,
                "source": "external",
            },
            {
                "name": "عبدالله المالكي",
                "headline": "Full-Stack AI Developer | Open Source Contributor | 200+ GitHub Stars",
                "summary": "مطور أنظمة ذكاء اصطناعي بخبرة 4 سنوات. مساهم في مشاريع مفتوحة المصدر "
                           "على GitHub مع أكثر من 200 نجمة. متخصص في LangChain و ChromaDB و FastAPI.",
                "url": "https://github.com/abd-almalki",
                "platform": "GitHub",
                "match_score": 87,
                "source": "external",
            },
            {
                "name": "م. ريم الدوسري",
                "headline": "Data Science Lead @ STC | AWS ML Certified | Speaker",
                "summary": "قائدة فريق علم البيانات في STC بخبرة 5 سنوات. "
                           "حاصلة على شهادة AWS Machine Learning Specialty. "
                           "متحدثة في مؤتمرات تقنية محلية ودولية.",
                "url": "https://linkedin.com/in/reem-aldossari-ds",
                "platform": "LinkedIn",
                "match_score": 88,
                "source": "external",
            },
            {
                "name": "م. فيصل الحربي",
                "headline": "Backend Architect @ Noon | Microservices | Kubernetes | 10+ Years",
                "summary": "مهندس معماري للأنظمة الخلفية بخبرة 10 سنوات في بناء أنظمة عالية التحمل. "
                           "قاد هجرة نون إلى بنية الخدمات المصغرة. خبير في Kubernetes و AWS.",
                "url": "https://linkedin.com/in/faisal-alharbi-arch",
                "platform": "LinkedIn",
                "match_score": 83,
                "source": "external",
            },
        ]

        for p in mock_profiles:
            keyword_hits = sum(1 for k in keywords if k.lower() in p["headline"].lower() or k.lower() in p["summary"].lower())
            p["match_score"] = min(99, p["match_score"] + keyword_hits * 3)

        mock_profiles.sort(key=lambda x: x["match_score"], reverse=True)
        results = mock_profiles[:max_results]

        print(f"🔍 NetworkScan (External): {len(results)} ملفات شخصية — أفضل تطابق: {results[0]['match_score']}%")
        return results

    def _extract_name(self, content: str) -> str:
        words = content.split()[:5]
        return " ".join(words[:3]) if words else "مرشح غير محدد"

    # ============================================================
    # EMAIL INBOX SOURCING
    # ============================================================
    def scan_company_inbox(self, keywords: list[str], max_results: int = 5) -> list[dict]:
        """
        Mock scan of company email inbox for CV attachments.
        Simulates fetching recent job application emails.
        """
        _inbox_cvs = [
            {
                "name": "م. علي العمري",
                "headline": "Python Developer | AI | 4 Years (Email Applicant)",
                "summary": "تقدم عبر البريد الإلكتروني. خبرة 4 سنوات في Python و LangChain. سعودي.",
                "url": "email://inbox/ali-alomari-cv.pdf",
                "platform": "Email Inbox",
                "match_score": 85,
                "source": "email",
            },
            {
                "name": "م. منيرة الشمري",
                "headline": "Data Analyst | SQL | Python | 3 Years (Email Applicant)",
                "summary": "تقدمت عبر البريد. خبرة 3 سنوات في تحليل البيانات. سعودية.",
                "url": "email://inbox/muneera-cv.pdf",
                "platform": "Email Inbox",
                "match_score": 78,
                "source": "email",
            },
            {
                "name": "م. عبدالله القحطاني",
                "headline": "ML Engineer | TensorFlow | Python | 5 Years (Email Applicant)",
                "summary": "تقدم عبر البريد. خبرة 5 سنوات في ML و Python. سعودي.",
                "url": "email://inbox/abdullah-alqahtani-cv.pdf",
                "platform": "Email Inbox",
                "match_score": 88,
                "source": "email",
            },
        ]

        # Score by keyword match
        for c in _inbox_cvs:
            text = f"{c['headline']} {c['summary']}".lower()
            hits = sum(1 for k in keywords if k.lower() in text)
            c["match_score"] = min(99, c["match_score"] + hits * 3)

        _inbox_cvs.sort(key=lambda x: x["match_score"], reverse=True)
        results = _inbox_cvs[:max_results]
        print(f"📧 EmailInbox: {len(results)} مرشحين من البريد الإلكتروني")
        return results


# Singleton
_sourcing_tools = None

def get_sourcing_tools() -> SourcingTools:
    global _sourcing_tools
    if _sourcing_tools is None:
        _sourcing_tools = SourcingTools()
    return _sourcing_tools
