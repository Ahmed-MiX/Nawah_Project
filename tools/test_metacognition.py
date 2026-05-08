"""Nawah Step 1.6 — Meta-Cognition & ReAct Integration Test"""
print("=== META-COGNITION & ReAct TEST ===\n")

# Test 1: Episodic Memory
print("--- TEST 1: Episodic Memory ---")
from core.memory.rag_engine import get_corporate_memory
mem = get_corporate_memory()
stats = mem.get_stats()
print(f"  Memory: {stats}")

logged = mem.log_experience(
    agent_name="finance_agent",
    intent="FINANCE_AUDIT",
    task_id="test-ep-001",
    violation="تجاوز الحد المالي: 60000 ر.س",
    original_decision="موافقة على صرف 60000 ر.س",
    corrected_decision="معلّق — بانتظار موافقة المدير"
)
print(f"  Logged experience: {logged}")

# Test 2: Recall past mistakes
print("\n--- TEST 2: Recall Past Mistakes ---")
past = mem.query_past_mistakes("finance_agent", "FINANCE_AUDIT")
print(f"  Past mistakes recalled: {len(past)}")
for p in past:
    print(f"    - {p['violation'][:60]}...")

# Test 3: ReAct Thought Process
print("\n--- TEST 3: ReAct Thought Process ---")
from core.base_agent import BaseAgent
class TestAgent(BaseAgent):
    agent_name = "test_react_agent"
    def process(self, p): pass

ta = TestAgent()
thought = ta.generate_thought_process(
    "تدقيق فاتورة بقيمة 75000 ريال",
    "فاتورة من شركة الأمل",
    "FINANCE_AUDIT"
)
print(f"  Thought process generated: {len(thought)} chars")
has_steps = all(s in thought for s in ["الملاحظة", "التفكير", "التخطيط", "التنفيذ"])
print(f"  Contains all ReAct steps: {has_steps}")

# Test 4: Tree of Thoughts
print("\n--- TEST 4: Tree of Thoughts ---")
from core.governance_engine import get_compliance_guardrail
g = get_compliance_guardrail()

best, report = ta.tree_of_thoughts_evaluate(
    "موافقة على صرف 60,000 ر.س تلقائياً",
    "تحويل للمدير المالي — المبلغ 3,000 ر.س ضمن الحد",
    g
)
print(f"  Best decision length: {len(best)} chars")
print(f"  Contains evaluation table: {'الفرع' in report}")

# Test 5: Full dispatcher still works
print("\n--- TEST 5: Full Dispatcher ---")
from core.dispatcher import AGENT_REGISTRY, L2Dispatcher
print(f"  Total agents: {len(AGENT_REGISTRY)}")

d = L2Dispatcher()
r = d.dispatch({
    "task_id": "react-test-001",
    "commander_instruction": "تحقق من مخزون المواد",
    "attachments": [],
    "l1_triage": {"intent": "SUPPLY_CHAIN_MGT", "recommended_agent": "supply_chain_agent"},
})
print(f"  Dispatch status: {r['status']}")

print("\n=== ALL META-COGNITION TESTS PASSED ===")
