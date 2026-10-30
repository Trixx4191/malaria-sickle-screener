const $ = (id) => document.getElementById(id);

const state = {
  viewer: null,
  currentPdbId: null,
  currentChain: null,
  currentResidue: null,
  currentStructureText: null,
  structureRequest: null,
  structureVersion: 0,
  structureGene: null,
  heatmapRequest: null,
  predictionRequest: null,
  predictionVersion: 0,
};

// Illustrative feature combinations, not retrieved variant annotations.
// The residue substitutions illustrate structures and are not model inputs.
const EXAMPLES = {
  "hbb-high-cadd":         { gene_name: "HBB",  allele_freq_afr: 0.004, cadd_score: 34.0, gene_region: "exonic", conservation_phylop: 2.1,  residue: 6,   wt: "GLU", mut: "VAL", note: "HBB high-CADD preset: residue 6" },
  "hbb-moderate-cadd":     { gene_name: "HBB",  allele_freq_afr: 0.001, cadd_score: 28.0, gene_region: "exonic", conservation_phylop: 1.8,  residue: 6,   wt: "GLU", mut: "LYS", note: "HBB moderate-CADD preset: residue 6" },
  "g6pd-common-frequency": { gene_name: "G6PD", allele_freq_afr: 0.420, cadd_score: 3.0,  gene_region: "exonic", conservation_phylop: -0.5, residue: 68,  wt: "VAL", mut: "MET", note: "G6PD common-frequency preset: residue 68" },
  "g6pd-rare-frequency":   { gene_name: "G6PD", allele_freq_afr: 0.000, cadd_score: 42.0, gene_region: "exonic", conservation_phylop: 2.8,  residue: 188, wt: "SER", mut: "PHE", note: "G6PD rare-frequency preset: residue 188" },
};

const AA3 = { GLU: "E", VAL: "V", LYS: "K", MET: "M", SER: "S", PHE: "F" };
const FEATURE_LABELS = {
  allele_freq_afr: "African allele frequency",
  cadd_score: "CADD score",
  gene_region: "Gene region",
  conservation_phylop: "Conservation proxy",
  is_hbb: "HBB gene flag",
  review_stars: "ClinVar review quality",
};

// Ensembl release 116, GRCh38, verified 2026-10-25. These 1-based inclusive
// intervals cover complete annotated genes, not transcripts or coding sequence.
const GENE_CONTEXT = {
  HBB:  { symbol: "HBB", name: "hemoglobin subunit beta", chromosome: "11", start: 5225464, end: 5229395, strand: -1, cytoband: "11p15.4", chromosomeLength: 135086622, ensemblId: "ENSG00000244734" },
  G6PD: { symbol: "G6PD", name: "glucose-6-phosphate dehydrogenase", chromosome: "X", start: 154517825, end: 154547584, strand: -1, cytoband: "Xq28", chromosomeLength: 156040895, ensemblId: "ENSG00000160211" },
  DARC: { symbol: "ACKR1", name: "atypical chemokine receptor 1 (Duffy blood group)", chromosome: "1", start: 159204568, end: 159206500, strand: 1, cytoband: "1q23.2", chromosomeLength: 248956422, ensemblId: "ENSG00000213088" },
  HBA1: { symbol: "HBA1", name: "hemoglobin subunit alpha 1", chromosome: "16", start: 176660, end: 177527, strand: 1, cytoband: "16p13.3", chromosomeLength: 90338345, ensemblId: "ENSG00000206172" },
  HBA2: { symbol: "HBA2", name: "hemoglobin subunit alpha 2", chromosome: "16", start: 172021, end: 173910, strand: 1, cytoband: "16p13.3", chromosomeLength: 90338345, ensemblId: "ENSG00000188536" },
};

function displayGene(gene) {
  return gene === "DARC" ? "ACKR1 (DARC)" : gene;
}

function cleanCopy(text) {
  return String(text).replace(/\s*\u2014\s*/g, ": ");
}

function setOptionalText(id, value) {
  const node = $(id);
  if (node) node.textContent = value;
}

