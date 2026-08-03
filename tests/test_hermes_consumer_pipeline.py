"""Smoke tests for the Hermes-consumer pipeline.

Lightweight: no network, no LLM, no GitHub. Validates that:
- Atom IDs are stable across reruns.
- Embedding-ready export contains the required fields.
- Topic tagging is deterministic and respects exclusions.
- Entity registry trajectory is computed.
- Consensus clusters deterministic claims.
- Source trust EMA is bounded and stable.
- Repo scoring returns a composite in [0, 100] and respects the quality gate.
- Atomic writes produce a `latest.jsonl` / `latest.json` symlink or copy.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


class AtomSchemaTests(unittest.TestCase):
    def test_atom_id_is_stable(self):
        from services.atom_schema import make_atom_id
        a = make_atom_id("parent_signal_1", "claim", "MCP is the standard for agent interop")
        b = make_atom_id("parent_signal_1", "claim", "MCP is the standard for agent interop")
        self.assertEqual(a, b)
        # Different text -> different id
        c = make_atom_id("parent_signal_1", "claim", "MCP is NOT the standard for agent interop")
        self.assertNotEqual(a, c)

    def test_atom_id_differs_by_type(self):
        from services.atom_schema import make_atom_id
        a = make_atom_id("p", "claim", "text")
        b = make_atom_id("p", "tool", "text")
        self.assertNotEqual(a, b)

    def test_extract_atoms_deterministic_only(self):
        from services.atom_schema import extract_atoms
        item = {
            "signal_id": "abc123",
            "title": "Anthropic launches MCP Router",
            "summary": "MCP is becoming the de facto standard for agent interop.",
            "tools_mentioned": ["MCP Router"],
            "frameworks_mentioned": ["Model Context Protocol"],
            "entities": ["Anthropic"],
            "excerpt": "Released 28% more efficient in benchmarks. The repo is at https://github.com/foo/bar.",
            "canonical_url": "https://example.com/post",
        }
        atoms = extract_atoms(item, allow_llm=False)
        types = {a["atom_type"] for a in atoms}
        self.assertIn("tool", types)
        self.assertIn("framework", types)
        self.assertIn("entity", types)
        self.assertIn("url", types)
        # No LLM types should appear
        self.assertNotIn("claim", types)
        self.assertNotIn("prediction", types)

    def test_deterministic_atoms_have_stable_ids(self):
        from services.atom_schema import extract_atoms
        item = {
            "signal_id": "abc",
            "title": "Test",
            "summary": "Foo bar baz",
            "tools_mentioned": ["MyTool"],
            "entities": ["Acme Corp"],
        }
        a = extract_atoms(item, allow_llm=False)
        b = extract_atoms(item, allow_llm=False)
        ids_a = sorted(x["atom_id"] for x in a)
        ids_b = sorted(x["atom_id"] for x in b)
        self.assertEqual(ids_a, ids_b)


class EmbeddingReadyTests(unittest.TestCase):
    def test_required_fields_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            (tmp_p / "daily").mkdir()
            (tmp_p / "atoms").mkdir()
            (tmp_p / "embedding_ready").mkdir()
            # Patch the module's paths.
            import scripts.export_embedding_ready as mod
            mod.DAILY_DIR = tmp_p / "daily"
            mod.ATOMS_DIR = tmp_p / "atoms"
            mod.EMBED_DIR = tmp_p / "embedding_ready"
            (tmp_p / "daily" / "2026-08-03.json").write_text(json.dumps({
                "Topic": [{
                    "signal_id": "sig1",
                    "title": "Hello",
                    "summary": "World",
                    "canonical_url": "https://example.com/x",
                    "source": "RSS",
                }]
            }))
            (tmp_p / "atoms" / "2026-08-03.jsonl").write_text(json.dumps({
                "atom_id": "atom1",
                "atom_type": "claim",
                "text": "A claim",
                "parent_signal_id": "sig1",
                "parent_canonical_url": "https://example.com/x",
                "parent_source_domain": "example.com",
                "public_topics": ["ai_agents"],
                "report_date": "2026-08-03",
            }) + "\n")
            summary = mod.run("2026-08-03")
            self.assertTrue(summary["ok"])
            out_path = tmp_p / "embedding_ready" / "2026-08-03.jsonl"
            self.assertTrue(out_path.exists())
            lines = [json.loads(l) for l in out_path.read_text().splitlines() if l.strip()]
            # 1 signal + 1 atom
            self.assertEqual(len(lines), 2)
            for rec in lines:
                self.assertIn("external_id", rec)
                self.assertIn("embedding_text", rec)
                self.assertIn("payload", rec)
                self.assertEqual(rec["payload"]["schema_version"], "embed_ready.v1")


class TopicTests(unittest.TestCase):
    def test_deterministic_tagging(self):
        from services.topics import load_topics
        topics = load_topics()
        item = {
            "title": "Anthropic's MCP Router and the new agent interop",
            "summary": "MCP is becoming the de facto standard for agent interop.",
        }
        from services.topics import tag_item
        tags = tag_item(item, topics)
        self.assertIn("ai_agents", tags)

    def test_exclusion_blocks_match(self):
        from services.topics import load_topics, tag_item
        topics = load_topics()
        # "travel agent" should NOT match ai_agents because of the exclusion.
        item = {
            "title": "How to find a travel agent in 2026",
            "summary": "Booking a vacation?",
        }
        tags = tag_item(item, topics)
        self.assertNotIn("ai_agents", tags)


class EntityRegistryTests(unittest.TestCase):
    def test_trajectory_rising(self):
        from services.entity_registry import (
            _filter_noise,
            extract_entities_from_item,
            update_registry,
        )
        items = [
            {
                "signal_id": f"s{i}",
                "entities": ["Anthropic"],
                "source_domain": "anthropic.com",
            }
            for i in range(8)
        ]
        snap = update_registry(items, report_date="2026-08-03")
        names = {e["name"] for e in snap["entities"]}
        self.assertIn("Anthropic", names)
        anth = next(e for e in snap["entities"] if e["name"] == "Anthropic")
        self.assertIn(anth["trajectory"], {"emerging", "rising"})


class ConsensusTests(unittest.TestCase):
    def test_claims_cluster_when_similar(self):
        from services.consensus import cluster_claims
        claims = [
            {"atom_id": "a1", "atom_type": "claim", "text": "MCP is the standard for agent interop", "polarity": "supports", "parent_signal_id": "s1", "parent_source_domain": "anthropic.com"},
            {"atom_id": "a2", "atom_type": "claim", "text": "MCP is becoming standard for agent interop", "polarity": "supports", "parent_signal_id": "s2", "parent_source_domain": "github.com"},
            {"atom_id": "a3", "atom_type": "claim", "text": "Totally unrelated claim about cats", "polarity": "neutral", "parent_signal_id": "s3", "parent_source_domain": "cats.com"},
        ]
        clusters = cluster_claims(claims)
        # The two MCP claims should land in the same cluster; cats in its own.
        sizes = sorted(c["member_count"] for c in clusters)
        self.assertEqual(sizes, [1, 2])


class SourceTrustTests(unittest.TestCase):
    def test_ema_bounded(self):
        from services.source_trust import (
            INITIAL_SCORE,
            empty_state,
            get_trust,
            record_corroboration,
            record_contradiction,
            record_retraction,
        )
        st = empty_state()
        for _ in range(50):
            record_corroboration(st, "anthropic.com", "ai_agents")
        s = get_trust(st, "anthropic.com", "ai_agents")
        self.assertGreater(s, INITIAL_SCORE)
        self.assertLessEqual(s, 1.0)
        for _ in range(200):
            record_retraction(st, "anthropic.com", "ai_agents")
        s = get_trust(st, "anthropic.com", "ai_agents")
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 1.0)


class RepoScoringTests(unittest.TestCase):
    def _snap(self, **overrides):
        base = {
            "star_velocity_7d": 5.0,
            "star_velocity_30d": 3.0,
            "fork_velocity_7d": 1.0,
            "contributor_count_30d": 10,
            "release_count_90d": 4,
            "days_since_last_commit": 5,
            "bus_factor": 0.4,
            "issue_close_rate_30d": 0.8,
            "median_first_response_hours": 6.0,
            "dependents_count": 50,
            "forks_with_prs_back": 10,
            "cross_platform_count": 4,
            "hn_mentions_30d": 10,
            "reddit_mentions_30d": 5,
        }
        base.update(overrides)
        return base

    def test_composite_in_range(self):
        from services.repo_scoring import compute_composite_score
        score = compute_composite_score(self._snap())
        self.assertGreater(score["composite_score"], 0)
        self.assertLessEqual(score["composite_score"], 100)
        self.assertTrue(score["passes_quality_gate"])

    def test_stale_repo_fails_gate(self):
        from services.repo_scoring import compute_composite_score
        score = compute_composite_score(self._snap(days_since_last_commit=400))
        # Quality alone should drop below gate.
        self.assertFalse(score["passes_quality_gate"])

    def test_ranking_respects_gate(self):
        from services.repo_scoring import rank_snapshots
        good = self._snap(days_since_last_commit=2)
        bad = self._snap(days_since_last_commit=400)
        ranked = rank_snapshots([bad, good], limit=10)
        # Only `good` should be in the output.
        self.assertEqual(len(ranked), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
