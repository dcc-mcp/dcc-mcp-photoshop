from pathlib import Path


def test_tagless_dispatch_only_runs_release_please():
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    decide = workflow.split("  decide:\n", 1)[1].split("  validate-release-version:\n", 1)[0]

    assert "inputs.tag_name != ''" in decide
