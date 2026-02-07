from __future__ import annotations

import threading
from pathlib import Path

from flask import Flask, redirect, render_template, url_for

from monitor.config import LOG_FILE
from monitor.os_monitor import iniciar_monitoramento


LOG_PATH = Path(LOG_FILE)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
monitor_thread: threading.Thread | None = None


def read_log(limit: int = 200) -> list[str]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    return lines[-limit:]


def ensure_monitor_running() -> None:
    global monitor_thread
    if monitor_thread and monitor_thread.is_alive():
        return

    monitor_thread = threading.Thread(target=iniciar_monitoramento, daemon=True)
    monitor_thread.start()


@app.route("/", methods=["GET"])
def index() -> str:
    ensure_monitor_running()
    lines = read_log()
    return render_template("index.html", lines=lines)


@app.route("/start", methods=["POST"])
def manual_start():
    ensure_monitor_running()
    return redirect(url_for("index"))


@app.route("/health", methods=["GET"])
def health() -> dict[str, str]:
    status = "running" if monitor_thread and monitor_thread.is_alive() else "stopped"
    return {"status": status}


if __name__ == "__main__":
    ensure_monitor_running()
    app.run(host="0.0.0.0", port=5000)
