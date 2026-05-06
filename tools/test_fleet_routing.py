"""
Nawah Fleet Routing Test — Iron-Clad Self-Testing Protocol

Generates 10 mock task payloads (one per IntentEnum).
Dispatches each through L2Dispatcher.
Verifies: correct agent, success status, zero crashes.
"""
import uuid
from datetime import datetime
from core.dispatcher import L2Dispatcher

# ============================================================
# INTENT → EXPECTED AGENT MAPPING
# ============================================================
TEST_CASES = [
    {"intent": "TEXT_SUMMARIZATION",   "agent": "analyst_agent",     "icon": "📊", "cmd": "لخص هذا النص"},
    {"intent": "DATA_EXTRACTION",      "agent": "analyst_agent",     "icon": "📊", "cmd": "استخرج البيانات"},
    {"intent": "TRANSLATION",          "agent": "translator_agent",  "icon": "🌐", "cmd": "ترجم هذا المستند"},
    {"intent": "MATH_SOLVING",         "agent": "math_agent",        "icon": "🔢", "cmd": "حل هذه المعادلة"},
    {"intent": "CODE_ANALYSIS",        "agent": "code_agent",        "icon": "💻", "cmd": "حلل هذا الكود"},
    {"intent": "RESEARCH",             "agent": "researcher_agent",  "icon": "🔬", "cmd": "ابحث عن هذا الموضوع"},
    {"intent": "REPORT_GENERATION",    "agent": "report_agent",      "icon": "📝", "cmd": "أنشئ تقريراً"},
    {"intent": "EMAIL_RESPONSE",       "agent": "email_agent",       "icon": "📧", "cmd": "رد على هذا البريد"},
    {"intent": "FILE_CLASSIFICATION",  "agent": "classifier_agent",  "icon": "🏷️", "cmd": "صنّف هذا الملف"},
    {"intent": "IMAGE_ANALYSIS",       "agent": "vision_agent",      "icon": "📷", "cmd": "حلل هذه الصورة"},
]

# ============================================================
# EXECUTE FLEET DRILL
# ============================================================
def build_payload(intent, agent, cmd):
    return {
        "task_id": str(uuid.uuid4()),
        "source": "test_harness",
        "timestamp": datetime.now().isoformat(),
        "commander_instruction": cmd,
        "attachments": [],
        "l1_triage": {
            "intent": intent,
            "priority": "HIGH",
            "complexity": "MEDIUM",
            "recommended_agent": agent,
            "task_summary": f"اختبار التوجيه: {cmd}",
        },
    }


def main():
    dispatcher = L2Dispatcher()
    passed = 0
    failed = 0
    errors = []

    print("=" * 70)
    print("  🎖️  NAWAH FLEET ROUTING TEST — IRON-CLAD PROTOCOL")
    print("=" * 70)

    for i, tc in enumerate(TEST_CASES, 1):
        payload = build_payload(tc["intent"], tc["agent"], tc["cmd"])
        task_id = payload["task_id"][:8]
        print(f"\n--- TEST {i:02d}/10: {tc['icon']} {tc['intent']} → {tc['agent']} ---")

        try:
            result = dispatcher.dispatch(payload)

            # Assertions
            assert result is not None, "Result is None"
            assert isinstance(result, dict), f"Result is not dict: {type(result)}"
            assert "status" in result, "Missing 'status' key"
            assert "agent" in result, "Missing 'agent' key"
            assert "message" in result, "Missing 'message' key"
            assert result["status"] == "completed", f"Status is '{result['status']}', expected 'completed'"
            assert result["agent"] == tc["agent"], f"Agent mismatch: got '{result['agent']}', expected '{tc['agent']}'"

            passed += 1
            print(f"  ✅ PASS | agent={result['agent']} | status={result['status']} | msg_len={len(result['message'])}")

        except AssertionError as e:
            failed += 1
            errors.append((tc["intent"], str(e)))
            print(f"  ❌ FAIL | {e}")
        except Exception as e:
            failed += 1
            errors.append((tc["intent"], f"CRASH: {e}"))
            print(f"  💥 CRASH | {e}")

    # Also test UNKNOWN intent → general_agent fallback
    print(f"\n--- TEST 11/11: 🤖 UNKNOWN → general_agent (FALLBACK) ---")
    payload = build_payload("UNKNOWN", "general_agent", "أمر غير معروف")
    try:
        result = dispatcher.dispatch(payload)
        assert result["status"] == "completed"
        assert result["agent"] == "general_agent"
        passed += 1
        print(f"  ✅ PASS | Fallback works | agent={result['agent']}")
    except Exception as e:
        failed += 1
        errors.append(("UNKNOWN", str(e)))
        print(f"  ❌ FAIL | {e}")

    # Summary
    total = passed + failed
    print("\n" + "=" * 70)
    print(f"  🎖️  FLEET DRILL COMPLETE: {passed}/{total} PASSED | {failed} FAILED")
    print("=" * 70)

    if errors:
        print("\n  ❌ FAILURES:")
        for intent, err in errors:
            print(f"    - {intent}: {err}")
    else:
        print("\n  ✅ ALL AGENTS OPERATIONAL — ZERO CRASHES — FLEET READY")

    print()
    return failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
