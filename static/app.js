'use strict';

// ── Backend URL detection ───────────────────────────────────────────────────
// When hosted on GitHub Pages the user must supply the Replit backend URL.
// When running locally the same origin is used.
const IS_GITHUB_PAGES = location.hostname.includes('github.io') ||
                        location.hostname.includes('github.com');

function getBackendBase() {
  if (!IS_GITHUB_PAGES) return '';           // same-origin (local dev / Replit)
  const saved = localStorage.getItem('backendUrl') || '';
  return saved.replace(/\/$/, '');
}

function api(path) {
  return getBackendBase() + path;
}

// ── State ──────────────────────────────────────────────────────────────────
const state = { jobId: null, polling: null };

// ── DOM refs ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const dropZone     = $('drop-zone');
const fileInput    = $('file-input');
const fileNameEl   = $('file-name');
const btnUpload    = $('btn-upload');
const btnProcess   = $('btn-process');
const btnGithub    = $('btn-github');
const btnRetry     = $('btn-retry');
const btnClearLog  = $('btn-clear-log');
const secConfig    = $('sec-config');
const secProcess   = $('sec-process');
const secResults   = $('sec-results');
const secGithub    = $('sec-github');
const tagFilename  = $('tag-filename');
const progressWrap = $('progress-wrap');
const progressFill = $('progress-fill');
const progressPct  = $('progress-pct');
const logBox       = $('log-box');
const logContent   = $('log-content');
const statsRow     = $('stats-row');
const previewsGrid = $('previews-grid');
const downloadRow  = $('download-row');
const errorBanner  = $('error-banner');
const errorMsg     = $('error-msg');
const githubResult = $('github-result');

// ── Show backend config section only on GitHub Pages ──────────────────────
if (IS_GITHUB_PAGES && secConfig) {
  secConfig.style.display = '';
  const inp = $('backend-url-input');
  if (inp) {
    inp.value = localStorage.getItem('backendUrl') || '';
    inp.addEventListener('change', () => {
      localStorage.setItem('backendUrl', inp.value.trim());
    });
  }
  const btnSave = $('btn-save-backend');
  if (btnSave) {
    btnSave.addEventListener('click', () => {
      const val = ($('backend-url-input').value || '').trim().replace(/\/$/, '');
      localStorage.setItem('backendUrl', val);
      btnSave.textContent = '✅ تم الحفظ';
      setTimeout(() => { btnSave.textContent = 'حفظ'; }, 2000);
    });
  }
}

// ── File selection ─────────────────────────────────────────────────────────
let selectedFile = null;

function setFile(file) {
  if (!file || !file.name.toLowerCase().endsWith('.pptx')) {
    alert('يُقبل فقط ملف .pptx');
    return;
  }
  selectedFile = file;
  fileNameEl.textContent = file.name;
  btnUpload.disabled = false;
}

fileInput.addEventListener('change', () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });
dropZone.addEventListener('click',     () => fileInput.click());
dropZone.addEventListener('dragover',  e  => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});

