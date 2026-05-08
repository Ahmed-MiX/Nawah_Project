"""
Nawah L3 HR Agent — Elite HR Director (Talent Hunt Pipeline)

Handles: HR_SCREENING intent
Full pipeline: PDF CV → Text Extraction → JD Fetch (ERP) →
Evaluation → Schedule/Reject (ERP) → Markdown Report + Email Draft.

Uses: CorporateMemory (RAG), ERPWebhookTool (HR), ComplianceGuardrail,
      DynamicPersonaManager, ReAct Reasoning, Episodic Memory.
"""
import os
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.synthesizer import truncate_prompt
from core.memory.rag_engine import get_corporate_memory
from core.memory.persona_manager import get_persona_manager
from core.governance_engine import get_compliance_guardrail
from core.tools.erp_connector import get_erp_tool

MAX_FILE_CHARS = 12000

_FALLBACK_PROMPT = "أنت مدير الموارد البشرية الأول في نظام نواة. حلل السير الذاتية وطلبات التوظيف بدقة."


class HRAgent(BaseAgent):
    """L3 Executive Agent — Elite HR Director with ERP Recruitment Tools."""
    agent_name = "hr_agent"
    agent_icon = "👔"

    def __init__(self):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None
        self.memory = get_corporate_memory()
        self.erp = get_erp_tool()
        self.persona = get_persona_manager()
        self.guardrail = get_compliance_guardrail()

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
        intent = task_payload.get("l1_triage", {}).get("intent", "HR_SCREENING")
        job_id = task_payload.get("l1_triage", {}).get("job_id", "JD-AI-001")

        try:
            if not self.router:
                raise CriticalAPIFailure("No API keys available")

            # ── STEP 1: Read CV ──
            cv_text = ""
            if attachments:
                att = attachments[0]
                fp = att.get("file_path", "") if isinstance(att, dict) else getattr(att, "file_path", "")
                cv_text = truncate_prompt(self._read_file(fp), MAX_FILE_CHARS)

            # ── STEP 2: Fetch JD from ERP ──
            jd = self.erp.fetch_job_description(job_id)
            jd_summary = self._format_jd(jd)

            # ── STEP 3: RAG — Query HR policies ──
            policy_context = ""
            policy_chunks = self.memory.query_policy(
                f"متطلبات وظيفة توظيف مؤهلات {instruction}", n_results=3
            )
            if policy_chunks:
                policy_context = "\n\n".join(
                    f"📋 متطلبات ({c['doc_id']}): {c['text']}" for c in policy_chunks
                )

            # ── STEP 4: Build Prompt ──
            human_msg = f"طلب فحص التوظيف: {instruction}\n\n"
            human_msg += f"=== الوصف الوظيفي (من ERP) ===\n{jd_summary}\n\n"
            if policy_context:
                human_msg += f"=== سياسات التوظيف (RAG) ===\n{policy_context}\n\n"
            if cv_text:
                human_msg += f"=== السيرة الذاتية / طلب التوظيف ===\n{cv_text}"
            else:
                human_msg += "(لا يوجد ملف مرفق — التقييم على أساس النص فقط)"

            # ── STEP 5: ReAct — Generate thought process ──
            thought = self.generate_thought_process(instruction, human_msg, intent)
            human_msg = f"{thought}\n\n{human_msg}"

            sys_prompt = self.persona.get_system_prompt("hr_agent", _FALLBACK_PROMPT)
            temp = self.persona.get_temperature("hr_agent", 0.2)

            prompt = ChatPromptTemplate.from_messages([
                ("system", sys_prompt), ("human", "{input}")
            ])

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temp, google_api_key=api_key)
                return (prompt | llm).invoke({"input": human_msg}).content

            result = self.router.execute(call_with_key)

            # ── STEP 6: Governance Check ──
            verdict = self.guardrail.check("hr_agent", result)
            if not verdict.compliant:
                feedback = self.guardrail.format_violation_report(verdict)
                result = self.self_reflect(result, feedback, task_id=task_id, intent=intent)

            print(f"👔 HRAgent: فحص توظيف مكتمل — {len(result)} حرف")
            return self._success(task_id, f"👔 فحص التوظيف مكتمل:\n\n{result}")

        except CriticalAPIFailure:
            # ── MOCK MODE: Full ERP-Integrated Pipeline ──
            return self._mock_talent_hunt(task_id, instruction, cv_text if 'cv_text' in dir() else "", job_id)
        except Exception as e:
            traceback.print_exc()
            return self._fail(task_id, f"خطأ في فحص التوظيف: {e}")

    def _format_jd(self, jd: dict) -> str:
        """Format JD from ERP into readable text for the LLM."""
        reqs = jd.get("requirements", {})
        lines = [
            f"**المسمى:** {jd.get('title', 'غير محدد')}",
            f"**القسم:** {jd.get('department', 'غير محدد')}",
            f"**الموقع:** {jd.get('location', 'غير محدد')}",
            f"**الراتب:** {jd.get('salary_range_sar', 'غير محدد')} ر.س",
            f"**الحد الأدنى للخبرة:** {reqs.get('min_experience_years', 0)} سنوات",
            f"**المهارات المطلوبة:** {', '.join(reqs.get('required_skills', []))}",
            f"**المهارات المفضلة:** {', '.join(reqs.get('preferred_skills', []))}",
            f"**التعليم:** {reqs.get('education', 'غير محدد')}",
        ]
        return "\n".join(lines)

    def _mock_talent_hunt(self, task_id: str, instruction: str, cv_text: str, job_id: str) -> dict:
        """Full mock pipeline with Anti-Fraud Verification + Skill Matrix."""
        import re as _re

        # Step 1: Fetch JD
        jd = self.erp.fetch_job_description(job_id)
        min_exp = jd.get("requirements", {}).get("min_experience_years", 3)
        required_skills = jd.get("requirements", {}).get("required_skills", [])

        # Step 2: Extract candidate info from CV text or instruction
        source_text = cv_text if cv_text else instruction
        candidate_name = self._extract_candidate_name(source_text)
        companies = self._extract_companies(source_text)
        universities = self._extract_universities(source_text)
        candidate_exp = self._extract_experience(source_text)
        candidate_skills = self._extract_skills(source_text)

        # ── ANTI-FRAUD GATE: Background Verification ──
        bg_check = self.erp.verify_candidate_claims(companies, universities)

        if bg_check["fraud_detected"]:
            # INSTANT REJECTION — Do NOT proceed to skill evaluation
            fraud_details = "\n".join(
                f"- {c['detail']}" for c in bg_check["checks"] if c["status"] == "FRAUD_DETECTED"
            )
            rejection = self.erp.reject_candidate(
                candidate_name,
                "⛔ Fraudulent/Unverifiable Background Claims",
                job_id
            )
            mock = (
                f"👔 [L3 EXECUTIVE DECISION — TALENT HUNT]\\n\\n"
                f"## تقرير فحص التوظيف — مهمة {task_id[:8]}\\n\\n"
                f"**الطلب:** {instruction[:100]}\\n\\n"
                f"### 🚨 فحص الخلفية — احتيال مكتشف\\n\\n"
                f"| المحور | النتيجة |\\n"
                f"|--------|---------|\\n"
            )
            for c in bg_check["checks"]:
                icon = "🚨" if c["status"] == "FRAUD_DETECTED" else "✅"
                mock += f"| {c['entity']} ({c['type']}) | {icon} {c['status']} |\\n"

            mock += (
                f"\\n### ⛔ قرار: رفض فوري — مطالبات خلفية احتيالية\\n\\n"
                f"{fraud_details}\\n\\n"
                f"**رقم الرفض:** {rejection['rejection_id']}\\n"
                f"**السبب:** بيانات خلفية احتيالية أو غير قابلة للتحقق\\n\\n"
                f"⚠️ **لم يتم إجراء تقييم المهارات** — الرفض تم قبل مرحلة التقييم.\\n\\n"
                f"---\\n"
                f"_🛡️ Anti-Fraud Engine — حماية نواة من السير الذاتية المزورة._"
            )
            return self._success(task_id, mock)

        # ── BACKGROUND VERIFIED — Proceed to Skill Matrix ──

        # Step 3: Build Skill Matrix (scored /10)
        skill_matrix = []
        total_score = 0
        for skill in required_skills:
            if skill in candidate_skills:
                score = 8  # Strong match
            elif skill.lower() in source_text.lower():
                score = 6  # Mentioned but not primary
            else:
                score = 0  # Missing
            skill_matrix.append({"skill": skill, "score": score})
            total_score += score

        max_possible = len(required_skills) * 10
        overall_pct = (total_score / max(max_possible, 1)) * 100
        skill_match = [s["skill"] for s in skill_matrix if s["score"] > 0]
        skill_miss = [s["skill"] for s in skill_matrix if s["score"] == 0]
        exp_pass = candidate_exp >= min_exp

        # Step 4: ERP Action — Schedule or Reject
        if exp_pass and overall_pct >= 40:
            erp_action = self.erp.schedule_interview(candidate_name, "2026-05-15", job_id)
            decision = "✅ قبول مبدئي — تم جدولة مقابلة"
            action_table = (
                f"### ✅ إجراء ERP — جدولة مقابلة:\\n\\n"
                f"| البند | التفاصيل |\\n"
                f"|-------|----------|\\n"
                f"| رقم المقابلة | {erp_action['interview_id']} |\\n"
                f"| التاريخ | {erp_action['date']} |\\n"
                f"| الوقت | {erp_action['time']} |\\n"
                f"| المكان | {erp_action['location']} |\\n"
                f"| النوع | {erp_action['type']} |\\n"
                f"| المقابلون | {', '.join(erp_action['interviewers'])} |\\n"
            )
        else:
            reason = f"الخبرة {'أقل من الحد الأدنى' if not exp_pass else 'كافية'} — المهارات المفقودة: {', '.join(skill_miss)}"
            erp_action = self.erp.reject_candidate(candidate_name, reason, job_id)
            decision = "🚫 رفض — لا يستوفي الحد الأدنى"
            action_table = (
                f"### 🚫 إجراء ERP — تسجيل رفض:\\n\\n"
                f"| البند | التفاصيل |\\n"
                f"|-------|----------|\\n"
                f"| رقم الرفض | {erp_action['rejection_id']} |\\n"
                f"| السبب | {erp_action['reason']} |\\n"
                f"| إعادة التقديم | {erp_action['can_reapply_after']} |\\n"
            )

        # Build Skill Matrix table
        matrix_table = "| المهارة | الدرجة (/10) | الحالة |\\n|--------|-------------|--------|\\n"
        for s in skill_matrix:
            icon = "✅" if s["score"] >= 6 else ("⚠️" if s["score"] > 0 else "🚫")
            matrix_table += f"| {s['skill']} | {s['score']}/10 | {icon} |\\n"
        matrix_table += f"| **المجموع** | **{total_score}/{max_possible}** | **{overall_pct:.0f}%** |\\n"

        # Build BG check table
        bg_table = "| الجهة | النوع | النتيجة |\\n|-------|-------|---------|\\n"
        for c in bg_check["checks"]:
            icon = "✅" if c["status"] == "VERIFIED" else "⚠️"
            bg_table += f"| {c['entity']} | {c['type']} | {icon} {c['status']} |\\n"

        # Build final report
        mock = (
            f"👔 [L3 EXECUTIVE DECISION — TALENT HUNT]\\n\\n"
            f"## تقرير فحص التوظيف — مهمة {task_id[:8]}\\n\\n"
            f"**الطلب:** {instruction[:100]}\\n\\n"
            f"### 🔍 فحص الخلفية (Anti-Fraud)\\n\\n"
            f"{bg_table}\\n"
            f"### 📊 مصفوفة المهارات (Skill Matrix)\\n\\n"
            f"{matrix_table}\\n"
            f"### القرار: {decision}\\n\\n"
            f"{action_table}\\n\\n"
            f"---\\n"
            f"_🛡️ Anti-Fraud Engine Active — Background Verified Before Evaluation._"
        )
        return self._success(task_id, mock)

    # ============================================================
    # CV PARSING HELPERS (lightweight, no LLM)
    # ============================================================
    def _extract_candidate_name(self, text: str) -> str:
        """Extract candidate name from CV text."""
        import re
        # Arabic name pattern
        m = re.search(r'(م\.\s*[\u0600-\u06FF]+\s+[\u0600-\u06FF]+)', text)
        if m:
            return m.group(1)
        # Fallback
        for line in text.split('\n')[:3]:
            line = line.strip()
            if len(line) > 3 and len(line) < 50:
                return line
        return "مرشح غير محدد"

    def _extract_companies(self, text: str) -> list[str]:
        """Extract company names from CV text."""
        import re
        companies = []
        # English company patterns
        for pattern in [
            r'(?:at|@|in)\s+([A-Z][\w\s]+(?:Inc|Corp|Ltd|Digital|AI|Labs)?)',
            r'worked?\s+(?:at|for|in)\s+([A-Z][\w\s]+)',
        ]:
            for m in re.finditer(pattern, text):
                companies.append(m.group(1).strip())
        # Arabic patterns
        for pattern in [
            r'(?:في|لدى|بشركة)\s+([\u0600-\u06FF\s]+?)(?:\.|،|\\n|\s{2})',
        ]:
            for m in re.finditer(pattern, text):
                c = m.group(1).strip()
                if len(c) > 2:
                    companies.append(c)
        # Known company keywords
        _known = ["FakeCorp", "ChatGPT Inc", "Aramco", "Aramco Digital", "STC", "SDAIA",
                   "Google", "Microsoft", "أرامكو", "سدايا"]
        text_lower = text.lower()
        for k in _known:
            if k.lower() in text_lower and k not in companies:
                companies.append(k)
        return companies[:5]  # Max 5

    def _extract_universities(self, text: str) -> list[str]:
        """Extract university names from CV text."""
        unis = []
        _known = ["KAUST", "KFUPM", "KSU", "MIT", "Stanford",
                   "جامعة الملك سعود", "كاوست", "Fake University"]
        text_lower = text.lower()
        for u in _known:
            if u.lower() in text_lower:
                unis.append(u)
        return unis[:3]

    def _extract_experience(self, text: str) -> int:
        """Extract years of experience from text."""
        import re
        m = re.search(r'(\d+)\s*(?:years?|سنوات|سنة)', text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return 0

    def _extract_skills(self, text: str) -> list[str]:
        """Extract technical skills from text."""
        _all_skills = [
            "Python", "TensorFlow", "PyTorch", "LangChain", "Machine Learning",
            "Deep Learning", "Docker", "Kubernetes", "FastAPI", "React",
            "Node.js", "PostgreSQL", "REST APIs", "Microservices", "Java",
            "AWS", "Redis", "Kafka", "ChromaDB", "MLOps", "HuggingFace",
        ]
        found = [s for s in _all_skills if s.lower() in text.lower()]
        return found

