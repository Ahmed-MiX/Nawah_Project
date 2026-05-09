"""
نواة (Nawah OS) — Unified Entry Point
======================================
Single command to launch the entire ecosystem:
  python start_nawah.py

Starts:
  1. Pre-flight health check
  2. Task broker (L2 message bus)
  3. Health monitor daemon
  4. Folder watcher daemon
  5. Email watcher daemon
  6. FastAPI server (uvicorn on port 8000)
"""

import subprocess
import sys
import time
import signal
import threading

# ── Daemon subprocesses (watchers run as separate processes) ──
DAEMON_CMDS = {
    "📧 رادار البريد": [sys.executable, "-m", "core.email_watcher"],
    "👁️ الحارس الرقابي": [sys.executable, "-m", "core.watcher"],
}

MAX_RESTARTS = 5
RESTART_WINDOW = 60


def run_uvicorn():
    """Run FastAPI server in-process via uvicorn."""
    import uvicorn
    uvicorn.run(
        "core.api_gateway:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  🚀 إطلاق منظومة نَوَاة الشاملة")
    print(f"   المُفسّر: {sys.executable}")
    print("=" * 60)

    # === PHASE 0: PRE-FLIGHT CHECK ===
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

    # === PHASE 3: Launch watcher daemons as subprocesses ===
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    processes = {}
    crash_log = {}

    def spawn(name):
        cmd = DAEMON_CMDS[name]
        processes[name] = subprocess.Popen(cmd, **kwargs)
        print(f"   ✅ {name} → PID {processes[name].pid}")

    for name in DAEMON_CMDS:
        spawn(name)
        crash_log[name] = []

    # === PHASE 4: Launch FastAPI server ===
    print(f"   ✅ 🌐 خادم FastAPI → http://0.0.0.0:8000")
    print(f"   ✅ 🖥️ الواجهة المؤسسية → http://localhost:8000/")
    print(f"   ✅ 🔬 لوحة القيادة المتقدمة → http://localhost:8000/dashboard.html")
    print("=" * 60)
    print("  ✅ منظومة نَوَاة جاهزة — جميع الأنظمة تعمل")
    print("=" * 60)

    # Watchdog thread to monitor and restart crashed daemons
    def daemon_watchdog():
        while True:
            for name, proc in list(processes.items()):
                if proc.poll() is not None:
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

    watchdog = threading.Thread(target=daemon_watchdog, daemon=True)
    watchdog.start()

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

    # Run uvicorn in the main thread (blocks until server stops)
    try:
        run_uvicorn()
    except KeyboardInterrupt:
        shutdown()
