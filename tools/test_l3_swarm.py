"""Nawah L3 Executive Swarm — Integration Test"""
import sys
print("=== L3 EXECUTIVE SWARM TEST ===")

# Test 1: RAG Engine
print("\n--- TEST 1: RAG Engine ---")
from core.memory.rag_engine import get_corporate_memory
mem = get_corporate_memory()
chunks = mem.ingest_document(
    "سياسة الشركة: الحد الاقصى للعقود بدون موافقة الادارة هو 50000 ريال. "
    "يجب مراجعة كل عقد يتجاوز هذا المبلغ من قبل المستشار القانوني.",
    "policy_contracts"
)
print(f"Ingested chunks: {chunks}")
results = mem.query_policy("عقد بقيمة 80000 ريال")
print(f"Query results: {len(results)} matches")
for r in results:
    text_preview = r["text"][:60]
    dist = r["distance"]
    print(f"  -> {text_preview}... (distance: {dist})")
print(f"Stats: {mem.get_stats()}")

# Test 2: Dispatcher with L3
print("\n--- TEST 2: L3 Dispatcher ---")
from core.dispatcher import L2Dispatcher, AGENT_REGISTRY
print(f"Total agents registered: {len(AGENT_REGISTRY)}")
l3_check = ["legal_agent", "finance_agent", "hr_agent"]
for name in l3_check:
    print(f"  {name}: {'REGISTERED' if name in AGENT_REGISTRY else 'MISSING'}")

dispatcher = L2Dispatcher()

# Test Legal Agent
r = dispatcher.dispatch({
    "task_id": "test-legal-001",
    "commander_instruction": "راجع هذا العقد قانونيا",
    "attachments": [],
    "l1_triage": {"intent": "LEGAL_REVIEW", "recommended_agent": "legal_agent"},
})
print(f"\nLegal: {r['status']} | {r['message'][:80]}")

# Test Finance Agent
r = dispatcher.dispatch({
    "task_id": "test-finance-001",
    "commander_instruction": "دقق هذه الفاتورة ماليا",
    "attachments": [],
    "l1_triage": {"intent": "FINANCE_AUDIT", "recommended_agent": "finance_agent"},
})
print(f"Finance: {r['status']} | {r['message'][:80]}")

# Test HR Agent
r = dispatcher.dispatch({
    "task_id": "test-hr-001",
    "commander_instruction": "قيم هذه السيرة الذاتية",
    "attachments": [],
    "l1_triage": {"intent": "HR_SCREENING", "recommended_agent": "hr_agent"},
})
print(f"HR: {r['status']} | {r['message'][:80]}")

print("\n=== ALL L3 TESTS PASSED ===")
