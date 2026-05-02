"""Tests for ``nom.mcp.integrations`` — credential-free starter tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nom.agents.protocol import Tool, ToolError
from nom.mcp.integrations import (
    CurrentTimeTool,
    FileGlobTool,
    JSONFieldTool,
    default_catalog,
)

# ---------- FileGlobTool ---------------------------------------------


def _populate(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a")
    (tmp_path / "src" / "b.py").write_text("b")
    (tmp_path / "src" / "nested").mkdir()
    (tmp_path / "src" / "nested" / "c.py").write_text("c")
    (tmp_path / "README.md").write_text("# readme")
    return tmp_path


def test_fileglob_satisfies_protocol(tmp_path: Path) -> None:
    assert isinstance(FileGlobTool(root=tmp_path), Tool)


def test_fileglob_lists_top_level(tmp_path: Path) -> None:
    _populate(tmp_path)
    out = FileGlobTool(root=tmp_path).call({"pattern": "*.md"})
    assert out["matches"] == ["README.md"]


def test_fileglob_recursive(tmp_path: Path) -> None:
    _populate(tmp_path)
    out = FileGlobTool(root=tmp_path).call({"pattern": "src/**/*.py"})
    assert sorted(out["matches"]) == ["src/a.py", "src/b.py", "src/nested/c.py"]


def test_fileglob_rejects_absolute(tmp_path: Path) -> None:
    _populate(tmp_path)
    with pytest.raises(ToolError, match="must be relative"):
        FileGlobTool(root=tmp_path).call({"pattern": "/etc/passwd"})


def test_fileglob_rejects_parent_traversal(tmp_path: Path) -> None:
    _populate(tmp_path)
    with pytest.raises(ToolError, match=r"'\.\.'"):
        FileGlobTool(root=tmp_path).call({"pattern": "../*"})


def test_fileglob_caps_results(tmp_path: Path) -> None:
    for i in range(50):
        (tmp_path / f"f{i}.txt").write_text("x")
    out = FileGlobTool(root=tmp_path, max_results=10).call({"pattern": "*.txt"})
    assert len(out["matches"]) == 10


# ---------- JSONFieldTool --------------------------------------------


def test_jsonfield_satisfies_protocol(tmp_path: Path) -> None:
    assert isinstance(JSONFieldTool(root=tmp_path), Tool)


def test_jsonfield_reads_top_level(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"version": "1.2.3", "debug": True}))
    out = JSONFieldTool(root=tmp_path).call({"path": "config.json", "field": "version"})
    assert out["value"] == "1.2.3"
    assert out["type"] == "str"


def test_jsonfield_dotted_path(tmp_path: Path) -> None:
    (tmp_path / "p.json").write_text(json.dumps({"a": {"b": {"c": 42}}}))
    out = JSONFieldTool(root=tmp_path).call({"path": "p.json", "field": "a.b.c"})
    assert out["value"] == 42


def test_jsonfield_array_index(tmp_path: Path) -> None:
    (tmp_path / "p.json").write_text(json.dumps({"items": [{"name": "first"}, {"name": "second"}]}))
    out = JSONFieldTool(root=tmp_path).call({"path": "p.json", "field": "items.1.name"})
    assert out["value"] == "second"


def test_jsonfield_empty_field_returns_whole_doc(tmp_path: Path) -> None:
    (tmp_path / "p.json").write_text(json.dumps({"a": 1}))
    out = JSONFieldTool(root=tmp_path).call({"path": "p.json", "field": ""})
    assert out["value"] == {"a": 1}


def test_jsonfield_path_traversal_blocked(tmp_path: Path) -> None:
    (tmp_path / "ok.json").write_text("{}")
    with pytest.raises(ToolError, match="escapes root"):
        JSONFieldTool(root=tmp_path).call({"path": "../etc/passwd", "field": ""})


def test_jsonfield_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="not found"):
        JSONFieldTool(root=tmp_path).call({"path": "no.json", "field": ""})


def test_jsonfield_unknown_key_clear_error(tmp_path: Path) -> None:
    (tmp_path / "p.json").write_text(json.dumps({"a": 1}))
    with pytest.raises(ToolError, match="not found"):
        JSONFieldTool(root=tmp_path).call({"path": "p.json", "field": "ghost"})


def test_jsonfield_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "p.json").write_text("not json")
    with pytest.raises(ToolError, match="not valid JSON"):
        JSONFieldTool(root=tmp_path).call({"path": "p.json", "field": ""})


# ---------- CurrentTimeTool ------------------------------------------


def test_currenttime_satisfies_protocol() -> None:
    assert isinstance(CurrentTimeTool(), Tool)


def test_currenttime_returns_iso_and_epoch() -> None:
    out = CurrentTimeTool().call({})
    assert "T" in out["iso"]
    assert out["iso"].endswith("Z")
    assert isinstance(out["epoch_seconds"], int)


# ---------- default_catalog ------------------------------------------


def test_default_catalog_returns_three_tools(tmp_path: Path) -> None:
    catalog = default_catalog(file_root=tmp_path)
    names = {t.name for t in catalog}
    assert names == {"file_glob", "json_field", "current_time"}


def test_default_catalog_uses_cwd_when_no_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    catalog = default_catalog()
    glob_tool = next(t for t in catalog if t.name == "file_glob")
    assert glob_tool.root == tmp_path.resolve()
