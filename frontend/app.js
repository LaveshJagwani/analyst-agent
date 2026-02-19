/* ── Autonomous Data Analyst — Frontend App ── */

const API = 'http://localhost:8000';

// ── Node display metadata ─────────────────────────────────────────
const NODES = [
  { id: 'metadata_parser', label: 'Metadata Parser', icon: '📋', detail: 'Parsing business context...' },
  { id: 'schema_analyzer', label: 'Schema Analyzer', icon: '🔍', detail: 'Profiling CSV structure...' },
  { id: 'context_classifier', label: 'Context Classifier', icon: '🏢', detail: 'Classifying business domain...' },
  { id: 'analysis_planner', label: 'Analysis Planner', icon: '📐', detail: 'Generating analysis plan...' },
  { id: 'code_executor', label: 'Code Executor', icon: '⚡', detail: 'Running analysis steps...' },
  { id: 'insight_validator', label: 'Insight Validator', icon: '✅', detail: 'Validating findings...' },
  { id: 'strategy_generator', label: 'Strategy Generator', icon: '🎯', detail: 'Generating recommendations...' },
  { id: 'benchmark', label: 'Benchmark (optional)', icon: '📊', detail: 'Fetching market data...' },
  { id: 'presentation_generator', label: 'Presentation Generator', icon: '🎬', detail: 'Building slide deck...' },
];

// ── DOM refs ──────────────────────────────────────────────────────
const dropZone = document.getElementById('drop-zone');
const csvInput = document.getElementById('csv-input');
const fileSelected = document.getElementById('file-selected');
const metaInput = document.getElementById('metadata-input');
const benchmarkToggle = document.getElementById('benchmark-toggle');
const analyzeBtn = document.getElementById('analyze-btn');
const uploadSection = document.getElementById('upload-section');
const pipelineSection = document.getElementById('pipeline-section');
const resultsSection = document.getElementById('results-section');
const timelineEl = document.getElementById('timeline');
const pipelineStatusBadge = document.getElementById('pipeline-status-badge');

// Summary
const summaryRows = document.getElementById('summary-rows');
const summaryCols = document.getElementById('summary-cols');
const summaryInsights = document.getElementById('summary-insights');
const summaryCharts = document.getElementById('summary-charts');
const summaryRecs = document.getElementById('summary-recs');
const summaryCtx = document.getElementById('summary-context');

// Tabs
const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

// Content grids
const insightsGrid = document.getElementById('insights-grid');
const chartsGrid = document.getElementById('charts-grid');
const recsList = document.getElementById('recs-list');

// Slide viewer
const slidePrev = document.getElementById('slide-prev');
const slideNext = document.getElementById('slide-next');
const slideCounter = document.getElementById('slide-counter');
const slideStage = document.getElementById('slide-stage');

// Lightbox
const lightbox = document.getElementById('lightbox');
const lightboxImg = document.getElementById('lightbox-img');
const lightboxClose = document.getElementById('lightbox-close');
const lightboxBg = document.getElementById('lightbox-backdrop');

// PPTX download
const downloadPptxBtn = document.getElementById('download-pptx-btn');

// ── State ──────────────────────────────────────────────────────────
let selectedFile = null;
let slides = [];
let slideIdx = 0;
let nodeStatus = {}; // node_id -> 'pending'|'active'|'done'
let currentRunId = null;

// ── File Handling ─────────────────────────────────────────────────
dropZone.addEventListener('click', () => csvInput.click());

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f && f.name.endsWith('.csv')) setFile(f);
});

csvInput.addEventListener('change', () => {
  if (csvInput.files[0]) setFile(csvInput.files[0]);
});

function setFile(f) {
  selectedFile = f;
  fileSelected.innerHTML = `✓ ${f.name} <span style="opacity:.6">(${(f.size / 1024).toFixed(1)} KB)</span>`;
  fileSelected.classList.remove('hidden');
  analyzeBtn.disabled = false;
}

// ── Analyze on click ──────────────────────────────────────────────
analyzeBtn.addEventListener('click', startAnalysis);

