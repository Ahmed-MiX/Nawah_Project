#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║       🎙️  نظام نواة — حلبة المقابلات الحية  🎙️                 ║
║           NAWAH AI INTERVIEW ARENA v2.0                           ║
║                                                                  ║
║   Real-time AI Technical Interviewer — Hackathon Live Demo       ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

Usage: python tools/live_interview_arena.py
"""
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================
# ANSI Color System (no external dependencies)
# ============================================================
class C:
    """ANSI color codes for terminal styling."""
    RESET    = "\033[0m"
    BOLD     = "\033[1m"
    DIM      = "\033[2m"
    ITALIC   = "\033[3m"
    UNDER    = "\033[4m"

    # Foreground
    BLACK    = "\033[30m"
    RED      = "\033[31m"
    GREEN    = "\033[32m"
    YELLOW   = "\033[33m"
    BLUE     = "\033[34m"
    MAGENTA  = "\033[35m"
    CYAN     = "\033[36m"
    WHITE    = "\033[37m"

    # Bright
    BRED     = "\033[91m"
    BGREEN   = "\033[92m"
    BYELLOW  = "\033[93m"
    BBLUE    = "\033[94m"
    BMAGENTA = "\033[95m"
    BCYAN    = "\033[96m"
    BWHITE   = "\033[97m"

    # Background
    BG_BLACK = "\033[40m"
    BG_BLUE  = "\033[44m"
    BG_CYAN  = "\033[46m"
    BG_GREEN = "\033[42m"
    BG_RED   = "\033[41m"


def banner():
    print(f"""
{C.BCYAN}{C.BOLD}╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   {C.BWHITE}🎙️  نظام نواة — حلبة المقابلات التقنية الحية  🎙️{C.BCYAN}                ║
║   {C.BYELLOW}     NAWAH AI LIVE INTERVIEW ARENA — v2.0{C.BCYAN}                         ║
║                                                                      ║
║   {C.DIM}{C.WHITE}Real-time AI Technical Interview • LangChain • ERP Integration{C.BCYAN}{C.BOLD}   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝{C.RESET}
""")


def divider(char="─", color=C.DIM):
    print(f"{color}{char * 70}{C.RESET}")


def print_agent(text: str):
    """Print the interviewer's message in styled format."""
    divider("━", C.CYAN)
    lines = text.split("\n")
    for line in lines:
        if line.strip().startswith("**السؤال") or line.strip().startswith("🔹"):
            print(f"  {C.BYELLOW}{C.BOLD}{line}{C.RESET}")
        elif line.strip().startswith("#"):
            print(f"  {C.BCYAN}{C.BOLD}{line}{C.RESET}")
        elif line.strip().startswith("|"):
            print(f"  {C.WHITE}{line}{C.RESET}")
        elif "FINAL_SCORE" in line:
            print(f"  {C.BGREEN}{C.BOLD}{line}{C.RESET}")
        elif "TECHNICAL_NOTES" in line:
            print(f"  {C.BYELLOW}{line}{C.RESET}")
        elif "INTERVIEW_COMPLETE" in line:
            print(f"  {C.BMAGENTA}{C.BOLD}{'═' * 50}{C.RESET}")
            print(f"  {C.BMAGENTA}{C.BOLD}  🏁  المقابلة انتهت رسمياً  🏁{C.RESET}")
            print(f"  {C.BMAGENTA}{C.BOLD}{'═' * 50}{C.RESET}")
        else:
            print(f"  {C.BCYAN}🤖 {C.WHITE}{line}{C.RESET}")
    divider("━", C.CYAN)


def print_erp_result(evaluation: dict):
    """Print the ERP evaluation result in a corporate console style."""
    print(f"""
{C.BGREEN}{C.BOLD}╔══════════════════════════════════════════════════════════════╗
║               🏭 ERP — تقرير التقييم النهائي                  ║
╠══════════════════════════════════════════════════════════════╣{C.RESET}""")

    rows = [
        ("رقم التقييم",     evaluation.get("evaluation_id", "—")),
        ("المرشح",          evaluation.get("candidate", "—")),
        ("الدرجة النهائية",  f"{evaluation.get('final_score', 0)}/100"),
        ("التقدير",         evaluation.get("grade", "—")),
        ("التوصية",         evaluation.get("hire_recommendation", "—")),
        ("المُقيّم",        evaluation.get("evaluator", "—")),
        ("الحالة",          evaluation.get("status", "—")),
    ]
    for label, value in rows:
        print(f"  {C.BCYAN}║  {C.WHITE}{label:20s}{C.RESET}  │  {C.BYELLOW}{C.BOLD}{value}{C.RESET}")

    print(f"""{C.BGREEN}{C.BOLD}╚══════════════════════════════════════════════════════════════╝{C.RESET}
""")


def main():
    banner()

    # Get candidate name
    print(f"  {C.BYELLOW}أدخل اسم المرشح (أو اضغط Enter للافتراضي):{C.RESET}")
    name = input(f"  {C.BWHITE}{C.BOLD}  👤 الاسم: {C.RESET}").strip()
    if not name:
        name = "القاضي المحترم"  # Default for hackathon judges

    print(f"\n  {C.BGREEN}✅ جاري تهيئة المحاور الآلي لـ {C.BOLD}{name}{C.RESET}{C.BGREEN}...{C.RESET}\n")

    # Initialize the agent
    from core.agents.interviewer_agent import InterviewerAgent
    agent = InterviewerAgent(candidate_name=name)

    # Start the interview (empty input triggers the opening)
    print(f"  {C.DIM}{'─' * 60}{C.RESET}")
    print(f"  {C.BMAGENTA}{C.BOLD}  📡  الاتصال بمحرك المقابلات... جاهز!{C.RESET}")
    print(f"  {C.DIM}  اكتب 'خروج' أو 'quit' للإنهاء المبكر{C.RESET}")
    print(f"  {C.DIM}{'─' * 60}{C.RESET}\n")

    response = agent.chat("")
    print_agent(response)

    # Main interview loop
    while not agent.interview_complete:
        print()
        try:
            user_input = input(f"  {C.BWHITE}{C.BOLD}  💬 {name}: {C.RESET}")
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {C.BRED}⚠️ تم إنهاء المقابلة.{C.RESET}\n")
            break

        if user_input.strip().lower() in ("خروج", "quit", "exit", "q"):
            print(f"\n  {C.BYELLOW}🏁 تم إنهاء المقابلة بطلب من المرشح.{C.RESET}\n")
            break

        if not user_input.strip():
            print(f"  {C.DIM}  ⚠️ يرجى كتابة إجابتك...{C.RESET}")
            continue

        # Get agent response
        response = agent.chat(user_input)
        print()
        print_agent(response)

    # Show ERP result
    status = agent.get_status()
    if status["evaluation"]:
        print_erp_result(status["evaluation"])

    # Final summary
    print(f"""
{C.BCYAN}{C.BOLD}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║          🎯  عملية Talent Hunt مكتملة  🎯                    ║
║                                                              ║
║   CV Screening → HR Decision → Live Interview → ERP Score    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}
""")
    print(f"  {C.DIM}Powered by Nawah OS — نظام نواة للأتمتة المؤسسية{C.RESET}\n")


if __name__ == "__main__":
    # Enable ANSI on Windows
    if sys.platform == "win32":
        os.system("color")
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

    main()