function updateGeneContext() {
  const gene = $("gene_name").value;
  const info = GENE_CONTEXT[gene];
  if (!info) return;
  const number = value => value.toLocaleString("en-US");
  const locus = `chr${info.chromosome}:${number(info.start)}-${number(info.end)}`;
  const span = info.end - info.start + 1;
  setOptionalText("gene-symbol-label", displayGene(gene));
  setOptionalText("gene-title", info.name);
  setOptionalText("gene-locus", locus);
  setOptionalText("gene-cytoband", info.cytoband);
  setOptionalText("gene-strand", info.strand === 1 ? "Forward (+)" : "Reverse (-)");
  setOptionalText("gene-track-name", `chr${info.chromosome}`);
  setOptionalText("gene-range-end", number(info.chromosomeLength));
  const marker = $("gene-locus-marker");
  if (marker) {
    marker.style.left = `${(info.start - 1) / info.chromosomeLength * 100}%`;
    marker.style.width = `${span / info.chromosomeLength * 100}%`;
    marker.title = `${displayGene(gene)}: ${locus}; ${number(span)} bp gene span. Marker enlarged for visibility.`;
  }
  const reference = $("gene-reference-link");
  if (reference) {
    reference.href = `https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${info.ensemblId}`;
    reference.title = `${info.symbol}: Ensembl GRCh38 gene record`;
  }
}

function setModelStatus(message, status, detail) {
  const bar = $("status-bar");
  bar.textContent = message;
  bar.title = detail;
  bar.style.color = "";
  bar.setAttribute?.("data-state", status);
}

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
  onGeneChange({ preserveResidue: true }).then(loaded => {
    if (loaded && $("gene_name").value === ex.gene_name && Number($("residue_number").value) === ex.residue) {
      highlightResidue(ex.residue, ex.wt, ex.mut, ex.note);
    }
  });
  submitPrediction();
}

async function loadModelInfo() {
  try {
    const res = await fetch("/api/model-info");
    if (!res.ok) throw new Error("Model information unavailable");
    const data = await res.json();
    const m = data.meta || {};
    const modelName = { random_forest: "Random Forest", logistic: "Logistic Regression" }[m.model_type] || "Model";
    const hasRealData = !data.demo_mode && data.data_provenance === "real";
    setOptionalText("model-auc", hasRealData && Number.isFinite(m.auc_all) ? m.auc_all.toFixed(3) : "n/a");
    setOptionalText("model-training-count", Number.isFinite(m.training_variants) ? m.training_variants.toLocaleString() : "n/a");
    const count = $("model-training-count");
    if (count) {
      count.title = data.demo_mode ? "Synthetic examples used to fit the demonstration model."
        : Number.isFinite(m.test_variants) ? "Variants used to fit the model; held-out test variants are excluded."
        : "Reported training variant count from the model metadata.";
    }

    if (data.demo_mode) {
      setModelStatus("Demo mode · synthetic data", "demo", "This demonstration model was trained on synthetic examples, not real genomic data.");
    } else if (data.data_provenance !== "real") {
      setModelStatus("Warning · unverified training data", "warning", `Training feature provenance: ${data.data_provenance || "unknown"}. These results are not verified as using real gnomAD/CADD features.`);
    } else {
      setModelStatus(`real data · ${modelName}`, "ready", "The model was trained with real gnomAD and CADD feature data.");
    }
  } catch (e) {
    setModelStatus("Model unavailable", "error", "Model information could not be loaded. Check your connection and reload the page.");
    setOptionalText("model-auc", "n/a");
    setOptionalText("model-training-count", "n/a");
  }
}

function predictionPayload() {
  return {
    gene_name: $("gene_name").value,
    allele_freq_afr: Number($("allele_freq_afr").value),
    cadd_score: Number($("cadd_score").value),
    gene_region: $("gene_region").value,
    conservation_phylop: Number($("conservation_phylop").value),
  };
}

