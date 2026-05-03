/**
 * Nawah Titanium — Frontend Controller (Light Theme Only)
 * Unified Command Bar: text + file → /api/command
 * Radar: auto-refresh + manual button
 */

const API = '';

// ============================================================
// STATS FETCHER
// ============================================================
async function refreshStats() {
    const icon = document.getElementById('refresh-icon');
    if (icon) icon.classList.add('spin');

    try {
        const res = await fetch(`${API}/api/stats`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // DB stats
        document.getElementById('stat-pending').textContent = data.db.pending;
        document.getElementById('stat-progress').textContent = data.db.in_progress;
        document.getElementById('stat-completed').textContent = data.db.completed;
        document.getElementById('stat-failed').textContent = data.db.failed;

        // FS stats
        document.getElementById('fs-inbox').textContent = data.fs.inbox;
        document.getElementById('fs-analyzed').textContent = data.fs.analyzed;
        document.getElementById('fs-processed').textContent = data.fs.processed;
        document.getElementById('fs-quarantine').textContent = data.fs.quarantine;

        // Quarantine
        const qc = data.fs.quarantine;
        document.getElementById('quarantine-info').textContent =
            qc === 0 ? '🔒 الحجر: 🟢 نظيف' : `🔒 الحجر: 🔴 ${qc} ملف`;

        // Recent tasks
        const container = document.getElementById('recent-tasks');
        if (data.recent && data.recent.length > 0) {
            container.innerHTML = data.recent.map(t => {
                const icon = {PENDING:'⏳', IN_PROGRESS:'🔄', COMPLETED:'✅', FAILED:'❌'}[t.state] || '❓';
                const intent = (t.intent || '—').substring(0, 35);
                return `<div class="task-item">${icon} ${intent} — ${t.complexity || '—'}</div>`;
            }).join('');
        } else {
            container.innerHTML = '<p class="text-slate-400 text-sm text-center py-2">لا توجد مهام بعد</p>';
        }
    } catch (err) {
        console.error('Stats error:', err);
    } finally {
        setTimeout(() => { if (icon) icon.classList.remove('spin'); }, 600);
    }
}

// Auto-refresh every 5s + initial load
setInterval(refreshStats, 5000);
refreshStats();

// ============================================================
// FILE ATTACHMENT
// ============================================================
const fileInput = document.getElementById('file-input');
const fileBadge = document.getElementById('file-badge');
const fileBadgeName = document.getElementById('file-badge-name');

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        const names = Array.from(fileInput.files).map(f => f.name).join(', ');
        fileBadgeName.textContent = `📎 ${names}`;
        fileBadge.classList.remove('hidden');
    }
});

function clearFile() {
    fileInput.value = '';
    fileBadge.classList.add('hidden');
    fileBadgeName.textContent = '';
}

// ============================================================
// UNIFIED COMMAND SUBMIT
// ============================================================
async function submitCommand() {
    const input = document.getElementById('command-input');
    const text = input.value.trim();
    const files = fileInput.files;

    if (!text && files.length === 0) return;

    const responses = document.getElementById('command-responses');
    const warRoom = document.getElementById('war-room-content');

    // Hide placeholder
    if (warRoom) warRoom.style.display = 'none';

    // Show user command
    const userCard = document.createElement('div');
    userCard.className = 'response-card';
    let userHTML = '';
    if (text) userHTML += `<div class="font-bold text-brand-navy mb-1">👤 الأمر:</div><div class="text-slate-700">${escapeHtml(text)}</div>`;
    if (files.length > 0) {
        const names = Array.from(files).map(f => `📎 ${escapeHtml(f.name)}`).join(' · ');
        userHTML += `<div class="text-sm text-slate-500 mt-1">${names}</div>`;
    }
    userCard.innerHTML = userHTML;
    responses.appendChild(userCard);

    // Process
    const resultCard = document.createElement('div');
    resultCard.className = 'response-card';
    resultCard.innerHTML = '<div class="text-brand-blue">⏳ جاري المعالجة...</div>';
    responses.appendChild(resultCard);

    try {
        const formData = new FormData();
        formData.append('command', text || '');
        if (files.length > 0) {
            for (const f of files) {
                formData.append('files', f);
            }
        }

        const res = await fetch(`${API}/api/command`, {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();

        if (res.ok) {
            let html = '';

            // Summary message
            if (data.summary) {
                html += `<div class="font-bold text-brand-green mb-2">✅ ${escapeHtml(data.summary)}</div>`;
            }
            if (data.message) {
                html += `<div class="text-sm text-slate-600 mb-2">${escapeHtml(data.message)}</div>`;
            }

            // Text task status
            if (data.text_task && data.text_task.status === 'accepted') {
                html += `<div class="text-sm text-brand-blue mb-1">📝 ${escapeHtml(data.text_task.message)}</div>`;
                html += `<div class="text-xs text-slate-400">الملف: ${escapeHtml(data.text_task.filename)}</div>`;
            }

            // File upload results
            if (data.uploads && data.uploads.length > 0) {
                html += `<div class="mt-2 flex flex-wrap gap-1">`;
                for (const u of data.uploads) {
                    if (u.status === 'accepted') {
                        html += `<span class="upload-badge accepted">✅ ${escapeHtml(u.filename)}</span>`;
                    } else if (u.status === 'blocked') {
                        html += `<span class="upload-badge blocked">🛡️ ${escapeHtml(u.filename)}: ${escapeHtml(u.reason || 'محجور')}</span>`;
                    }
                }
                html += `</div>`;
            }

            resultCard.className = 'response-card success';
            resultCard.innerHTML = html;
        } else {
            resultCard.className = 'response-card error';
            resultCard.innerHTML = `<div class="text-red-600">❌ خطأ: ${escapeHtml(data.detail || 'غير معروف')}</div>`;
        }
    } catch (err) {
        resultCard.className = 'response-card error';
        resultCard.innerHTML = `<div class="text-red-600">❌ فشل الاتصال بالخادم</div>`;
    }

    // Reset
    input.value = '';
    clearFile();
    setTimeout(refreshStats, 1500);

    // Scroll to bottom
    resultCard.scrollIntoView({ behavior: 'smooth' });
}

// Enter key submits
document.getElementById('command-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        submitCommand();
    }
});

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
