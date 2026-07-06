/* ---------------------------------------------------------------------
   3D DNA helix — the signature visual. Two strands + rungs; rungs sweep
   to a new color (teal/gold/clay) and one rung pulses gold/teal to mark
   the queried variant's locus once a prediction comes back.
--------------------------------------------------------------------- */

const COLORS = {
  teal: 0x21a190,
  gold: 0xd9a62e,
  clay: 0xc4432e,
  neutral: 0x3a4a52,
  strand: 0x1c2b31,
};

class Helix {
  constructor(container) {
    this.container = container;
    this.rungCount = 22;
    this.turns = 3.1;
    this.height = 6.4;
    this.radius = 1.05;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    this.camera.position.set(0, 0, 6.2);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(this.renderer.domElement);

    this.group = new THREE.Group();
    this.scene.add(this.group);

    this._buildStrands();
    this._buildRungs();
    this._buildLights();

    this.highlightIndex = Math.floor(this.rungCount * 0.4);
    this.pulseOn = false;

    this._resize();
    window.addEventListener("resize", () => this._resize());

    this.clock = new THREE.Clock();
    this._tick();
  }

  _pointAt(t, offset) {
    const angle = t * this.turns * Math.PI * 2 + offset;
    const y = (t - 0.5) * this.height;
    return new THREE.Vector3(Math.cos(angle) * this.radius, y, Math.sin(angle) * this.radius);
  }

  _buildStrands() {
    const samples = 220;
    [0, Math.PI].forEach((offset) => {
      const pts = [];
      for (let i = 0; i <= samples; i++) pts.push(this._pointAt(i / samples, offset));
      const curve = new THREE.CatmullRomCurve3(pts);
      const geo = new THREE.TubeGeometry(curve, 220, 0.045, 8, false);
      const mat = new THREE.MeshStandardMaterial({
        color: COLORS.strand, emissive: COLORS.teal, emissiveIntensity: 0.35,
        roughness: 0.4, metalness: 0.2,
      });
      this.group.add(new THREE.Mesh(geo, mat));
    });
  }

  _buildRungs() {
    this.rungs = [];
    for (let i = 0; i < this.rungCount; i++) {
      const t = (i + 0.5) / this.rungCount;
      const a = this._pointAt(t, 0);
      const b = this._pointAt(t, Math.PI);
      const mid = a.clone().add(b).multiplyScalar(0.5);
      const dist = a.distanceTo(b);

      const geo = new THREE.CylinderGeometry(0.032, 0.032, dist, 8);
      const mat = new THREE.MeshStandardMaterial({
        color: COLORS.neutral, roughness: 0.5, metalness: 0.1,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(mid);
      mesh.lookAt(b);
      mesh.rotateX(Math.PI / 2);
      this.group.add(mesh);
      this.rungs.push(mesh);
    }
  }

  _buildLights() {
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const p1 = new THREE.PointLight(0x21a190, 1.1, 20);
    p1.position.set(3, 2, 4);
    this.scene.add(p1);
    const p2 = new THREE.PointLight(0xd9a62e, 0.5, 20);
    p2.position.set(-3, -2, -3);
    this.scene.add(p2);
  }

  _resize() {
    const w = this.container.clientWidth || 400;
    const h = this.container.clientHeight || 360;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  /** Set locus highlight by gene region: exonic=near top, UTR=mid, intronic=near bottom */
  setLocus(regionValue) {
    const frac = { 2: 0.72, 1: 0.5, 0: 0.28 }[regionValue] ?? 0.4;
    this.highlightIndex = Math.min(this.rungCount - 1, Math.floor(frac * this.rungCount));
  }

  /** Sweep rung colors to reflect a tier: 'high' | 'medium' | 'low' | null (reset) */
  paint(tier) {
    const color = tier === "high" ? COLORS.clay : tier === "medium" ? COLORS.gold : tier === "low" ? COLORS.teal : COLORS.neutral;
    this.rungs.forEach((mesh, i) => {
      const delay = Math.abs(i - this.highlightIndex) * 40;
      setTimeout(() => {
        mesh.material.color.setHex(i === this.highlightIndex ? COLORS.gold : color);
        mesh.material.emissive = new THREE.Color(i === this.highlightIndex ? COLORS.gold : color);
        mesh.material.emissiveIntensity = i === this.highlightIndex ? 0.9 : 0.25;
      }, delay);
    });
    this.pulseOn = tier != null;
  }

  _tick() {
    requestAnimationFrame(() => this._tick());
    const dt = this.clock.getDelta();
    const t = this.clock.getElapsedTime();
    this.group.rotation.y += dt * 0.35;

    if (this.pulseOn && this.rungs[this.highlightIndex]) {
      const s = 1 + Math.sin(t * 3.2) * 0.28;
      this.rungs[this.highlightIndex].scale.set(s, 1, s);
    }
    this.renderer.render(this.scene, this.camera);
  }
}

/* ---------------------------------------------------------------------
   App wiring
--------------------------------------------------------------------- */

const helix = new Helix(document.getElementById("helixStage"));

const REGION_VALUE = { "Exonic (coding)": 2, "UTR (untranslated)": 1, "Intronic / other": 0 };

const state = {
  allele_freq_afr: 0.01,
  cadd_score: 15.0,
  gene_region: "Exonic (coding)",
  conservation_phylop: 0.5,
  gene_name: "HBB",
};

const $ = (id) => document.getElementById(id);

function syncLabels() {
  $("afLabel").textContent = state.allele_freq_afr.toFixed(3);
  $("caddLabel").textContent = state.cadd_score.toFixed(1);
  $("consLabel").textContent = state.conservation_phylop.toFixed(1);
}

$("afSlider").addEventListener("input", (e) => { state.allele_freq_afr = parseFloat(e.target.value); syncLabels(); });
$("caddSlider").addEventListener("input", (e) => { state.cadd_score = parseFloat(e.target.value); syncLabels(); });
$("consSlider").addEventListener("input", (e) => { state.conservation_phylop = parseFloat(e.target.value); syncLabels(); });
$("geneInput").addEventListener("input", (e) => { state.gene_name = e.target.value; });

document.querySelectorAll("#regionSeg button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#regionSeg button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.gene_region = btn.dataset.value;
    helix.setLocus(REGION_VALUE[state.gene_region]);
    $("helixCaption").textContent = `${state.gene_name || "—"} · ${state.gene_region.split(" ")[0].toLowerCase()} region highlighted`;
  });
});

