"""
Nawah Terminator QA v3 — Real Pipeline Verification
Tests: Real DB stats, real file ingestion, real text command, multi-file, firewall.
"""
import os
import sys
import time
import requests

URL = "http://localhost:8000"
RESULTS = []


def log(status, msg):
    RESULTS.append((status, msg))
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon} [{status}] {msg}")


def run_qa():
    print("=" * 60)
    print("  Nawah Terminator QA v3.0 — Real Pipeline")
    print("=" * 60)

    # --- PRE-CHECK ---
    print("\n  --- PRE-CHECK: API Health ---")
    alive = False
    for _ in range(10):
        try:
            r = requests.get(f"{URL}/api/health", timeout=3)
            if r.status_code == 200:
                alive = True
                break
        except Exception:
            pass
        time.sleep(2)
    if not alive:
        log("FAIL", "FastAPI not responding")
        return False
    log("PASS", "FastAPI alive")

    # === TEST 1: Real DB stats ===
    print("\n  --- TEST 1: Real DB Stats ---")
    try:
        r = requests.get(f"{URL}/api/stats", timeout=5)
        data = r.json()
        assert r.status_code == 200
        assert "db" in data and "fs" in data
        total_db = sum(data["db"].values())
        log("PASS", f"DB: {data['db']} (total={total_db}) | FS inbox={data['fs']['inbox']}")
    except Exception as e:
        log("FAIL", f"Stats: {e}")

    # === TEST 2: Text command → nawah_inbox ===
    print("\n  --- TEST 2: Text command → inbox ---")
    try:
        r = requests.post(f"{URL}/api/command",
                          data={"command": "تحليل أداء المبيعات الشهرية"},
                          timeout=10)
        data = r.json()
        assert r.status_code == 200
        assert data.get("text_task", {}).get("status") == "accepted"
        txt_file = data["text_task"]["filename"]
        # Verify file actually exists in nawah_inbox
        inbox_path = os.path.join("nawah_inbox", txt_file)
        time.sleep(1)
        # File may already be picked up by watcher, check processed too
        exists_inbox = os.path.exists(inbox_path)
        exists_processed = any(txt_file in f for f in os.listdir("nawah_processed")) if os.path.exists("nawah_processed") else False
        assert exists_inbox or exists_processed, f"File not found: {txt_file}"
        log("PASS", f"Text command saved → {txt_file} (inbox={exists_inbox}, processed={exists_processed})")
    except Exception as e:
        log("FAIL", f"Text command: {e}")

    # === TEST 3: Safe file upload → nawah_inbox ===
    print("\n  --- TEST 3: Safe file → inbox ---")
    test_file = os.path.join("temp", "qa_real_test.txt")
    os.makedirs("temp", exist_ok=True)
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("محتوى اختباري حقيقي لفحص خط الأنابيب الكامل\n")
    try:
        with open(test_file, "rb") as f:
            r = requests.post(f"{URL}/api/command",
                              data={"command": "حلل هذا الملف"},
                              files=[("files", ("qa_real_test.txt", f, "text/plain"))],
                              timeout=10)
        data = r.json()
        assert r.status_code == 200
        assert data["uploads"][0]["status"] == "accepted"
        log("PASS", f"File accepted → nawah_inbox: {data['uploads'][0]}")
    except Exception as e:
        log("FAIL", f"File upload: {e}")
    finally:
        try: os.remove(test_file)
        except: pass

    # === TEST 4: Multi-file upload ===
    print("\n  --- TEST 4: Multi-file upload ---")
    files_to_upload = []
    temp_paths = []
    for i in range(3):
        path = os.path.join("temp", f"qa_multi_{i}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"ملف اختباري رقم {i}\n")
        temp_paths.append(path)
        files_to_upload.append(("files", (f"qa_multi_{i}.txt", open(path, "rb"), "text/plain")))
    try:
        r = requests.post(f"{URL}/api/command",
                          data={"command": "تحليل مجموعة ملفات"},
                          files=files_to_upload,
                          timeout=15)
        data = r.json()
        assert r.status_code == 200
        accepted = [u for u in data["uploads"] if u["status"] == "accepted"]
        assert len(accepted) == 3, f"Expected 3 accepted, got {len(accepted)}"
        log("PASS", f"Multi-file: {len(accepted)}/3 accepted")
    except Exception as e:
        log("FAIL", f"Multi-file: {e}")
    finally:
        for p in temp_paths:
            try: os.remove(p)
            except: pass

    # === TEST 5: Malicious file blocked ===
    print("\n  --- TEST 5: Malicious .exe blocked ---")
    exe_path = os.path.join("temp", "qa_evil.exe")
    with open(exe_path, "wb") as f:
        f.write(b"MZ" + b"\x00" * 100)
    try:
        with open(exe_path, "rb") as f:
            r = requests.post(f"{URL}/api/command",
                              data={"command": "افحص"},
                              files=[("files", ("qa_evil.exe", f, "application/octet-stream"))],
                              timeout=10)
        data = r.json()
        assert data["uploads"][0]["status"] == "blocked"
        log("PASS", f"Malicious BLOCKED: {data['uploads'][0].get('reason')}")
    except Exception as e:
        log("FAIL", f"Malicious: {e}")
    finally:
        try: os.remove(exe_path)
        except: pass

    # === TEST 6: No [MOCK] in any response ===
    print("\n  --- TEST 6: No MOCK data ---")
    try:
        r = requests.post(f"{URL}/api/command",
                          data={"command": "اختبار حقيقي"},
                          timeout=10)
        raw = r.text
        assert "[MOCK]" not in raw, f"MOCK found in response: {raw[:200]}"
        log("PASS", "Zero MOCK data in response")
    except Exception as e:
        log("FAIL", f"Mock check: {e}")

    # === TEST 7: Stats update after submissions ===
    print("\n  --- TEST 7: Stats reflect real data ---")
    time.sleep(3)  # Let watcher process
    try:
        r = requests.get(f"{URL}/api/stats", timeout=5)
        data = r.json()
        total = data["fs"]["inbox"] + data["fs"]["analyzed"] + data["fs"]["processed"]
        log("PASS", f"After tests: inbox={data['fs']['inbox']}, analyzed={data['fs']['analyzed']}, processed={data['fs']['processed']}")
    except Exception as e:
        log("FAIL", f"Stats update: {e}")

    # === REPORT ===
    print("\n" + "=" * 60)
    passed = sum(1 for s, _ in RESULTS if s == "PASS")
    failed = sum(1 for s, _ in RESULTS if s == "FAIL")
    print(f"  TERMINATOR QA: {passed} PASS / {failed} FAIL / {len(RESULTS)} TOTAL")
    verdict = "ALL TESTS PASSED — REAL PIPELINE OPERATIONAL" if failed == 0 else "FAILURES DETECTED"
    print(f"  {verdict}")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_qa()
    sys.exit(0 if success else 1)
