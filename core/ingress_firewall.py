"""
Nawah Omni-Gate — Unified Ingress Firewall

Single centralized security checkpoint for ALL input sources:
- Shared Folder (watcher.py)
- Email Attachments (email_watcher.py)
- Web UI Uploads (app.py)

Every file MUST pass through scan_file() before reaching L1.
"""

import os
import shutil
import uuid

QUARANTINE_DIR = "nawah_quarantine"
os.makedirs(QUARANTINE_DIR, exist_ok=True)

# === SECURITY RULES ===
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.csv', '.docx', '.xlsx', '.xls', '.png', '.jpg', '.jpeg'}
MAX_FILE_SIZE_MB = 20

# Magic byte signatures for MIME-type sniffing (catches disguised executables)
DANGEROUS_MAGIC_BYTES = {
    b'MZ': 'Windows Executable (PE/EXE/DLL)',
    b'\x7fELF': 'Linux Executable (ELF)',
    b'#!/': 'Shell Script',
    b'PK\x03\x04': None,  # ZIP — allowed (DOCX/XLSX are ZIPs), will be None-checked
}

# Executables disguised as documents — these magic bytes are ALWAYS blocked
BLOCKED_MAGIC_BYTES = {
    b'MZ': 'Windows Executable (PE/EXE/DLL)',
    b'\x7fELF': 'Linux Executable (ELF)',
    b'\xcf\xfa\xed\xfe': 'macOS Mach-O Binary',
    b'\xfe\xed\xfa\xcf': 'macOS Mach-O Binary (64-bit)',
    b'\xca\xfe\xba\xbe': 'Java Class / macOS Universal Binary',
}


class IngressVerdict:
    """Result of an Omni-Gate scan."""

    def __init__(self, allowed, reason="", source="unknown"):
        self.allowed = allowed
        self.reason = reason
        self.source = source

    def __bool__(self):
        return self.allowed

    def __repr__(self):
        status = "ALLOWED" if self.allowed else "BLOCKED"
        return f"IngressVerdict({status}: {self.reason})"


def scan_file(filepath, source="unknown"):
    """
    Unified security scan for any incoming file.

    Args:
        filepath: Absolute or relative path to the file
        source: Origin identifier ('folder', 'email', 'web_ui')

    Returns:
        IngressVerdict — allowed=True if file passes all checks
    """
    filename = os.path.basename(filepath)

    # 1. PATH TRAVERSAL CHECK
    if '..' in filename or '/' in filename or '\\' in filename:
        return IngressVerdict(False, f"Path traversal attempt: {filename}", source)

    # 2. EXTENSION CHECK
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return IngressVerdict(False, f"Blocked extension: {ext}", source)

    # 3. FILE EXISTS CHECK
    if not os.path.exists(filepath):
        return IngressVerdict(False, f"File does not exist: {filename}", source)

    # 4. SIZE CHECK
    try:
        size_bytes = os.path.getsize(filepath)
        size_mb = size_bytes / (1024 * 1024)
    except OSError:
        return IngressVerdict(False, f"Cannot read file size: {filename}", source)

    if size_mb > MAX_FILE_SIZE_MB:
        return IngressVerdict(False, f"File too large: {size_mb:.1f}MB > {MAX_FILE_SIZE_MB}MB", source)

    if size_bytes == 0:
        return IngressVerdict(False, f"Empty file: {filename}", source)

    # 5. MAGIC BYTE SNIFFING (catches disguised executables)
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
    except (OSError, PermissionError):
        return IngressVerdict(False, f"Cannot read file header: {filename}", source)

    for magic, label in BLOCKED_MAGIC_BYTES.items():
        if header.startswith(magic):
            return IngressVerdict(
                False,
                f"Disguised malware detected: {filename} has {label} header (magic: {magic[:4]})",
                source
            )

    # ALL CHECKS PASSED
    return IngressVerdict(True, "All security checks passed", source)


def scan_and_quarantine(filepath, source="unknown"):
    """
    Scan a file and auto-quarantine if it fails.

    Returns:
        IngressVerdict — if not allowed, the file has already been moved to quarantine
    """
    verdict = scan_file(filepath, source)
    if not verdict:
        print(f"🛡️ Omni-Gate [{source}]: رفض {os.path.basename(filepath)} — {verdict.reason}")
        quarantine_file(filepath, reason=verdict.reason)
    return verdict


def quarantine_file(filepath, reason="unknown"):
    """Move a failed file to quarantine instead of leaving it as orphan."""
    filename = os.path.basename(filepath)
    dest = os.path.join(QUARANTINE_DIR, f"{uuid.uuid4().hex[:8]}_{filename}")
    try:
        if os.path.exists(filepath):
            shutil.move(filepath, dest)
            print(f"🔒 حجر: {filename} → {os.path.basename(dest)} — السبب: {reason}")
    except Exception as e:
        print(f"⚠️ فشل الحجر: {filename} — {e}")
