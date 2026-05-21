# app.py
"""
Simple single‑page app to browse the bands in discovered_bands.md,
mark the ones you know / have listened to, and save the choices locally.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "discovered_bands.md"
STATE_FILE = BASE_DIR / "listened.json"

app = Flask(__name__, static_folder="static", template_folder="templates")


def load_bands() -> Dict[str, List[str]]:
    country_bands: Dict[str, List[str]] = {}
    current_country = None
    with DATA_FILE.open(encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^##\s+([^#\n\r]+)", line)
            if m:
                title = m.group(1).strip()
                if title.lower() != "table of contents":
                    current_country = title
                    country_bands.setdefault(current_country, [])
                continue
            if current_country:
                m = re.match(r"^\|\s*\*\*(.+?)\*\*\s*\|", line)
                if m:
                    band = m.group(1).strip()
                    if band not in country_bands[current_country]:
                        country_bands[current_country].append(band)
    return country_bands


def load_state() -> Dict[str, bool]:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state: Dict[str, bool]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


@app.route("/", methods=["GET"])
def index():
    bands_by_country = load_bands()
    state = load_state()
    return render_template("index.html", bands_by_country=bands_by_country, state=state)


@app.route("/save", methods=["POST"])
def save():
    payload = request.get_json()
    if not payload or "listened" not in payload:
        return jsonify({"error": "Invalid payload"}), 400
    current_state = load_state()
    current_state.update({k: bool(v) for k, v in payload["listened"].items()})
    save_state(current_state)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