async function startAnalysis() {
  if (!selectedFile) return;

  // UI transition
  analyzeBtn.disabled = true;
  analyzeBtn.querySelector('.btn-text').textContent = 'Uploading…';

  const formData = new FormData();
  formData.append('csv_file', selectedFile);
  formData.append('metadata', metaInput.value.trim() || '');
  formData.append('benchmark', benchmarkToggle.checked ? 'true' : 'false');

  let runId;
  try {
    const res = await fetch(`${API}/analyze`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    runId = data.run_id;
    currentRunId = runId;
  } catch (err) {
    alert(`Upload failed: ${err.message}`);
    analyzeBtn.disabled = false;
    analyzeBtn.querySelector('.btn-text').textContent = 'Run Analysis';
    return;
  }

  // Show pipeline panel
  uploadSection.classList.add('hidden');
  pipelineSection.classList.remove('hidden');
  buildTimeline();

  // Connect SSE
  streamProgress(runId);
}

// ── Build Timeline DOM ────────────────────────────────────────────
function buildTimeline() {
  timelineEl.innerHTML = '';
  nodeStatus = {};
  NODES.forEach(n => {
    nodeStatus[n.id] = 'pending';
    const item = document.createElement('div');
    item.className = 'tl-item pending';
    item.id = `tl-${n.id}`;
    item.innerHTML = `
      <div class="tl-dot">${n.icon}</div>
      <div class="tl-content">
        <div class="tl-name">${n.label}</div>
        <div class="tl-detail" id="tl-detail-${n.id}">Waiting…</div>
      </div>`;
    timelineEl.appendChild(item);
  });
}

function setNodeState(nodeId, state, detail = '') {
  const item = document.getElementById(`tl-${nodeId}`);
  if (!item) return;
  item.className = `tl-item ${state}`;
  nodeStatus[nodeId] = state;
  if (detail) {
    const d = document.getElementById(`tl-detail-${nodeId}`);
    if (d) d.textContent = detail;
  }
}

// ── SSE Streaming ─────────────────────────────────────────────────
function streamProgress(runId) {
  const evtSource = new EventSource(`${API}/stream/${runId}`);

  // Track code_executor step progress for completion detection
  let lastCodeStep = 0;
  let totalCodeSteps = 0;

  evtSource.onmessage = (e) => {
    const ev = JSON.parse(e.data);

    if (ev.type === 'node_complete') {
      setNodeState(ev.node, 'done', '✓ Complete');
      // After a node completes, mark the next one active
      advanceActiveNode(ev.node);

    } else if (ev.type === 'node_progress') {
      // Code executor is actively running a step
      lastCodeStep = ev.step ?? lastCodeStep;
      totalCodeSteps = ev.total ?? totalCodeSteps;
      setNodeState('code_executor', 'active', ev.message);

      // If we just finished the last step, push a synthetic done
      if (totalCodeSteps > 0 && lastCodeStep >= totalCodeSteps) {
        // will be confirmed by server's node_complete soon — no action needed
      }

    } else if (ev.type === 'status' && ev.node === 'start') {
      setNodeState('metadata_parser', 'active', NODES.find(n => n.id === 'metadata_parser').detail);

    } else if (ev.type === 'done') {
      evtSource.close();
      // Mark any still-active nodes as done
      NODES.forEach(n => { if (nodeStatus[n.id] === 'active') setNodeState(n.id, 'done', '✓ Complete'); });
      pipelineStatusBadge.className = 'status-badge status-done';
      pipelineStatusBadge.textContent = 'Done';
      fetchResults(runId);

    } else if (ev.type === 'error') {
      evtSource.close();
      pipelineStatusBadge.className = 'status-badge status-error';
      pipelineStatusBadge.textContent = 'Error';
      alert(`Analysis failed: ${ev.message}`);
    }
  };

  evtSource.onerror = () => {
    evtSource.close();
  };
}

function advanceActiveNode(completedNodeId) {
  const nodeOrder = NODES.map(n => n.id);
  const completedIdx = nodeOrder.indexOf(completedNodeId);
  if (completedIdx === -1) return;
  // Find the next node that isn't already done
  for (let i = completedIdx + 1; i < nodeOrder.length; i++) {
    const nextId = nodeOrder[i];
    if (nodeStatus[nextId] !== 'done') {
      setNodeState(nextId, 'active', NODES[i].detail);
      break;
    }
  }
}

// ── Fetch & Render Results ────────────────────────────────────────
async function fetchResults(runId) {
  try {
    const res = await fetch(`${API}/results/${runId}`);
    const data = await res.json();
    if (data.status !== 'done') return;
    window._analysisResult = data.result; // store globally for chart lookup
    renderResults(data.result);
    // Enable download button
    if (downloadPptxBtn) {
      downloadPptxBtn.disabled = false;
      downloadPptxBtn.onclick = () => triggerPptxDownload(runId);
    }
  } catch (err) {
    console.error('Failed to fetch results:', err);
  }
}

function triggerPptxDownload(runId) {
  downloadPptxBtn.classList.add('loading');
  downloadPptxBtn.textContent = '⏳ Generating…';
  // Use a hidden anchor to trigger the download
  const a = document.createElement('a');
  a.href = `${API}/export/pptx/${runId}`;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Reset button after a moment
  setTimeout(() => {
    downloadPptxBtn.classList.remove('loading');
    downloadPptxBtn.innerHTML = '⤓ Download .pptx';
  }, 3000);
}

function renderResults(r) {
  resultsSection.classList.remove('hidden');

  // Summary bar
  const ss = r.schema_summary || {};
  summaryRows.textContent = ss.row_count ?? '—';
  summaryCols.textContent = ss.column_count ?? '—';
  summaryInsights.textContent = r.insights?.length ?? 0;
  summaryCharts.textContent = r.charts?.length ?? 0;
  summaryRecs.textContent = r.recommendations?.length ?? 0;
  summaryCtx.textContent = r.business_context || '—';

  // Insights
  renderInsights(r.insights || []);

  // Charts
  renderCharts(r.charts || []);

  // Recommendations
  renderRecommendations(r.recommendations || []);

  // Slides
  slides = r.presentation?.slides || [];
  slideIdx = 0;
  renderSlide(slideIdx);

  // Scroll to results
  setTimeout(() => resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200);
}

// ── Insights ──────────────────────────────────────────────────────
function renderInsights(insights) {
  insightsGrid.innerHTML = '';
  insights.forEach(ins => {
    const conf = (ins.confidence || 'medium').toLowerCase();
    const confClass = conf === 'high' ? 'conf-high' : conf === 'low' ? 'conf-low' : 'conf-medium';
    const card = document.createElement('div');
    card.className = 'insight-card';
    card.innerHTML = `
      <div class="insight-header">
        <div class="insight-title">${escHtml(ins.title || '')}</div>
        <span class="conf-badge ${confClass}">${conf.toUpperCase()}</span>
      </div>
      ${ins.metric_value ? `<div class="insight-metric">📈 ${escHtml(ins.metric_value)}</div>` : ''}
      <div class="insight-desc">${escHtml(ins.description || '')}</div>`;
    insightsGrid.appendChild(card);
  });
}

// ── Charts ───────────────────────────────────────────────────────
function renderCharts(chartList) {
  chartsGrid.innerHTML = '';
  chartList.forEach((entry, i) => {
    // Support both new object format {url, step_id, step_title} and legacy strings
    const url = typeof entry === 'string' ? entry : entry.url;
    const stepTitle = typeof entry === 'string' ? `Chart ${i + 1}` : (entry.step_title || `Chart ${i + 1}`);
    const stepId = typeof entry === 'string' ? '' : (entry.step_id || '');

    // Fallback: also look up objective from analysis_plan if we have a step_id
    const plan = window._analysisResult?.analysis_plan || [];
    const planStep = plan.find(s => String(s.id) === String(stepId)) || plan[parseInt(stepId) - 1];
    const stepObjective = planStep?.objective || '';

    const fullUrl = `${API}${url}`;

    const card = document.createElement('div');
    card.className = 'chart-card';
    card.innerHTML = `
      <img src="${fullUrl}" alt="${escHtml(stepTitle)}" loading="lazy" onerror="this.style.display='none'" />
      <div class="chart-meta">
        <div class="chart-label">${escHtml(stepTitle)}</div>
        ${stepObjective ? `<div class="chart-objective">${escHtml(stepObjective)}</div>` : ''}
      </div>`;
    card.addEventListener('click', () => openLightbox(fullUrl, stepTitle, stepObjective));
    chartsGrid.appendChild(card);
  });
}

// ── Recommendations ───────────────────────────────────────────────
function renderRecommendations(recs) {
  recsList.innerHTML = '';
  recs.forEach((rec, i) => {
    const card = document.createElement('div');
    card.className = 'rec-card';

    // Handle both flat string fields and structured dict
    const action = rec.action || rec.ACTION || '';
    const why = rec.rationale || rec.why || rec.WHY || '';
    const impact = rec.expected_impact || rec.impact || rec.IMPACT || '';
    const risk = rec.risk || rec.RISK || '';
    const next = rec.suggested_next_step || rec.next || rec.NEXT || '';

    card.innerHTML = `
      <div class="rec-number">Recommendation ${i + 1}</div>
      <div class="rec-action">${escHtml(action)}</div>
      <div class="rec-grid">
        ${why ? `<div><div class="rec-field-label">Why</div><div class="rec-field-value">${escHtml(why)}</div></div>` : ''}
        ${impact ? `<div><div class="rec-field-label">Impact</div><div class="rec-field-value">${escHtml(impact)}</div></div>` : ''}
        ${risk ? `<div><div class="rec-field-label">Risk</div><div class="rec-field-value">${escHtml(risk)}</div></div>` : ''}
        ${next ? `<div><div class="rec-field-label">Next Step</div><div class="rec-field-value">${escHtml(next)}</div></div>` : ''}
      </div>`;
    recsList.appendChild(card);
  });
}

// ── Slide Viewer ─────────────────────────────────────────────────
function renderSlide(idx) {
  if (!slides.length) { slideStage.innerHTML = '<p style="color:var(--text-muted)">No slides generated.</p>'; return; }
  const s = slides[idx];

  // Resolve chart_reference to a displayable URL
  let chartHtml = '';
  if (s.chart_reference) {
    const ref = String(s.chart_reference);
    // chart_reference can be a full path or just a filename
    const fname = ref.split(/[\\/]/).pop();
    const chartUrl = `${API}/charts/${fname}`;
    // Look up the step title from the chart list for context
    const chartEntry = (window._analysisResult?.charts || []).find(
      c => (typeof c === 'string' ? c : c.url || '').includes(fname)
    );
    const chartTitle = (typeof chartEntry === 'object' ? chartEntry.step_title : '') || s.title;
    chartHtml = `
      <div class="slide-chart-wrap">
        <img src="${chartUrl}" alt="${escHtml(chartTitle)}" class="slide-chart-img"
             onerror="this.parentElement.innerHTML='<div class=slide-chart-missing>Chart not available</div>'" />
        <div class="slide-chart-label">${escHtml(chartTitle)}</div>
      </div>`;
  }

  const bullets = (s.content || []).map(b => `<div class="slide-bullet">${escHtml(b)}</div>`).join('');
  const notes = s.speaker_notes ? `<div class="slide-notes">🎙 ${escHtml(s.speaker_notes)}</div>` : '';

  slideStage.innerHTML = `
    <div class="slide-title">${escHtml(s.title || `Slide ${idx + 1}`)}</div>
    <div class="slide-body ${chartHtml ? 'slide-has-chart' : ''}">
      <div class="slide-bullets">${bullets}</div>
      ${chartHtml}
    </div>
    ${notes}`;
  slideCounter.textContent = `${idx + 1} / ${slides.length}`;
}

slidePrev.addEventListener('click', () => {
  if (slideIdx > 0) { slideIdx--; renderSlide(slideIdx); }
});
slideNext.addEventListener('click', () => {
  if (slideIdx < slides.length - 1) { slideIdx++; renderSlide(slideIdx); }
});

// ── Tabs ─────────────────────────────────────────────────────────
tabBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    tabBtns.forEach(b => b.classList.remove('active'));
    tabContents.forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
  });
});

// ── Lightbox ─────────────────────────────────────────────────────
function openLightbox(src, title, desc) {
  lightboxImg.src = src;
  const cap = document.getElementById('lightbox-caption');
  if (cap) {
    cap.querySelector('.lb-title').textContent = title || '';
    cap.querySelector('.lb-desc').textContent = desc || '';
    cap.style.display = (title || desc) ? 'block' : 'none';
  }
  lightbox.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}
function closeLightbox() {
  lightbox.classList.add('hidden');
  lightboxImg.src = '';
  document.body.style.overflow = '';
}
lightboxClose.addEventListener('click', closeLightbox);
lightboxBg.addEventListener('click', closeLightbox);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeLightbox(); });

// ── Helpers ───────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
