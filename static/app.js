'use strict';

// ── Config ─────────────────────────────────────────────────────────────────
const SUPABASE_URL      = 'https://sdpjpgnwztqoncismayd.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_D5bNKo8DSUzUmdiq9_TuZA_xGB66_Ii';
const GITHUB_OWNER      = 'fa78383012731al-collab';
const GITHUB_REPO       = 'background1';
const BUCKET_INPUT      = 'pptx-inputs';

// ── Supabase helpers ───────────────────────────────────────────────────────
const sb = {
  headers: {
    'apikey':        SUPABASE_ANON_KEY,
    'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
  },

  // Upload file + create job + trigger GH Actions — all via Edge Function (uses service key)
  async uploadAndTrigger(file) {
    const jobId = crypto.randomUUID();
    const form  = new FormData();
    form.append('file',     file, file.name);
    form.append('job_id',   jobId);
    form.append('filename', file.name);

    const r = await fetch(`${SUPABASE_URL}/functions/v1/rapid-responder`, {
      method:  'POST',
      headers: { 'apikey': SUPABASE_ANON_KEY },
      body:    form,
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || `Upload failed: ${r.status}`);
    return data; // { success, job_id, file_path, job }
  },

  async getJob(jobId) {
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/jobs?id=eq.${jobId}&select=*`,
      { headers: this.headers }
    );
    if (!r.ok) throw new Error(`Job fetch failed: ${r.status}`);
    const rows = await r.json();
    return rows[0] || null;
  },
};

// ── State ──────────────────────────────────────────────────────────────────
let state = { jobId: null, polling: null, startTime: null };

// ── DOM ────────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const dropZone     = $('drop-zone');
const fileInput    = $('file-input');
const fileNameEl   = $('file-name');
const btnUpload    = $('btn-upload');
const secProcess   = $('sec-process');
const secResults   = $('sec-results');
const tagFilename  = $('tag-filename');
const tagStatus    = $('tag-status');
const progressFill = $('progress-fill');
const progressPct  = $('progress-pct');
const logContent   = $('log-content');
const logEta       = $('log-eta');
const statsRow     = $('stats-row');
const previewsGrid = $('previews-grid');
const downloadRow  = $('download-row');
const errorBanner  = $('error-banner');
const errorMsg     = $('error-msg');
const btnRetry     = $('btn-retry');
const btnNew       = $('btn-new');

// ── File selection ─────────────────────────────────────────────────────────
let selectedFile = null;
function setFile(f) {
  if (!f || !f.name.toLowerCase().endsWith('.pptx')) { alert('يُقبل فقط ملف .pptx'); return; }
  selectedFile = f;
  fileNameEl.textContent = f.name;
  btnUpload.disabled = false;
}
fileInput.addEventListener('change', () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });
dropZone.addEventListener('click',     () => fileInput.click());
dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});

// ── Upload & trigger ───────────────────────────────────────────────────────
btnUpload.addEventListener('click', async () => {
  if (!selectedFile) return;
  btnUpload.disabled = true;
  btnUpload.innerHTML = '<span class="spinner"></span> جارٍ الرفع…';

  try {
    // Single call: upload + create job + trigger GH Actions (all via Edge Function)
    setProgress(5, 'رفع الملف…');
    const result = await sb.uploadAndTrigger(selectedFile);

    state.jobId     = result.job_id;
    state.startTime = Date.now();
    tagFilename.textContent = selectedFile.name;

    // Show processing section
    secProcess.style.display = '';
    secProcess.scrollIntoView({ behavior: 'smooth' });

    setProgress(15, '✅ الملف وصل — GitHub Actions يعالج الآن…');
    tagStatus.textContent = '🚀 GitHub Actions يعمل…';
    tagStatus.className   = 'tag tag-blue';

    // Start polling
    startPolling(result.job_id);

  } catch (err) {
    showError(err.message);
    btnUpload.disabled = false;
    btnUpload.textContent = '⬆ رفع وبدء المعالجة';
  }
});

// ── Polling ────────────────────────────────────────────────────────────────
function startPolling(jobId) {
  clearInterval(state.polling);
  state.polling = setInterval(() => pollJob(jobId), 3000);
}

async function pollJob(jobId) {
  try {
    const job = await sb.getJob(jobId);
    if (!job) return;

    setProgress(job.progress || 0, job.log || '');

    const elapsed = Math.round((Date.now() - state.startTime) / 1000);
    logEta.textContent = `⏱ ${elapsed}s`;

    // Update status badge
    const statusMap = {
      queued:     ['⏳ في قائمة الانتظار', 'tag-blue'],
      processing: ['⚙ جارٍ المعالجة…',    'tag-blue'],
      done:       ['✅ اكتمل',             'tag-green'],
      error:      ['❌ خطأ',               'tag-red'],
    };
    const [label, cls] = statusMap[job.status] || ['…', 'tag-blue'];
    tagStatus.textContent = label;
    tagStatus.className   = `tag ${cls}`;

    if (job.status === 'done') {
      clearInterval(state.polling);
      renderResults(job);
    } else if (job.status === 'error') {
      clearInterval(state.polling);
      showError(job.log || 'حدث خطأ غير معروف');
    }
  } catch (_) {}
}

// ── Results ────────────────────────────────────────────────────────────────
function renderResults(job) {
  secResults.style.display = '';
  secResults.scrollIntoView({ behavior: 'smooth' });

  statsRow.innerHTML = `
    <div class="stat-card"><div class="stat-val">${job.slide_count || 0}</div><div class="stat-lbl">شريحة</div></div>
    <div class="stat-card"><div class="stat-val">${job.diagram_count || 0}</div><div class="stat-lbl">مخطط مُعاد بناؤه</div></div>
  `;

  // Previews
  previewsGrid.innerHTML = '';
  let previews = [];
  try { previews = JSON.parse(job.result_previews || '[]'); } catch (_) {}
  previews.forEach(p => {
    if (!p.url) return;
    const card = document.createElement('div');
    card.className = 'preview-card';
    card.innerHTML = `
      <img src="${p.url}" alt="شريحة ${p.slide}" loading="lazy" />
      <div class="preview-card-info">
        <strong>شريحة ${p.slide} — ${p.type}</strong>
        ${p.description || ''}
      </div>`;
    previewsGrid.appendChild(card);
  });

  // Downloads
  downloadRow.innerHTML = '';
  if (job.result_pptx) downloadRow.appendChild(mkDl('⬇ PPTX', job.result_pptx, 'pptx'));
  if (job.result_svg)  downloadRow.appendChild(mkDl('⬇ SVG',  job.result_svg,  'svg'));
  if (job.result_png)  downloadRow.appendChild(mkDl('⬇ PNG',  job.result_png,  'png'));
  if (!job.result_pptx && !job.result_svg && !job.result_png)
    downloadRow.innerHTML = '<p style="color:var(--muted)">لم تُكتشف مخططات قابلة لإعادة البناء في هذا الملف.</p>';
}

function mkDl(label, url, cls) {
  const a = document.createElement('a');
  a.className = `download-btn ${cls}`;
  a.href = url; a.textContent = label; a.target = '_blank';
  return a;
}

// ── Helpers ────────────────────────────────────────────────────────────────
let lastLog = '';
function setProgress(pct, log) {
  progressFill.style.width = pct + '%';
  progressPct.textContent  = pct + '%';
  if (log && log !== lastLog) {
    lastLog = log;
    logContent.textContent += (logContent.textContent ? '\n' : '') + log;
    logContent.scrollTop    = logContent.scrollHeight;
  }
}

function showError(msg) {
  errorBanner.style.display = '';
  errorMsg.textContent = msg;
  secResults.style.display = '';
  tagStatus.textContent = '❌ خطأ';
  tagStatus.className   = 'tag tag-red';
}

btnRetry.addEventListener('click', () => {
  errorBanner.style.display = 'none';
  btnUpload.disabled  = false;
  btnUpload.textContent = '⬆ رفع وبدء المعالجة';
  secProcess.style.display  = 'none';
  secResults.style.display  = 'none';
});

btnNew.addEventListener('click', () => {
  clearInterval(state.polling);
  state = { jobId: null, polling: null, startTime: null };
  selectedFile = null;
  fileNameEl.textContent = 'لم يُختر ملف بعد';
  btnUpload.disabled = true;
  btnUpload.textContent = '⬆ رفع وبدء المعالجة';
  logContent.textContent = '';
  lastLog = '';
  secProcess.style.display = 'none';
  secResults.style.display = 'none';
  window.scrollTo({ top: 0, behavior: 'smooth' });
});