// ── Upload ─────────────────────────────────────────────────────────────────
btnUpload.addEventListener('click', async () => {
  if (!selectedFile) return;
  if (IS_GITHUB_PAGES && !getBackendBase()) {
    alert('أدخل رابط الخادم (Backend URL) أولاً وانقر حفظ.');
    secConfig.scrollIntoView({ behavior: 'smooth' });
    return;
  }

  btnUpload.disabled = true;
  btnUpload.innerHTML = '<span class="spinner"></span> جارٍ الرفع…';

  const form = new FormData();
  form.append('file', selectedFile);

  try {
    const res  = await fetch(api('/api/upload'), { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');

    state.jobId = data.job_id;
    tagFilename.textContent = data.filename;
    secProcess.style.display = '';
    secProcess.scrollIntoView({ behavior: 'smooth' });
    btnUpload.textContent = '⬆ رفع الملف';
    btnUpload.disabled = false;
  } catch (err) {
    alert('فشل الرفع: ' + err.message);
    btnUpload.disabled = false;
    btnUpload.textContent = '⬆ رفع الملف';
  }
});

// ── Process ────────────────────────────────────────────────────────────────
btnProcess.addEventListener('click', async () => {
  if (!state.jobId) return;
  resetResults();
  btnProcess.disabled = true;
  btnProcess.innerHTML = '<span class="spinner"></span> جارٍ التحليل…';
  progressWrap.style.display = '';
  logBox.style.display = '';
  setProgress(0);

  try {
    const res  = await fetch(api(`/api/process/${state.jobId}`), { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Process failed');
    startPolling();
  } catch (err) {
    showError(err.message);
    btnProcess.disabled = false;
    btnProcess.textContent = '▶ بدء التحليل';
  }
});

// ── Polling ────────────────────────────────────────────────────────────────
function startPolling() {
  clearInterval(state.polling);
  state.polling = setInterval(pollStatus, 1500);
}

async function pollStatus() {
  if (!state.jobId) return;
  try {
    const res  = await fetch(api(`/api/status/${state.jobId}`));
    const data = await res.json();
    if (!res.ok) return;
    updateLogs(data.logs || []);
    setProgress(data.progress || 0);
    if (data.status === 'done') {
      clearInterval(state.polling);
      renderResults(data);
      btnProcess.disabled = false;
      btnProcess.textContent = '▶ إعادة التحليل';
    } else if (data.status === 'error') {
      clearInterval(state.polling);
      showError(data.error || 'حدث خطأ غير معروف');
      btnProcess.disabled = false;
      btnProcess.textContent = '▶ بدء التحليل';
    }
  } catch (_) {}
}

// ── Results rendering ──────────────────────────────────────────────────────
function renderResults(data) {
  secResults.style.display = '';
  secResults.scrollIntoView({ behavior: 'smooth' });

  statsRow.innerHTML = `
    <div class="stat-card"><div class="stat-val">${data.slide_count}</div><div class="stat-lbl">شريحة</div></div>
    <div class="stat-card"><div class="stat-val">${data.diagram_count}</div><div class="stat-lbl">مخطط مُعاد بناؤه</div></div>
  `;

  previewsGrid.innerHTML = '';
  (data.previews || []).forEach(p => {
    const card = document.createElement('div');
    card.className = 'preview-card';
    card.innerHTML = `
      <img src="${api(p.url)}" alt="مخطط الشريحة ${p.slide}" loading="lazy" />
      <div class="preview-card-info">
        <strong>شريحة ${p.slide} — ${p.type}</strong>
        ${p.description}
      </div>`;
    previewsGrid.appendChild(card);
  });

  downloadRow.innerHTML = '';
  const dl = data.downloads || {};
  if (dl.pptx) downloadRow.appendChild(makeDownloadBtn('⬇ PPTX', api(dl.pptx), 'pptx'));
  if (dl.svg)  downloadRow.appendChild(makeDownloadBtn('⬇ SVG',  api(dl.svg),  'svg'));
  if (dl.png)  downloadRow.appendChild(makeDownloadBtn('⬇ PNG',  api(dl.png),  'png'));
  if (!dl.pptx && !dl.svg && !dl.png)
    downloadRow.innerHTML = '<p style="color:var(--muted)">لم تُكتشف مخططات قابلة لإعادة البناء في هذا الملف.</p>';

  secGithub.style.display = '';
}

function makeDownloadBtn(label, url, cls) {
  const a = document.createElement('a');
  a.className = `download-btn ${cls}`;
  a.href = url;
  a.textContent = label;
  a.download = '';
  return a;
}

// ── GitHub push ────────────────────────────────────────────────────────────
btnGithub.addEventListener('click', async () => {
  const repoUrl = $('repo-url').value.trim();
  if (!repoUrl) { alert('أدخل رابط المستودع'); return; }
  btnGithub.disabled = true;
  btnGithub.innerHTML = '<span class="spinner"></span> جارٍ الرفع…';
  githubResult.className = 'github-result';
  githubResult.textContent = '';
  try {
    const res  = await fetch(api(`/api/github-push/${state.jobId}`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: repoUrl }),
    });
    const data = await res.json();
    githubResult.className = `github-result ${data.success ? 'ok' : 'fail'}`;
    githubResult.textContent = (data.success ? '✅ ' : '❌ ') + data.message;
  } catch (err) {
    githubResult.className = 'github-result fail';
    githubResult.textContent = '❌ ' + err.message;
  } finally {
    btnGithub.disabled = false;
    btnGithub.textContent = '🚀 رفع إلى GitHub';
  }
});

// ── Retry ──────────────────────────────────────────────────────────────────
btnRetry.addEventListener('click', () => { errorBanner.style.display = 'none'; btnProcess.click(); });

// ── Helpers ────────────────────────────────────────────────────────────────
function setProgress(pct) {
  progressFill.style.width = pct + '%';
  progressPct.textContent  = pct + '%';
}

let lastLogLen = 0;
function updateLogs(logs) {
  if (logs.length === lastLogLen) return;
  lastLogLen = logs.length;
  logContent.textContent = logs.join('\n');
  logContent.scrollTop   = logContent.scrollHeight;
}

function showError(msg) {
  errorBanner.style.display = '';
  errorMsg.textContent = msg;
  secResults.style.display = '';
  secResults.scrollIntoView({ behavior: 'smooth' });
}

function resetResults() {
  statsRow.innerHTML = '';
  previewsGrid.innerHTML = '';
  downloadRow.innerHTML  = '';
  errorBanner.style.display = 'none';
  githubResult.textContent  = '';
  lastLogLen = 0;
  logContent.textContent = '';
}

btnClearLog.addEventListener('click', () => { logContent.textContent = ''; lastLogLen = 0; });
