"""
Nawah API Gateway — FastAPI Central Nervous System
Serves REST API + static frontend from web_root/

REAL PIPELINE: Web uploads drop into nawah_inbox like email.
The Watcher picks them up → Synthesizer → JSON → TaskBroker.
"""
import os
import sys
import uuid
import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# APP
# ============================================================
app = FastAPI(title="Nawah API Gateway", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# DIRECTORIES
# ============================================================
for d in ["nawah_inbox", "nawah_outbox", "nawah_processed", "nawah_quarantine", "nawah_logs", "temp"]:
    os.makedirs(d, exist_ok=True)


# ============================================================
# GET /api/stats — REAL DB + REAL FILESYSTEM
# ============================================================
@app.get("/api/stats")
def get_stats():
    """Fetch REAL stats from nawah_state.db via TaskBroker."""
    try:
        from core.message_bus import TaskBroker
        broker = TaskBroker()
        stats = broker.get_stats()
        recent = broker.get_recent_tasks(limit=5)
    except Exception:
        stats = {}
        recent = []

    def safe_count(path, ext=None):
        try:
            if not os.path.exists(path):
                return 0
            files = os.listdir(path)
            if ext:
                files = [f for f in files if f.endswith(ext)]
            return len(files)
        except Exception:
            return 0

    return {
        "db": {
            "pending": stats.get("PENDING", 0),
            "in_progress": stats.get("IN_PROGRESS", 0),
            "completed": stats.get("COMPLETED", 0),
            "failed": stats.get("FAILED", 0),
        },
        "fs": {
            "inbox": safe_count("nawah_inbox"),
            "analyzed": safe_count("nawah_outbox", ext=".json"),
            "processed": safe_count("nawah_processed"),
            "quarantine": safe_count("nawah_quarantine"),
        },
        "recent": recent,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================
# POST /api/command — REAL PIPELINE (Equal Citizen)
# Files → ingress_firewall → nawah_inbox (Watcher picks up)
# Text → saved as .txt → nawah_inbox (Watcher picks up)
# ============================================================
@app.post("/api/command")
async def unified_command(
    command: str = Form(""),
    files: Optional[List[UploadFile]] = File(None),
):
    """
    Unified Command Bar: text + files enter the REAL pipeline.
    Files go to nawah_inbox. The Watcher/Synthesizer processes them.
    NO MOCKS. Real DB. Real L1 analysis.
    """
    result = {"status": "received", "uploads": [], "text_task": None}

    # --- 1. Process file uploads through ingress_firewall → nawah_inbox ---
    if files:
        for file in files:
            if not file.filename:
                continue

            temp_dir = os.path.join("temp", "web_uploads")
            os.makedirs(temp_dir, exist_ok=True)
            safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
            temp_path = os.path.join(temp_dir, safe_name)

            try:
                content = await file.read()
                with open(temp_path, "wb") as f:
                    f.write(content)

                # === INGRESS FIREWALL — Same pipeline as email ===
                from core.ingress_firewall import scan_file as fw_scan, scan_and_quarantine
                verdict = fw_scan(temp_path, source="web_ui")

                if not verdict.allowed:
                    scan_and_quarantine(temp_path, source="web_ui")
                    result["uploads"].append({
                        "filename": file.filename,
                        "status": "blocked",
                        "reason": verdict.reason,
                    })
                else:
                    # SAFE → Move to nawah_inbox for the Watcher to pick up
                    inbox_path = os.path.join("nawah_inbox", safe_name)
                    shutil.move(temp_path, inbox_path)
                    result["uploads"].append({
                        "filename": file.filename,
                        "status": "accepted",
                        "destination": "nawah_inbox",
                        "size": len(content),
                    })
                    print(f"📥 بوابة الويب: ملف مقبول → {safe_name} → nawah_inbox")

            except Exception as e:
                result["uploads"].append({
                    "filename": file.filename,
                    "status": "error",
                    "reason": str(e),
                })
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    # --- 2. Process text command → save as .txt → nawah_inbox ---
    if command.strip():
        text_filename = f"web_cmd_{uuid.uuid4().hex[:8]}.txt"
        text_path = os.path.join("nawah_inbox", text_filename)
        try:
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(command.strip())
            result["text_task"] = {
                "status": "accepted",
                "filename": text_filename,
                "message": "تم إيداع الأمر في صندوق الوارد. سيتم تحليله تلقائياً.",
            }
            print(f"📥 بوابة الويب: أمر نصي → {text_filename} → nawah_inbox")
        except Exception as e:
            result["text_task"] = {
                "status": "error",
                "message": f"فشل حفظ الأمر: {e}",
            }

    # Summary message
    accepted_files = sum(1 for u in result["uploads"] if u["status"] == "accepted")
    blocked_files = sum(1 for u in result["uploads"] if u["status"] == "blocked")
    text_ok = result["text_task"] and result["text_task"]["status"] == "accepted"

    parts = []
    if text_ok:
        parts.append("تم استلام الأمر")
    if accepted_files > 0:
        parts.append(f"تم قبول {accepted_files} ملف(ات)")
    if blocked_files > 0:
        parts.append(f"تم حجر {blocked_files} ملف(ات) خطيرة")

    result["summary"] = " | ".join(parts) if parts else "لا يوجد محتوى للمعالجة"
    result["message"] = "تم الإيداع في النظام بنجاح. الحارس الرقابي سيعالج المهام تلقائياً."

    return result


# ============================================================
# POST /api/upload — Legacy single-file upload (backward compat)
# ============================================================
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Legacy single-file upload. Same firewall pipeline."""
    temp_dir = os.path.join("temp", "web_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    temp_path = os.path.join(temp_dir, safe_name)

    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save: {e}")

    try:
        from core.ingress_firewall import scan_file as fw_scan, scan_and_quarantine
        verdict = fw_scan(temp_path, source="web_ui")

        if not verdict.allowed:
            scan_and_quarantine(temp_path, source="web_ui")
            return JSONResponse(status_code=403, content={
                "status": "blocked", "filename": file.filename, "reason": verdict.reason,
            })
        else:
            inbox_path = os.path.join("nawah_inbox", safe_name)
            shutil.move(temp_path, inbox_path)
            return {"status": "accepted", "filename": file.filename, "destination": "nawah_inbox", "size": len(content)}
    except Exception as e:
        try: os.remove(temp_path)
        except: pass
        raise HTTPException(status_code=500, detail=f"Scan error: {e}")


# ============================================================
# GET /api/health
# ============================================================
@app.get("/api/health")
def health_check():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}


# ============================================================
# SERVE FRONTEND (web_root/)
# ============================================================
WEB_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web_root")
if os.path.exists(WEB_ROOT):
    app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(WEB_ROOT, "index.html"))
