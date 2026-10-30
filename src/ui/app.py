"""
app.py — legacy Gradio prototype, outside the supported serving path.

The current app is FastAPI with static HTML/CSS/JavaScript. Use:
    python -m pip install -r requirements-runtime.txt
    python -m uvicorn webapp.main:app --reload --port 8000

See README.md and docs/DEPLOYMENT.md for Docker Spaces and native deployment.
Gradio is not included in the current requirements. This retained prototype
does not implement the current service's scaler, artifact/provenance validation,
or synthetic-demo handling and should not be used to verify a current model.
"""

import json
import sys
from pathlib import Path

import gradio as gr
import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.config import MODEL_FILE, MODELS_DIR, CADD_DELETERIOUS_THRESHOLD

#  Load model 

def load_model():
    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_FILE}.\n"
            "Run: python src/models/train.py  first."
        )
    return joblib.load(MODEL_FILE)

try:
    BUNDLE = load_model()
    MODEL_LOADED = True
except FileNotFoundError:
    BUNDLE = None
    MODEL_LOADED = False

# Load metadata if available
META = {}
meta_path = MODELS_DIR / "model_meta.json"
if meta_path.exists():
    with open(meta_path) as f:
        META = json.load(f)

#  Prediction logic 

GENE_REGION_MAP = {"Exonic (coding)": 2, "UTR (untranslated)": 1, "Intronic / other": 0}
HBB_GENES = {"HBB", "HBB-LCR"}  # sickle-cell genes

def predict(
    allele_freq_afr: float,
    cadd_score: float,
    gene_region: str,
    conservation: float,
    gene_name: str,
) -> tuple[str, str, str]:
    """
    Returns: (risk_label, confidence_str, interpretation)
    """
    if not MODEL_LOADED:
        return "Model not loaded", "—", "Run python src/models/train.py first."

    is_hbb = 1 if gene_name.strip().upper() in HBB_GENES else 0
    review_stars = 1   # fixed serving input; not a conservative clinical estimate

    # Canonical feature ordering comes from the saved model bundle.
    feature_order = BUNDLE.get("feature_names")
    if not feature_order:
        return "Model schema missing", "—", "Saved model bundle does not include feature_names.\nRe-train the model with src/models/train.py."

    feature_order_set = set(feature_order)
    missing = [f for f in feature_order if f not in {
        "allele_freq_afr",
        "cadd_score",
        "gene_region",
        "conservation_phylop",
        "is_hbb",
        "review_stars",
    }]
    if missing:
        return "Model schema mismatch", "—", f"UI cannot construct these required features: {missing}."

    feature_values = {
        "allele_freq_afr": allele_freq_afr,
        "cadd_score": cadd_score,
        "gene_region": GENE_REGION_MAP.get(gene_region, 0),
        "conservation_phylop": conservation,
        "is_hbb": is_hbb,
        "review_stars": review_stars,
    }

    X = np.array([[feature_values[name] for name in feature_order]])

    prob_pathogenic = BUNDLE["model"].predict_proba(X)[0][1]
    prob_pct = round(prob_pathogenic * 100, 1)

    if prob_pathogenic >= 0.75:
        label = "Likely Pathogenic"
        color_hint = "high"
    elif prob_pathogenic >= 0.40:
        label = "Uncertain / Borderline"
        color_hint = "medium"
    else:
        label = "Likely Benign"
        color_hint = "low"

    # Build interpretation
    lines = []
    if allele_freq_afr > 0.05:
        lines.append(f"• Supplied AFR frequency {allele_freq_afr:.3f} is common in the annotated population group. "
                     "Frequency alone does not determine pathogenicity.")
    elif allele_freq_afr < 0.001:
        lines.append(f"• Supplied AFR frequency {allele_freq_afr:.4f} is very rare. "
                     "Interpret it with the other annotations and their source coverage.")

    if cadd_score >= CADD_DELETERIOUS_THRESHOLD:
        lines.append(f"• CADD score {cadd_score:.1f} meets the configured score threshold (20).")
    else:
        lines.append(f"• CADD score {cadd_score:.1f} is below the configured score threshold (20).")

    if is_hbb:
        lines.append("• This is an HBB gene variant — associated with sickle-cell disease "
                     "or beta-thalassemia. Interpret in full clinical context.")

    interpretation = "\n".join(lines) if lines else "No specific flags."

    return label, f"{prob_pct}% pathogenic probability", interpretation


#  UI Layout

CSS = """
/* ── Typography ── */
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;1,9..144,300&display=swap');

body, .gradio-container {
    font-family: 'Fraunces', Georgia, serif !important;
    background: #F8F5EE !important;
}

/* Header */
.app-header {
    border-bottom: 1px solid #1a1a1a;
    padding: 1.5rem 0 1rem;
    margin-bottom: 1.5rem;
}
.app-header h1 {
    font-size: 1.6rem;
    font-weight: 300;
    letter-spacing: -0.02em;
    color: #0e0e0e;
    margin: 0;
}
.app-header p {
    font-size: 0.85rem;
    color: #666;
    margin: 0.3rem 0 0;
    font-family: 'DM Mono', monospace;
}

/* Panels */
.panel {
    background: #fff;
    border: 1px solid #e0dbd0;
    border-radius: 4px;
    padding: 1.5rem;
}

/* Result display */
.result-label {
    font-size: 2rem;
    font-weight: 300;
    letter-spacing: -0.03em;
    padding: 1rem 0 0.5rem;
}
.result-label.high   { color: #8B1A1A; }
.result-label.medium { color: #7A5C00; }
.result-label.low    { color: #0F5E3A; }

/* Mono elements */
.mono { font-family: 'DM Mono', monospace; font-size: 0.8rem; color: #888; }

/* Override Gradio defaults */
.gr-button-primary {
    background: #0e0e0e !important;
    color: #F8F5EE !important;
    border-radius: 2px !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.05em !important;
}
label.svelte-1b6s6g { font-family: 'DM Mono', monospace !important; font-size: 0.75rem !important; color: #555 !important; }
"""

