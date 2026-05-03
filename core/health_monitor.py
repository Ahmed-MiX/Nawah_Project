"""
Nawah Health Monitor — Self-Verifying Continuous Verification Engine (CVE)

Two modes:
1. PRE-FLIGHT: Fast critical infrastructure check (runs before boot, blocks if fail)
2. DAEMON: Lightweight periodic health checks + self-healing (runs every 60s)
"""

import os
import time
import json
import sqlite3
import threading
from datetime import datetime


# === ESSENTIAL DIRECTORIES ===
ESSENTIAL_DIRS = [
    "nawah_inbox",
    "nawah_outbox",
    "nawah_processed",
    "nawah_quarantine",
    "nawah_assets",
]

DB_PATH = "nawah_state.db"
HEALTH_LOG = "nawah_health.log"


class HealthStatus:
    """Result of a health check."""

    def __init__(self):
        self.checks = []
        self.healed = []
        self.failures = []

    def ok(self, name, detail=""):
        self.checks.append(("OK", name, detail))

    def healed_item(self, name, detail=""):
        self.healed.append(("HEALED", name, detail))
        self.checks.append(("HEALED", name, detail))

    def fail(self, name, detail=""):
        self.failures.append(("FAIL", name, detail))
        self.checks.append(("FAIL", name, detail))

    @property
    def healthy(self):
        return len(self.failures) == 0

    def summary(self):
        total = len(self.checks)
        healed = len(self.healed)
        failed = len(self.failures)
        return f"{total} checks, {healed} healed, {failed} failures"


