"""Раздаёт папку design_export по http://127.0.0.1:8765 для скрипта в Figma.

Запуск::

    .venv\\Scripts\\python.exe tools\\serve_export.py

Скрипт (design_export/build.js) работает внутри плагина Figma и забирает отсюда
кадры (SVG) и список переходов. Разрешены запросы со страницы figma.com.
"""

import http.server
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "design_export"
PORT = 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def translate_path(self, path: str) -> str:
        if path.split("?")[0] == "/build.js":  # сам скрипт лежит в tools
            return str(Path(__file__).resolve().parent / "figma_build.js")
        return super().translate_path(path)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s\n" % (fmt % args))


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"http://127.0.0.1:{PORT}/  ->  {ROOT}")
    server.serve_forever()
