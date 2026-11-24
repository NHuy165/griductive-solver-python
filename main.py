"""Entry point for the Griductive web interface.

Run:
    python main.py
    python main.py --port 8000 --debug
"""

from __future__ import annotations

import argparse
import sys

from src.web.app import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chạy giao diện web của Griductive."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Địa chỉ máy chủ (mặc định: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Cổng máy chủ (mặc định: 5000).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Bật chế độ debug của Flask.",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    app = create_app()
    print(f"Griductive đang chạy tại http://{args.host}:{args.port}")
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug,
    )


if __name__ == "__main__":
    main()