function invalidatePrediction() {
  ++state.predictionVersion;
  if (state.predictionRequest) state.predictionRequest.abort();
  state.predictionRequest = null;
  const btn = document.querySelector(".btn-primary");
  btn.disabled = false;
  btn.textContent = "Score variant";
  setOptionalText("result-state", "Ready");
  setOptionalText("result-gene", displayGene($("gene_name").value));
  setOptionalText("probability-value", "n/a");
  $("result-empty").textContent = "Inputs changed. Score again.";
  $("result-empty").classList.remove("hidden");
  $("result-body").classList.add("hidden");
}

async function submitPrediction() {
  if (state.predictionRequest) state.predictionRequest.abort();
  const controller = new AbortController();
  const version = ++state.predictionVersion;
  state.predictionRequest = controller;
  const timeout = setTimeout(() => controller.abort(), 20000);
  const btn = document.querySelector(".btn-primary");
  btn.disabled = true;
  btn.textContent = "Scoring…";
  setOptionalText("result-state", "Scoring");
  setOptionalText("result-gene", displayGene($("gene_name").value));
  setOptionalText("probability-value", "n/a");
  $("result-empty").textContent = "Scoring variant…";
  $("result-empty").classList.remove("hidden");
  $("result-body").classList.add("hidden");
  const payload = predictionPayload();
  const requestKey = JSON.stringify(payload);

  try {
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(await res.text());
    const result = await res.json();
    if (version !== state.predictionVersion) return;
    if (requestKey !== JSON.stringify(predictionPayload())) {
      invalidatePrediction();
      return;
    }
    renderResult(result);
  } catch (e) {
    if (version !== state.predictionVersion) return;
    console.error(e);
    $("result-empty").textContent = controller.signal.aborted
      ? "Prediction timed out. Try again."
      : "Prediction unavailable. Check your connection and try again.";
    $("result-empty").classList.remove("hidden");
    $("result-body").classList.add("hidden");
    setOptionalText("result-state", "Ready");
  } finally {
    clearTimeout(timeout);
    if (version === state.predictionVersion) {
      state.predictionRequest = null;
      btn.disabled = false;
      btn.textContent = "Score variant";
    }
  }
}

function renderResult(result) {
  $("result-empty").classList.add("hidden");
  $("result-body").classList.remove("hidden");
  setOptionalText("probability-value", `${result.probability}%`);
  setOptionalText("result-gene", displayGene($("gene_name").value));
  setOptionalText("result-state", "Complete");

  const stamp = $("tier-stamp");
  stamp.textContent = result.tier === "pathogenic" ? "LIKELY PATHOGENIC"
                     : result.tier === "benign" ? "LIKELY BENIGN"
                     : "UNCERTAIN / BORDERLINE";
  stamp.className = "tier-stamp " + result.color;

  $("prob-bar-fill").style.width = result.probability + "%";
  let caveat = "";
  if (result.demo_mode) caveat = "  (demo model, synthetic data)";
  else if (result.data_provenance !== "real") caveat = `  (⚠ trained on ${result.data_provenance} data, not real gnomAD/CADD)`;
  $("prob-label").textContent = `${result.probability}% pathogenic probability` + caveat;

  const notesList = $("notes-list");
  notesList.innerHTML = "";
  result.notes.forEach(n => {
    const li = document.createElement("li");
    li.textContent = cleanCopy(n);
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
      const label = document.createElement("span");
      label.textContent = FEATURE_LABELS[c.feature] || c.feature;
      const track = document.createElement("div");
      track.className = "contrib-track";
      const fill = document.createElement("div");
      fill.className = "contrib-fill";
      fill.style.left = "0%";
      fill.style.width = `${Math.min(Math.abs(c.weight), 1) * 100}%`;
      track.appendChild(fill);
      row.appendChild(label);
      row.appendChild(track);
      bars.appendChild(row);
    });
}

/* ── Structure panel ───────────────────────────────────────────── */

