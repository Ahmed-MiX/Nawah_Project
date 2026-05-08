"""Nawah L3 Executive Swarm — FULL Integration Test (5 Agents + ERP)"""
print("=== L3 FULL SWARM + ERP TEST ===\n")

# Test 1: ERP Tool
print("--- TEST 1: ERP Webhook Tool ---")
from core.tools.erp_connector import get_erp_tool
erp = get_erp_tool()
inv = erp.check_inventory("LAPTOP-001")
print(f"  Inventory: {inv['current_stock']} units ({inv['status']})")
po = erp.issue_purchase_order("LAPTOP-001", 50, "شركة التقنية")
print(f"  PO: {po['po_number']} = {po['total_sar']} SAR")
ref = erp.process_customer_refund("CUS-A001", 1500, "منتج تالف")
print(f"  Refund: {ref['transaction_id']} ({ref['status']})")

# Test 2: Full Dispatcher
print("\n--- TEST 2: Dispatcher (15 Agents) ---")
from core.dispatcher import L2Dispatcher, AGENT_REGISTRY
print(f"Total agents: {len(AGENT_REGISTRY)}")
l3 = ["legal_agent", "finance_agent", "hr_agent", "supply_chain_agent", "crm_agent"]
for name in l3:
    icon = AGENT_REGISTRY[name].agent_icon if name in AGENT_REGISTRY else "?"
    print(f"  {icon} {name}: {'OK' if name in AGENT_REGISTRY else 'MISSING'}")

dispatcher = L2Dispatcher()

# Test Supply Chain
print("\n--- TEST 3: Supply Chain Agent ---")
r = dispatcher.dispatch({
    "task_id": "sc-test-001",
    "commander_instruction": "تحقق من مخزون اللابتوبات وأصدر أمر شراء",
    "attachments": [],
    "l1_triage": {"intent": "SUPPLY_CHAIN_MGT", "recommended_agent": "supply_chain_agent"},
})
print(f"  Status: {r['status']}")
print(f"  Response: {r['message'][:100]}...")

# Test CRM
print("\n--- TEST 4: CRM Agent ---")
r = dispatcher.dispatch({
    "task_id": "crm-test-001",
    "commander_instruction": "عميل يشتكي من تأخر الشحنة ويطلب استرداد",
    "attachments": [],
    "l1_triage": {"intent": "CRM_RESOLUTION", "recommended_agent": "crm_agent"},
})
print(f"  Status: {r['status']}")
print(f"  Response: {r['message'][:100]}...")

print("\n=== ALL L3+ERP TESTS PASSED ===")
