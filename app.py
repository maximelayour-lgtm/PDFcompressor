#!/usr/bin/env python3
"""
app.py — Compresseur PDF en ligne (Flask + Ghostscript)
Déployable sur Render.com
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from flask import Flask, render_template, request, send_file, jsonify

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 Mo max

# ── Ghostscript ───────────────────────────────────────────────────────────────
GS_EXEC    = shutil.which("gs") or "gs"
GS_PRESETS = ["printer", "ebook", "screen"]


def run_gs(input_path: str, output_path: str, preset: str) -> int:
    cmd = [
        GS_EXEC, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5",
        f"-dPDFSETTINGS=/{preset}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={output_path}", input_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return os.path.getsize(output_path)


def compress_logic(input_path: Path, output_path: Path, target_pct: float = 25.0):
    original_size = input_path.stat().st_size
    final_size    = original_size
    best_tmp      = None
    success       = False

    for preset in GS_PRESETS:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            current_size = run_gs(str(input_path), tmp_path, preset)
            reduction    = (1 - current_size / original_size) * 100

            if reduction >= target_pct:
                if best_tmp and os.path.exists(best_tmp):
                    os.remove(best_tmp)
                best_tmp   = tmp_path
                final_size = current_size
                success    = True
                break

            if current_size < final_size:
                if best_tmp and os.path.exists(best_tmp):
                    os.remove(best_tmp)
                best_tmp   = tmp_path
                final_size = current_size
            else:
                os.remove(tmp_path)

        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    if best_tmp and os.path.exists(best_tmp):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(best_tmp, str(output_path))

    return original_size, final_size, success


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/compress", methods=["POST"])
def compress():
    if "pdf" not in request.files:
        return jsonify({"error": "Aucun fichier reçu."}), 400

    file = request.files["pdf"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Seul le format PDF est accepté."}), 400

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir    = Path(tmpdir)
        input_path = tmp_dir / "input.pdf"
        output_path= tmp_dir / "compressed.pdf"

        file.save(str(input_path))

        try:
            orig, final, success = compress_logic(input_path, output_path)
        except Exception as e:
            return jsonify({"error": f"Erreur de compression : {e}"}), 500

        reduction = (1 - final / orig) * 100
        orig_mo   = round(orig  / (1024 * 1024), 2)
        final_mo  = round(final / (1024 * 1024), 2)

        # Nom du fichier de sortie
        stem        = Path(file.filename).stem
        output_name = f"{stem}_compressed.pdf"

        response = send_file(
            str(output_path),
            as_attachment=True,
            download_name=output_name,
            mimetype="application/pdf",
        )
        response.headers["X-Original-Size"]   = str(orig_mo)
        response.headers["X-Compressed-Size"] = str(final_mo)
        response.headers["X-Reduction"]       = f"{reduction:.1f}"
        response.headers["X-Target-Hit"]      = "1" if success else "0"
        response.headers["Access-Control-Expose-Headers"] = "X-Original-Size,X-Compressed-Size,X-Reduction,X-Target-Hit"
        return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
