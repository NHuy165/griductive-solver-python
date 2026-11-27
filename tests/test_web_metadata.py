"""Kiểm thử phần đọc metadata và khám phá màn chơi của lớp web."""

from __future__ import annotations

import json
from pathlib import Path

from src.web import app as web_app


def write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_level_meta_returns_empty_when_file_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(web_app, "LEVEL_META_PATH", tmp_path / "missing.json")

    assert web_app._load_level_meta() == {}


def test_load_level_meta_rejects_malformed_json(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "level_metadata.json"
    path.write_text("{", encoding="utf-8")
    monkeypatch.setattr(web_app, "LEVEL_META_PATH", path)

    assert web_app._load_level_meta() == {}


def test_load_level_meta_rejects_non_object_root(
    monkeypatch, tmp_path: Path
) -> None:
    path = write_json(tmp_path / "level_metadata.json", [])
    monkeypatch.setattr(web_app, "LEVEL_META_PATH", path)

    assert web_app._load_level_meta() == {}


def test_load_level_meta_rejects_non_object_levels(
    monkeypatch, tmp_path: Path
) -> None:
    path = write_json(
        tmp_path / "level_metadata.json", {"levels": []}
    )
    monkeypatch.setattr(web_app, "LEVEL_META_PATH", path)

    assert web_app._load_level_meta() == {}


def test_load_level_meta_normalizes_and_skips_invalid_entries(
    monkeypatch, tmp_path: Path
) -> None:
    path = write_json(
        tmp_path / "level_metadata.json",
        {
            "levels": {
                "level_01": {
                    "title": "  Vườn chuối  ",
                    "subtitle": "  Mở đầu  ",
                },
                "level_02.json": {"title": "Hai"},
                "level_03.json": {"title": "   "},
                "level_04.json": "không phải object",
                "level_05.json": {"subtitle": "thiếu title"},
            }
        },
    )
    monkeypatch.setattr(web_app, "LEVEL_META_PATH", path)

    assert web_app._load_level_meta() == {
        "level_01.json": {
            "title": "Vườn chuối",
            "subtitle": "Mở đầu",
        },
        "level_02.json": {"title": "Hai", "subtitle": ""},
    }


def test_load_level_meta_accepts_flat_object(
    monkeypatch, tmp_path: Path
) -> None:
    path = write_json(
        tmp_path / "level_metadata.json",
        {"level_01.json": {"title": "Một"}},
    )
    monkeypatch.setattr(web_app, "LEVEL_META_PATH", path)

    assert web_app._load_level_meta() == {
        "level_01.json": {"title": "Một", "subtitle": ""}
    }


def test_default_level_meta_uses_generation_and_clue_types() -> None:
    meta = web_app._default_level_meta(
        42,
        5,
        {"FACT", "PARITY"},
        {"difficulty": "Khó"},
    )

    assert meta["title"] == "Màn chơi mới"
    assert "5×5" in meta["subtitle"]
    assert "mức khó" in meta["subtitle"]
    assert "2 loại manh mối" in meta["subtitle"]


def test_default_level_meta_handles_missing_generation() -> None:
    meta = web_app._default_level_meta(1, 3, {"FACT"}, None)

    assert "Màn 3×3" in meta["subtitle"]
    assert "1 loại manh mối" in meta["subtitle"]
    assert "mức" not in meta["subtitle"]


def test_walk_clue_types_includes_nested_conclusion() -> None:
    assert web_app._walk_clue_types(
        {"type": "IMPLIES", "conclusion": {"type": "PARITY"}}
    ) == {"IMPLIES", "PARITY"}


def test_discover_levels_skips_unparseable_level_number(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "level_bad.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(web_app, "MAPS_DIR", tmp_path)

    assert web_app._discover_levels() == []


def test_discover_levels_builds_default_metadata_and_extensions(
    monkeypatch, tmp_path: Path
) -> None:
    write_json(
        tmp_path / "level_42.json",
        {
            "size": 3,
            "people": [{"clue": {"type": "PARITY"}}],
            "generation": {"difficulty": "Khó"},
        },
    )
    monkeypatch.setattr(web_app, "MAPS_DIR", tmp_path)

    levels = web_app._discover_levels()

    assert len(levels) == 1
    level = levels[0]
    assert level["id"] == "level_42.json"
    assert level["number"] == 42
    assert level["title"] == "Màn chơi mới"
    assert level["size"] == 3
    assert level["people_count"] == 1
    assert level["extensions"] == ["PARITY"]
    assert level["difficulty"] == "Mở rộng"
    assert "3×3" in level["caption"]