DESCRIPTION = """
<div class="app-header">
  <h1>West Africa Variant Screener</h1>
  <p>Legacy Gradio prototype · Use the FastAPI app described in README.md · Accra, Ghana</p>
</div>

<p style="font-size:0.9rem;color:#444;line-height:1.6;margin-bottom:1rem">
This retained prototype scores manually supplied annotations. The current
pipeline uses ClinVar labels, gnomAD AFR frequencies and CADD-derived features.
West African clinical performance has not been established. Use the current
FastAPI interface for model-state checks and supported serving behavior.
</p>
"""

MODEL_INFO = f"""
<div style="font-family:'DM Mono',monospace;font-size:0.75rem;color:#888;border-top:1px solid #e0dbd0;padding-top:1rem;margin-top:1rem;line-height:1.8">
Model type: {META.get('model_type', 'random_forest').replace('_',' ').title()}<br>
Reported test AUC-ROC (sidecar metadata): {META.get('auc_all', '—')}<br>
Cross-validation: {META.get('cv_mean', '—')} ± {META.get('cv_std', '—')}<br>
Training variants: {META.get('training_variants', '—')}<br>
Features: allele_freq_afr · cadd_score · gene_region · conservation · is_hbb · review_stars
</div>
""" if META else ""

DISCLAIMER = """
<div style="font-size:0.75rem;color:#999;font-family:'DM Mono',monospace;margin-top:1.5rem;border-top:1px solid #e0dbd0;padding-top:1rem">
⚠ Research prototype. Not validated for clinical use. Predictions reflect patterns
in ClinVar training data. Consult a medical geneticist for clinical variant interpretation.<br><br>
Alhassan Salifu · Accra, Ghana ·
<a href="https://github.com/Trixx4191/malaria-sickle-screener" style="color:#555">GitHub</a>
</div>
"""


with gr.Blocks(css=CSS, title="West Africa Variant Screener") as demo:
    gr.HTML(DESCRIPTION)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Variant features", elem_classes=["mono"])

            allele_freq = gr.Slider(
                minimum=0.0, maximum=1.0, value=0.01, step=0.001,
                label="AFR allele frequency (fraction, 0–1)",
                info="Manually supplied annotation; the current pipeline queries gnomAD genome AFR"
            )
            cadd = gr.Slider(
                minimum=0.0, maximum=60.0, value=15.0, step=0.5,
                label="CADD Phred score",
                info="Manually supplied annotation; the current pipeline uses GRCh38-v1.7"
            )
            gene_region = gr.Radio(
                choices=["Exonic (coding)", "UTR (untranslated)", "Intronic / other"],
                value="Exonic (coding)",
                label="Gene region"
            )
            conservation = gr.Slider(
                minimum=-3.0, maximum=3.0, value=0.5, step=0.1,
                label="Conservation (CADD-derived proxy)",
                info="Training uses clip(CADD / 40, -3, 3), not measured UCSC phyloP"
            )
            gene_name = gr.Textbox(
                value="HBB",
                label="Gene symbol",
                placeholder="HBB, G6PD, DARC, HBA1, HBA2 …",
                info="Only the HBB flag enters the classifier; use DARC for ACKR1"
            )

            btn = gr.Button("Predict pathogenicity →", variant="primary")

        with gr.Column(scale=1):
            gr.Markdown("### Prediction", elem_classes=["mono"])

            result_label    = gr.Textbox(label="Classification", interactive=False)
            result_conf     = gr.Textbox(label="Model percentage", interactive=False)
            result_interp   = gr.Textbox(
                label="Interpretation notes", lines=5, interactive=False
            )
            gr.HTML(MODEL_INFO)

    gr.HTML(DISCLAIMER)

    btn.click(
        fn=predict,
        inputs=[allele_freq, cadd, gene_region, conservation, gene_name],
        outputs=[result_label, result_conf, result_interp]
    )

    # Illustrative feature presets, not retrieved annotations for named variants.
    gr.Examples(
        examples=[
            [0.004, 34.0, "Exonic (coding)", 2.1, "HBB"],    # higher-CADD HBB preset
            [0.001, 28.0, "Exonic (coding)", 1.8, "HBB"],    # moderate-CADD HBB preset
            [0.420, 3.0,  "Intronic / other", -0.5, "G6PD"], # common-frequency G6PD preset
            [0.000, 42.0, "Exonic (coding)", 2.8, "G6PD"],   # rare-frequency G6PD preset
        ],
        inputs=[allele_freq, cadd, gene_region, conservation, gene_name],
        label="Illustrative presets (no variant lookup)",
    )


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,      # set share=True to get a public URL
        show_error=True,
    )
