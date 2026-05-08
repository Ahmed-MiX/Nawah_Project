"""
Nawah Base Agent — Abstract Constitution for All L2/L3 Agents

Every agent MUST inherit from BaseAgent and implement the
`process(task_payload) -> dict` method. No exceptions.

Meta-Cognition Features (L3):
    - ReAct Loop: Reason → Act → Observe cycle before finalizing
    - Tree of Thoughts: Generate & evaluate 2 decision branches
    - Self-Reflection: Governance-triggered self-correction
    - Episodic Memory: Learn from past mistakes
"""
from abc import ABC, abstractmethod
from datetime import datetime


class BaseAgent(ABC):
    """
    Abstract base class for all Nawah L2/L3 agents.

    Subclasses MUST implement:
        process(task_payload: dict) -> dict

    The returned dict MUST contain at minimum:
        - status: "completed" | "failed" | "routed"
        - agent: agent name string
        - task_id: from the payload
        - message: human-readable result
        - timestamp: ISO-8601
    """

    # Each subclass sets its own name and icon
    agent_name: str = "base_agent"
    agent_icon: str = "🤖"

    @abstractmethod
    def process(self, task_payload: dict) -> dict:
        """
        Process a Military Task Order.

        Args:
            task_payload: Validated L1 payload dict with task_id,
                          commander_instruction, attachments, l1_triage.

        Returns:
            dict with status, agent, task_id, message, timestamp.
        """
        raise NotImplementedError

    def _success(self, task_id: str, message: str) -> dict:
        """Helper to build a standard success response."""
        return {
            "status": "completed",
            "agent": self.agent_name,
            "task_id": task_id,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }

    def _fail(self, task_id: str, error: str) -> dict:
        """Helper to build a standard failure response."""
        return {
            "status": "failed",
            "agent": self.agent_name,
            "task_id": task_id,
            "message": f"❌ {error}",
            "timestamp": datetime.now().isoformat(),
        }

    # ============================================================
    # META-COGNITION: ReAct Reasoning Engine
    # ============================================================
    def generate_thought_process(self, instruction: str, context: str, intent: str) -> str:
        """
        ReAct Loop — Force explicit step-by-step reasoning before action.

        Generates a structured Thought_Process that shows the agent's
        internal logical deduction chain. This is injected into the LLM
        prompt to enforce disciplined reasoning.

        Args:
            instruction: Commander's instruction.
            context: Gathered context (RAG policies, ERP data, files).
            intent: Task intent (e.g., FINANCE_AUDIT).

        Returns:
            Formatted thought process string for prompt injection.
        """
        # Recall past mistakes (Episodic Memory)
        past_lessons = self._recall_past_mistakes(intent)

        thought = (
            f"## 🧠 عملية التفكير المنهجي (ReAct)\n\n"
            f"### الخطوة 1: الملاحظة (Observe)\n"
            f"- **التعليمات:** {instruction[:150]}\n"
            f"- **السياق المتاح:** {len(context)} حرف من البيانات\n"
            f"- **النية:** {intent}\n\n"
            f"### الخطوة 2: التفكير (Reason)\n"
            f"- تحليل التعليمات وربطها بالسياسات المؤسسية.\n"
            f"- تقييم المخاطر والبدائل المتاحة.\n"
            f"- مراجعة القيود والحدود المالية/القانونية.\n\n"
        )

        if past_lessons:
            thought += (
                f"### الخطوة 2.5: التعلم من التجارب السابقة (Episodic Memory)\n"
            )
            for i, lesson in enumerate(past_lessons, 1):
                thought += f"- ⚠️ تجربة سابقة {i}: {lesson.get('violation', 'غير محدد')}\n"
            thought += "\n"

        thought += (
            f"### الخطوة 3: التخطيط (Plan)\n"
            f"- صياغة قرارين محتملين (شجرة الأفكار).\n"
            f"- تقييم كل قرار ضد حارس الامتثال.\n"
            f"- اختيار القرار الأمثل بدون مخالفات.\n\n"
            f"### الخطوة 4: التنفيذ (Act)\n"
            f"- تنفيذ القرار المختار مع التوثيق الكامل.\n"
        )

        print(f"🧠 {self.agent_name}: ReAct — عملية تفكير منهجي مُفعّلة")
        return thought

    # ============================================================
    # META-COGNITION: Tree of Thoughts
    # ============================================================
    def tree_of_thoughts_evaluate(self, decision_a: str, decision_b: str, guardrail) -> tuple:
        """
        Tree of Thoughts — Evaluate 2 decision branches and select
        the one with zero governance violations.

        Args:
            decision_a: First decision candidate.
            decision_b: Second decision candidate.
            guardrail: ComplianceGuardrail instance.

        Returns:
            Tuple of (best_decision: str, evaluation_report: str)
        """
        print(f"🌳 {self.agent_name}: Tree of Thoughts — تقييم فرعين")

        verdict_a = guardrail.check(self.agent_name, decision_a)
        verdict_b = guardrail.check(self.agent_name, decision_b)

        eval_report = (
            f"## 🌳 تقييم شجرة الأفكار\n\n"
            f"| الفرع | المخالفات | الحالة |\n"
            f"|-------|----------|--------|\n"
            f"| القرار أ | {len(verdict_a.violations)} | "
            f"{'✅ متوافق' if verdict_a.compliant else '🚫 مخالف'} |\n"
            f"| القرار ب | {len(verdict_b.violations)} | "
            f"{'✅ متوافق' if verdict_b.compliant else '🚫 مخالف'} |\n\n"
        )

        # Selection logic: prefer zero violations, then fewer violations
        if verdict_a.compliant and not verdict_b.compliant:
            eval_report += "**القرار:** تم اختيار الفرع أ (متوافق مع الحوكمة).\n"
            return decision_a, eval_report
        elif verdict_b.compliant and not verdict_a.compliant:
            eval_report += "**القرار:** تم اختيار الفرع ب (متوافق مع الحوكمة).\n"
            return decision_b, eval_report
        elif verdict_a.compliant and verdict_b.compliant:
            # Both compliant — prefer A (original/conservative)
            eval_report += "**القرار:** كلا الفرعين متوافق — تم اختيار الفرع أ (المحافظ).\n"
            return decision_a, eval_report
        else:
            # Both violate — pick the one with fewer violations
            if len(verdict_a.violations) <= len(verdict_b.violations):
                eval_report += f"**القرار:** كلا الفرعين مخالف — الفرع أ أقل مخالفات ({len(verdict_a.violations)}).\n"
                return decision_a, eval_report
            else:
                eval_report += f"**القرار:** كلا الفرعين مخالف — الفرع ب أقل مخالفات ({len(verdict_b.violations)}).\n"
                return decision_b, eval_report

    # ============================================================
    # SELF-REFLECTION: Governance-Triggered Correction
    # ============================================================
    def self_reflect(self, decision: str, guardrail_feedback: str,
                     task_id: str = "", intent: str = "") -> str:
        """
        Self-Reflection Loop — Agent corrects its own decision
        when the Governance Guardrail flags violations.

        Also logs the mistake to Episodic Memory for future learning.

        Args:
            decision: The original decision text that was flagged.
            guardrail_feedback: Formatted violation report from ComplianceGuardrail.
            task_id: Task identifier for experience logging.
            intent: Task intent for experience logging.

        Returns:
            Corrected decision string with governance annotations.
        """
        corrected = (
            f"{decision}\n\n"
            f"---\n\n"
            f"## 🛡️ مراجعة الحوكمة المؤسسية\n\n"
            f"{guardrail_feedback}\n\n"
            f"### ⚠️ تنبيه:\n"
            f"تم تعديل هذا القرار تلقائياً بواسطة محرك الحوكمة. "
            f"القرار الأصلي يتطلب مراجعة بشرية قبل التنفيذ النهائي.\n\n"
            f"**الحالة:** 🔒 معلّق — بانتظار موافقة المسؤول المختص\n"
        )

        # Log to Episodic Memory
        if task_id and intent:
            try:
                from core.memory.rag_engine import get_corporate_memory
                memory = get_corporate_memory()
                memory.log_experience(
                    agent_name=self.agent_name,
                    intent=intent,
                    task_id=task_id,
                    violation=guardrail_feedback[:300],
                    original_decision=decision[:200],
                    corrected_decision=corrected[:200],
                )
            except Exception:
                pass  # Non-critical — don't crash the agent

        print(f"🔄 {self.agent_name}: تم تفعيل حلقة التصحيح الذاتي + حفظ التجربة")
        return corrected

    # ============================================================
    # EPISODIC MEMORY: Past Mistake Recall
    # ============================================================
    def _recall_past_mistakes(self, intent: str) -> list[dict]:
        """
        Query episodic memory for past mistakes before starting a task.
        This is the meta-cognition layer — agents learn from history.

        Args:
            intent: Current task intent.

        Returns:
            List of past experience dicts.
        """
        try:
            from core.memory.rag_engine import get_corporate_memory
            memory = get_corporate_memory()
            past = memory.query_past_mistakes(self.agent_name, intent, n_results=3)
            if past:
                print(f"🧠 {self.agent_name}: استذكار {len(past)} تجربة سابقة")
            return past
        except Exception:
            return []
