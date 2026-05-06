import os
import time
import json
import shutil
import uuid
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from core.synthesizer import TaskSynthesizer
from core.vision import DocumentReader
from core.message_bus import TaskBroker
from core.dispatcher import L2Dispatcher

INBOX_DIR = "nawah_inbox"
OUTBOX_DIR = "nawah_outbox"
PROCESSED_DIR = "nawah_processed"
QUARANTINE_DIR = "nawah_quarantine"
ASSETS_DIR = "nawah_assets"

ALL_DIRS = [INBOX_DIR, OUTBOX_DIR, PROCESSED_DIR, QUARANTINE_DIR, ASSETS_DIR]

def ensure_directories():
    """Dynamically recreate all essential directories (survives mid-operation deletion)."""
    for d in ALL_DIRS:
        os.makedirs(d, exist_ok=True)

ensure_directories()

ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.csv', '.docx', '.xlsx', '.xls', '.png', '.jpg', '.jpeg'}
MAX_FILE_SIZE_MB = 20
FILE_STABLE_CHECKS = 3
FILE_STABLE_INTERVAL = 1.0


def wait_until_file_is_ready(filepath, checks=FILE_STABLE_CHECKS, interval=FILE_STABLE_INTERVAL):
    """Wait until a file's size stabilizes and it can be opened exclusively."""
    last_size = -1
    stable_count = 0
    for _ in range(checks * 3):  # Max total wait = checks * 3 * interval
        try:
            current_size = os.path.getsize(filepath)
        except OSError:
            return False
        if current_size == last_size and current_size > 0:
            stable_count += 1
            if stable_count >= checks:
                # Verify we can actually open it
                try:
                    with open(filepath, 'rb') as f:
                        f.read(1)
                    return True
                except (OSError, PermissionError):
                    pass
        else:
            stable_count = 0
        last_size = current_size
        time.sleep(interval)
    return False


def quarantine_file(filepath, reason="unknown"):
    """Move a failed file to quarantine instead of leaving it as orphan."""
    filename = os.path.basename(filepath)
    dest = os.path.join(QUARANTINE_DIR, f"{uuid.uuid4().hex[:8]}_{filename}")
    try:
        shutil.move(filepath, dest)
        print(f"🔒 تم نقل الملف للحجر: {filename} — السبب: {reason}")
    except Exception as e:
        print(f"⚠️ فشل نقل الملف للحجر: {filename} — {e}")


class NawahEventHandler(FileSystemEventHandler):

    def __init__(self):
        super().__init__()
        self.synthesizer = TaskSynthesizer()
        self.reader = DocumentReader()
        self.broker = TaskBroker()
        self.dispatcher = L2Dispatcher()

    def process_file(self, filepath):
        ensure_directories()  # Survive mid-operation directory deletion
        if not os.path.exists(filepath):
            return

        # OMNI-GATE: Unified security scan (extension + size + magic bytes + path traversal)
        from core.ingress_firewall import scan_and_quarantine
        verdict = scan_and_quarantine(filepath, source="folder")
        if not verdict:
            return

        filename = os.path.basename(filepath)

        try:
            with open(filepath, 'rb') as f:
                docs_text = self.reader.read_files([f])

            if docs_text:
                # Strip BOM character injected by some editors/PowerShell
                docs_text = docs_text.lstrip('\ufeff')
                query = f"ملف آلي جديد للتحليل:\n{docs_text}"
                _, fext = os.path.splitext(filename)
                file_meta = [{
                    "filename": filename,
                    "filepath": os.path.abspath(filepath),
                    "filetype": fext.lower().lstrip('.') or "bin",
                    "size_bytes": os.path.getsize(filepath) if os.path.exists(filepath) else 0
                }]
                result = self.synthesizer.analyze(query, file_meta, source="folder")

                # Use task_id from Military Task Order if available
                task_id = result.get("task_id", os.path.splitext(filename)[0])
                output_filename = filename + ".json"
                output_path = os.path.join(OUTBOX_DIR, output_filename)
                with open(output_path, 'w', encoding='utf-8') as out:
                    json.dump(result, out, ensure_ascii=False, indent=4)

                # Register task in L2 message bus
                self.broker.register_task(task_id, output_filename, result)

                # L2 Dispatch — Route to appropriate agent
                dispatch_result = self.dispatcher.dispatch(result)

                # FEEDBACK LOOP: Save agent result to DB
                ai_response = dispatch_result.get("message", "")
                dispatch_status = "COMPLETED" if dispatch_result.get("status") == "completed" else "FAILED"
                self.broker.update_task_result(task_id, dispatch_status, ai_response)
                print(f"🔗 FOLDER→L1→L2→DB: مهمة {task_id[:8]} → {dispatch_result.get('agent', '?')} → {dispatch_status}")

                # Prevent archive collision with UUID suffix
                dest_path = os.path.join(PROCESSED_DIR, filename)
                if os.path.exists(dest_path):
                    name, fext = os.path.splitext(filename)
                    dest_path = os.path.join(PROCESSED_DIR, f"{name}_{uuid.uuid4().hex[:8]}{fext}")

                shutil.move(filepath, dest_path)
                print(f"✅ الحارس الرقابي: تمت أتمتة الملف ونقله للأرشيف [{filename}]")
            else:
                print(f"⚠️ لم يتم استخراج نص من الملف: {filename}")

        except Exception as e:
            print(f"❌ خطأ في معالجة الملف {filename}: {e}")
            quarantine_file(filepath, reason=str(e))

    def on_created(self, event):
        if event.is_directory:
            return

        filepath = event.src_path
        filename = os.path.basename(filepath)

        # Wait for file to be fully written
        if not wait_until_file_is_ready(filepath):
            print(f"⚠️ الملف غير مستقر أو محجوز: {filename}")
            return

        self.process_file(filepath)

    def initial_sweep(self):
        print("🧹 جاري إجراء المسح الاستهلالي للملفات المتأخرة...")
        for filename in os.listdir(INBOX_DIR):
            filepath = os.path.join(INBOX_DIR, filename)
            if os.path.isfile(filepath):
                self.process_file(filepath)


if __name__ == "__main__":
    handler = NawahEventHandler()
    handler.initial_sweep()

    print("👁️ نَوَاة: الحارس الرقابي يعمل في الخلفية... بانتظار الملفات")

    observer = Observer()
    observer.schedule(handler, INBOX_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
