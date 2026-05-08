"""Quick smoke test for InterviewerAgent mock pipeline."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=== INTERVIEWER AGENT SMOKE TEST ===\n")

from core.agents.interviewer_agent import InterviewerAgent

agent = InterviewerAgent(candidate_name="Ahmed Test")

# Simulate full 3-question interview
r1 = agent.chat("")  # Opening + Q1
print(f"Q1: {r1[:80]}...")
assert "السؤال" in r1 or "سؤال" in r1.lower() or "مرحب" in r1

r2 = agent.chat("List comprehension ينشئ القائمة كاملة في الذاكرة بينما Generator يولد العناصر عند الطلب وهو أفضل للبيانات الكبيرة")
print(f"Q2: {r2[:80]}...")

r3 = agent.chat("ReAct يجعل الوكيل يفكر خطوة بخطوة قبل التنفيذ مما يقلل الأخطاء ويحسن جودة القرارات")
print(f"Q3: {r3[:80]}...")

r4 = agent.chat("Embedding هو تحويل النص إلى متجه رقمي يحافظ على المعنى الدلالي، ويستخدم في RAG للبحث الدلالي في قاعدة المعرفة")
print(f"Final: {r4[:80]}...")

assert agent.interview_complete, "Interview should be complete"
assert agent.final_score is not None, "Score should be set"
assert agent.evaluation_result is not None, "ERP result should exist"

status = agent.get_status()
print(f"\nScore: {status['final_score']}/100")
print(f"ERP Eval ID: {status['evaluation']['evaluation_id']}")
print(f"Grade: {status['evaluation']['grade']}")
print(f"Hire: {status['evaluation']['hire_recommendation']}")

print("\n=== SMOKE TEST PASSED ===")
