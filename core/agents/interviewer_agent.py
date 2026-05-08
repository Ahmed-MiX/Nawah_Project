"""
Nawah Interviewer Agent — Live AI Technical Interviewer

Unlike standard agents, this agent is STATEFUL — it maintains a
conversation history across multiple turns using message history.
Conducts a 3-question technical interview, evaluates answers,
and submits the final score to ERP.

Used by: tools/live_interview_arena.py (hackathon demo)
"""
import re
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from core.base_agent import BaseAgent
from core.api_router import LLMFailoverRouter, CriticalAPIFailure
from core.tools.erp_connector import get_erp_tool

INTERVIEWER_SYSTEM_PROMPT = (
    "أنت محاور تقني نخبوي في شركة نواة للذكاء الاصطناعي.\n"
    "أنت تجري مقابلة تقنية قصيرة من 3 أسئلة لوظيفة مطور ذكاء اصطناعي (Python AI Developer).\n\n"
    "القواعد الصارمة:\n"
    "1. اسأل سؤالاً واحداً فقط في كل رسالة.\n"
    "2. لا تعطِ الإجابة الصحيحة أبداً أثناء المقابلة.\n"
    "3. بعد إجابة المرشح، علّق بإيجاز (جملة واحدة) ثم انتقل للسؤال التالي.\n"
    "4. الأسئلة يجب أن تكون تقنية بحتة عن: Python, LangChain, Machine Learning.\n"
    "5. بعد السؤال الثالث والإجابة عليه، اختم المقابلة وأعلن النتيجة.\n"
    "6. في الختام، اكتب بالضبط:\n"
    "   FINAL_SCORE: [رقم من 0 إلى 100]\n"
    "   TECHNICAL_NOTES: [ملاحظاتك التقنية]\n"
    "   INTERVIEW_COMPLETE\n"
    "7. اكتب بالعربية الفصحى بأسلوب مهني ومحترم.\n"
    "8. ابدأ بتحية المرشح وتعريف نفسك ثم اسأل السؤال الأول فوراً.\n"
)

# Mock questions for offline mode
MOCK_QUESTIONS = [
    "ما هو الفرق بين List Comprehension و Generator Expression في Python؟ ومتى تفضل استخدام كل منهما؟",
    "اشرح كيف يعمل نمط ReAct (Reason + Act) في LangChain، وما ميزته عن التنفيذ المباشر؟",
    "ما هو مفهوم Embedding في سياق الذكاء الاصطناعي؟ وكيف يُستخدم في أنظمة RAG؟",
]


