"""
Nawah CV Triage Firewall — Zero-LLM Cost Gate

Runs BEFORE any LLM agent. Performs lightweight keyword-overlap
scoring to instantly reject spam/irrelevant CVs without burning tokens.

Cost Defense: 500 spam CVs → 0 LLM tokens.
"""
import re
from datetime import datetime


class CVTriageVerdict:
    """Result of a cheap CV triage check."""
    def __init__(self, relevant: bool, overlap_pct: float, matched_keywords: list,
                 cv_length: int, reason: str = ""):
        self.relevant = relevant
        self.overlap_pct = overlap_pct
        self.matched_keywords = matched_keywords
        self.cv_length = cv_length
        self.reason = reason

    def __repr__(self):
        icon = "✅" if self.relevant else "🚫"
        return f"{icon} CVTriage: {self.overlap_pct:.0f}% overlap ({self.reason})"


# Minimum thresholds
_MIN_OVERLAP_PCT = 15       # Below this → instant drop
_MIN_CV_LENGTH = 50         # Below this → spam/empty
_MAX_CV_LENGTH = 50_000     # Above this → suspicious


def cheap_cv_triage(cv_text: str, dynamic_jd: dict) -> CVTriageVerdict:
    """
    Non-LLM keyword overlap check. O(n) string matching.
    Runs in <1ms per CV. No API calls. No token costs.

    Args:
        cv_text: Raw CV text (extracted from PDF/email).
        dynamic_jd: The JD dict from SourcingTools.generate_dynamic_jd().

    Returns:
        CVTriageVerdict — relevant=True if CV passes minimum threshold.
    """
    # Gate 1: Empty/Too Short
    if len(cv_text.strip()) < _MIN_CV_LENGTH:
        return CVTriageVerdict(
            relevant=False, overlap_pct=0, matched_keywords=[],
            cv_length=len(cv_text), reason="CV فارغ أو قصير جداً (SPAM)"
        )

    # Gate 2: Suspiciously Long (potential payload injection)
    if len(cv_text) > _MAX_CV_LENGTH:
        return CVTriageVerdict(
            relevant=False, overlap_pct=0, matched_keywords=[],
            cv_length=len(cv_text), reason="CV كبير بشكل مشبوه — رفض أمني"
        )

    # Gate 3: Keyword overlap scoring
    reqs = dynamic_jd.get("requirements", {})
    jd_keywords = set()

    # Collect all JD keywords (lowercase)
    for skill in reqs.get("required_skills", []):
        jd_keywords.add(skill.lower())
    for skill in reqs.get("preferred_skills", []):
        jd_keywords.add(skill.lower())
    for skill in reqs.get("leadership_skills", []):
        jd_keywords.add(skill.lower())

    # Add role title keywords
    title = dynamic_jd.get("title", "")
    for word in title.lower().split():
        if len(word) > 2:
            jd_keywords.add(word)

    # Add domain
    domain = dynamic_jd.get("domain", "")
    if domain:
        jd_keywords.add(domain.lower())

    if not jd_keywords:
        # No keywords to match → pass through (safety)
        return CVTriageVerdict(
            relevant=True, overlap_pct=100, matched_keywords=[],
            cv_length=len(cv_text), reason="لا توجد كلمات مفتاحية في الوصف الوظيفي"
        )

    # Match against CV text
    cv_lower = cv_text.lower()
    matched = [kw for kw in jd_keywords if kw in cv_lower]
    overlap_pct = (len(matched) / len(jd_keywords)) * 100

    if overlap_pct < _MIN_OVERLAP_PCT:
        return CVTriageVerdict(
            relevant=False, overlap_pct=overlap_pct,
            matched_keywords=matched, cv_length=len(cv_text),
            reason=f"تطابق {overlap_pct:.0f}% < الحد الأدنى {_MIN_OVERLAP_PCT}% — IRRELEVANT"
        )

    return CVTriageVerdict(
        relevant=True, overlap_pct=overlap_pct,
        matched_keywords=matched, cv_length=len(cv_text),
        reason=f"تطابق {overlap_pct:.0f}% — مقبول للتحليل المتقدم"
    )


def batch_triage(cv_texts: list[str], dynamic_jd: dict) -> dict:
    """
    Batch triage multiple CVs. Returns stats + filtered list.
    This is the DDoS defense: 500 spam CVs → 0 LLM calls.
    """
    results = []
    passed = []
    dropped = []

    for i, cv in enumerate(cv_texts):
        verdict = cheap_cv_triage(cv, dynamic_jd)
        entry = {
            "index": i,
            "verdict": verdict,
            "length": len(cv),
        }
        results.append(entry)
        if verdict.relevant:
            passed.append(entry)
        else:
            dropped.append(entry)

    stats = {
        "total_received": len(cv_texts),
        "passed": len(passed),
        "dropped": len(dropped),
        "drop_rate_pct": (len(dropped) / max(len(cv_texts), 1)) * 100,
        "llm_tokens_saved": sum(len(d["verdict"].cv_length.__str__()) for d in dropped),
        "passed_entries": passed,
        "dropped_entries": dropped,
        "timestamp": datetime.now().isoformat(),
    }

    print(
        f"🔥 CVFirewall: {len(cv_texts)} CVs → "
        f"{len(passed)} مقبول | {len(dropped)} مرفوض "
        f"(توفير {stats['drop_rate_pct']:.0f}% من تكلفة LLM)"
    )
    return stats
