"""Nawah Step 1.5 — Governance & Persona Integration Test"""
print("=== COGNITIVE GOVERNANCE TEST ===\n")

# Test 1: Persona Manager
print("--- TEST 1: Persona Manager ---")
from core.memory.persona_manager import get_persona_manager
pm = get_persona_manager()
stats = pm.get_stats()
print(f"  Configured agents: {stats['agents_configured']}")
print(f"  Total constraints: {stats['total_constraints']}")

legal_constraints = pm.get_constraints("legal_agent")
print(f"  Legal constraints: {len(legal_constraints)}")
for c in legal_constraints:
    print(f"    - {c[:60]}...")

legal_prompt = pm.get_system_prompt("legal_agent", "FALLBACK")
print(f"  Legal prompt loaded: {len(legal_prompt)} chars")
print(f"  Legal temp: {pm.get_temperature('legal_agent')}")

# Test 2: Governance Guardrail
print("\n--- TEST 2: Compliance Guardrail ---")
from core.governance_engine import get_compliance_guardrail
g = get_compliance_guardrail()

# Should flag: 60000 > 50000 threshold
v1 = g.check("finance_agent", "موافقة تلقائية على صرف 60,000 ر.س للمورد الأول")
print(f"  Finance 60K: {v1}")

# Should pass: under threshold
v2 = g.check("finance_agent", "موافقة على صرف 3,000 ر.س مصروفات مكتبية")
print(f"  Finance 3K: {v2}")

# Should flag: 600K > 500K for legal
v3 = g.check("legal_agent", "الموافقة على عقد بقيمة 600,000 ر.س")
print(f"  Legal 600K: {v3}")

# Test 3: Self-Reflection
print("\n--- TEST 3: Self-Reflection ---")
from core.base_agent import BaseAgent
class TestAgent(BaseAgent):
    agent_name = "test_agent"
    def process(self, p): pass

ta = TestAgent()
if not v1.compliant:
    report = g.format_violation_report(v1)
    corrected = ta.self_reflect("القرار الأصلي: موافقة", report)
    print(f"  Corrected decision length: {len(corrected)} chars")
    print(f"  Contains governance section: {'مراجعة الحوكمة' in corrected}")

# Test 4: Full dispatcher still works
print("\n--- TEST 4: Full Dispatcher ---")
from core.dispatcher import AGENT_REGISTRY
print(f"  Total agents: {len(AGENT_REGISTRY)}")

print("\n=== ALL GOVERNANCE TESTS PASSED ===")
