/* ==========================================================================
   STATE
   ========================================================================== */
const state = {
  allele_freq_afr: 0.01,
  cadd_score: 15,
  gene_region: "Exonic (coding)",
  conservation_phylop: 0.5,
  gene_name: "HBB",
};

let caseCounter = 0;
let geneRegistry = {};
let viewer = null;
let currentPdbId = null;
let currentPdbText = null;
let heatmapData = null; // {gene, sequence, positions:[{pos,wt,effects}]}
const ROW_ORDER = ["L","I","M","V","F","Y","W","K","R","H","E","D","N","Q","S","T","G","A","P","C"];
const HEAT_STOPS = ["#1B1B3A", "#3D5A80", "#93B7D6", "#E8C77A"];
const CELL_W = 10;
const CELL_H = 14;

/* ==========================================================================
   INIT
   ========================================================================== */
document.addEventListener("DOMContentLoaded", async () => {
  caseCounter = Math.floor(Math.random() * 900000) + 100000;
  document.getElementById("case-number").textContent = `No. ${caseCounter}`;

  bindInputs();
  loadModelInfo();
  initViewer();

  await loadGeneRegistry();
  await refreshGene(state.gene_name);

  document.getElementById("predict-btn").addEventListener("click", runPrediction);
  document.getElementById("pdb-select").addEventListener("change", onPdbSelectChange);
  document.getElementById("download-btn").addEventListener("click", downloadStructure);
  document.getElementById("reset-btn").addEventListener("click", () => { if (viewer) { viewer.zoomTo(); viewer.render(); } });
});

/* ==========================================================================
   INPUT BINDING
   ========================================================================== */
function bindInputs() {
  const freq = document.getElementById("allele_freq_afr");
  freq.addEventListener("input", () => {
    state.allele_freq_afr = Number(freq.value);
    document.getElementById("allele_freq_afr_val").textContent = state.allele_freq_afr.toFixed(3);
  });

  const cadd = document.getElementById("cadd_score");
  cadd.addEventListener("input", () => {
    state.cadd_score = Number(cadd.value);
    document.getElementById("cadd_score_val").textContent = state.cadd_score.toFixed(1);
  });

  const cons = document.getElementById("conservation_phylop");
  cons.addEventListener("input", () => {
    state.conservation_phylop = Number(cons.value);
    document.getElementById("conservation_phylop_val").textContent = state.conservation_phylop.toFixed(1);
  });

  const gene = document.getElementById("gene_name");
  gene.addEventListener("change", async () => {
    const val = gene.value.trim().toUpperCase() || "HBB";
    gene.value = val;
    state.gene_name = val;
    await refreshGene(val);
  });

  const segGroup = document.getElementById("gene_region_group");
  segGroup.querySelectorAll(".seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      segGroup.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.gene_region = btn.dataset.value;
    });
  });
}

/* ==========================================================================
   MODEL INFO
   ========================================================================== */
async function loadModelInfo() {
  try {
    const res = await fetch("/api/model-info");
    const info = await res.json();
    document.getElementById("model-type").textContent = `MODEL — ${(info.model_type || "unknown").toUpperCase()}`;
    document.getElementById("model-auc").textContent = info.auc_all != null ? `AUC — ${Number(info.auc_all).toFixed(3)}` : "AUC — N/A";
    document.getElementById("model-training").textContent = info.training_variants != null ? `TRAINING SET — ${info.training_variants} VARIANTS` : "TRAINING SET — N/A";
    if (info.demo_mode) document.getElementById("demo-flag").classList.remove("hidden");
  } catch (err) {
    document.getElementById("model-type").textContent = "MODEL — UNREACHABLE";
  }
}

/* ==========================================================================
   PREDICTION
   ========================================================================== */