async function onGeneChange({ preserveResidue = false } = {}) {
  const gene = $("gene_name").value;
  updateGeneContext();
  setOptionalText("viewer-gene", displayGene(gene));
  if (state.structureGene && state.structureGene !== gene && !preserveResidue) {
    $("residue_number").value = "";
  }
  state.structureGene = gene;
  const version = ++state.structureVersion;
  if (state.structureRequest) state.structureRequest.abort();
  state.currentPdbId = null;
  state.currentChain = null;
  state.currentStructureText = null;
  state.currentResidue = null;
  $("struct-label").textContent = "";
  $("struct-label").title = "";
  $("btn-download").disabled = true;
  $("btn-reset").disabled = true;
  $("residue-readout").classList.add("hidden");
  $("btn-zoom-residue").classList.add("hidden");
  // The matrix and prediction form work independently of the optional viewer.
  loadHeatmap(gene);
  if (!state.viewer) return false;

  state.viewer.clear();
  state.viewer.render();
  const controller = new AbortController();
  state.structureRequest = controller;
  const timeout = setTimeout(() => controller.abort(), 20000);
  setViewerStatus("Loading structure…");
  try {
    const res = await fetch(`/api/structure/${gene}`, { signal: controller.signal });
    if (!res.ok) {
      throw new Error(`No structure registered for ${gene}`);
    }
    const info = await res.json();
    if (version !== state.structureVersion) return false;
    $("struct-label").textContent = info.source === "alphafold"
      ? `AlphaFold ${info.pdb_id} · chain ${info.chain} · predicted`
      : `PDB ${info.pdb_id} · chain ${info.chain} · experimental`;
    $("struct-label").title = cleanCopy(info.label || "");
    const url = await structureUrl(info, controller.signal);
    const pdbResponse = await fetch(url, { signal: controller.signal });
    if (!pdbResponse.ok) throw new Error(`Structure download failed (${pdbResponse.status})`);
    const pdbText = await pdbResponse.text();
    if (version !== state.structureVersion) return false;
    state.viewer.addModel(pdbText, "pdb");
    if (!state.viewer.selectedAtoms({}).length) throw new Error("Structure file contains no atoms");
    state.currentPdbId = info.pdb_id;
    state.currentChain = info.chain;
    state.currentStructureText = pdbText;
    applyAllStyles();
    state.viewer.zoomTo();
    state.viewer.render();
    setViewerStatus("");
    $("btn-download").disabled = false;
    $("btn-reset").disabled = false;
    readManualResidue();
    return true;
  } catch (e) {
    if (version !== state.structureVersion) return false;
    console.error(e);
    state.viewer.clear();
    state.viewer.render();
    setViewerStatus("Structure unavailable. Check your connection and select the gene again to retry.");
    return false;
  } finally {
    clearTimeout(timeout);
    if (state.structureRequest === controller) state.structureRequest = null;
  }
}

function setViewerStatus(message) {
  $("viewer-status").textContent = message;
  $("viewer-status").classList.toggle("hidden", !message);
}

async function initViewer() {
  try {
    if (!window.$3Dmol) await new Promise((resolve, reject) => {
      const script = document.createElement("script");
      const timeout = setTimeout(() => reject(new Error("Viewer download timed out")), 15000);
      script.src = "https://3dmol.org/build/3Dmol-min.js";
      script.async = true;
      script.onload = () => { clearTimeout(timeout); resolve(); };
      script.onerror = () => { clearTimeout(timeout); reject(new Error("Viewer download failed")); };
      document.head.appendChild(script);
    });
    state.viewer = window.$3Dmol.createViewer($("viewer"), { backgroundColor: "0x111c1a" });
    return true;
  } catch (e) {
    console.error(e);
    state.viewer = null;
    setViewerStatus("3D viewer unavailable. Predictions and substitution matrices are still available.");
    return false;
  }
}

