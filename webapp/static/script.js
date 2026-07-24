const $ = (id) => document.getElementById(id);

const state = {
  viewer: null,
  currentPdbId: null,
  currentChain: null,
  currentTierColor: null,
  currentResidue: null,
};

// Residue positions below are well-documented textbook variants (HbS/HbC at
// β-globin codon 6; G6PD A- and G6PD Mediterranean at their established
// positions) — not invented for this demo. gene_region/cadd/etc. are still
// illustrative slider presets, but the residue identity itself is real.
const EXAMPLES = {
  "hbs":          { gene_name: "HBB",  allele_freq_afr: 0.004, cadd_score: 34.0, gene_region: "exonic",   conservation_phylop: 2.1, residue: 6,   wt: "GLU", mut: "VAL", note: "HbS — Glu6Val (rs334)" },
  "hbb-path":     { gene_name: "HBB",  allele_freq_afr: 0.001, cadd_score: 28.0, gene_region: "exonic",   conservation_phylop: 1.8, residue: 6,   wt: "GLU", mut: "LYS", note: "HbC — Glu6Lys" },
  "g6pd-benign":  { gene_name: "G6PD", allele_freq_afr: 0.420, cadd_score: 3.0,  gene_region: "intronic", conservation_phylop: -0.5, residue: 68,  wt: "VAL", mut: "MET", note: "G6PD A- — Val68Met" },
  "g6pd-rare":    { gene_name: "G6PD", allele_freq_afr: 0.000, cadd_score: 42.0, gene_region: "exonic",   conservation_phylop: 2.8, residue: 188, wt: "SER", mut: "PHE", note: "G6PD Mediterranean — Ser188Phe" },
};

const AA3 = { GLU: "E", VAL: "V", LYS: "K", MET: "M", SER: "S", PHE: "F" };

function initSliders() {
  const af = $("allele_freq_afr"), afVal = $("af-val");
  af.addEventListener("input", () => afVal.textContent = Number(af.value).toFixed(3));

  const cadd = $("cadd_score"), caddVal = $("cadd-val");
  cadd.addEventListener("input", () => caddVal.textContent = Number(cadd.value).toFixed(1));

  const cons = $("conservation_phylop"), consVal = $("cons-val");
  cons.addEventListener("input", () => consVal.textContent = Number(cons.value).toFixed(1));
}

function applyExample(key) {
  const ex = EXAMPLES[key];
  if (!ex) return;
  $("gene_name").value = ex.gene_name;
  $("allele_freq_afr").value = ex.allele_freq_afr;
  $("af-val").textContent = ex.allele_freq_afr.toFixed(3);
  $("cadd_score").value = ex.cadd_score;
  $("cadd-val").textContent = ex.cadd_score.toFixed(1);
  $("gene_region").value = ex.gene_region;
  $("conservation_phylop").value = ex.conservation_phylop;
  $("cons-val").textContent = ex.conservation_phylop.toFixed(1);
  $("residue_number").value = ex.residue;
  onGeneChange().then(() => highlightResidue(ex.residue, ex.wt, ex.mut, ex.note));
  submitPrediction();
}

async function loadModelInfo() {
  try {
    const res = await fetch("/api/model-info");
    const data = await res.json();
    const bar = $("status-bar");
    const m = data.meta || {};

    if (data.demo_mode) {
      bar.textContent = "⚠ DEMO MODE — synthetic fallback model (real pipeline not yet run)";
      bar.style.color = "#8B1A1A";
    } else if (data.data_provenance !== "real") {
      bar.textContent = `⚠ REAL MODEL, PLACEHOLDER DATA — trained on features with data_provenance="${data.data_provenance}". ` +
                         `Re-run build_features.py (real data is now the default) and retrain.`;
      bar.style.color = "#8B1A1A";
    } else {
      bar.textContent = `✓ real data · model: ${m.model_type || "?"} · AUC ${m.auc_all ?? "?"} · n=${m.training_variants ?? "?"}`;
      bar.style.color = "#0F5E3A";
    }
  } catch (e) {
    $("status-bar").textContent = "model-info unavailable";
  }
}

async function submitPrediction() {
  const btn = document.querySelector(".btn-primary");
  btn.disabled = true;
  btn.textContent = "SCORING…";

  const payload = {
    gene_name: $("gene_name").value,
    allele_freq_afr: Number($("allele_freq_afr").value),
    cadd_score: Number($("cadd_score").value),
    gene_region: $("gene_region").value,
    conservation_phylop: Number($("conservation_phylop").value),
  };

  try {
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    const result = await res.json();
    renderResult(result);
    recolorStructure(result.color);
  } catch (e) {
    console.error(e);
    $("result-empty").textContent = "Prediction failed — check server logs.";
    $("result-empty").classList.remove("hidden");
    $("result-body").classList.add("hidden");
  } finally {
    btn.disabled = false;
    btn.textContent = "PREDICT PATHOGENICITY →";
  }
}