document.querySelectorAll(".gene-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    state.gene_name = chip.dataset.gene;
    $("geneInput").value = chip.dataset.gene;
    $("helixCaption").textContent = `${state.gene_name} · ${state.gene_region.split(" ")[0].toLowerCase()} region highlighted`;
  });
});

const EXAMPLES = [
  { allele_freq_afr: 0.004, cadd_score: 34.0, gene_region: "Exonic (coding)", conservation_phylop: 2.1, gene_name: "HBB" },
  { allele_freq_afr: 0.001, cadd_score: 28.0, gene_region: "Exonic (coding)", conservation_phylop: 1.8, gene_name: "HBB" },
  { allele_freq_afr: 0.420, cadd_score: 3.0, gene_region: "Intronic / other", conservation_phylop: -0.5, gene_name: "G6PD" },
  { allele_freq_afr: 0.000, cadd_score: 42.0, gene_region: "Exonic (coding)", conservation_phylop: 2.8, gene_name: "G6PD" },
];

document.querySelectorAll(".example-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const ex = EXAMPLES[parseInt(chip.dataset.ex, 10)];
    Object.assign(state, ex);
    $("afSlider").value = ex.allele_freq_afr;
    $("caddSlider").value = ex.cadd_score;
    $("consSlider").value = ex.conservation_phylop;
    $("geneInput").value = ex.gene_name;
    document.querySelectorAll("#regionSeg button").forEach((b) => {
      b.classList.toggle("active", b.dataset.value === ex.gene_region);
    });
    syncLabels();
    helix.setLocus(REGION_VALUE[ex.gene_region]);
    runPrediction();
  });
});

async function loadModelInfo() {
  try {
    const res = await fetch("/api/model-info");
    const info = await res.json();
    const demo = info.demo_mode
      ? `<span class="demo-flag">DEMO MODEL — synthetic, run src/models/train.py for real results</span>`
      : `AUC ${info.auc_all ?? "—"} · CV ${info.cv_mean ?? "—"}±${info.cv_std ?? "—"}`;
    $("modelMeta").innerHTML = `${info.model_type ?? "model"} · ${info.training_variants ?? "—"} variants<br/>${demo}`;
    $("modelStrip").innerHTML =
      `Model: ${info.model_type ?? "—"}<br/>Training variants: ${info.training_variants ?? "—"}<br/>` +
      `Features: ${info.feature_names.join(" · ")}`;
  } catch (e) {
    $("modelMeta").textContent = "model info unavailable";
  }
}

function renderGel(contributions) {
  const container = $("gelLanes");
  container.innerHTML = "";
  contributions.forEach((c) => {
    const pct = Math.min(100, Math.abs(c.push) * 50); // half-track max width
    const cls = c.push >= 0 ? "push-path" : "push-benign";
    const lane = document.createElement("div");
    lane.className = "lane";
    lane.innerHTML = `
      <div class="lane-name">${c.feature}</div>
      <div class="lane-track"><div class="lane-mid"></div><div class="lane-band ${cls}" style="width:${pct}%"></div></div>
      <div class="lane-val">${c.value}</div>
    `;
    container.appendChild(lane);
  });
}

async function runPrediction() {
  const btn = $("runBtn");
  btn.disabled = true;
  btn.textContent = "Running…";

  try {
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state),
    });
    if (!res.ok) throw new Error(await res.text());
    const result = await res.json();

    $("resultEmpty").style.display = "none";
    $("resultBody").style.display = "block";

    const labelEl = $("resultLabel");
    labelEl.textContent = result.label;
    labelEl.className = `result-label ${result.tier}`;
    $("resultProb").textContent = `${result.probability}%`;

    const notesEl = $("resultNotes");
    notesEl.innerHTML = "";
    result.interpretation.forEach((line) => {
      const li = document.createElement("li");
      li.textContent = line;
      notesEl.appendChild(li);
    });

    renderGel(result.contributions);

    const statusEl = $("helixStatus");
    statusEl.className = `helix-status ${result.tier}`;
    statusEl.textContent = result.label.toLowerCase();
    $("helixCaption").textContent = `${state.gene_name} · ${state.gene_region.split(" ")[0].toLowerCase()} region · ${result.probability}% pathogenic`;

    helix.setLocus(REGION_VALUE[state.gene_region]);
    helix.paint(result.tier);
  } catch (e) {
    $("resultEmpty").style.display = "block";
    $("resultEmpty").textContent = "Prediction failed — check the console / API logs.";
    $("resultBody").style.display = "none";
  } finally {
    btn.disabled = false;
    btn.textContent = "Predict pathogenicity →";
  }
}

$("runBtn").addEventListener("click", runPrediction);

syncLabels();
loadModelInfo();
