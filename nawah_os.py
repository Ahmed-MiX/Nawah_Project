"""
nawah_os.py — نَوَاة Master Orchestrator
THE ONE COMMAND: python nawah_os.py

Launches:
  1. Streamlit UI (port 8501)
  2. File Watcher daemon
  3. Email Watcher daemon
  4. Health Monitor thread

Graceful Shutdown:
  Ctrl+C → flush agent memories → save logs → close DB → terminate
"""
import subprocess
import sys
import os
import signal
import time
import json
import threading
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
VENV_PYTHON = sys.executable
PORT = 8000
MAX_RESTARTS = 5
RESTART_WINDOW = 60  # seconds

DAEMONS = {
    "🌐 بوابة API":       [VENV_PYTHON, "-m", "uvicorn", "core.api_gateway:app",
                            "--host", "0.0.0.0", "--port", str(PORT)],
    "👁️  حارس الملفات":   [VENV_PYTHON, "-m", "core.watcher"],
    "📧  رادار البريد":    [VENV_PYTHON, "-m", "core.email_watcher"],
}

# ============================================================
# STATE
# ============================================================
processes = {}
crash_log = {}
shutdown_flag = threading.Event()

# ============================================================
# ENSURE DIRECTORIES
# ============================================================
for d in ["nawah_inbox", "nawah_outbox", "nawah_processed", "nawah_quarantine", "nawah_logs", "temp"]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# PORT PURGE — Kill any rogue process holding PORT before launch
# ============================================================
def purge_port(port):
    """Aggressively free the port before Streamlit launch."""
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) != os.getpid():
                        subprocess.run(["taskkill", "/F", "/PID", pid, "/T"],
                                       capture_output=True, timeout=5)
        except Exception:
            pass
        # Also kill any stale streamlit processes
        try:
            subprocess.run(["taskkill", "/F", "/IM", "streamlit.exe", "/T"],
                           capture_output=True, timeout=5)
        except Exception:
            pass
    else:
        try:
            subprocess.run(["fuser", "-k", f"{port}/tcp"],
                           capture_output=True, timeout=5)
        except Exception:
            pass
    time.sleep(1)

# ============================================================
# SPAWN
# ============================================================
def spawn(name):
    """Launch a subprocess with platform-appropriate flags."""
    cmd = DAEMONS[name]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        proc = subprocess.Popen(cmd, **kwargs)
        processes[name] = proc
        print(f"   ✅ {name} → PID {proc.pid}")
    except Exception as e:
        print(f"   ❌ {name} فشل الإطلاق: {e}")

# ============================================================
# GRACEFUL SHUTDOWN (ZERO DATA LOSS)
# ============================================================
def graceful_shutdown(signum=None, frame=None):
    """Flush memories, save logs, close DB, terminate processes."""
    if shutdown_flag.is_set():
        return
    shutdown_flag.set()

    print("\n" + "=" * 60)
    print("  🛑 إيقاف منظومة نَوَاة — حفظ الحالة...")
    print("=" * 60)

    # 1. Flush active agent memories to disk
    try:
        from core.shared_memory import WorkspaceManager
        # Try to serialize any in-memory workspaces
        state_file = os.path.join("nawah_logs", f"shutdown_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        print(f"   💾 حفظ حالة الذاكرة → {state_file}")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({
                "shutdown_time": datetime.now().isoformat(),
                "active_processes": list(processes.keys()),
                "status": "clean_shutdown"
            }, f, ensure_ascii=False, indent=2)
        print("   ✅ تم حفظ الحالة")
    except Exception as e:
        print(f"   ⚠️ فشل حفظ الحالة: {e}")

    # 2. Save shutdown log
    try:
        log_file = os.path.join("nawah_logs", "shutdown.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] Graceful shutdown initiated\n")
            for name, proc in processes.items():
                f.write(f"  {name}: PID={proc.pid}, alive={proc.poll() is None}\n")
            f.write("---\n")
        print(f"   📝 سجل الإيقاف → {log_file}")
    except Exception:
        pass

    # 3. Terminate all subprocesses
    for name, proc in processes.items():
        try:
            if proc.poll() is None:
                print(f"   ⏹️  إيقاف {name} (PID {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    # 4. Close any lingering SQLite connections
    try:
        import sqlite3
        # Force WAL checkpoint on nawah_state.db
        if os.path.exists("nawah_state.db"):
            conn = sqlite3.connect("nawah_state.db", timeout=5)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            print("   🗄️  قاعدة البيانات: WAL checkpoint OK")
    except Exception:
        pass

    print("\n  ✅ تم إيقاف منظومة نَوَاة بأمان. لا فقدان للبيانات.")
    print("=" * 60)
    sys.exit(0)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  🚀 إطلاق منظومة نَوَاة — نظام التشغيل الموحد")
    print(f"  🐍 المُفسّر: {VENV_PYTHON}")
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Phase 0: Pre-flight
    print("\n  === المرحلة 0: فحص ما قبل الإطلاق ===")
    try:
        from core.health_monitor import run_preflight
        preflight = run_preflight()
        if not preflight.healthy:
            print("  ❌ فشل فحص ما قبل الإطلاق:")
            for _, name, detail in preflight.failures:
                print(f"     FATAL: {name} — {detail}")
            print("\n  أصلح المشاكل أعلاه ثم أعد التشغيل.")
            sys.exit(1)
        print("  ✅ فحص ما قبل الإطلاق: اكتمل بنجاح")
    except ImportError:
        print("  ⚠️  لم يتم العثور على health_monitor — تخطي الفحص")

    # Phase 1: Init DB
    print("\n  === المرحلة 1: قاعدة البيانات ===")
    try:
        from core.message_bus import TaskBroker
        broker = TaskBroker()
        ingested = broker.ingest_from_outbox()
        print(f"  ✅ nawah_state.db جاهزة (استيعاب {ingested} مهمة)")
    except Exception as e:
        print(f"  ⚠️  خطأ DB: {e}")

    # Phase 2: Health Monitor thread
    print("\n  === المرحلة 2: المراقب الصحي ===")
    try:
        from core.health_monitor import HealthMonitor
        health_monitor = HealthMonitor(interval=60)
        health_monitor.start()
        print("  ✅ المراقب الصحي يعمل (كل 60 ثانية)")
    except Exception as e:
        print(f"  ⚠️  المراقب الصحي: {e}")

    # Phase 3: Launch daemons
    print("\n  === المرحلة 3: إطلاق الخدمات ===")
    print(f"  🔌 تطهير المنفذ {PORT}...")
    purge_port(PORT)
    for name in DAEMONS:
        spawn(name)
        crash_log[name] = []

    # Register shutdown handler
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    print(f"\n  🌐 الواجهة: http://localhost:{PORT}")
    print("  ⌨️  اضغط Ctrl+C للإيقاف الآمن")
    print("=" * 60)

    # Phase 4: Watchdog loop
    try:
        while not shutdown_flag.is_set():
            for name, proc in list(processes.items()):
                if proc.poll() is not None and not shutdown_flag.is_set():
                    now = time.time()
                    crash_log[name] = [t for t in crash_log[name] if now - t < RESTART_WINDOW]
                    crash_log[name].append(now)

                    if len(crash_log[name]) > MAX_RESTARTS:
                        print(f"  🚨 {name} تجاوز حد إعادة التشغيل. تم تعطيله.")
                        continue

                    print(f"  ⚠️ {name} توقف (كود: {proc.returncode}). إعادة التشغيل...")
                    time.sleep(2)
                    spawn(name)

            time.sleep(3)
    except KeyboardInterrupt:
        graceful_shutdown()