async function runPrediction() {
  const btn = document.getElementById("predict-btn");
  const errorHint = document.getElementById("error-hint");
  errorHint.textContent = "";
  btn.disabled = true;
  btn.textContent = "SCANNING…";

  try {
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ? JSON.stringify(body.detail) : `Request failed (${res.status})`);
    }
    const data = await res.json();
    renderResult(data);
    applyTierToStructure(data.tier);
  } catch (err) {
    errorHint.textContent = `REQUEST FAILED — ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = "RUN PREDICTION →";
  }
}

function renderResult(data) {
  document.getElementById("result-empty").classList.add("hidden");
  const card = document.getElementById("result-card");
  card.classList.remove("hidden");

  const stamp = document.getElementById("stamp");
  stamp.textContent = (data.label || "UNKNOWN").toUpperCase();
  stamp.className = `stamp tier-${data.tier || "default"}`;

  document.getElementById("probability-value").textContent = `${data.probability}%`;
  document.getElementById("probability-bar-fill").style.width = `${data.probability}%`;

  const list = document.getElementById("interpretation-list");
  list.innerHTML = "";
  (data.interpretation || []).forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    list.appendChild(li);
  });

  const contribWrap = document.getElementById("contributions");
  contribWrap.innerHTML = "";
  (data.contributions || []).forEach((c) => {
    const row = document.createElement("div");
    row.className = "contribution-row";
    const label = document.createElement("div");
    label.className = "contribution-label";
    label.innerHTML = `<span>${c.feature}</span><span>${c.push >= 0 ? "+" : ""}${(c.push * 100).toFixed(0)}%</span>`;
    const track = document.createElement("div");
    track.className = "contribution-track";
    const fill = document.createElement("div");
    fill.className = `contribution-fill${c.push < 0 ? " negative" : ""}`;
    const pct = Math.min(Math.abs(c.push) * 50, 50);
    if (c.push >= 0) { fill.style.left = "50%"; fill.style.width = `${pct}%`; }
    else { fill.style.right = "50%"; fill.style.width = `${pct}%`; }
    track.appendChild(fill);
    row.appendChild(label);
    row.appendChild(track);
    contribWrap.appendChild(row);
  });
}

/* ==========================================================================
   GENE REGISTRY + STRUCTURE
   ========================================================================== */
async function loadGeneRegistry() {
  try {
    const res = await fetch("/api/gene-registry");
    geneRegistry = await res.json();
  } catch (err) {
    geneRegistry = {};
  }
}

async function refreshGene(geneSymbol) {
  populatePdbSelect(geneSymbol);
  const select = document.getElementById("pdb-select");
  const chosen = select.value;
  await loadStructureFromSelection(geneSymbol, chosen);
  await loadHeatmap(geneSymbol);
}

function populatePdbSelect(geneSymbol) {
  const select = document.getElementById("pdb-select");
  select.innerHTML = "";
  const entry = geneRegistry[geneSymbol];

  if (entry && entry.structures && entry.structures.length > 0) {
    entry.structures.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = JSON.stringify({ source: "pdb", id: s.id, chain: s.chain });
      opt.textContent = s.label;
      select.appendChild(opt);
    });
  } else if (entry && entry.alphafold_uniprot) {
    const opt = document.createElement("option");
    opt.value = JSON.stringify({ source: "alphafold", id: entry.alphafold_uniprot, chain: "A" });
    opt.textContent = `AlphaFold model — ${entry.alphafold_uniprot} (predicted, no experimental structure)`;
    select.appendChild(opt);
  } else {
    const opt = document.createElement("option");
    opt.value = JSON.stringify({ source: "pdb", id: "2HHB", chain: "B" });
    opt.textContent = "2HHB — reference (no structure mapped for this gene)";
    select.appendChild(opt);
  }
}

function onPdbSelectChange() {
  const select = document.getElementById("pdb-select");
  loadStructureFromSelection(state.gene_name, select.value);
}

function initViewer() {
  const el = document.getElementById("viewer");
  viewer = $3Dmol.createViewer(el, { backgroundColor: "white" });
}

async function loadStructureFromSelection(geneSymbol, selectionJson) {
  let sel;
  try { sel = JSON.parse(selectionJson); } catch (e) { return; }

  document.getElementById("pdb-id").textContent = sel.source === "pdb" ? `PDB ${sel.id}` : `ALPHAFOLD ${sel.id}`;
  document.getElementById("pdb-chain").textContent = sel.chain;
  document.getElementById("pdb-note").textContent = sel.source === "pdb"
    ? `Experimental structure, chain ${sel.chain}`
    : `Predicted model (AlphaFold), UniProt ${sel.id}`;

  viewer.clear();
  currentPdbId = sel.id;
  currentPdbText = null;

  const url = sel.source === "pdb"
    ? `https://files.rcsb.org/download/${sel.id}.pdb`
    : `https://alphafold.ebi.ac.uk/files/AF-${sel.id}-F1-model_v4.pdb`;

  try {
    const r = await fetch(url);
    const pdbText = await r.text();
    viewer.addModel(pdbText, "pdb");
    currentPdbText = pdbText;
    viewer.setStyle({}, { cartoon: { color: "grey", opacity: 0.35 } });
    viewer.setStyle({ chain: sel.chain }, { cartoon: { color: "#D1301F", opacity: 1.0 } });
    viewer.zoomTo();
    viewer.render();
  } catch (err) {
    document.getElementById("pdb-note").textContent = "Structure unavailable — network blocked or model not found";
  }
}

function applyTierToStructure(tier) {
  if (!viewer) return;
  const entry = geneRegistry[state.gene_name];
  const chain = (entry && entry.structures && entry.structures[0]) ? entry.structures[0].chain : "A";
  const colorMap = { high: "#D1301F", medium: "#B5790A", low: "#1F6B44" };
  viewer.setStyle({ chain: chain }, { cartoon: { color: colorMap[tier] || "#D1301F", opacity: 1.0 } });
  viewer.render();
}

