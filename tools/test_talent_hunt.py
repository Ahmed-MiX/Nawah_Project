"""Nawah Talent Hunt — End-to-End HR Pipeline Test"""
print("=== TALENT HUNT PIPELINE TEST ===\n")

# Test 1: ERP HR Tools
print("--- TEST 1: ERP HR Tools ---")
from core.tools.erp_connector import get_erp_tool
erp = get_erp_tool()

jd = erp.fetch_job_description("JD-AI-001")
print(f"  JD: {jd['title']} — Min Exp: {jd['requirements']['min_experience_years']} years")
print(f"  Skills: {', '.join(jd['requirements']['required_skills'])}")

interview = erp.schedule_interview("أحمد الغامدي", "2026-05-15")
print(f"  Interview: {interview['interview_id']} — {interview['status']}")

rejection = erp.reject_candidate("سعد العتيبي", "خبرة أقل من المطلوب")
print(f"  Rejection: {rejection['rejection_id']} — {rejection['status']}")

# Test 2: HR Persona loaded
print("\n--- TEST 2: HR Persona ---")
from core.memory.persona_manager import get_persona_manager
pm = get_persona_manager()
hr_prompt = pm.get_system_prompt("hr_agent")
hr_constraints = pm.get_constraints("hr_agent")
print(f"  Prompt length: {len(hr_prompt)} chars")
print(f"  Contains ERP tools: {'fetch_job_description' in hr_prompt}")
print(f"  Constraints: {len(hr_constraints)}")
for c in hr_constraints:
    if "ERP" in c or "رفض" in c or "خبرت" in c:
        print(f"    ★ {c}")

# Test 3: Full HR Pipeline (Mock Mode)
print("\n--- TEST 3: Full HR Pipeline ---")
from core.dispatcher import L2Dispatcher
d = L2Dispatcher()
result = d.dispatch({
    "task_id": "talent-hunt-001",
    "commander_instruction": "فحص السيرة الذاتية لمرشح لوظيفة مطور ذكاء اصطناعي",
    "attachments": [],
    "l1_triage": {
        "intent": "HR_SCREENING",
        "recommended_agent": "hr_agent",
        "job_id": "JD-AI-001",
    },
})
print(f"  Status: {result['status']}")
print(f"  Report length: {len(result['message'])} chars")

# Verify key elements in the report
msg = result["message"]
checks = {
    "JD fetched": "Python AI Developer" in msg,
    "Evaluation table": "المحور" in msg,
    "ERP action": "ERP" in msg,
    "Email draft": "الموضوع:" in msg,
    "Decision": "القرار:" in msg,
}
for check, passed in checks.items():
    icon = "✅" if passed else "❌"
    print(f"  {icon} {check}")

print("\n=== TALENT HUNT PIPELINE — LOCKED & LOADED ===")
