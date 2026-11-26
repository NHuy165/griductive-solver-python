"""Flask application for the Griductive graphical interface."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from src.web.session import GameSession

ROOT = Path(__file__).resolve().parents[2]
MAPS_DIR = ROOT / "src" / "maps"
LEVEL_META_PATH = MAPS_DIR / "level_metadata.json"

LOGGER = logging.getLogger(__name__)

EXTENSION_TYPES = {"IMPLIES", "COMPARE", "PARITY"}


def _load_level_meta() -> dict[str, dict[str, str]]:
    """Đọc metadata màn chơi từ ``src/maps/level_metadata.json``.

    Tệp có thể dùng trực tiếp dạng ``{"level_01.json": {...}}`` hoặc bọc
    trong khóa ``"levels"``. Mỗi mục cần có ``title``; ``subtitle`` là tùy
    chọn. Tên tệp được chuẩn hóa về dạng ``*.json`` để dễ dùng.
    """

    if not LEVEL_META_PATH.exists():
        LOGGER.warning(
            "Không tìm thấy %s; dùng metadata mặc định.", LEVEL_META_PATH
        )
        return {}

    try:
        raw = json.loads(LEVEL_META_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        LOGGER.warning("Không đọc được %s: %s", LEVEL_META_PATH, error)
        return {}

    if not isinstance(raw, dict):
        LOGGER.warning("%s phải là một JSON object.", LEVEL_META_PATH)
        return {}

    entries = raw.get("levels", raw)
    if not isinstance(entries, dict):
        LOGGER.warning(
            "Khóa 'levels' trong %s phải là một JSON object.",
            LEVEL_META_PATH,
        )
        return {}

    metadata: dict[str, dict[str, str]] = {}
    for key, value in entries.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue

        title = value.get("title")
        subtitle = value.get("subtitle", "")
        if not isinstance(title, str) or not title.strip():
            continue

        filename = Path(key).name
        if not filename.endswith(".json"):
            filename += ".json"

        metadata[filename] = {
            "title": title.strip(),
            "subtitle": subtitle.strip() if isinstance(subtitle, str) else "",
        }

    return metadata


def _default_level_meta(
    number: int,
    size: int,
    clue_types: set[str],
    generation: Any,
) -> dict[str, str]:
    """Tạo metadata tạm cho màn chưa có mục trong tệp metadata."""

    details = [f"Màn {size}×{size}"]
    if isinstance(generation, dict):
        difficulty = generation.get("difficulty")
        if isinstance(difficulty, str) and difficulty.strip():
            details.append(f"mức {difficulty.strip().lower()}")
    details.append(f"{len(clue_types)} loại manh mối")

    return {
        "title": "Màn chơi mới",
        "subtitle": " · ".join(details) + ".",
    }


LEVEL_META = _load_level_meta()


def _walk_clue_types(clue: dict[str, Any]) -> set[str]:
    types = {clue["type"]}
    conclusion = clue.get("conclusion")
    if isinstance(conclusion, dict):
        types |= _walk_clue_types(conclusion)
    return types


def _discover_levels() -> list[dict[str, Any]]:
    levels: list[dict[str, Any]] = []

    for path in sorted(MAPS_DIR.glob("level_*.json")):
        if path.name == LEVEL_META_PATH.name:
            continue

        try:
            number = int(path.stem.split("_")[1])
        except (IndexError, ValueError):
            continue

        data = json.loads(path.read_text(encoding="utf-8"))
        clue_types: set[str] = set()
        for person in data["people"]:
            clue_types |= _walk_clue_types(person["clue"])

        extensions = sorted(clue_types & EXTENSION_TYPES)
        size = int(data["size"])
        meta = LEVEL_META.get(path.name) or _default_level_meta(
            number,
            size,
            clue_types,
            data.get("generation"),
        )

        if size >= 4:
            difficulty = "Thử thách"
        elif extensions:
            difficulty = "Mở rộng"
        elif number <= 1:
            difficulty = "Khởi động"
        else:
            difficulty = "Cơ bản"

        levels.append(
            {
                "id": path.name,
                "number": number,
                "title": meta["title"],
                "subtitle": meta["subtitle"],
                "size": size,
                "people_count": len(data["people"]),
                "initial_revealed": len(data.get("initially_revealed", [])),
                "clue_types": sorted(clue_types),
                "extensions": extensions,
                "difficulty": difficulty,
                "caption": f"{size}×{size} · {len(clue_types)} loại clue",
            }
        )

    levels.sort(key=lambda level: level["number"])
    return levels


LEVELS = _discover_levels()
LEVELS_BY_ID = {level["id"]: level for level in LEVELS}


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.json.ensure_ascii = False

    lock = threading.Lock()
    session_holder: dict[str, GameSession | None] = {"session": None}

    def current_session() -> GameSession:
        session = session_holder["session"]
        if session is None:
            if not LEVELS:
                raise RuntimeError("Không tìm thấy màn chơi nào trong src/maps.")
            first = LEVELS[0]
            session = GameSession(MAPS_DIR / first["id"], first)
            session_holder["session"] = session
        return session

    def json_for_script(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

    @app.get("/")
    def index() -> str:
        with lock:
            initial_state = current_session().state()
        return render_template(
            "index.html",
            levels_json=json_for_script(LEVELS),
            initial_state_json=json_for_script(initial_state),
        )

    @app.get("/api/levels")
    def api_levels():
        return jsonify({"levels": LEVELS})

    @app.get("/api/state")
    def api_state():
        with lock:
            return jsonify({"state": current_session().state()})

    @app.post("/api/load")
    def api_load():
        payload = request.get_json(silent=True) or {}
        level_id = payload.get("level_id")
        level_meta = LEVELS_BY_ID.get(level_id)

        if level_meta is None:
            return jsonify({"error": "Màn chơi không tồn tại."}), 400

        with lock:
            session = GameSession(MAPS_DIR / level_meta["id"], level_meta)
            session_holder["session"] = session
            return jsonify(
                {
                    "state": session.state(),
                    "message": (
                        f"Đã mở màn {level_meta['number']} · "
                        f"{level_meta['title']}."
                    ),
                }
            )

    @app.post("/api/restart")
    def api_restart():
        with lock:
            session = current_session()
            session.reset()
            return jsonify(
                {
                    "state": session.state(),
                    "message": "Đã đưa màn chơi về trạng thái ban đầu.",
                }
            )

    @app.post("/api/verdict")
    def api_verdict():
        payload = request.get_json(silent=True) or {}
        try:
            index = int(payload.get("index"))
        except (TypeError, ValueError):
            return jsonify({"error": "Chỉ số nhân vật không hợp lệ."}), 400

        verdict = payload.get("verdict")
        if verdict not in {"CRIMINAL", "INNOCENT"}:
            return jsonify({"error": "Phán đoán không hợp lệ."}), 400

        with lock:
            result = current_session().submit_verdict(index, verdict)

        if result.get("result") == "ERROR":
            return jsonify(result), 400
        return jsonify(result)

    @app.post("/api/hint")
    def api_hint():
        with lock:
            return jsonify(current_session().hint())

    @app.post("/api/auto-solve")
    def api_auto_solve():
        with lock:
            return jsonify(current_session().auto_solve())

    return app