function renderResult(result) {
  $("result-empty").classList.add("hidden");
  $("result-body").classList.remove("hidden");

  const stamp = $("tier-stamp");
  stamp.textContent = result.tier === "pathogenic" ? "LIKELY PATHOGENIC"
                     : result.tier === "benign" ? "LIKELY BENIGN"
                     : "UNCERTAIN / BORDERLINE";
  stamp.className = "tier-stamp " + result.color;

  $("prob-bar-fill").style.width = result.probability + "%";
  let caveat = "";
  if (result.demo_mode) caveat = "  (demo model — not real data)";
  else if (result.data_provenance !== "real") caveat = `  (⚠ trained on ${result.data_provenance} data, not real gnomAD/CADD)`;
  $("prob-label").textContent = `${result.probability}% pathogenic probability` + caveat;

  const notesList = $("notes-list");
  notesList.innerHTML = "";
  result.notes.forEach(n => {
    const li = document.createElement("li");
    li.textContent = n;
    notesList.appendChild(li);
  });

  const bars = $("contrib-bars");
  bars.innerHTML = "";
  result.contributions
    .slice()
    .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight))
    .forEach(c => {
      const row = document.createElement("div");
      row.className = "contrib-row";
      const w = Math.min(Math.abs(c.weight), 1) * 50;
      const isNeg = c.weight < 0;
      row.innerHTML = `
        <span>${c.feature}</span>
        <div class="contrib-track">
          <div class="contrib-fill ${isNeg ? "neg" : ""}"
               style="left:${isNeg ? 50 - w : 50}%; width:${w}%;"></div>
        </div>`;
      bars.appendChild(row);
    });
}

/* ── Structure panel ───────────────────────────────────────────── */

async function onGeneChange() {
  const gene = $("gene_name").value;
  state.currentResidue = null;
  $("residue-readout").classList.add("hidden");
  $("btn-zoom-residue").classList.add("hidden");
  try {
    const res = await fetch(`/api/structure/${gene}`);
    if (!res.ok) {
      $("struct-label").textContent = `No structure registered for ${gene}`;
      return;
    }
    const info = await res.json();
    $("struct-label").textContent =
      `${info.pdb_id} · chain ${info.chain} · ${info.source === "alphafold" ? "AlphaFold (predicted)" : "experimental"} — ${info.label}`;
    await loadStructure(info.pdb_id, info.chain);
  } catch (e) {
    console.error(e);
  }
  loadHeatmap(gene);
}

function initViewer() {
  state.viewer = $3Dmol.createViewer($("viewer"), { backgroundColor: "0x0e0e0e" });
}

function loadStructure(pdbId, chain) {
  state.viewer.clear();
  state.currentPdbId = pdbId;
  state.currentChain = chain;
  state.currentTierColor = null;
  return new Promise((resolve) => {
    $3Dmol.download(`pdb:${pdbId}`, state.viewer, {}, () => {
      applyAllStyles();
      state.viewer.zoomTo();
      state.viewer.render();
      resolve();
    });
  });
}

/**
 * Single source of truth for what the structure looks like: base spectrum
 * cartoon, an optional tier-colored tint on the relevant chain (set after a
 * prediction), and an optional highlighted residue (set from an example or
 * the manual residue field). Re-run this any time either input changes,
 * rather than patching styles incrementally — avoids one setStyle() call
 * silently wiping out another.
 */
function applyAllStyles() {
  if (!state.viewer) return;
  state.viewer.setStyle({}, { cartoon: { color: "spectrum" } });

  if (state.currentChain) {
    const chainColor = state.currentTierColor || "orange";
    state.viewer.setStyle({ chain: state.currentChain }, { cartoon: { color: chainColor } });
  }

  state.viewer.removeAllLabels();
  if (state.currentResidue && state.currentChain) {
    const { pos, note } = state.currentResidue;
    const sel = { chain: state.currentChain, resi: pos };
    state.viewer.setStyle(sel, {
      cartoon: { color: state.currentTierColor || "orange" },
      stick: { colorscheme: "yellowCarbon", radius: 0.28 },
      sphere: { scale: 0.35, color: "yellow" },
    });

    // addLabel needs a concrete {x,y,z}, not a selector — pull it from the
    // residue's alpha carbon (falling back to any atom in the residue).
    let atoms = state.viewer.selectedAtoms({ ...sel, atom: "CA" });
    if (!atoms.length) atoms = state.viewer.selectedAtoms(sel);
    if (atoms.length) {
      const a = atoms[0];
      state.viewer.addLabel(note || `residue ${pos}`, {
        position: { x: a.x, y: a.y, z: a.z },
        backgroundColor: "0x0e0e0e",
        backgroundOpacity: 0.75,
        fontColor: "0xffffff",
        fontSize: 12,
        borderThickness: 0,
      });
    }
  }
  state.viewer.render();
}