def _log_health(message):
    """Append to health log file."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(HEALTH_LOG, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def run_preflight():
    """
    Pre-flight infrastructure check. Runs synchronously before boot.
    Returns HealthStatus. If not healthy, system MUST NOT boot.
    """
    status = HealthStatus()
    print("\n🔍 فحص ما قبل الإطلاق (Pre-Flight Check)...")

    # CHECK 1: Essential directories
    for d in ESSENTIAL_DIRS:
        if os.path.isdir(d):
            # Verify writable
            test_file = os.path.join(d, ".health_check_probe")
            try:
                with open(test_file, 'w') as f:
                    f.write("probe")
                os.remove(test_file)
                status.ok(f"DIR:{d}", "exists & writable")
            except Exception as e:
                status.fail(f"DIR:{d}", f"not writable: {e}")
        else:
            try:
                os.makedirs(d, exist_ok=True)
                status.healed_item(f"DIR:{d}", "missing → recreated")
            except Exception as e:
                status.fail(f"DIR:{d}", f"cannot create: {e}")

    # CHECK 2: SQLite database
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA integrity_check")
        # Verify tasks table exists
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        if tables:
            status.ok("DB:nawah_state.db", "connected, WAL mode, tasks table present")
        else:
            status.ok("DB:nawah_state.db", "connected but tasks table will be created by TaskBroker")
        conn.close()
    except Exception as e:
        status.fail("DB:nawah_state.db", f"cannot connect: {e}")

    # CHECK 3: Core modules importable
    modules_to_check = [
        ("core.synthesizer", "TaskSynthesizer"),
        ("core.message_bus", "TaskBroker"),
        ("core.shared_memory", "AgentWorkspace"),
        ("core.ingress_firewall", "scan_file"),
        ("core.vision", "DocumentReader"),
    ]
    for mod_name, class_name in modules_to_check:
        try:
            mod = __import__(mod_name, fromlist=[class_name])
            if hasattr(mod, class_name):
                status.ok(f"MODULE:{mod_name}", f"{class_name} loaded")
            else:
                status.fail(f"MODULE:{mod_name}", f"{class_name} not found")
        except Exception as e:
            status.fail(f"MODULE:{mod_name}", f"import error: {e}")

    # CHECK 4: TaskBroker functional test
    try:
        from core.message_bus import TaskBroker
        broker = TaskBroker()
        stats = broker.get_stats()
        status.ok("BROKER:functional", f"stats={stats}")
    except Exception as e:
        status.fail("BROKER:functional", str(e))

    # CHECK 5: Ingress firewall functional
    try:
        from core.ingress_firewall import scan_file as _sf
        # Quick scan on a nonexistent file — should return blocked verdict
        v = _sf("nonexistent_test_file.exe", source="preflight")
        if not v.allowed:
            status.ok("FIREWALL:functional", "blocking works")
        else:
            status.fail("FIREWALL:functional", "failed to block .exe")
    except Exception as e:
        status.fail("FIREWALL:functional", str(e))

    # Print results
    for check_type, name, detail in status.checks:
        if check_type == "OK":
            print(f"   ✅ {name}: {detail}")
        elif check_type == "HEALED":
            print(f"   🔧 {name}: {detail}")
        else:
            print(f"   ❌ {name}: {detail}")

    if status.healthy:
        msg = f"Pre-flight PASSED — {status.summary()}"
        print(f"\n   ✅ {msg}")
    else:
        msg = f"Pre-flight FAILED — {status.summary()}"
        print(f"\n   ❌ {msg}")
        for _, name, detail in status.failures:
            print(f"      FATAL: {name} — {detail}")

    _log_health(msg)
    return status


def run_vital_check():
    """
    Lightweight vital check for the HealthMonitor daemon.
    Runs every 60 seconds. Self-heals when possible.
    Returns HealthStatus.
    """
    status = HealthStatus()

    # 1. Directory check + auto-heal
    for d in ESSENTIAL_DIRS:
        if os.path.isdir(d):
            status.ok(f"DIR:{d}")
        else:
            try:
                os.makedirs(d, exist_ok=True)
                status.healed_item(f"DIR:{d}", "auto-recreated")
                _log_health(f"SELF-HEAL: recreated {d}")
            except Exception as e:
                status.fail(f"DIR:{d}", str(e))

    # 2. SQLite connectivity
    try:
        conn = sqlite3.connect(DB_PATH, timeout=3)
        conn.execute("SELECT COUNT(*) FROM tasks")
        conn.close()
        status.ok("DB:responsive")
    except Exception as e:
        status.fail("DB:responsive", str(e))
        _log_health(f"DB FAILURE: {e}")

    # 3. Disk space (warn if < 100MB free)
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        free_mb = free / (1024 * 1024)
        if free_mb < 100:
            status.fail("DISK:space", f"only {free_mb:.0f}MB free")
            _log_health(f"DISK WARNING: {free_mb:.0f}MB free")
        else:
            status.ok("DISK:space", f"{free_mb:.0f}MB free")
    except Exception:
        status.ok("DISK:space", "check skipped")

    return status


class HealthMonitor(threading.Thread):
    """
    Background daemon thread that runs vital checks periodically.
    Self-heals anomalies without bringing down the system.
    """

    def __init__(self, interval=60):
        super().__init__(daemon=True, name="NawahHealthMonitor")
        self.interval = interval
        self._stop_event = threading.Event()
        self.last_status = None
        self.check_count = 0

    def run(self):
        """Main loop — runs vital checks every `interval` seconds."""
        _log_health("HealthMonitor STARTED")
        print(f"   🩺 مراقب الصحة: نشط (كل {self.interval} ثانية)")

        while not self._stop_event.is_set():
            self._stop_event.wait(self.interval)
            if self._stop_event.is_set():
                break

            try:
                self.last_status = run_vital_check()
                self.check_count += 1

                if self.last_status.healed:
                    for _, name, detail in self.last_status.healed:
                        print(f"   🔧 HealthMonitor: تم الإصلاح التلقائي — {name}: {detail}")

                if not self.last_status.healthy:
                    for _, name, detail in self.last_status.failures:
                        print(f"   ❌ HealthMonitor: خلل — {name}: {detail}")
                        _log_health(f"ANOMALY: {name} — {detail}")

            except Exception as e:
                _log_health(f"HealthMonitor ERROR: {e}")

    def stop(self):
        """Signal the monitor to stop."""
        self._stop_event.set()
        _log_health("HealthMonitor STOPPED")
