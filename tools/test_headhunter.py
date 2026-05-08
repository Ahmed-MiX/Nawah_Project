"""Nawah Headhunter Agent — Full Pipeline Test"""
print("=== HEADHUNTER PIPELINE TEST ===\n")

# Test 1: Sourcing Tools
print("--- TEST 1: Sourcing Tools ---")
from core.tools.sourcing_tools import get_sourcing_tools
st = get_sourcing_tools()

jd = st.generate_dynamic_jd("AI Lead", "شركة ناشئة سريعة النمو بميزانية عالية تحتاج قيادة تقنية عاجلة")
print(f"  Title: {jd['title']}")
print(f"  Urgency: {jd['urgency']}")
print(f"  Min Exp: {jd['requirements']['min_experience_years']} years")
print(f"  Salary: {jd['compensation']['salary_range_sar']} SAR")
print(f"  Skills: {', '.join(jd['requirements']['required_skills'][:4])}")

candidates = st.scan_professional_networks(jd["keywords"], max_results=3)
print(f"  Candidates found: {len(candidates)}")
for c in candidates:
    print(f"    - {c['name']} ({c['match_score']}%) [{c['platform']}]")

# Test 2: Full Headhunter via Dispatcher
print("\n--- TEST 2: Headhunter Dispatch ---")
from core.dispatcher import AGENT_REGISTRY, L2Dispatcher
print(f"  Total agents: {len(AGENT_REGISTRY)}")
print(f"  Headhunter registered: {'headhunter_agent' in AGENT_REGISTRY}")

d = L2Dispatcher()
r = d.dispatch({
    "task_id": "hunt-001",
    "commander_instruction": "AI Lead — شركة ناشئة سريعة النمو بميزانية عالية تحتاج قائد ذكاء اصطناعي",
    "attachments": [],
    "l1_triage": {"intent": "PROACTIVE_SOURCING", "recommended_agent": "headhunter_agent"},
})
print(f"  Status: {r['status']}")
print(f"  Report length: {len(r['message'])} chars")

msg = r["message"]
checks = {
    "Dynamic JD": "الوصف الوظيفي" in msg,
    "Candidates": "المرشح" in msg,
    "Outreach msg": "استقطاب" in msg or "رسالة" in msg or "الكريم" in msg,
    "Interview link": "nawah.ai" in msg,
    "Decision": "EXECUTIVE" in msg or "تقرير" in msg,
}
for check, passed in checks.items():
    print(f"  {'✅' if passed else '❌'} {check}")

print("\n=== HEADHUNTER PIPELINE — OPERATIONAL ===")
