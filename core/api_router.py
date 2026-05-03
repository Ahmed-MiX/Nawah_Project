"""
Nawah LLM Failover Router — Enterprise API Key Waterfall

Eliminates Single-Point-of-Failure (SPOF) for Gemini API access.

Architecture:
1. Scans .env for GEMINI_API_KEY, GEMINI_API_KEY_1, GEMINI_API_KEY_2, ...
2. Establishes strict priority hierarchy (Key 1 > Key 2 > Key 3 ...)
3. ALWAYS starts with highest-priority key (Immediate Snapback)
4. Falls through to lower keys only on 429/503 errors
5. Raises CriticalAPIFailure ONLY when ALL keys exhausted
"""

import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class CriticalAPIFailure(Exception):
    """All API keys exhausted. System must quarantine the task."""
    pass


class LLMFailoverRouter:
    """
    Hierarchical API key router with immediate snapback.

    Usage:
        router = LLMFailoverRouter()
        result = router.execute(callable_fn)
    """

    MAX_RETRIES_PER_KEY = 2
    BASE_DELAY = 2

    def __init__(self, keys=None):
        """
        Initialize with explicit keys or auto-scan from environment.

        Args:
            keys: Optional list of API keys (for testing). If None, scans .env.
        """
        if keys is not None:
            self._keys = [k for k in keys if k]
        else:
            self._keys = self._scan_env_keys()

        if not self._keys:
            raise ValueError("No GEMINI API keys found. Set GEMINI_API_KEY in .env")

        self._failover_log = []

    def _scan_env_keys(self):
        """Scan environment for all GEMINI_API_KEY* variables, sorted by priority."""
        keys = []

        # Primary key (highest priority)
        primary = os.getenv("GEMINI_API_KEY", "")
        if primary:
            keys.append(primary)

        # Numbered keys: GEMINI_API_KEY_1, _2, _3, ...
        for i in range(1, 100):
            key = os.getenv(f"GEMINI_API_KEY_{i}", "")
            if key:
                # Avoid duplicates if GEMINI_API_KEY == GEMINI_API_KEY_1
                if key not in keys:
                    keys.append(key)
            elif i > 10:
                break  # Stop scanning after 10 consecutive misses

        return keys

    @property
    def key_count(self):
        return len(self._keys)

    @property
    def failover_log(self):
        return list(self._failover_log)

    def _is_retryable(self, error):
        """Check if an error is a rate-limit/transient failure worth failing over."""
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in (
            "429", "resource", "exhausted", "rate",
            "503", "overloaded", "unavailable",
            "timeout", "connection", "getaddrinfo", "network"
        ))

    def _mask_key(self, key):
        """Mask API key for safe logging."""
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}****{key[-4:]}"

    def execute(self, fn_factory, *args, **kwargs):
        """
        Execute a callable with hierarchical failover.

        Args:
            fn_factory: A callable(api_key) -> result. Takes the API key and
                        performs the LLM call. Must raise on failure.

        Returns:
            The result from the first successful call.

        Raises:
            CriticalAPIFailure: If ALL keys are exhausted.
        """
        all_errors = []

        # IMMEDIATE SNAPBACK: Always start from Key 1
        for key_idx, api_key in enumerate(self._keys):
            key_label = f"Key-{key_idx + 1}"
            masked = self._mask_key(api_key)

            for attempt in range(self.MAX_RETRIES_PER_KEY):
                try:
                    result = fn_factory(api_key)
                    # SUCCESS — log if we had to failover
                    if key_idx > 0:
                        self._failover_log.append({
                            "timestamp": datetime.now().isoformat(),
                            "event": "FAILOVER_SUCCESS",
                            "key_used": key_label,
                            "masked": masked,
                            "attempts_total": len(all_errors) + 1
                        })
                    return result

                except Exception as e:
                    all_errors.append((key_label, attempt + 1, e))

                    if self._is_retryable(e):
                        if attempt < self.MAX_RETRIES_PER_KEY - 1:
                            # Retry same key with backoff
                            delay = self.BASE_DELAY * (2 ** attempt)
                            print(f"⏳ Router [{key_label}]: خطأ مؤقت — محاولة {attempt + 1}/{self.MAX_RETRIES_PER_KEY}، انتظار {delay}ث...")
                            time.sleep(delay)
                        else:
                            # This key is exhausted — log and move to next
                            self._failover_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "event": "KEY_EXHAUSTED",
                                "key": key_label,
                                "masked": masked,
                                "error": str(e)[:100]
                            })
                            if key_idx < len(self._keys) - 1:
                                next_key = f"Key-{key_idx + 2}"
                                print(f"🔄 Router: {key_label} مستنفد → تحويل إلى {next_key}")
                            break
                    else:
                        # Non-retryable error — hard fail immediately
                        raise CriticalAPIFailure(
                            f"خطأ غير قابل للاسترداد من {key_label}: {type(e).__name__}: {e}"
                        ) from e

        # ALL KEYS EXHAUSTED
        error_summary = "; ".join(f"{k}[{a}]: {type(e).__name__}" for k, a, e in all_errors[-3:])
        raise CriticalAPIFailure(
            f"جميع المفاتيح مستنفدة ({self.key_count} مفاتيح، {len(all_errors)} محاولة) — {error_summary}"
        )
