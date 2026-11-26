"""Flask application for the Griductive graphical interface."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from src.web.session import GameSession

ROOT = Path(__file__).resolve().parents[2]
MAPS_DIR = ROOT / "src" / "maps"

LEVEL_META: dict[str, dict[str, str]] = {
    "level_1.json": {
        "title": "Vườn chuối",
        "subtitle": (
            "Một buổi sáng yên bình trong vườn chuối — nhưng có người "
            "đang giấu điều gì đó."
        ),
    },
    "level_2.json": {
        "title": "Đầm lầy",
        "subtitle": (
            "Sương mù che khuất những lá bài. Hãy lần theo từng manh mối "
            "đã được mở."
        ),
    },
    "level_3.json": {
        "title": "Rừng mưa",
        "subtitle": (
            "Rừng mưa rậm rạp, nơi mọi manh mối đều đúng và không ai "
            "được phép đoán."
        ),
    },
    "level_4.json": {
        "title": "Bãi biển",
        "subtitle": (
            "Nắng và gió biển. Chỉ những kết luận chắc chắn mới được "
            "chấp nhận."
        ),
    },
    "level_5.json": {
        "title": "Hang đá",
        "subtitle": (
            "Những manh mối so sánh và chẵn lẻ bắt đầu xuất hiện. "
            "Hãy cẩn thận với từng bước suy luận."
        ),
    },
    "level_6.json": {
        "title": "Đảo nhiệt đới",
        "subtitle": (
            "Hòn đảo lớn nhất: 4×4, đủ chín loại manh mối, dành cho "
            "người chơi muốn thử thách."
        ),
    },
}

EXTENSION_TYPES = {"IMPLIES", "COMPARE", "PARITY"}


def _walk_clue_types(clue: dict[str, Any]) -> set[str]:
    types = {clue["type"]}
    conclusion = clue.get("conclusion")
    if isinstance(conclusion, dict):
        types |= _walk_clue_types(conclusion)
    return types


def _discover_levels() -> list[dict[str, Any]]:
    levels: list[dict[str, Any]] = []

    for path in sorted(MAPS_DIR.glob("level_*.json")):
        try:
            number = int(path.stem.split("_")[1])
        except (IndexError, ValueError):
            continue

        data = json.loads(path.read_text(encoding="utf-8"))
        clue_types: set[str] = set()
        for person in data["people"]:
            clue_types |= _walk_clue_types(person["clue"])

        meta = LEVEL_META.get(
            path.name,
            {
                "title": f"Màn {number}",
                "subtitle": "Một màn chơi Griductive.",
            },
        )
        extensions = sorted(clue_types & EXTENSION_TYPES)
        size = int(data["size"])

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
