"""Tests for atoms, embedding_ready, topics, traction gate, and manifest artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.atom_schema import build_atom, extract_deterministic_atoms, make_atom_id
from services.repo_scoring import apply_quality_gate, score_repo
from services.topics import tag_text
from services.tutorial_flags import flag_tutorial_potential


def test_atom_id_stable():
    a = make_atom_id("sig1", "tool", "LangChain")
    b = make_atom_id("sig1", "tool", "langchain")
    assert a == b
    c = make_atom_id("sig1", "tool", "crewai")
    assert a != c


def test_atom_jsonl_schema_fields():
    atom = build_atom(
        parent_signal_id="sigabc",
        atom_type="claim",
        text="OpenAI will release a new model",
        evidence_urls=["https://example.com/x"],
    )
    assert atom["schema_version"] == "atom.v1"
    assert atom["atom_id"]
    assert atom["parent_signal_id"] == "sigabc"
    assert atom["atom_type"] == "claim"


def test_deterministic_extraction_finds_tools():
    item = {
        "signal_id": "sigtools",
        "title": "Building agents with LangChain and Qdrant",
        "summary": "A guide using Next.js and FastAPI",
        "url": "https://example.com/guide",
        "canonical_url": "https://example.com/guide",
    }
    atoms = extract_deterministic_atoms(item)
    types = {a["atom_type"] for a in atoms}
    texts = {a["text"].lower() for a in atoms}
    assert "tool" in types or "framework" in types
    assert any("langchain" in t for t in texts)


def test_embedding_ready_required_fields(tmp_path, monkeypatch):
    import scripts.export_embedding_ready as er

    daily = tmp_path / "daily"
    daily.mkdir()
    report = {
        "AI": [
            {
                "title": "Hello Agents",
                "url": "https://example.com/hello",
                "summary": "Agent frameworks rise",
                "source": "RSS",
                "bucket": "ai",
            }
        ]
    }
    (daily / "2026-08-03.json").write_text(json.dumps(report), encoding="utf-8")
    out = tmp_path / "embedding_ready"
    atoms = tmp_path / "atoms"
    atoms.mkdir()
    (atoms / "2026-08-03.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setattr(er, "DAILY_DIR", daily)
    monkeypatch.setattr(er, "OUT_DIR", out)
    monkeypatch.setattr(er, "ATOMS_DIR", atoms)
    monkeypatch.setattr(sys, "argv", ["export_embedding_ready.py", "--date", "2026-08-03"])
    er.main()
    lines = (out / "2026-08-03.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert lines
    rec = json.loads(lines[0])
    for key in ("external_id", "embedding_text", "schema_version", "record_type", "provenance"):
        assert key in rec
    assert rec["schema_version"] == "embedding_ready.v1"
    assert rec["embedding_text"]


def test_manifest_lists_artifact_paths(tmp_path, monkeypatch):
    import scripts.build_report_manifest as bm

    root = tmp_path
    daily = root / "outputs" / "daily"
    daily.mkdir(parents=True)
    report = {"AI": [{"title": "T", "url": "https://ex.com/t", "bucket": "ai"}]}
    report_path = daily / "2026-08-03.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    (root / "outputs" / "atoms").mkdir(parents=True)
    (root / "outputs" / "atoms" / "2026-08-03.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "outputs" / "embedding_ready").mkdir(parents=True)
    (root / "outputs" / "embedding_ready" / "2026-08-03.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "HERMES_CONTRACT.md").write_text("v1\n", encoding="utf-8")

    monkeypatch.setattr(bm, "ROOT_DIR", root)
    monkeypatch.setattr(bm, "DAILY_DIR", daily)
    manifest = bm.build_manifest(report_path)
    assert "artifacts" in manifest
    assert manifest["artifacts"]["atoms_jsonl"] == "outputs/atoms/2026-08-03.jsonl"
    assert manifest["artifacts"]["embedding_ready_jsonl"] == "outputs/embedding_ready/2026-08-03.jsonl"
    assert manifest["artifacts"]["hermes_contract"] == "HERMES_CONTRACT.md"


def test_topics_tagging():
    tags = tag_text("New LangGraph multi-agent MCP workflow")
    assert "ai_agents" in tags


def test_quality_gate_excludes_low_quality():
    low = score_repo(
        "example/low",
        {
            "stars_total": 50000,
            "forks_total": 1000,
            "open_issues": 0,
            "has_license": False,
            "has_ci": False,
            "docs_present": False,
            "archived": True,
            "contributors": 1,
            "pr_merge_rate": 0.1,
            "stars_delta_7d": 100,
            "forks_delta_7d": 10,
            "commits_delta_7d": 5,
        },
    )
    high = score_repo(
        "example/high",
        {
            "stars_total": 5000,
            "forks_total": 400,
            "open_issues": 40,
            "has_license": True,
            "has_ci": True,
            "docs_present": True,
            "archived": False,
            "contributors": 25,
            "contributors_active": 20,
            "pr_merge_rate": 0.8,
            "discussion_activity": 10,
            "stars_delta_7d": 20,
            "forks_delta_7d": 5,
            "commits_delta_7d": 10,
            "dependents_proxy": 40,
        },
    )
    gated = apply_quality_gate([low, high])
    names = {r["full_name"] for r in gated}
    assert "example/high" in names
    if not low["passes_quality_gate"]:
        assert "example/low" not in names


def test_tutorial_flag():
    flags = flag_tutorial_potential(
        {
            "title": "How to build an AI agent with LangChain",
            "summary": "Step-by-step beginner tutorial",
            "source": "YouTube",
            "public_topics": ["ai_agents"],
        }
    )
    assert flags["tutorial_candidate"] is True
    assert flags["tutorial_potential"] >= 0.45