async function structureUrl(info, signal) {
  if (info.source !== "alphafold") {
    return `https://files.rcsb.org/download/${encodeURIComponent(info.pdb_id)}.pdb`;
  }
  const modelId = info.pdb_id.match(/^AF-([A-Z0-9]+)-F\d+$/);
  if (!modelId) throw new Error("Invalid AlphaFold model identifier");
  // Discover the current file version instead of pinning a model_vN URL.
  const response = await fetch(`https://alphafold.ebi.ac.uk/api/prediction/${modelId[1]}`, { signal });
  if (!response.ok) throw new Error("AlphaFold prediction metadata unavailable");
  const predictions = await response.json();
  const prediction = predictions.find(item =>
    item.entryId === info.pdb_id || item.modelEntityId === info.pdb_id ||
    (typeof item.pdbUrl === "string" &&
      item.pdbUrl.startsWith(`https://alphafold.ebi.ac.uk/files/${info.pdb_id}-model_v`))
  );
  if (!prediction || !prediction.pdbUrl) throw new Error("AlphaFold PDB file unavailable");
  const url = new URL(prediction.pdbUrl);
  if (url.protocol !== "https:" || url.hostname !== "alphafold.ebi.ac.uk") {
    throw new Error("Unexpected AlphaFold file URL");
  }
  return url.href;
}

/**
 * Keep secondary-structure colors independent of prediction risk:
 * 3Dmol's ssPyMol palette is helix red, sheet yellow, coil green.
 * Fade other chains to focus the selected gene without changing the palette.
 * Residue atom details use Jmol element colors (C gray, N blue, O red, S yellow).
 * Reapply all layers together so a residue selection preserves the cartoon.
 */
