import json
import shutil
from pathlib import Path

from scraper.validator import validate_archive

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "sample-website-source"


def test_sample_archive_is_valid():
    assert validate_archive(SAMPLE) == []


def test_invalid_archive_reports_clear_errors(tmp_path):
    archive = tmp_path / "archive"
    shutil.copytree(SAMPLE, archive)
    page = archive / "pages" / "kontakt" / "content.json"
    data = json.loads(page.read_text())
    data["sections"][0]["blocks"].append({"type": "heading", "level": 9, "content": []})
    data["sections"][0]["blocks"].append({"type": "unknown-block"})
    page.write_text(json.dumps(data))
    manifest = json.loads((archive / "manifest.json").read_text())
    manifest["pages"].append(dict(manifest["pages"][0]))
    (archive / "manifest.json").write_text(json.dumps(manifest))
    (archive / "assets" / "images" / next(p.name for p in (archive / "assets" / "images").iterdir())).unlink()

    problems = validate_archive(archive)
    text = "\n".join(problems)
    assert "pages/kontakt/content.json: sections/0/blocks/2" in text
    assert "9 is greater than the maximum of 6" in text
    assert "duplicate page path /" in text
    assert "file missing assets/images/" in text


def test_wrong_schema_version(tmp_path):
    archive = tmp_path / "archive"
    shutil.copytree(SAMPLE, archive)
    nav = json.loads((archive / "navigation.json").read_text())
    nav["schemaVersion"] = "2.0"
    (archive / "navigation.json").write_text(json.dumps(nav))
    assert any("unsupported schemaVersion '2.0'" in p for p in validate_archive(archive))
