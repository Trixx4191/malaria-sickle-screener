"""Check a running deployment without training dependencies or test fixtures.

Usage: python3 scripts/smoke_deployment.py --base-url https://your-hostname
"""

import argparse
import itertools
import json
import math
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:7860")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    def request(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = urllib.request.Request(base + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    status, raw = request("/api/health")
    health = json.loads(raw)
    assert status == 200 and health == {
        "status": "ok", "demo_mode": False, "data_provenance": "real"
    }, (status, health)
    status, raw = request("/api/model-info")
    info = json.loads(raw)
    assert status == 200 and info["data_provenance"] == "real" and not info["demo_mode"]
    genes = info["genes"]
    assert set(genes) == {"HBB", "G6PD", "DARC", "HBA1", "HBA2"}

    standard = {"gene_name": "HBB", "gene_region": "exonic", "allele_freq_afr": 0.01,
                "cadd_score": 25, "conservation_phylop": 1}
    cases = [dict(zip(standard, values)) for values in itertools.product(
        genes, ["exonic", "utr", "intronic"], [0, 1], [0, 60], [-5, 5]
    )]
    cases += [{**standard, "gene_name": gene, "gene_region": region}
              for gene, region in itertools.product(genes, ["exonic", "utr", "intronic"])]
    cases.append({**standard, "gene_name": " hbb ", "gene_region": " EXONIC "})
    timings, tiers = [], set()
    for body in cases:
        started = time.perf_counter()
        status, raw = request("/api/predict", body)
        timings.append((time.perf_counter() - started) * 1000)
        result = json.loads(raw)
        assert status == 200, (body, status, result)
        assert result["data_provenance"] == "real" and not result["demo_mode"]
        assert math.isfinite(result["probability"]) and 0 <= result["probability"] <= 100
        assert result["tier"] in {"benign", "uncertain", "pathogenic"}
        tiers.add(result["tier"])

    invalid = [{"allele_freq_afr": -0.001}, {"allele_freq_afr": 1.001},
               {"cadd_score": -0.1}, {"cadd_score": 60.1},
               {"conservation_phylop": -5.1}, {"conservation_phylop": 5.1},
               {"gene_name": "unknown"}, {"gene_region": "unknown"},
               {"gene_name": None}, {"gene_region": None},
               {"allele_freq_afr": "NaN"}, {"cadd_score": "Infinity"},
               {"conservation_phylop": "-Infinity"}, {"allele_freq_afr": None}]
    for changes in invalid:
        status, raw = request("/api/predict", {**standard, **changes})
        assert status == 422, (changes, status, raw)
    for omitted in standard:
        status, raw = request("/api/predict", {k: v for k, v in standard.items() if k != omitted})
        assert status == 422, (omitted, status, raw)

    for path in ("/", "/style.css", "/script.js", "/openapi.json"):
        status, raw = request(path)
        assert status == 200, (path, status)
        if path == "/script.js":
            assert b"ssPyMol" in raw
    for gene in genes:
        status, raw = request("/api/structure/" + gene)
        assert status == 200 and json.loads(raw)["source"] in {"experimental", "alphafold"}
        status, raw = request("/api/heatmap/" + gene)
        assert status in {200, 404}, (gene, status)
    for path in ("/api/structure/unknown", "/api/heatmap/unknown", "/not-a-file"):
        status, raw = request(path)
        assert status == 404, (path, status)

    timings.sort()
    print(json.dumps({"base_url": base, "health": health, "valid_predictions": len(cases),
                      "invalid_requests_rejected": len(invalid) + len(standard),
                      "tiers_exercised": sorted(tiers),
                      "median_ms": round(timings[len(timings) // 2], 1),
                      "p95_ms": round(timings[int(len(timings) * 0.95) - 1], 1),
                      "model_meta": info["meta"]}, indent=2))


if __name__ == "__main__":
    main()