function applyAllStyles() {
  if (!state.viewer) return;
  const cartoon = { colorscheme: "ssPyMol", arrows: true };
  state.viewer.setStyle({}, { cartoon: { ...cartoon, opacity: state.currentChain ? 0.35 : 1 } });

  if (state.currentChain) {
    state.viewer.setStyle({ chain: state.currentChain }, { cartoon: { ...cartoon, opacity: 1 } });
  }

  state.viewer.removeAllLabels();
  if (state.currentResidue && state.currentChain) {
    const { pos, note } = state.currentResidue;
    const sel = { chain: state.currentChain, resi: pos };
    state.viewer.setStyle(sel, {
      cartoon: { ...cartoon, opacity: 1 },
      stick: { colorscheme: "Jmol", radius: 0.24 },
      sphere: { colorscheme: "Jmol", scale: 0.3 },
    });

    // addLabel needs a concrete {x,y,z}, not a selector. Pull it from the
    // residue's alpha carbon (falling back to any atom in the residue).
    let atoms = state.viewer.selectedAtoms({ ...sel, atom: "CA" });
    if (!atoms.length) atoms = state.viewer.selectedAtoms(sel);
    if (atoms.length) {
      const a = atoms[0];
      state.viewer.addLabel(cleanCopy(note || `residue ${pos}`), {
        position: { x: a.x, y: a.y, z: a.z },
        backgroundColor: "0x111c1a",
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
  if (!state.viewer || !state.currentChain) return false;
  if (!Number.isInteger(pos) || pos < 1) {
    clearResidueSelection("Enter a whole-number residue of at least 1.");
    return false;
  }
  if (!state.viewer.selectedAtoms({ chain: state.currentChain, resi: pos }).length) {
    clearResidueSelection(`Residue ${pos} is not present in chain ${state.currentChain} of this structure.`);
    return false;
  }
  state.currentResidue = { pos, wt, mut, note };
  applyAllStyles();

  const readout = $("residue-readout");
  readout.classList.remove("hidden");
  const wtLabel = wt ? `${wt}${AA3[wt] ? ` (${AA3[wt]})` : ""}` : null;
  const mutLabel = mut ? `${mut}${AA3[mut] ? ` (${AA3[mut]})` : ""}` : null;
  readout.innerHTML = `<b>residue ${pos}</b>${wtLabel && mutLabel ? `: ${wtLabel} → ${mutLabel}` : ""}${note ? `<br/>${cleanCopy(note)}` : ""}`;
  $("btn-zoom-residue").classList.remove("hidden");

  zoomToResidue();
  return true;
}

function clearResidueSelection(message = "") {
  state.currentResidue = null;
  applyAllStyles();
  $("residue-readout").textContent = message;
  $("residue-readout").classList.toggle("hidden", !message);
  $("btn-zoom-residue").classList.add("hidden");
}

function zoomToResidue() {
  if (!state.viewer || !state.currentResidue || !state.currentChain) return;
  state.viewer.zoomTo({ chain: state.currentChain, resi: state.currentResidue.pos });
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  state.viewer.zoom(0.4, reducedMotion ? 0 : 600);  // pull back slightly from an extreme close-up
  state.viewer.render();
}

function resetViewer() {
  if (!state.viewer) return;
  state.viewer.zoomTo();
  state.viewer.render();
}

function readManualResidue() {
  const raw = String($("residue_number").value || "").trim();
  if (!raw) {
    clearResidueSelection();
    return;
  }
  const val = Number(raw);
  if (!Number.isInteger(val) || val < 1) {
    clearResidueSelection("Enter a whole-number residue of at least 1.");
    return;
  }
  // Preserve the field while the optional viewer or structure is still loading.
  highlightResidue(val, null, null, `manually selected residue ${val}`);
}

function downloadStructure() {
  if (!state.currentStructureText) return;
  const url = URL.createObjectURL(new Blob([state.currentStructureText], { type: "chemical/x-pdb" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${state.currentPdbId}.pdb`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ── Amino acid substitutions panel (04) ──────────────────────── */

async function loadHeatmap(gene) {
  const panel = $("panel-matrix");
  if (state.heatmapRequest) state.heatmapRequest.abort();
  const controller = new AbortController();
  state.heatmapRequest = controller;
  panel.classList.add("hidden");
  $("matrix-detail").classList.add("hidden");
  try {
    const res = await fetch(`/api/heatmap/${gene}`, { signal: controller.signal });
    if (!res.ok) return;
    const data = await res.json();
    if (state.heatmapRequest !== controller) return;
    renderMatrix(data);
    panel.classList.remove("hidden");
  } catch (e) {
    if (state.heatmapRequest === controller) panel.classList.add("hidden");
  } finally {
    if (state.heatmapRequest === controller) state.heatmapRequest = null;
  }
}

function positionScores(position) {
  // Current precompute output uses effects; retain older scores caches.
  return position.effects || position.scores || {};
}

function renderMatrix(data) {
  // Expected shape: { gene, positions: [{pos, wt, effects: {A: -1.2, C: -3.4, ...}}, ...] }
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
      const score = positionScores(p)[aa];
      const color = Number.isFinite(score) ? scoreToColor(score) : "#eee";
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
  const rows = Object.entries(positionScores(posData))
    .filter(([, score]) => Number.isFinite(score))
    .sort((a, b) => a[1] - b[1])
    .map(([aa, s]) => `<tr><td>${posData.wt}${pos}${aa}</td><td>${s.toFixed(2)}</td></tr>`)
    .join("");
  detail.innerHTML = `<div class="sub-title">position ${pos} (WT ${posData.wt}): ranked substitutions</div>
    <table class="matrix-table"><tr><th>mutation</th><th>score</th></tr>${rows}</table>`;
}

/* ── Wire up ───────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => {
  updateGeneContext();
  initSliders();
  setOptionalText("result-state", "Ready");
  setOptionalText("result-gene", displayGene($("gene_name").value));
  setOptionalText("viewer-gene", displayGene($("gene_name").value));

  $("variant-form").addEventListener("submit", (e) => {
    e.preventDefault();
    submitPrediction();
  });

  $("gene_name").addEventListener("change", () => {
    invalidatePrediction();
    onGeneChange();
  });
  for (const id of ["allele_freq_afr", "cadd_score", "conservation_phylop"]) {
    $(id).addEventListener("input", invalidatePrediction);
  }
  $("gene_region").addEventListener("change", invalidatePrediction);
  $("btn-reset").addEventListener("click", resetViewer);
  $("btn-download").addEventListener("click", downloadStructure);
  $("btn-zoom-residue").addEventListener("click", zoomToResidue);
  $("residue_number").addEventListener("change", readManualResidue);

  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => applyExample(chip.dataset.ex));
  });

  loadModelInfo();
  loadHeatmap($("gene_name").value);
  initViewer().then(ready => { if (ready) onGeneChange(); });
});