function highlightResidue(pos, wt, mut, note) {
  if (!state.viewer || !state.currentChain) return;
  state.currentResidue = { pos, wt, mut, note };
  applyAllStyles();

  const readout = $("residue-readout");
  readout.classList.remove("hidden");
  const wtLabel = wt ? `${wt}${AA3[wt] ? ` (${AA3[wt]})` : ""}` : null;
  const mutLabel = mut ? `${mut}${AA3[mut] ? ` (${AA3[mut]})` : ""}` : null;
  readout.innerHTML = `<b>residue ${pos}</b>${wtLabel && mutLabel ? ` — ${wtLabel} → ${mutLabel}` : ""}${note ? `<br/>${note}` : ""}`;
  $("btn-zoom-residue").classList.remove("hidden");

  zoomToResidue();
}

function zoomToResidue() {
  if (!state.viewer || !state.currentResidue || !state.currentChain) return;
  state.viewer.zoomTo({ chain: state.currentChain, resi: state.currentResidue.pos });
  state.viewer.zoom(0.4, 600);  // pull back slightly from an extreme close-up
  state.viewer.render();
}

function recolorStructure(color) {
  if (!state.viewer || !state.currentPdbId) return;
  const tierColor = color === "high" ? "0x8B1A1A" : color === "medium" ? "0x7A5C00" : "0x0F5E3A";
  state.currentTierColor = tierColor;
  applyAllStyles();
}

function resetViewer() {
  if (!state.viewer) return;
  state.viewer.zoomTo();
  state.viewer.render();
}

function readManualResidue() {
  const val = Number($("residue_number").value);
  if (!val || val < 1) return;
  highlightResidue(val, null, null, `manually selected residue ${val}`);
}

function downloadStructure() {
  if (!state.currentPdbId) return;
  window.open(`https://files.rcsb.org/download/${state.currentPdbId}.pdb`, "_blank");
}

/* ── Substitution matrix panel (03) ───────────────────────────── */

async function loadHeatmap(gene) {
  const panel = $("panel-matrix");
  try {
    const res = await fetch(`/api/heatmap/${gene}`);
    if (!res.ok) { panel.classList.add("hidden"); return; }
    const data = await res.json();
    renderMatrix(data);
    panel.classList.remove("hidden");
  } catch (e) {
    panel.classList.add("hidden");
  }
}

function renderMatrix(data) {
  // Expected shape: { gene, positions: [{pos, wt, scores: {A: -1.2, C: -3.4, ...}}, ...] }
  const AA = "ACDEFGHIKLMNPQRSTVWY".split("");
  const container = $("matrix-scroll");
  container.innerHTML = "";
  const table = document.createElement("table");
  table.className = "matrix-table";

  const headRow = document.createElement("tr");
  headRow.innerHTML = "<th></th>" + data.positions.map(p => `<th>${p.pos}</th>`).join("");
  table.appendChild(headRow);

  AA.forEach(aa => {
    const row = document.createElement("tr");
    let cells = `<th>${aa}</th>`;
    data.positions.forEach(p => {
      const score = p.scores[aa];
      const color = scoreToColor(score);
      cells += `<td class="matrix-cell" style="background:${color}" data-pos="${p.pos}"></td>`;
    });
    row.innerHTML = cells;
    table.appendChild(row);
  });

  container.appendChild(table);
  container.querySelectorAll(".matrix-cell").forEach(cell => {
    cell.addEventListener("click", () => showColumnDetail(data, Number(cell.dataset.pos)));
  });
}

function scoreToColor(score) {
  // score near 0 = tolerated (light), very negative = disfavored (dark red)
  const clamped = Math.max(-10, Math.min(0, score));
  const t = (clamped + 10) / 10; // 0 (bad) -> 1 (neutral)
  const r = Math.round(139 + (255 - 139) * t);
  const g = Math.round(26 + (255 - 26) * t);
  const b = Math.round(26 + (255 - 26) * t);
  return `rgb(${r},${g},${b})`;
}

function showColumnDetail(data, pos) {
  const posData = data.positions.find(p => p.pos === pos);
  if (!posData) return;
  const detail = $("matrix-detail");
  detail.classList.remove("hidden");
  const rows = Object.entries(posData.scores)
    .sort((a, b) => a[1] - b[1])
    .map(([aa, s]) => `<tr><td>${posData.wt}${pos}${aa}</td><td>${s.toFixed(2)}</td></tr>`)
    .join("");
  detail.innerHTML = `<div class="sub-title">position ${pos} (WT ${posData.wt}) — ranked substitutions</div>
    <table class="matrix-table"><tr><th>mutation</th><th>score</th></tr>${rows}</table>`;
}

/* ── Wire up ───────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => {
  initSliders();
  initViewer();
  loadModelInfo();
  onGeneChange();

  $("variant-form").addEventListener("submit", (e) => {
    e.preventDefault();
    submitPrediction();
  });

  $("gene_name").addEventListener("change", onGeneChange);
  $("btn-reset").addEventListener("click", resetViewer);
  $("btn-download").addEventListener("click", downloadStructure);
  $("btn-zoom-residue").addEventListener("click", zoomToResidue);
  $("residue_number").addEventListener("change", readManualResidue);

  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => applyExample(chip.dataset.ex));
  });
});
