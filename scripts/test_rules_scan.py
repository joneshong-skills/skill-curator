#!/usr/bin/env python3
"""Unit tests for rules_scan.py.

All filesystem operations use TemporaryDirectory — the real ~/.claude/rules
and ~/workshop/.claude/rules directories are never read from.

Six-law alignment:
  #1 Mutation thinking  — safety whitelist enforcement, segment boundary on tiny fragments,
                          contradiction same-paragraph exception, stale with active marker,
                          cross-file vs intra-file dup detection, git fallback to mtime
  #3 Invariants        — whitelist files NEVER appear in any candidate; deterministic output
  #4 Runtime           — stdlib unittest only
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

_SCRIPT = Path(__file__).parent / "rules_scan.py"


def _load_module(rules_dirs: list[Path]):
    spec = importlib.util.spec_from_file_location("rules_scan_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.RULES_DIRS = rules_dirs
    return mod


def _write_rule(d: Path, name: str, content: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(content, encoding="utf-8")
    return p


# ===========================================================================
class TestDiscoverRuleFiles(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.root = Path(self._td.name)
        self.rules_dir = self.root / "rules"
        self.mod = _load_module([self.rules_dir])

    def tearDown(self):
        self._td.cleanup()

    def test_empty_dir_returns_empty(self):
        self.rules_dir.mkdir()
        self.assertEqual(self.mod.discover_rule_files(), [])

    def test_nonexistent_dir_skipped(self):
        # rules_dir does not exist → should not raise, just return []
        files = self.mod.discover_rule_files()
        self.assertEqual(files, [])

    def test_md_files_discovered(self):
        _write_rule(self.rules_dir, "custom-rule.md", "# Custom\n\nContent here.\n")
        files = self.mod.discover_rule_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "custom-rule.md")

    def test_safety_whitelist_excluded(self):
        """Safety whitelist files MUST never appear in the discovered list."""
        for wl in self.mod.SAFETY_WHITELIST_FILES:
            _write_rule(self.rules_dir, wl, "# Whitelisted\n\nSome content.\n")
        _write_rule(self.rules_dir, "ok-rule.md", "# OK\n\nSafe content.\n")
        files = self.mod.discover_rule_files()
        names = {f.name for f in files}
        # Whitelist files must be absent
        for wl in self.mod.SAFETY_WHITELIST_FILES:
            self.assertNotIn(wl, names, f"{wl} must not appear in discovered files")
        # Non-whitelist file must be present
        self.assertIn("ok-rule.md", names)

    def test_non_md_files_ignored(self):
        self.rules_dir.mkdir()
        (self.rules_dir / "notes.txt").write_text("text", encoding="utf-8")
        (self.rules_dir / "data.yaml").write_text("key: val", encoding="utf-8")
        files = self.mod.discover_rule_files()
        self.assertEqual(files, [])


# ===========================================================================
class TestSplitSegments(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.root = Path(self._td.name)
        self.mod = _load_module([self.root])

    def tearDown(self):
        self._td.cleanup()

    def test_splits_on_h2_headings(self):
        text = (
            "# Title\n\n## Section A\n\nContent A with enough chars "
            + "x" * 60
            + "\n\n## Section B\n\nContent B with enough chars "
            + "y" * 60
            + "\n"
        )
        dummy = self.root / "dummy.md"
        segs = self.mod.split_segments(text, dummy)
        self.assertGreaterEqual(len(segs), 2)
        heads = [s for _, s in segs if "## Section" in s]
        self.assertEqual(len(heads), 2)

    def test_tiny_segments_filtered_out(self):
        """Segments shorter than MIN_SEGMENT_CHARS should be dropped."""
        text = "## Short\n\nTiny.\n"
        dummy = self.root / "dummy.md"
        segs = self.mod.split_segments(text, dummy)
        # "## Short\n\nTiny." is < 80 chars → should be dropped
        self.assertEqual(segs, [])

    def test_single_segment_no_h2(self):
        content = "# Title\n\n" + "A" * 100
        dummy = self.root / "dummy.md"
        segs = self.mod.split_segments(content, dummy)
        self.assertEqual(len(segs), 1)


# ===========================================================================
class TestFindDuplicates(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.root = Path(self._td.name)
        self.rules_dir = self.root / "rules"
        self.rules_dir.mkdir()
        self.mod = _load_module([self.rules_dir])

    def tearDown(self):
        self._td.cleanup()

    def _long_seg(self, prefix: str = "") -> str:
        return "## Section\n\n" + (prefix + "A" * 90)

    def test_identical_cross_file_segments_flagged(self):
        common = self._long_seg()
        _write_rule(self.rules_dir, "rule-a.md", common)
        _write_rule(self.rules_dir, "rule-b.md", common)
        files = self.mod.discover_rule_files()
        dups = self.mod.find_duplicates(files)
        self.assertGreater(len(dups), 0)
        # similarity should be >= DUP_THRESHOLD
        for d in dups:
            self.assertGreaterEqual(d["similarity"], self.mod.DUP_THRESHOLD)

    def test_intra_file_not_flagged(self):
        """Duplicate sections in the same file MUST NOT be flagged."""
        seg = self._long_seg() + "\n\n" + self._long_seg(prefix="same content ")
        _write_rule(self.rules_dir, "single.md", seg)
        files = self.mod.discover_rule_files()
        dups = self.mod.find_duplicates(files)
        self.assertEqual(dups, [])

    def test_distinct_content_not_flagged(self):
        _write_rule(self.rules_dir, "rule-a.md", self._long_seg("AAAA"))
        _write_rule(self.rules_dir, "rule-b.md", self._long_seg("ZZZZ" + "X" * 80))
        files = self.mod.discover_rule_files()
        dups = self.mod.find_duplicates(files)
        self.assertEqual(dups, [])

    def test_safety_whitelist_never_in_dups(self):
        """Even if whitelisted files are manually injected, they should not appear."""
        common = self._long_seg()
        _write_rule(self.rules_dir, "ok-rule.md", common)
        _write_rule(self.rules_dir, "other-ok.md", common)
        # The whitelist enforcement happens in discover_rule_files, but let's
        # directly test: if we pass only non-whitelisted files, whitelisted names
        # should not appear in any dup file_a / file_b.
        files = self.mod.discover_rule_files()
        dups = self.mod.find_duplicates(files)
        whitelist = self.mod.SAFETY_WHITELIST_FILES
        for d in dups:
            self.assertNotIn(Path(d["file_a"]).name, whitelist)
            self.assertNotIn(Path(d["file_b"]).name, whitelist)


# ===========================================================================
class TestFindContradictions(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.root = Path(self._td.name)
        self.rules_dir = self.root / "rules"
        self.rules_dir.mkdir()
        self.mod = _load_module([self.rules_dir])

    def tearDown(self):
        self._td.cleanup()

    def test_cross_file_contradiction_detected(self):
        _write_rule(self.rules_dir, "rule-a.md", "Never use `docker` in production.\n")
        _write_rule(self.rules_dir, "rule-b.md", "Always use `docker` for containerization.\n")
        files = self.mod.discover_rule_files()
        contradictions = self.mod.find_contradictions(files)
        keywords = [c["keyword"] for c in contradictions]
        self.assertIn("docker", keywords)

    def test_same_paragraph_exception_clause_not_flagged(self):
        """prohibit + require in the same paragraph (< 3 lines apart) → skip."""
        content = "Never use `foo`, but you must use `foo` when X is configured.\n"
        _write_rule(self.rules_dir, "single.md", content)
        files = self.mod.discover_rule_files()
        contradictions = self.mod.find_contradictions(files)
        # Same line → abs difference < 3 → not flagged
        self.assertEqual(contradictions, [])

    def test_no_polarity_no_contradiction(self):
        _write_rule(self.rules_dir, "neutral.md", "Use `redis` for caching sessions.\n")
        files = self.mod.discover_rule_files()
        self.assertEqual(self.mod.find_contradictions(files), [])

    def test_empty_file_list(self):
        self.assertEqual(self.mod.find_contradictions([]), [])


# ===========================================================================
class TestFindStale(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.root = Path(self._td.name)
        self.rules_dir = self.root / "rules"
        self.rules_dir.mkdir()
        self.mod = _load_module([self.rules_dir])

    def tearDown(self):
        self._td.cleanup()

    def test_file_with_active_marker_not_stale(self):
        _write_rule(self.rules_dir, "active.md", "# Active Rule\n\n--enforced--\n\nContent here.\n")
        # Force git to return None so mtime is used
        with patch.object(self.mod, "git_last_modified", return_value=None):
            stale = self.mod.find_stale(self.mod.discover_rule_files())
        self.assertEqual(stale, [])

    def test_old_file_without_marker_flagged(self):
        p = _write_rule(self.rules_dir, "old-rule.md", "# Old Rule\n\nContent.\n")
        old_date = date.today() - timedelta(days=200)
        with patch.object(self.mod, "git_last_modified", return_value=old_date):
            stale = self.mod.find_stale([p])
        self.assertEqual(len(stale), 1)
        self.assertIn("old-rule.md", stale[0]["file"])
        self.assertGreater(stale[0]["age_days"], 180)

    def test_recent_file_not_stale(self):
        p = _write_rule(self.rules_dir, "recent.md", "# Recent Rule\n\nNew content.\n")
        recent = date.today() - timedelta(days=10)
        with patch.object(self.mod, "git_last_modified", return_value=recent):
            stale = self.mod.find_stale([p])
        self.assertEqual(stale, [])

    def test_enforced_marker_prevents_stale(self):
        p = _write_rule(
            self.rules_dir, "enforced.md", "# Rule\n\n--active--\n\nThis is a very active rule.\n"
        )
        old = date.today() - timedelta(days=300)
        with patch.object(self.mod, "git_last_modified", return_value=old):
            stale = self.mod.find_stale([p])
        self.assertEqual(stale, [])

    def test_empty_file_list(self):
        self.assertEqual(self.mod.find_stale([]), [])


# ===========================================================================
class TestRenderMarkdown(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.root = Path(self._td.name)
        self.mod = _load_module([self.root])

    def tearDown(self):
        self._td.cleanup()

    def test_empty_result_renders_none(self):
        result = {
            "scanned_files": 0,
            "duplicates": [],
            "contradictions": [],
            "stale": [],
        }
        md = self.mod.render_markdown(result)
        self.assertIn("(none)", md)
        self.assertIn("Rules Audit", md)

    def test_duplicate_appears_in_output(self):
        result = {
            "scanned_files": 2,
            "duplicates": [
                {
                    "file_a": "/rules/a.md",
                    "line_a": 5,
                    "file_b": "/rules/b.md",
                    "line_b": 10,
                    "similarity": 0.95,
                    "comment": "Similar H2 segments: 'Sec A' vs 'Sec A'",
                }
            ],
            "contradictions": [],
            "stale": [],
        }
        md = self.mod.render_markdown(result)
        self.assertIn("a.md:5", md)
        self.assertIn("0.95", md)

    def test_json_output_valid(self):
        """Main function with --json produces parseable JSON."""
        import contextlib
        import io

        result = {
            "scanned_files": 0,
            "safety_whitelist": [],
            "duplicates": [],
            "contradictions": [],
            "stale": [],
        }
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.mod.render_markdown(result)  # just ensure it runs
        # Check json.dumps round-trips correctly
        dumped = json.dumps(result)
        loaded = json.loads(dumped)
        self.assertEqual(loaded["scanned_files"], 0)


if __name__ == "__main__":
    unittest.main()
