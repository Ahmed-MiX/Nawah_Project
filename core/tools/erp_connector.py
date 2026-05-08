"""
Nawah ERP Webhook Tool — Simulated Enterprise Resource Planning Connector

Provides mock ERP operations for L3 Executive Agents to demonstrate
Hyper-Automation capabilities where Nawah actually modifies company data.

In production, these methods would call real ERP APIs (SAP, Oracle, Odoo, etc.)
"""
import uuid
import random
from datetime import datetime


class ERPWebhookTool:
    """
    Simulated ERP connector for Nawah L3 Hyper-Automation.

    Methods simulate real corporate actions:
        - Inventory checks
        - Purchase order issuance
        - Customer refund processing
        - Invoice generation
    """

    def __init__(self):
        self.connected = True
        print("🏭 ERP Connector: نظام تخطيط الموارد المؤسسية جاهز (وضع المحاكاة)")

    # ============================================================
    # INVENTORY MANAGEMENT
    # ============================================================
    def check_inventory(self, item_id: str) -> dict:
        """
        Check current stock level for an item.
        Returns simulated inventory data.
        """
        stock = random.randint(0, 500)
        min_threshold = random.randint(20, 80)
        status = "LOW_STOCK" if stock < min_threshold else "IN_STOCK"

        result = {
            "action": "INVENTORY_CHECK",
            "item_id": item_id,
            "current_stock": stock,
            "min_threshold": min_threshold,
            "status": status,
            "warehouse": random.choice(["مستودع الرياض", "مستودع جدة", "مستودع الدمام"]),
            "last_restock": "2024-12-15",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🏭 ERP: فحص مخزون [{item_id}] → {stock} وحدة ({status})")
        return result

    # ============================================================
    # PURCHASE ORDERS
    # ============================================================
    def issue_purchase_order(self, item_id: str, quantity: int, vendor: str = "المورد الافتراضي") -> dict:
        """
        Issue a purchase order to restock an item.
        Returns PO confirmation.
        """
        po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        unit_price = round(random.uniform(10, 500), 2)
        total = round(unit_price * quantity, 2)

        result = {
            "action": "PURCHASE_ORDER_ISSUED",
            "po_number": po_number,
            "item_id": item_id,
            "quantity": quantity,
            "vendor": vendor,
            "unit_price_sar": unit_price,
            "total_sar": total,
            "estimated_delivery": "5-7 أيام عمل",
            "status": "APPROVED",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🏭 ERP: أمر شراء {po_number} → {quantity}× [{item_id}] = {total} ر.س")
        return result

    # ============================================================
    # CUSTOMER REFUNDS
    # ============================================================
    def process_customer_refund(self, customer_id: str, amount: float, reason: str = "") -> dict:
        """
        Process a customer refund through the ERP system.
        Returns transaction confirmation.
        """
        txn_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
        approved = amount <= 5000  # Auto-approve refunds under 5000 SAR

        result = {
            "action": "REFUND_PROCESSED" if approved else "REFUND_ESCALATED",
            "transaction_id": txn_id,
            "customer_id": customer_id,
            "amount_sar": amount,
            "reason": reason or "طلب عميل",
            "status": "APPROVED" if approved else "REQUIRES_MANAGER_APPROVAL",
            "refund_method": "تحويل بنكي",
            "processing_time": "2-3 أيام عمل",
            "timestamp": datetime.now().isoformat(),
        }
        tag = "✅ موافقة" if approved else "⚠️ يتطلب موافقة مدير"
        print(f"🏭 ERP: استرداد {txn_id} → {amount} ر.س للعميل {customer_id} [{tag}]")
        return result

    # ============================================================
    # INVOICE GENERATION
    # ============================================================
    def generate_invoice(self, client_name: str, items: list, tax_rate: float = 0.15) -> dict:
        """
        Generate a new invoice.
        """
        inv_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        subtotal = sum(item.get("amount", 0) for item in items)
        tax = round(subtotal * tax_rate, 2)
        total = round(subtotal + tax, 2)

        result = {
            "action": "INVOICE_GENERATED",
            "invoice_number": inv_number,
            "client": client_name,
            "items_count": len(items),
            "subtotal_sar": subtotal,
            "vat_15_sar": tax,
            "total_sar": total,
            "status": "ISSUED",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🏭 ERP: فاتورة {inv_number} → {client_name} = {total} ر.س")
        return result

    # ============================================================
    # HR RECRUITMENT TOOLS
    # ============================================================
    def fetch_job_description(self, job_id: str) -> dict:
        """
        Fetch a job description from the ERP HR module.
        Returns strict requirements for candidate evaluation.
        """
        jd_library = {
            "JD-AI-001": {
                "title": "Python AI Developer",
                "department": "قسم الذكاء الاصطناعي",
                "requirements": {
                    "min_experience_years": 3,
                    "required_skills": ["Python", "LangChain", "Machine Learning", "REST APIs"],
                    "preferred_skills": ["ChromaDB", "Docker", "FastAPI", "PyTorch"],
                    "education": "بكالوريوس علوم حاسب أو ما يعادلها",
                    "certifications": ["AWS ML Specialty", "Google AI Certificate"],
                },
                "salary_range_sar": "15,000 - 25,000",
                "location": "الرياض — حضوري/هجين",
                "status": "OPEN",
            },
            "JD-SE-002": {
                "title": "Senior Software Engineer",
                "department": "قسم التطوير",
                "requirements": {
                    "min_experience_years": 5,
                    "required_skills": ["Java", "Spring Boot", "Microservices", "PostgreSQL"],
                    "preferred_skills": ["Kubernetes", "AWS", "Redis"],
                    "education": "بكالوريوس هندسة برمجيات أو ما يعادلها",
                    "certifications": [],
                },
                "salary_range_sar": "20,000 - 35,000",
                "location": "جدة — حضوري",
                "status": "OPEN",
            },
        }

        jd = jd_library.get(job_id, jd_library["JD-AI-001"])
        result = {
            "action": "JOB_DESCRIPTION_FETCHED",
            "job_id": job_id,
            **jd,
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🏭 ERP-HR: وصف وظيفي [{job_id}] → {jd['title']} ({jd['department']})")
        return result

    def schedule_interview(self, candidate_name: str, date: str, job_id: str = "JD-AI-001") -> dict:
        """
        Schedule an interview for a candidate.
        Returns confirmation with meeting details.
        """
        interview_id = f"INT-{uuid.uuid4().hex[:6].upper()}"
        result = {
            "action": "INTERVIEW_SCHEDULED",
            "interview_id": interview_id,
            "candidate": candidate_name,
            "job_id": job_id,
            "date": date,
            "time": "10:00 صباحاً",
            "location": "مقر الشركة — قاعة الاجتماعات A3",
            "interviewers": ["مدير التقنية", "مدير الموارد البشرية"],
            "type": "مقابلة تقنية + سلوكية",
            "status": "CONFIRMED",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🏭 ERP-HR: مقابلة {interview_id} → {candidate_name} في {date}")
        return result

    def reject_candidate(self, candidate_name: str, reason: str, job_id: str = "JD-AI-001") -> dict:
        """
        Log a candidate rejection in the ERP system.
        Returns rejection record.
        """
        rejection_id = f"REJ-{uuid.uuid4().hex[:6].upper()}"
        result = {
            "action": "CANDIDATE_REJECTED",
            "rejection_id": rejection_id,
            "candidate": candidate_name,
            "job_id": job_id,
            "reason": reason,
            "can_reapply_after": "6 أشهر",
            "logged_by": "HRAgent — نظام نواة",
            "status": "LOGGED",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🏭 ERP-HR: رفض {rejection_id} → {candidate_name} ({reason[:40]})")
        return result

    # ============================================================
    # INTERVIEW EVALUATION
    # ============================================================
    def submit_interview_evaluation(
        self, candidate_name: str, final_score: int,
        technical_notes: str, job_id: str = "JD-AI-001"
    ) -> dict:
        """
        Submit final interview evaluation to the HR database.
        Called by InterviewerAgent after completing the live interview.
        """
        eval_id = f"EVAL-{uuid.uuid4().hex[:6].upper()}"
        grade = (
            "A — ممتاز" if final_score >= 85 else
            "B — جيد جداً" if final_score >= 70 else
            "C — مقبول" if final_score >= 55 else
            "D — غير مؤهل"
        )
        hire_recommendation = final_score >= 60

        result = {
            "action": "INTERVIEW_EVALUATION_SUBMITTED",
            "evaluation_id": eval_id,
            "candidate": candidate_name,
            "job_id": job_id,
            "final_score": final_score,
            "grade": grade,
            "hire_recommendation": "✅ يُنصح بالتوظيف" if hire_recommendation else "🚫 لا يُنصح",
            "technical_notes": technical_notes[:500],
            "evaluator": "InterviewerAgent — نظام نواة",
            "status": "LOGGED",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🏭 ERP-HR: تقييم {eval_id} → {candidate_name} [{final_score}/100 — {grade}]")
        return result

    # ============================================================
    # EMPLOYEE ONBOARDING
    # ============================================================
    def onboard_new_employee(
        self, name: str, job_title: str, department: str = "التقنية",
        salary: float = 0, start_date: str = ""
    ) -> dict:
        """
        Auto-create all onboarding artifacts for a new employee.
        Creates: corporate email, Slack account, payroll entry, badge.
        """
        emp_id = f"EMP-{uuid.uuid4().hex[:6].upper()}"
        name_slug = name.replace(" ", ".").lower()[:20]
        email = f"{name_slug}@nawah.ai"

        result = {
            "action": "EMPLOYEE_ONBOARDED",
            "employee_id": emp_id,
            "name": name,
            "job_title": job_title,
            "department": department,
            "provisions": {
                "corporate_email": email,
                "slack_account": f"@{name_slug}",
                "payroll_entry": f"PAY-{emp_id}",
                "monthly_salary_sar": salary,
                "badge_id": f"BADGE-{uuid.uuid4().hex[:4].upper()}",
                "laptop_request": f"IT-REQ-{uuid.uuid4().hex[:4].upper()}",
                "access_card": "مُصدرة",
            },
            "start_date": start_date or "يُحدد لاحقاً",
            "status": "ACTIVE",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🏭 ERP-HR: تم ضم {name} [{emp_id}] → {email}")
        return result

    # ============================================================
    # PDPL/GDPR — CANDIDATE DATA ANONYMIZATION
    # ============================================================
    def anonymize_rejected_candidate(self, candidate_id: str, candidate_name: str) -> dict:
        """
        Anonymize a rejected candidate's data for PDPL/GDPR compliance.
        """
        result = {
            "action": "CANDIDATE_DATA_ANONYMIZED",
            "original_id": candidate_id,
            "anonymized_name": "████████",
            "anonymized_email": "████@████.com",
            "data_purged": ["cv_text", "phone", "address", "photo"],
            "retention": "metadata فقط — تم حذف البيانات الشخصية",
            "legal_basis": "PDPL المادة 18 / GDPR Article 17",
            "status": "PURGED",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🔒 ERP-PDPL: تم إخفاء بيانات المرشح {candidate_id} ({candidate_name})")
        return result

    # ============================================================
    # DEPARTMENT HIRING BUDGET CHECK
    # ============================================================
    def check_department_hiring_budget(self, department_name: str) -> dict:
        """
        Check if a department has approved hiring budget.
        Must be called BEFORE any JD generation or sourcing.
        """
        dept_lower = department_name.lower()

        # Mock budget database — Marketing deliberately at 0 for judge-trap
        _budgets = {
            "it": {"budget_sar": 150_000, "open_positions": 3, "status": "APPROVED"},
            "تقنية": {"budget_sar": 150_000, "open_positions": 3, "status": "APPROVED"},
            "التقنية": {"budget_sar": 150_000, "open_positions": 3, "status": "APPROVED"},
            "ai": {"budget_sar": 200_000, "open_positions": 2, "status": "APPROVED"},
            "ذكاء اصطناعي": {"budget_sar": 200_000, "open_positions": 2, "status": "APPROVED"},
            "الذكاء الاصطناعي": {"budget_sar": 200_000, "open_positions": 2, "status": "APPROVED"},
            "engineering": {"budget_sar": 180_000, "open_positions": 4, "status": "APPROVED"},
            "هندسة": {"budget_sar": 180_000, "open_positions": 4, "status": "APPROVED"},
            "marketing": {"budget_sar": 0, "open_positions": 0, "status": "FROZEN"},
            "تسويق": {"budget_sar": 0, "open_positions": 0, "status": "FROZEN"},
            "التسويق": {"budget_sar": 0, "open_positions": 0, "status": "FROZEN"},
            "hr": {"budget_sar": 50_000, "open_positions": 1, "status": "APPROVED"},
            "موارد بشرية": {"budget_sar": 50_000, "open_positions": 1, "status": "APPROVED"},
            "finance": {"budget_sar": 80_000, "open_positions": 1, "status": "APPROVED"},
            "مالية": {"budget_sar": 80_000, "open_positions": 1, "status": "APPROVED"},
            "operations": {"budget_sar": 60_000, "open_positions": 2, "status": "APPROVED"},
            "عمليات": {"budget_sar": 60_000, "open_positions": 2, "status": "APPROVED"},
        }

        # Lookup — try exact, then partial match
        entry = _budgets.get(dept_lower)
        if not entry:
            for key, val in _budgets.items():
                if key in dept_lower or dept_lower in key:
                    entry = val
                    break

        if not entry:
            entry = {"budget_sar": 0, "open_positions": 0, "status": "UNKNOWN"}

        result = {
            "action": "HIRING_BUDGET_CHECK",
            "department": department_name,
            "hiring_budget_sar": entry["budget_sar"],
            "open_positions": entry["open_positions"],
            "budget_status": entry["status"],
            "can_hire": entry["budget_sar"] > 0 and entry["open_positions"] > 0,
            "timestamp": datetime.now().isoformat(),
        }

        icon = "✅" if result["can_hire"] else "🚫"
        print(f"🏭 ERP-Budget: {icon} {department_name} → {entry['budget_sar']:,.0f} ر.س ({entry['status']})")
        return result

    # ============================================================
    # SAUDIZATION / LOCALIZATION QUOTA CHECK
    # ============================================================
    def check_localization_quota(self, department_name: str) -> dict:
        """
        Check Saudization (Nitaqat) compliance quota for a department.
        Must be called BEFORE generating JDs to enforce localization constraints.
        """
        dept_lower = department_name.lower()

        _quotas = {
            "it": {"current_pct": 85, "required_pct": 35, "band": "بلاتيني", "status": "SAFE"},
            "تقنية": {"current_pct": 85, "required_pct": 35, "band": "بلاتيني", "status": "SAFE"},
            "التقنية": {"current_pct": 85, "required_pct": 35, "band": "بلاتيني", "status": "SAFE"},
            "ai": {"current_pct": 70, "required_pct": 35, "band": "أخضر عالي", "status": "SAFE"},
            "ذكاء اصطناعي": {"current_pct": 70, "required_pct": 35, "band": "أخضر عالي", "status": "SAFE"},
            "الذكاء الاصطناعي": {"current_pct": 70, "required_pct": 35, "band": "أخضر عالي", "status": "SAFE"},
            "engineering": {"current_pct": 55, "required_pct": 40, "band": "أخضر", "status": "SAFE"},
            "هندسة": {"current_pct": 55, "required_pct": 40, "band": "أخضر", "status": "SAFE"},
            "marketing": {"current_pct": 30, "required_pct": 50, "band": "أحمر", "status": "CRITICAL"},
            "تسويق": {"current_pct": 30, "required_pct": 50, "band": "أحمر", "status": "CRITICAL"},
            "التسويق": {"current_pct": 30, "required_pct": 50, "band": "أحمر", "status": "CRITICAL"},
            "hr": {"current_pct": 90, "required_pct": 30, "band": "بلاتيني", "status": "SAFE"},
            "موارد بشرية": {"current_pct": 90, "required_pct": 30, "band": "بلاتيني", "status": "SAFE"},
            "finance": {"current_pct": 60, "required_pct": 40, "band": "أخضر", "status": "SAFE"},
            "مالية": {"current_pct": 60, "required_pct": 40, "band": "أخضر", "status": "SAFE"},
            "operations": {"current_pct": 45, "required_pct": 40, "band": "أخضر منخفض", "status": "WARNING"},
            "عمليات": {"current_pct": 45, "required_pct": 40, "band": "أخضر منخفض", "status": "WARNING"},
        }

        entry = _quotas.get(dept_lower)
        if not entry:
            for key, val in _quotas.items():
                if key in dept_lower or dept_lower in key:
                    entry = val
                    break
        if not entry:
            entry = {"current_pct": 50, "required_pct": 40, "band": "غير محدد", "status": "UNKNOWN"}

        is_critical = entry["current_pct"] < 40
        must_hire_local = is_critical

        result = {
            "action": "LOCALIZATION_QUOTA_CHECK",
            "department": department_name,
            "current_saudization_pct": entry["current_pct"],
            "required_pct": entry["required_pct"],
            "nitaqat_band": entry["band"],
            "quota_status": entry["status"],
            "must_hire_local": must_hire_local,
            "timestamp": datetime.now().isoformat(),
        }

        icon = "🟢" if not is_critical else "🔴"
        print(f"🏭 ERP-نطاقات: {icon} {department_name} → {entry['current_pct']}% ({entry['band']})")
        return result

    # ============================================================
    # BACKGROUND VERIFICATION — ANTI-FRAUD ENGINE
    # ============================================================
    def verify_candidate_claims(self, companies: list[str], universities: list[str] = None) -> dict:
        """
        Verify candidate's employment and education claims.
        Anti-fraud: Catches fake companies/universities before wasting interview time.
        """
        universities = universities or []
        _FRAUD_COMPANIES = {
            "fakecorp", "fake corp", "chatgpt inc", "chatgpt", "ai fake labs",
            "شركة وهمية", "فيك كورب", "شات جي بي تي",
        }
        _FRAUD_UNIVERSITIES = {
            "fake university", "diploma mill", "جامعة وهمية", "buy degree online",
        }
        _VERIFIED_COMPANIES = {
            "aramco", "aramco digital", "stc", "sdaia", "sabic", "neom",
            "noon", "careem", "تمارا", "أرامكو", "الاتصالات السعودية",
            "سدايا", "سابك", "نيوم", "google", "microsoft", "amazon", "meta",
        }
        _VERIFIED_UNIVERSITIES = {
            "kaust", "kfupm", "ksu", "mit", "stanford", "جامعة الملك سعود",
            "جامعة الملك فهد", "كاوست", "جامعة الملك عبدالعزيز",
        }

        results = []
        all_verified = True
        fraud_detected = False

        for company in companies:
            c_lower = company.lower().strip()
            if c_lower in _FRAUD_COMPANIES:
                results.append({
                    "entity": company, "type": "company",
                    "status": "FRAUD_DETECTED",
                    "detail": f"⛔ VERIFICATION FAILED: '{company}' is a known fraudulent entity."
                })
                fraud_detected = True
                all_verified = False
            elif any(v in c_lower for v in _VERIFIED_COMPANIES):
                results.append({
                    "entity": company, "type": "company",
                    "status": "VERIFIED", "detail": f"✅ Confirmed employer."
                })
            else:
                results.append({
                    "entity": company, "type": "company",
                    "status": "UNVERIFIABLE",
                    "detail": f"⚠️ Cannot verify '{company}' — not in registry."
                })

        for uni in universities:
            u_lower = uni.lower().strip()
            if u_lower in _FRAUD_UNIVERSITIES:
                results.append({
                    "entity": uni, "type": "university",
                    "status": "FRAUD_DETECTED",
                    "detail": f"⛔ VERIFICATION FAILED: '{uni}' is a known diploma mill."
                })
                fraud_detected = True
                all_verified = False
            elif any(v in u_lower for v in _VERIFIED_UNIVERSITIES):
                results.append({
                    "entity": uni, "type": "university",
                    "status": "VERIFIED", "detail": f"✅ Confirmed institution."
                })
            else:
                results.append({
                    "entity": uni, "type": "university",
                    "status": "UNVERIFIABLE",
                    "detail": f"⚠️ Cannot verify '{uni}' — not in registry."
                })

        overall = "FRAUD_DETECTED" if fraud_detected else ("VERIFIED" if all_verified else "PARTIAL")
        icon = "🚨" if fraud_detected else "✅"
        print(f"🏭 ERP-BGCheck: {icon} {overall} — {len(companies)} شركة, {len(universities)} جامعة")

        return {
            "action": "BACKGROUND_VERIFICATION",
            "overall_status": overall,
            "fraud_detected": fraud_detected,
            "checks": results,
            "timestamp": datetime.now().isoformat(),
        }

# Singleton
_erp_tool = None

def get_erp_tool() -> ERPWebhookTool:
    """Get or create the singleton ERPWebhookTool instance."""
    global _erp_tool
    if _erp_tool is None:
        _erp_tool = ERPWebhookTool()
    return _erp_tool
