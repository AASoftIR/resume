#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import shutil
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "resume.json"
DIST = ROOT / "dist"
LOCAL = ROOT / ".local"
BACKUPS = LOCAL / "backups"
HOST = "127.0.0.1"
PORT = 8788

sys.path.insert(0, str(ROOT / "scripts"))
import build as resume_build  # noqa: E402


def rebuild() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def read_resume() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def validate_resume(payload: dict) -> list[str]:
    try:
        resume_build.validate(payload)
        return []
    except Exception as exc:
        text = str(exc)
        return [line.removeprefix("- ").strip() for line in text.splitlines() if line.strip() and "validation failed" not in line.lower()]


def backup_current() -> Path | None:
    if not DATA.exists():
        return None
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = BACKUPS / f"resume-{stamp}.json"
    shutil.copyfile(DATA, path)
    backups = sorted(BACKUPS.glob("resume-*.json"), reverse=True)
    for old in backups[30:]:
        old.unlink(missing_ok=True)
    return path


def list_backups() -> list[dict]:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    result = []
    for path in sorted(BACKUPS.glob("resume-*.json"), reverse=True)[:30]:
        stat = path.stat()
        result.append({
            "name": path.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return result


def diagnostics() -> dict:
    pdf = DIST / "resume.pdf"
    index = DIST / "index.html"
    sitemap = DIST / "sitemap.xml"
    robots = DIST / "robots.txt"
    seo_pages = len([p for p in DIST.rglob("index.html") if p.is_file()]) if DIST.exists() else 0
    git = "not a git checkout"
    try:
        p = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, timeout=3)
        if p.returncode == 0:
            git = p.stdout.strip() or "clean"
    except Exception:
        pass
    return {
        "python": sys.version.split()[0],
        "json_bytes": DATA.stat().st_size if DATA.exists() else 0,
        "json_modified": datetime.fromtimestamp(DATA.stat().st_mtime).isoformat(timespec="seconds") if DATA.exists() else None,
        "site_built": index.exists(),
        "site_bytes": index.stat().st_size if index.exists() else 0,
        "pdf_built": pdf.exists(),
        "pdf_bytes": pdf.stat().st_size if pdf.exists() else 0,
        "seo_pages": seo_pages,
        "sitemap_built": sitemap.exists(),
        "robots_built": robots.exists(),
        "backups": len(list_backups()),
        "git": git,
    }


def reply(handler: BaseHTTPRequestHandler, status: int, body, content_type="application/json; charset=utf-8") -> None:
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    elif isinstance(body, str):
        body = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[studio]", fmt % args)

    def _json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 5_000_000:
            raise ValueError("Payload is too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            return reply(self, 200, (ROOT / "editor.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        if path == "/api/resume":
            return reply(self, 200, read_resume())
        if path == "/api/diagnostics":
            return reply(self, 200, diagnostics())
        if path == "/api/backups":
            return reply(self, 200, list_backups())
        if path == "/api/build":
            ok, log = rebuild()
            return reply(self, 200 if ok else 500, {"ok": ok, "log": log, "diagnostics": diagnostics()})
        if path.startswith("/preview"):
            relative = path[len("/preview"):].lstrip("/") or "index.html"
            target = (DIST / relative).resolve()
            if DIST.resolve() not in target.parents and target != DIST.resolve():
                return reply(self, 403, "forbidden", "text/plain")
            if target.is_dir():
                target = (target / "index.html").resolve()
            if not target.is_file():
                return reply(self, 404, "not found", "text/plain")
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return reply(self, 404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/validate":
                payload = self._json_body()
                errors = validate_resume(payload)
                return reply(self, 200 if not errors else 400, {"ok": not errors, "errors": errors})

            if path == "/api/resume":
                payload = self._json_body()
                errors = validate_resume(payload)
                if errors:
                    return reply(self, 400, {"ok": False, "error": "Validation failed", "errors": errors})
                old = DATA.read_text(encoding="utf-8")
                backup_current()
                DATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                ok, log = rebuild()
                if not ok:
                    DATA.write_text(old, encoding="utf-8")
                    rebuild()
                    return reply(self, 400, {"ok": False, "error": "Build failed; changes were rolled back.", "log": log})
                return reply(self, 200, {"ok": True, "log": log, "diagnostics": diagnostics()})

            if path == "/api/restore":
                payload = self._json_body()
                name = Path(str(payload.get("name", ""))).name
                target = BACKUPS / name
                if not target.is_file() or not name.startswith("resume-"):
                    return reply(self, 404, {"ok": False, "error": "Backup not found"})
                restored = json.loads(target.read_text(encoding="utf-8"))
                errors = validate_resume(restored)
                if errors:
                    return reply(self, 400, {"ok": False, "error": "Backup is invalid", "errors": errors})
                old = DATA.read_text(encoding="utf-8")
                backup_current()
                DATA.write_text(json.dumps(restored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                ok, log = rebuild()
                if not ok:
                    DATA.write_text(old, encoding="utf-8")
                    rebuild()
                    return reply(self, 500, {"ok": False, "error": "Restore build failed; previous resume was restored.", "log": log})
                return reply(self, 200, {"ok": True, "log": log})

            return reply(self, 404, {"error": "not found"})
        except subprocess.TimeoutExpired:
            return reply(self, 500, {"ok": False, "error": "Build timed out"})
        except Exception as exc:
            return reply(self, 400, {"ok": False, "error": str(exc)})


def main():
    LOCAL.mkdir(exist_ok=True)
    ok, log = rebuild()
    print(log)
    if not ok:
        raise SystemExit(1)
    print(f"Resume Studio: http://{HOST}:{PORT}")
    print(f"3D preview:    http://{HOST}:{PORT}/preview/")
    print(f"PDF preview:   http://{HOST}:{PORT}/preview/resume.pdf")
    try:
        webbrowser.open(f"http://{HOST}:{PORT}")
    except Exception:
        pass
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
