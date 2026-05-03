import subprocess
import sys
import time
import signal

# Store command templates for clean restart
DAEMON_CMDS = {
    "📧 رادار البريد": [sys.executable, "-m", "core.email_watcher"],
    "👁️ الحارس الرقابي": [sys.executable, "-m", "core.watcher"],
    "🖥️ الواجهة": [sys.executable, "-m", "streamlit", "run", "main.py"],
}

MAX_RESTARTS = 5
RESTART_WINDOW = 60


if __name__ == "__main__":
    print("=" * 60)
    print("  🚀 إطلاق منظومة نَوَاة الشاملة")
    print(f"   المُفسّر: {sys.executable}")
    print("=" * 60)

    # === PHASE 0: PRE-FLIGHT CHECK (blocks boot on failure) ===
    from core.health_monitor import run_preflight, HealthMonitor
    preflight = run_preflight()
    if not preflight.healthy:
        print("\n" + "=" * 60)
        print("  ❌ فشل فحص ما قبل الإطلاق — النظام يرفض الإقلاع")
        print("=" * 60)
        for _, name, detail in preflight.failures:
            print(f"     FATAL: {name} — {detail}")
        print("\n  أصلح المشاكل أعلاه ثم أعد تشغيل النظام.")
        sys.exit(1)

    # === PHASE 1: Initialize L2 message bus ===
    from core.message_bus import TaskBroker
    broker = TaskBroker()
    ingested = broker.ingest_from_outbox()
    print(f"   📋 قاعدة بيانات المهام: nawah_state.db (تم استيعاب {ingested} مهمة موجودة)")

    # === PHASE 2: Launch HealthMonitor daemon thread ===
    health_monitor = HealthMonitor(interval=60)
    health_monitor.start()

    # CREATE_NEW_PROCESS_GROUP allows clean termination on Windows
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    processes = {}
    crash_log = {}  # Track restart timestamps per daemon

    def spawn(name):
        cmd = DAEMON_CMDS[name]
        processes[name] = subprocess.Popen(cmd, **kwargs)
        print(f"   ✅ {name} → PID {processes[name].pid}")

    for name in DAEMON_CMDS:
        spawn(name)
        crash_log[name] = []

    def shutdown(signum=None, frame=None):
        print("\n🛑 جاري إيقاف منظومة نَوَاة الشاملة...")
        for name, proc in processes.items():
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("✅ تم إيقاف النظام بأمان.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            for name, proc in list(processes.items()):
                if proc.poll() is not None:
                    # Prune old crash timestamps outside the window
                    now = time.time()
                    crash_log[name] = [t for t in crash_log[name] if now - t < RESTART_WINDOW]
                    crash_log[name].append(now)

                    if len(crash_log[name]) > MAX_RESTARTS:
                        print(f"🚨 {name} تجاوز حد إعادة التشغيل ({MAX_RESTARTS} خلال {RESTART_WINDOW}ث). تم تعطيله.")
                        continue

                    print(f"⚠️ {name} توقف (كود: {proc.returncode}). إعادة التشغيل بعد 3ث...")
                    time.sleep(3)
                    spawn(name)

            time.sleep(3)
    except KeyboardInterrupt:
        shutdown()
