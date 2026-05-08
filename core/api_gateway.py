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
# POST /api/command — FUSED PIPELINE (File + Text = ONE Task)
# Files → ingress_firewall → nawah_inbox (stored)
# Then: L1 Synthesizer + L2 Dispatcher invoked IMMEDIATELY
# ============================================================
@app.post("/api/command")
async def unified_command(
    command: str = Form(""),
    files: Optional[List[UploadFile]] = File(None),
):
    """
    Unified Command Bar: text + files are FUSED into ONE task.
    Files pass through firewall → saved to nawah_inbox.
    Then L1 + L2 are invoked synchronously with BOTH the instruction and file metadata.
    """
    result = {"status": "received", "uploads": [], "text_task": None}

    accepted_files_meta = []  # Collect metadata for fusion
    command_text = command.strip()

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
                    # SAFE → Move to nawah_inbox for storage
                    inbox_path = os.path.join("nawah_inbox", safe_name)
                    shutil.move(temp_path, inbox_path)
                    accepted_files_meta.append({
                        "file_name": file.filename,
                        "file_path": os.path.abspath(inbox_path),
                        "file_type": os.path.splitext(file.filename)[1].lower().lstrip(".") or "bin",
                        "file_size_bytes": len(content),
                        "security_status": "CLEARED",
                    })
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

    # --- 2. FUSION LOGIC: Route based on what we received ---
    has_files = len(accepted_files_meta) > 0
    has_text = bool(command_text)

    if has_files:
        # === FUSED PATH: File(s) + optional text → ONE task ===
        try:
            from core.synthesizer import TaskSynthesizer, CriticalAPIFailure
            from core.message_bus import TaskBroker
            from core.dispatcher import L2Dispatcher
            import json

            synthesizer = TaskSynthesizer()
            broker = TaskBroker()
            dispatcher = L2Dispatcher()

            # Build instruction
            if has_text:
                instruction = command_text
            else:
                file_names = ", ".join(m["file_name"] for m in accepted_files_meta)
                instruction = f"تحليل الملف(ات): {file_names}"

            # L1: Analyze (with graceful degradation)
            l1_failed = False
            try:
                l1_result = synthesizer.analyze(
                    user_input=instruction,
                    attachments_metadata=accepted_files_meta,
                    source="web_portal",
                )
            except (CriticalAPIFailure, Exception) as l1_err:
                print(f"⚠️ L1 API OFFLINE (FUSED) — تفعيل وضع التحليل المحلي: {l1_err}")
                l1_failed = True
                task_id = str(uuid.uuid4())
                l1_result = {
                    "task_id": task_id,
                    "commander_instruction": instruction,
                    "attachments": accepted_files_meta,
                    "l1_triage": {
                        "intent": "DOCUMENT_ANALYSIS",
                        "recommended_agent": "analyst_agent",
                        "priority": "HIGH",
                        "language": "ar",
                    },
                    "source": "web_portal",
                    "api_fallback": True,
                }

            # Save to outbox
            task_id = l1_result.get("task_id", str(uuid.uuid4()))
            output_filename = f"web_{task_id[:8]}.json"
            output_path = os.path.join("nawah_outbox", output_filename)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(l1_result, f, ensure_ascii=False, indent=4)

            # Register in DB
            broker.register_task(task_id, output_filename, l1_result)

            # L2: Dispatch to agent (agents have graceful degradation)
            dispatch_result = dispatcher.dispatch(l1_result)

            # Save result to DB
            ai_response = dispatch_result.get("message", "")
            dispatch_status = "COMPLETED" if dispatch_result.get("status") == "completed" else "FAILED"
            broker.update_task_result(task_id, dispatch_status, ai_response)

            # Extract triage info for UI
            triage = l1_result.get("l1_triage", {})
            intent_raw = triage.get("intent", "UNKNOWN")
            agent_raw = triage.get("recommended_agent", "general_agent")
            intent = intent_raw.value if hasattr(intent_raw, 'value') else str(intent_raw)
            agent = agent_raw.value if hasattr(agent_raw, 'value') else str(agent_raw)

            result["ai_response"] = ai_response
            result["triage"] = {
                "intent": intent,
                "agent": agent,
                "task_id": task_id,
                "api_fallback": l1_failed,
            }
            result["text_task"] = {
                "status": "accepted",
                "filename": output_filename,
                "message": f"تم دمج الأمر مع الملف(ات) → {agent}" + (" [وضع محلي]" if l1_failed else ""),
            }
            pipeline_tag = "FUSION" if not l1_failed else "FUSION→FALLBACK"
            print(f"🔗 {pipeline_tag}: أمر + {len(accepted_files_meta)} ملف(ات) → مهمة {task_id[:8]}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            result["text_task"] = {
                "status": "error",
                "message": f"فشل المعالجة المباشرة: {e}",
            }

    elif has_text:
        # === TEXT-ONLY PATH: Run L1 + L2 synchronously ===
        try:
            from core.synthesizer import TaskSynthesizer, CriticalAPIFailure
            from core.message_bus import TaskBroker
            from core.dispatcher import L2Dispatcher
            import json as _json

            synthesizer = TaskSynthesizer()
            broker = TaskBroker()
            dispatcher = L2Dispatcher()

            # L1: Analyze text command (may fail if API key invalid)
            l1_failed = False
            try:
                l1_result = synthesizer.analyze(
                    user_input=command_text,
                    attachments_metadata=[],
                    source="web_portal",
                )
            except (CriticalAPIFailure, Exception) as l1_err:
                print(f"⚠️ L1 API OFFLINE — تفعيل وضع التحليل المحلي: {l1_err}")
                l1_failed = True
                # Build fallback triage payload so L2 can still process
                task_id = str(uuid.uuid4())
                l1_result = {
                    "task_id": task_id,
                    "commander_instruction": command_text,
                    "attachments": [],
                    "l1_triage": {
                        "intent": "TEXT_SUMMARIZATION",
                        "recommended_agent": "general_agent",
                        "priority": "MEDIUM",
                        "language": "ar",
                    },
                    "source": "web_portal",
                    "api_fallback": True,
                }

            # Save to outbox
            task_id = l1_result.get("task_id", str(uuid.uuid4()))
            output_filename = f"web_{task_id[:8]}.json"
            output_path = os.path.join("nawah_outbox", output_filename)
            with open(output_path, "w", encoding="utf-8") as f:
                _json.dump(l1_result, f, ensure_ascii=False, indent=4)

            # Register in DB
            broker.register_task(task_id, output_filename, l1_result)

            # L2: Dispatch to agent (agents have their own graceful degradation)
            dispatch_result = dispatcher.dispatch(l1_result)

            # Save result to DB (Feedback Loop)
            ai_response = dispatch_result.get("message", "")
            dispatch_status = "COMPLETED" if dispatch_result.get("status") == "completed" else "FAILED"
            broker.update_task_result(task_id, dispatch_status, ai_response)

            # Extract triage info for UI
            triage = l1_result.get("l1_triage", {})
            intent_raw = triage.get("intent", "UNKNOWN")
            agent_raw = triage.get("recommended_agent", "general_agent")
            intent = intent_raw.value if hasattr(intent_raw, 'value') else str(intent_raw)
            agent = agent_raw.value if hasattr(agent_raw, 'value') else str(agent_raw)

            result["ai_response"] = ai_response
            result["triage"] = {
                "intent": intent,
                "agent": agent,
                "task_id": task_id,
                "api_fallback": l1_failed,
            }
            result["text_task"] = {
                "status": "accepted",
                "filename": output_filename,
                "message": f"تم تحليل الأمر → {agent}" + (" [وضع محلي]" if l1_failed else ""),
            }
            pipeline_tag = "WEB→L1→L2→DB" if not l1_failed else "WEB→FALLBACK→L2→DB"
            print(f"🔗 {pipeline_tag}: أمر نصي → مهمة {task_id[:8]} → {agent} → {dispatch_status}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            result["text_task"] = {
                "status": "error",
                "message": f"فشل المعالجة المباشرة: {e}",
            }

    # Summary message
    accepted_count = sum(1 for u in result["uploads"] if u["status"] == "accepted")
    blocked_count = sum(1 for u in result["uploads"] if u["status"] == "blocked")
    text_ok = result["text_task"] and result["text_task"]["status"] == "accepted"

    parts = []
    if text_ok:
        parts.append("تم استلام الأمر")
    if accepted_count > 0:
        parts.append(f"تم قبول {accepted_count} ملف(ات)")
    if blocked_count > 0:
        parts.append(f"تم حجر {blocked_count} ملف(ات) خطيرة")

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
# POST /api/v1/source_candidates — UI-Dictated Sourcing
# ============================================================
@app.post("/api/v1/source_candidates")
async def source_candidates(payload: dict):
    """
    UI-dictated candidate sourcing endpoint.
    Accepts: {"jd_id": "...", "source": "EMAIL_ONLY"|"LINKEDIN"|"BOTH"|"AUTO", "max_candidates": int}
    The system STRICTLY obeys source and max_candidates.
    """
    from core.tools.sourcing_tools import get_sourcing_tools
    from core.tools.erp_connector import get_erp_tool

    jd_id = payload.get("jd_id", "")
    source = payload.get("source", "AUTO").upper()
    max_candidates = min(payload.get("max_candidates", 5), 20)  # Hard cap at 20

    if source not in ("EMAIL_ONLY", "LINKEDIN", "BOTH", "AUTO"):
        return JSONResponse(status_code=400, content={
            "error": f"Invalid source: {source}. Must be EMAIL_ONLY, LINKEDIN, BOTH, or AUTO."
        })

    sourcing = get_sourcing_tools()
    erp = get_erp_tool()

    # Get JD keywords (from ERP or fallback)
    keywords = ["Python", "AI", "LangChain"]
    if jd_id:
        try:
            jd_data = erp.fetch_job_description(jd_id)
            keywords = jd_data.get("requirements", {}).get("required_skills", keywords)
        except Exception:
            pass

    result = sourcing.execute_dual_sourcing_strategy(
        keywords=keywords, max_results=max_candidates, source=source
    )

    return {
        "status": "completed",
        "jd_id": jd_id,
        "source_mode": source,
        "max_candidates_requested": max_candidates,
        "candidates_returned": len(result["final_candidates"]),
        "strategy_used": result["strategy"],
        "external_api_calls": 1 if result["external_search_triggered"] else 0,
        "cost_savings": result["cost_savings"],
        "candidates": result["final_candidates"],
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================
# GET /api/health
# ============================================================
@app.get("/api/health")
def health_check():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}


# ============================================================
# SERVE FRONTEND (web_root/) — React SPA via Vite Build
# ============================================================
WEB_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web_root")
ASSETS_DIR = os.path.join(WEB_ROOT, "assets")

if os.path.exists(WEB_ROOT):
    # Serve /assets/ for Vite's hashed JS/CSS bundles
    if os.path.exists(ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

    # Serve nawah_logo if it exists at project root level
    LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nawah_logo.png")
    if os.path.exists(LOGO_PATH):
        @app.get("/nawah_logo.png")
        def serve_logo():
            return FileResponse(LOGO_PATH)

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(WEB_ROOT, "index.html"))

    # SPA catch-all: any unmatched GET returns index.html (for React Router)
    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        # Don't catch API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = os.path.join(WEB_ROOT, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(WEB_ROOT, "index.html"))