class InterviewerAgent(BaseAgent):
    """
    Stateful Conversational Agent — AI Technical Interviewer.

    Unlike standard agents, this maintains message history for
    multi-turn interview conversations.
    """
    agent_name = "interviewer_agent"
    agent_icon = "🎙️"

    def __init__(self, candidate_name: str = "المرشح"):
        try:
            self.router = LLMFailoverRouter()
        except Exception:
            self.router = None
        self.erp = get_erp_tool()
        self.candidate_name = candidate_name
        self.messages = [SystemMessage(content=INTERVIEWER_SYSTEM_PROMPT)]
        self.question_count = 0
        self.interview_complete = False
        self.final_score = None
        self.evaluation_result = None
        print(f"🎙️ InterviewerAgent: جاهز لمقابلة {candidate_name}")

    def process(self, task_payload: dict) -> dict:
        """Standard dispatcher interface — starts the interview."""
        task_id = task_payload.get("task_id", "unknown")
        self.candidate_name = task_payload.get("candidate_name", "المرشح")
        first_msg = self.chat("")  # Trigger opening
        return self._success(task_id, first_msg)

    def chat(self, user_input: str) -> str:
        """
        Send a message and get the interviewer's response.
        This is the main interface for the live arena.

        Args:
            user_input: Candidate's answer (empty string to start).

        Returns:
            Interviewer's response string.
        """
        if self.interview_complete:
            return "🏁 المقابلة انتهت. شكراً لك."

        # Add candidate's answer (skip if first message)
        if user_input.strip():
            self.messages.append(HumanMessage(content=user_input))

        try:
            if not self.router:
                raise CriticalAPIFailure("No API keys")

            def call_with_key(api_key):
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    temperature=0.3,
                    google_api_key=api_key,
                )
                response = llm.invoke(self.messages)
                return response.content

            response = self.router.execute(call_with_key)

        except (CriticalAPIFailure, Exception):
            # Mock mode — simulate interview
            response = self._mock_response(user_input)

        # Track conversation
        self.messages.append(AIMessage(content=response))

        # Check if interview is complete
        if "INTERVIEW_COMPLETE" in response:
            self.interview_complete = True
            self._extract_and_submit_score(response)

        return response

    def _mock_response(self, user_input: str) -> str:
        """Generate mock interviewer responses for offline mode."""
        if not user_input.strip():
            # Opening + first question
            self.question_count = 1
            return (
                f"مرحباً بك في مقابلة نواة التقنية. أنا المحاور الآلي المسؤول عن تقييمك.\n\n"
                f"سأطرح عليك 3 أسئلة تقنية متخصصة. خذ وقتك في الإجابة.\n\n"
                f"**السؤال 1 من 3:**\n\n"
                f"🔹 {MOCK_QUESTIONS[0]}"
            )
        elif self.question_count < 3:
            # Next question
            self.question_count += 1
            comment = "إجابة مقبولة. " if len(user_input) > 20 else "إجابة مختصرة. "
            return (
                f"{comment}لننتقل للسؤال التالي.\n\n"
                f"**السؤال {self.question_count} من 3:**\n\n"
                f"🔹 {MOCK_QUESTIONS[self.question_count - 1]}"
            )
        else:
            # Final evaluation
            score = min(95, max(40, len(user_input) * 2 + 50))
            return (
                f"شكراً لك على إجاباتك. المقابلة انتهت.\n\n"
                f"## 📊 تقرير التقييم النهائي\n\n"
                f"| المحور | التقييم |\n"
                f"|--------|--------|\n"
                f"| Python الأساسيات | {'ممتاز' if score > 75 else 'جيد'} |\n"
                f"| LangChain & ReAct | {'جيد جداً' if score > 65 else 'مقبول'} |\n"
                f"| AI / Embeddings | {'جيد' if score > 60 else 'يحتاج تطوير'} |\n\n"
                f"FINAL_SCORE: {score}\n"
                f"TECHNICAL_NOTES: المرشح أظهر فهماً {'جيداً' if score > 65 else 'أساسياً'} للمفاهيم التقنية المطلوبة. "
                f"{'يُنصح بالتوظيف مع فترة تدريب.' if score >= 60 else 'يحتاج مزيداً من الخبرة.'}\n"
                f"INTERVIEW_COMPLETE"
            )

    def _extract_and_submit_score(self, response: str):
        """Extract score from the final response and submit to ERP."""
        # Extract score
        score_match = re.search(r'FINAL_SCORE:\s*(\d+)', response)
        notes_match = re.search(r'TECHNICAL_NOTES:\s*(.+?)(?:\n|INTERVIEW_COMPLETE)', response, re.DOTALL)

        score = int(score_match.group(1)) if score_match else 65
        notes = notes_match.group(1).strip() if notes_match else "تقييم تلقائي"

        self.final_score = score

        # Submit to ERP
        self.evaluation_result = self.erp.submit_interview_evaluation(
            candidate_name=self.candidate_name,
            final_score=score,
            technical_notes=notes,
        )
        print(f"🎙️ InterviewerAgent: تم إرسال التقييم → {score}/100")

    def get_status(self) -> dict:
        """Get current interview status."""
        return {
            "candidate": self.candidate_name,
            "questions_asked": self.question_count,
            "complete": self.interview_complete,
            "final_score": self.final_score,
            "evaluation": self.evaluation_result,
        }
