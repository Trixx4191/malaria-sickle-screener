const $ = (id) => document.getElementById(id);

const state = {
  viewer: null,
  currentPdbData: null,
  currentPdbId: null,
};

const EXAMPLES = {
  "hbs":          { gene_name: "HBB",  allele_freq_afr: 0.004, cadd_score: 34.0, gene_region: "exonic",   conservation_phylop: 2.1 },
  "hbb-path":     { gene_name: "HBB",  allele_freq_afr: 0.001, cadd_score: 28.0, gene_region: "exonic",   conservation_phylop: 1.8 },
  "g6pd-benign":  { gene_name: "G6PD", allele_freq_afr: 0.420, cadd_score: 3.0,  gene_region: "intronic", conservation_phylop: -0.5 },
  "g6pd-rare":    { gene_name: "G6PD", allele_freq_afr: 0.000, cadd_score: 42.0, gene_region: "exonic",   conservation_phylop: 2.8 },
};

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
  onGeneChange();
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
  try {
    const res = await fetch(`/api/structure/${gene}`);
    if (!res.ok) {
      $("struct-label").textContent = `No structure registered for ${gene}`;
      return;
    }
    const info = await res.json();
    $("struct-label").textContent =
      `${info.pdb_id} · chain ${info.chain} · ${info.source === "alphafold" ? "AlphaFold (predicted)" : "experimental"} — ${info.label}`;
    loadStructure(info.pdb_id, info.chain);
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
  $3Dmol.download(`pdb:${pdbId}`, state.viewer, {}, () => {
    state.viewer.setStyle({}, { cartoon: { color: "spectrum" } });
    if (chain) {
      state.viewer.setStyle({ chain: chain }, { cartoon: { color: "orange" } });
    }
    state.viewer.zoomTo();
    state.viewer.render();
    state.currentPdbData = state.viewer.exportJSON ? null : null; // placeholder for download
  });
}

function recolorStructure(color) {
  if (!state.viewer || !state.currentPdbId) return;
  const chain = $("struct-label").textContent.split("chain ")[1]?.split(" ")[0];
  const tierColor = color === "high" ? "0x8B1A1A" : color === "medium" ? "0x7A5C00" : "0x0F5E3A";
  if (chain) {
    state.viewer.setStyle({ chain: chain }, { cartoon: { color: tierColor } });
    state.viewer.render();
  }
}

function resetViewer() {
  if (!state.viewer) return;
  state.viewer.zoomTo();
  state.viewer.render();
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

  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => applyExample(chip.dataset.ex));
  });
});