function downloadStructure() {
  if (!currentPdbText || !currentPdbId) return;
  const blob = new Blob([currentPdbText], { type: "chemical/x-pdb" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${currentPdbId}.pdb`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/* ==========================================================================
   SUBSTITUTION MATRIX (precomputed ESM2 masked-marginal scores)
   ========================================================================== */
async function loadHeatmap(geneSymbol) {
  const panel = document.getElementById("matrix-panel");
  try {
    const res = await fetch(`/api/heatmap/${geneSymbol}`);
    if (!res.ok) {
      heatmapData = null;
      panel.classList.add("hidden");
      return;
    }
    heatmapData = await res.json();
    panel.classList.remove("hidden");
    document.getElementById("matrix-sub").textContent = `${heatmapData.model || "ESM2"} ZERO-SHOT — CLICK A COLUMN`;
    drawMatrix();
  } catch (err) {
    heatmapData = null;
    panel.classList.add("hidden");
  }
}

function heatColor(t) {
  t = Math.max(0, Math.min(1, t));
  const seg = t * (HEAT_STOPS.length - 1);
  const idx = Math.min(Math.floor(seg), HEAT_STOPS.length - 2);
  const frac = seg - idx;
  const c1 = hexToRgb(HEAT_STOPS[idx]);
  const c2 = hexToRgb(HEAT_STOPS[idx + 1]);
  const r = Math.round(c1.r + (c2.r - c1.r) * frac);
  const g = Math.round(c1.g + (c2.g - c1.g) * frac);
  const b = Math.round(c1.b + (c2.b - c1.b) * frac);
  return `rgb(${r},${g},${b})`;
}
function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function drawMatrix() {
  if (!heatmapData) return;
  const positions = heatmapData.positions;
  const cols = positions.length;
  const rows = ROW_ORDER.length;

  let min = Infinity, max = -Infinity;
  positions.forEach((p) => ROW_ORDER.forEach((aa) => {
    const v = p.effects[aa];
    if (v != null) { if (v < min) min = v; if (v > max) max = v; }
  }));
  document.getElementById("legend-min").textContent = min.toFixed(1);
  document.getElementById("legend-max").textContent = max.toFixed(1);

  // main heat canvas
  const canvas = document.getElementById("matrix-canvas");
  canvas.width = cols * CELL_W;
  canvas.height = rows * CELL_H;
  const ctx = canvas.getContext("2d");
  for (let c = 0; c < cols; c++) {
    const effects = positions[c].effects;
    for (let r = 0; r < rows; r++) {
      const v = effects[ROW_ORDER[r]];
      const t = v == null ? 0 : (v - min) / (max - min || 1);
      ctx.fillStyle = v == null ? "#DDDAD0" : heatColor(t);
      ctx.fillRect(c * CELL_W, r * CELL_H, CELL_W, CELL_H);
    }
  }

  // row labels (amino acids)
  const rowCanvas = document.getElementById("matrix-row-labels");
  rowCanvas.width = 24;
  rowCanvas.height = rows * CELL_H;
  const rctx = rowCanvas.getContext("2d");
  rctx.fillStyle = "#FFFFFF";
  rctx.fillRect(0, 0, rowCanvas.width, rowCanvas.height);
  rctx.font = "9px 'IBM Plex Mono', monospace";
  rctx.fillStyle = "#121210";
  rctx.textAlign = "center";
  rctx.textBaseline = "middle";
  ROW_ORDER.forEach((aa, r) => rctx.fillText(aa, 12, r * CELL_H + CELL_H / 2));

  // column labels (positions, every Nth)
  const colCanvas = document.getElementById("matrix-col-labels");
  colCanvas.width = cols * CELL_W;
  colCanvas.height = 22;
  const cctx = colCanvas.getContext("2d");
  cctx.fillStyle = "#FFFFFF";
  cctx.fillRect(0, 0, colCanvas.width, colCanvas.height);
  cctx.font = "8px 'IBM Plex Mono', monospace";
  cctx.fillStyle = "#4A4842";
  const step = Math.max(1, Math.ceil(cols / 60));
  for (let c = 0; c < cols; c += step) {
    cctx.save();
    cctx.translate(c * CELL_W + CELL_W / 2, 20);
    cctx.rotate(-Math.PI / 2);
    cctx.textAlign = "left";
    cctx.fillText(String(positions[c].pos), 0, 0);
    cctx.restore();
  }

  canvas.onclick = (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const col = Math.floor(x / CELL_W);
    if (col >= 0 && col < cols) populateMatrixTable(positions[col]);
  };
}

function populateMatrixTable(position) {
  document.getElementById("matrix-table-pos").textContent = `— ${position.wt}${position.pos}`;
  const body = document.getElementById("matrix-table-body");
  body.innerHTML = "";

  let min = Infinity, max = -Infinity;
  Object.values(position.effects).forEach((v) => { if (v < min) min = v; if (v > max) max = v; });

  const rows = Object.keys(position.effects)
    .map((aa) => ({ aa, v: position.effects[aa] }))
    .sort((a, b) => a.v - b.v);

  rows.forEach(({ aa, v }) => {
    const tr = document.createElement("tr");
    const t = (v - min) / (max - min || 1);
    tr.innerHTML = `
      <td>${position.wt}</td>
      <td>${position.pos}</td>
      <td>${aa}${aa === position.wt ? " (=WT)" : ""}</td>
      <td><span class="effect-swatch" style="background:${heatColor(t)}"></span>${v.toFixed(2)}</td>
    `;
    body.appendChild(tr);
  });
}
