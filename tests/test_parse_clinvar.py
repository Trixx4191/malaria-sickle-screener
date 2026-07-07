from pathlib import Path

from src.data import parse_clinvar


def test_parse_filters_and_labels(tmp_path, monkeypatch):
    data_path = tmp_path / "variant_summary.txt"
    clean_path = tmp_path / "clinvar_clean.csv"

    data_path.write_text(
        "\t".join([
            "VariationID",
            "GeneSymbol",
            "Assembly",
            "ClinicalSignificance",
            "Name",
            "ReviewStatus",
            "Chromosome",
            "PositionVCF",
            "ReferenceAlleleVCF",
            "AlternateAlleleVCF",
        ])
        + "\n"
        + "\t".join(["101", "HBB", "GRCh38", "Pathogenic", "c.17A>T", "criteria provided, multiple submitters, no conflicts", "11", "5246696", "A", "T"]) + "\n"
        + "\t".join(["102", "G6PD", "GRCh38", "Benign", "c.1G>A", "reviewed by expert panel", "X", "1537592", "C", "T"]) + "\n"
        + "\t".join(["103", "HBB", "GRCh37", "Conflicting", "c.2C>G", "no assertion criteria provided", "11", "5246697", "G", "C"]) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(parse_clinvar, "DATA_RAW", tmp_path)
    monkeypatch.setattr(parse_clinvar, "CLINVAR_CLEAN", clean_path)

    result = parse_clinvar.parse(save=True)

    assert len(result) == 2
    assert set(result["gene"]) == {"HBB", "G6PD"}
    assert set(result["label"]) == {0, 1}
    assert clean_path.exists()
