#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

from seo import build_seo, seo_config

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "resume.json"
WEB = ROOT / "web"
DIST = ROOT / "dist"

THEMES = {
    "midnight": {"bg":"#0b1120","paper":"#f8fafc","ink":"#0f172a","muted":"#475569","accent":"#0891b2","accent2":"#7c3aed","soft":"#e0f2fe"},
    "aurora":   {"bg":"#061713","paper":"#f7fffc","ink":"#10231e","muted":"#46645b","accent":"#0f9f8f","accent2":"#7e22ce","soft":"#d7fff5"},
    "ember":    {"bg":"#190a10","paper":"#fffafa","ink":"#2d1218","muted":"#6b4b52","accent":"#e11d48","accent2":"#d97706","soft":"#ffe4e6"},
    "matrix":   {"bg":"#020a05","paper":"#fbfffc","ink":"#082c16","muted":"#3d6049","accent":"#15803d","accent2":"#16a34a","soft":"#dcfce7"},
    "mono":     {"bg":"#08090b","paper":"#fbfbfc","ink":"#17191d","muted":"#616874","accent":"#334155","accent2":"#64748b","soft":"#e2e8f0"},
    "ocean":    {"bg":"#031523","paper":"#f7fcff","ink":"#092236","muted":"#466779","accent":"#0284c7","accent2":"#0f766e","soft":"#e0f2fe"},
    "synthwave":{"bg":"#160b24","paper":"#fff8ff","ink":"#291239","muted":"#6e4d7d","accent":"#db2777","accent2":"#0891b2","soft":"#fce7f3"},
    "solar":    {"bg":"#160e05","paper":"#fffaf4","ink":"#321b08","muted":"#765438","accent":"#d97706","accent2":"#dc2626","soft":"#fef3c7"},
}


def e(value) -> str:
    return html.escape(str(value or ""), quote=True)


def load_resume() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    validate(data)
    return data


def validate(data: dict) -> None:
    errors: list[str] = []
    for path in [
        "meta.name", "meta.title", "meta.email", "profile", "projects",
        "experience", "skills", "education", "languages", "layout.layers",
    ]:
        cur = data
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                errors.append(f"missing {path}")
                break
            cur = cur[part]

    appearance = data.get("appearance", {})
    for key in ("default_theme", "pdf_theme"):
        if appearance.get(key, "midnight") not in THEMES:
            errors.append(f"appearance.{key} must be one of: {', '.join(THEMES)}")
    if appearance.get("quality", "auto") not in {"auto", "high", "balanced", "eco"}:
        errors.append("appearance.quality must be one of: auto, high, balanced, eco")
    if appearance.get("intro", "smart") not in {"smart", "always", "skip"}:
        errors.append("appearance.intro must be one of: smart, always, skip")

    email = str(data.get("meta", {}).get("email", ""))
    if email and "@" not in email:
        errors.append("meta.email does not look like an email address")

    seo = seo_config(data)
    site_url = str(seo.get("site_url", ""))
    parsed_site = urlparse(site_url)
    if parsed_site.scheme not in {"http", "https"} or not parsed_site.netloc:
        errors.append("seo.site_url must be an absolute public http(s) URL")
    if site_url.endswith("/"):
        errors.append("seo.site_url must not end with a slash")
    if len(str(seo.get("description", ""))) > 200:
        errors.append("seo.description should be 200 characters or fewer")

    ids = set()
    for i, project in enumerate(data.get("projects", [])):
        if not isinstance(project, dict):
            errors.append(f"projects[{i}] must be an object")
            continue
        pid = str(project.get("id", ""))
        if not pid:
            errors.append(f"projects[{i}].id is required")
        elif not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", pid):
            errors.append(f"projects[{i}].id must be a lowercase URL-safe slug")
        elif pid in ids:
            errors.append(f"duplicate project id: {pid}")
        ids.add(pid)
        if project.get("status_kind", "dev") not in {"ok", "dev", "thesis"}:
            errors.append(f"projects[{i}].status_kind must be ok, dev or thesis")
        for key in ("stack", "bullets"):
            if not isinstance(project.get(key, []), list):
                errors.append(f"projects[{i}].{key} must be a list")

    for i, language in enumerate(data.get("languages", [])):
        try:
            level = int(language.get("level", 0))
            if not 1 <= level <= 5:
                errors.append(f"languages[{i}].level must be between 1 and 5")
        except (TypeError, ValueError):
            errors.append(f"languages[{i}].level must be an integer")

    page = data.get("layout", {}).get("page", {})
    for key in ("width", "height", "scale"):
        try:
            if float(page.get(key, 0)) <= 0:
                errors.append(f"layout.page.{key} must be greater than zero")
        except (TypeError, ValueError):
            errors.append(f"layout.page.{key} must be numeric")

    if errors:
        raise ValueError("Resume JSON validation failed:\n- " + "\n- ".join(errors))


def layout(data: dict, key: str, box: dict, explode: dict | None = None) -> dict:
    default = {"box": box, "explode": explode or {}}
    return data.get("layout", {}).get("layers", {}).get(key, default)


def layer(id_: str, title: str, path: str, spec: dict, body: str, cls: str = "") -> dict:
    return {
        "id": id_, "title": title, "path": path,
        "box": spec["box"], "ex": spec.get("explode", {}),
        "cls": cls, "html": body,
    }


def chips(items: list[str], cls: str = "") -> str:
    return "".join(f'<span class="chip {cls}" data-pop>{e(item)}</span>' for item in items)


def dots(level: int) -> str:
    return "".join(f'<i class="{"on" if i < int(level) else ""}"></i>' for i in range(5))


def make_layers(data: dict) -> list[dict]:
    m = data["meta"]
    first = m["name"].split()[0].lower()
    phone_href = re.sub(r"[^+0-9]", "", m.get("phone", ""))
    website_label = m.get("website", "").replace("https://", "").replace("http://", "")
    github_label = m.get("github", "").replace("https://", "").replace("http://", "")

    contact_html = "".join([
        f'<li data-pop><a href="mailto:{e(m.get("email"))}"><b>@</b> {e(m.get("email"))}</a></li>',
        f'<li data-pop><a href="tel:{e(phone_href)}"><b>☎</b> {e(m.get("phone"))}</a></li>',
        f'<li data-pop><a href="{e(m.get("github"))}" target="_blank" rel="noopener"><b>gh</b> {e(github_label)}</a></li>',
        f'<li data-pop><a href="{e(m.get("website"))}" target="_blank" rel="noopener"><b>www</b> {e(website_label)}</a></li>',
        f'<li data-pop><span><b>⌖</b> {e(m.get("location"))} · {e(m.get("availability"))}</span></li>',
    ])

    layers = [
        layer(
            "header", "whoami", "header/identity",
            layout(data, "header", {"x":0,"y":0,"w":924,"h":224}, {"z":430,"dy":120,"rx":-0.08,"ry":0.1}),
            f'<div class="prompt" data-pop>~/{e(first)} $ whoami<span class="caret"></span></div>'
            f'<h1 data-pop data-z="35">{e(m["name"])}</h1>'
            f'<p class="role" data-pop data-z="22">{e(m["title"])}</p>'
            f'<ul class="contacts">{contact_html}</ul><div class="bar"></div>',
            "p-header",
        ),
        layer(
            "profile", "Profile", "sections/01-profile",
            layout(data, "profile", {"x":49,"y":240,"w":535,"h":218}, {"z":250,"dx":-60,"ry":0.16,"rx":0.02}),
            f'<h2 data-pop data-z="20"><span class="num">01</span> Profile</h2>'
            f'<p data-pop data-z="10">{e(data["profile"])}</p>',
        ),
        layer(
            "projects", "Selected Projects", "sections/02-projects",
            layout(data, "projects-title", {"x":49,"y":462,"w":535,"h":44}, {"z":360,"dx":-120,"dy":40,"ry":0.2}),
            '<h2 data-pop data-z="25"><span class="num">02</span> Selected Projects</h2>',
            "p-strip",
        ),
    ]

    for i, project in enumerate(data.get("projects", [])):
        spec = layout(
            data, f"project-{i}",
            {"x":49,"y":508 + i * 136,"w":535,"h":126},
            {"z":190 + (i % 2) * 100,"dx":-170 - i * 15,"ry":0.20},
        )
        repo = project.get("repo", "")
        repo_html = (
            f'<a class="gh" href="{e(repo)}" target="_blank" rel="noopener" data-pop>github ↗</a>'
            if repo else '<span class="gh muted" data-pop>in progress</span>'
        )
        bullets = "".join(f'<li data-pop>{e(item)}</li>' for item in project.get("bullets", []))
        body = (
            '<div class="proj-head">'
            f'<h3 data-pop data-z="22">{e(project.get("title"))} '
            f'<span class="badge {e(project.get("status_kind", "dev"))}">{e(project.get("status"))}</span></h3>'
            f'{repo_html}</div>'
            f'<div class="stack" data-pop data-z="15">{" · ".join(e(x) for x in project.get("stack", []))}</div>'
            f'<ul class="bul">{bullets}</ul>'
        )
        pid = project.get("id", f"project-{i}")
        layers.append(layer(pid, project.get("title", "Project"), f"projects/{pid}", spec, body))

    exp_parts = ['<h2 data-pop data-z="20"><span class="num">03</span> Experience</h2>']
    for item in data.get("experience", []):
        org = f' <em>· {e(item.get("organization"))}</em>' if item.get("organization") else ""
        exp_parts.append(
            f'<div class="job" data-pop data-z="17"><b>{e(item.get("role"))}{org}</b>'
            f'<span class="when">{e(item.get("period"))}</span></div>'
        )
        if item.get("bullets"):
            exp_parts.append('<ul class="bul">' + "".join(f'<li data-pop>{e(b)}</li>' for b in item["bullets"]) + '</ul>')
    layers.append(layer(
        "experience", "Experience", "sections/03-experience",
        layout(data, "experience", {"x":49,"y":972,"w":535,"h":206}, {"z":210,"dx":-110,"dy":-110,"ry":0.15,"rx":0.04}),
        "".join(exp_parts),
    ))

    layers.append(layer(
        "motto", "How I work", "mantra/how-i-work",
        layout(data, "motto", {"x":61,"y":1186,"w":511,"h":56}, {"z":470,"dx":-60,"dy":-170,"ry":0.12,"rx":0.06}),
        f'<div class="c" data-pop data-z="15">// how I work</div><div class="q" data-pop data-z="28">{e(data.get("motto"))}</div>',
        "p-motto",
    ))

    skill_parts = ['<h2 class="side" data-pop data-z="20">Skills</h2>']
    for group in data.get("skills", []):
        cls = "ai" if "AI" in group.get("group", "") else ""
        skill_parts.append(f'<h4 data-pop>{e(group.get("group"))}</h4>')
        skill_parts.append(f'<div class="chips">{chips(group.get("items", []), cls)}</div>')
    layers.append(layer(
        "skills", "Skills", "sidebar/skills",
        layout(data, "skills", {"x":596,"y":240,"w":282,"h":532}, {"z":300,"dx":180,"dy":40,"ry":-0.06,"rz":0.01}),
        "".join(skill_parts),
    ))

    edu_parts = ['<h2 class="side" data-pop data-z="20">Education</h2>']
    for item in data.get("education", []):
        edu_parts.append(
            f'<div class="edu" data-pop data-z="15"><b>{e(item.get("degree"))}</b>'
            f'{e(item.get("school"))}<span class="mono">{e(item.get("period"))}</span></div>'
        )
    layers.append(layer(
        "education", "Education", "sidebar/education",
        layout(data, "education", {"x":596,"y":778,"w":282,"h":110}, {"z":160,"dx":250,"dy":-10,"ry":-0.1,"rz":-0.01}),
        "".join(edu_parts),
    ))

    cert = m.get("certificates", "")
    cert_label = cert.replace("https://", "").replace("http://", "")
    cert_html = f'<a class="certs mono" href="{e(cert)}" target="_blank" rel="noopener" data-pop>{e(cert_label)} ↗</a>' if cert else ""
    learning_html = (
        '<h2 class="side" data-pop data-z="20">Learning</h2><ul class="checks">'
        + "".join(f'<li data-pop>{e(item)}</li>' for item in data.get("learning", []))
        + f'</ul>{cert_html}'
    )
    layers.append(layer(
        "learning", "Learning", "sidebar/learning",
        layout(data, "learning", {"x":596,"y":892,"w":282,"h":232}, {"z":260,"dx":210,"dy":-50,"ry":-0.04,"rz":0.012}),
        learning_html,
    ))

    language_html = '<h2 class="side" data-pop data-z="20">Languages</h2>' + "".join(
        f'<div class="lang" data-pop><span>{e(item.get("name"))}</span><span class="dots">{dots(item.get("level", 0))}</span></div>'
        for item in data.get("languages", [])
    )
    layers.append(layer(
        "languages", "Languages", "sidebar/languages",
        layout(data, "languages", {"x":596,"y":1128,"w":282,"h":120}, {"z":380,"dx":160,"dy":-120,"ry":-0.08,"rx":0.05}),
        language_html,
    ))

    layers.append(layer(
        "footer", "Footer", "meta/footer",
        layout(data, "footer", {"x":49,"y":1252,"w":826,"h":42}, {"z":-140,"dy":-160,"rx":0.1}),
        f'<span data-pop>{e(m["name"])} · Resume</span><span data-pop>'
        f'<a href="{e(m.get("github"))}" target="_blank" rel="noopener">{e(github_label)}</a> · '
        f'<a href="{e(m.get("website"))}" target="_blank" rel="noopener">{e(website_label)}</a></span>',
        "p-footer",
    ))
    return layers


def write_data_js(data: dict, out_path: Path) -> None:
    page = data.get("layout", {}).get("page", {})
    scale = float(page.get("scale", 1.2))
    width = round(float(page.get("width", 924)) * scale)
    height = round(float(page.get("height", 1307)) * scale)
    output = [
        "// GENERATED from data/resume.json. Do not edit.\n",
        f"export const DEFAULT_THEME = {json.dumps(data.get('appearance', {}).get('default_theme', 'midnight'))};\n",
        f"export const APPEARANCE = {json.dumps(data.get('appearance', {}), ensure_ascii=False)};\n",
        f"export const RESUME_META = {json.dumps(data.get('meta', {}), ensure_ascii=False)};\n",
        f"export const PAGE = {{ w: {width}, h: {height} }};\n",
        "export const LAYERS = [\n",
    ]
    for item in make_layers(data):
        box = {k: round(float(v) * scale) for k, v in item["box"].items()}
        record = {
            "id": item["id"], "title": item["title"], "path": item["path"],
            "box": box, "ex": item.get("ex", {}), "cls": item.get("cls", ""),
            "html": item["html"],
        }
        output.append("  " + json.dumps(record, ensure_ascii=False) + ",\n")
    output.append("];\n")
    out_path.write_text("".join(output), encoding="utf-8")


def patch_index(data: dict, path: Path) -> None:
    m = data["meta"]
    text = path.read_text(encoding="utf-8")
    title = f'{m["name"]} · Developer Universe'
    desc = f'Explore {m["name"]} interactive 3D resume: {m["title"]}.'
    text = re.sub(r"<title>.*?</title>", f"<title>{e(title)}</title>", text, count=1)
    text = re.sub(r'<meta name="description" content="[^"]*"\s*/>', f'<meta name="description" content="{e(desc)}" />', text, count=1)
    text = re.sub(r'<meta property="og:title" content="[^"]*"\s*/>', f'<meta property="og:title" content="{e(title)}" />', text, count=1)
    text = re.sub(r'<meta property="og:description" content="[^"]*"\s*/>', f'<meta property="og:description" content="{e(m["title"])}" />', text, count=1)
    text = text.replace("assets/Alireza_Mohebbi_Resume.pdf", "resume.pdf")
    first = m["name"].split()[0].lower()
    text = re.sub(r'<span class="prompt">~/[^<]+\$</span>', f'<span class="prompt">~/{e(first)} $</span>', text, count=1)
    text = re.sub(r'<span class="availability"><i></i>.*?</span>', f'<span class="availability"><i></i> {e(m.get("availability", ""))}</span>', text, count=1)
    path.write_text(text, encoding="utf-8")


def build_pdf(data: dict, out_path: Path) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    theme = THEMES[data.get("appearance", {}).get("pdf_theme", "midnight")]
    W, H = A4
    c = canvas.Canvas(str(out_path), pagesize=A4, pageCompression=1)
    paper = HexColor(theme["paper"])
    ink = HexColor(theme["ink"])
    muted = HexColor(theme["muted"])
    accent = HexColor(theme["accent"])
    accent2 = HexColor(theme["accent2"])
    soft = HexColor(theme["soft"])
    m = data["meta"]

    def fit_text(text: str, font: str, size: float, width: float) -> str:
        text = str(text or "")
        if stringWidth(text, font, size) <= width:
            return text
        while text and stringWidth(text + "…", font, size) > width:
            text = text[:-1]
        return text.rstrip() + "…"

    def wrapped(text: str, x: float, y: float, width: float, *, font="Helvetica", size=7.5, leading=9.2, color=None, max_lines=None) -> float:
        words = str(text or "").split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            if stringWidth(test, font, size) <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = fit_text(lines[-1] + "…", font, size, width)
        c.setFont(font, size)
        c.setFillColor(color or ink)
        for ln in lines:
            c.drawString(x, y, ln)
            y -= leading
        return y

    def section_title(x: float, y: float, num: int, title: str, width: float) -> float:
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 6.8)
        c.drawString(x, y + 1.2 * mm, f"{num:02d}")
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 10.4)
        c.drawString(x + 8 * mm, y, title.upper())
        c.setStrokeColor(HexColor("#dbe3ec"))
        c.setLineWidth(0.5)
        c.line(x, y - 2.4 * mm, x + width, y - 2.4 * mm)
        return y - 7 * mm

    c.setFillColor(paper)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(HexColor(theme["bg"]))
    c.rect(0, H - 55 * mm, W, 55 * mm, stroke=0, fill=1)
    c.setFillColor(accent)
    c.roundRect(16 * mm, H - 17 * mm, 31 * mm, 7 * mm, 3.5 * mm, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 7.2)
    c.drawCentredString(31.5 * mm, H - 14.6 * mm, "~/resume $ whoami")
    c.setFont("Helvetica-Bold", 23)
    c.drawString(16 * mm, H - 29 * mm, m["name"])
    c.setFillColor(HexColor("#cbd5e1"))
    c.setFont("Helvetica", 8.5)
    c.drawString(16 * mm, H - 36 * mm, fit_text(m["title"], "Helvetica", 8.5, W - 32 * mm))
    c.setStrokeColor(HexColor("#334155"))
    c.line(16 * mm, H - 41 * mm, W - 16 * mm, H - 41 * mm)
    contact = "   •   ".join(x for x in [m.get("email"), m.get("phone"), m.get("github", "").replace("https://", ""), m.get("location")] if x)
    c.setFont("Helvetica", 7.1)
    c.setFillColor(HexColor("#e2e8f0"))
    c.drawString(16 * mm, H - 48 * mm, fit_text(contact, "Helvetica", 7.1, W - 32 * mm))

    left = 16 * mm
    top = H - 64 * mm
    gap = 8 * mm
    side_w = 57 * mm
    main_w = W - left * 2 - side_w - gap
    x2 = left + main_w + gap

    y = section_title(left, top, 1, "Profile", main_w)
    y = wrapped(data["profile"], left, y, main_w, size=7.5, leading=9.15, color=muted, max_lines=7) - 2.5 * mm
    y = section_title(left, y, 2, "Selected Projects", main_w)
    for project in data.get("projects", []):
        if y < 68 * mm:
            break
        card_h = 24 * mm
        c.setFillColor(soft)
        c.roundRect(left, y - card_h, main_w, card_h, 3 * mm, stroke=0, fill=1)
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(left + 4 * mm, y - 5 * mm, fit_text(project.get("title", "Project"), "Helvetica-Bold", 8.5, main_w - 42 * mm))
        badge = project.get("status", "")
        badge_w = min(30 * mm, max(15 * mm, stringWidth(badge, "Helvetica-Bold", 5.9) + 6 * mm))
        c.setFillColor(accent)
        c.roundRect(left + main_w - badge_w - 4 * mm, y - 8 * mm, badge_w, 5.5 * mm, 2.75 * mm, stroke=0, fill=1)
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica-Bold", 5.9)
        c.drawCentredString(left + main_w - badge_w / 2 - 4 * mm, y - 6.1 * mm, fit_text(badge, "Helvetica-Bold", 5.9, badge_w - 3 * mm))
        stack = " · ".join(project.get("stack", []))
        c.setFillColor(accent2)
        c.setFont("Helvetica-Bold", 6.2)
        c.drawString(left + 4 * mm, y - 10.5 * mm, fit_text(stack, "Helvetica-Bold", 6.2, main_w - 8 * mm))
        by = y - 14 * mm
        for bullet in project.get("bullets", [])[:2]:
            c.setFillColor(accent)
            c.circle(left + 5 * mm, by + 1.2, 1.15, stroke=0, fill=1)
            by = wrapped(bullet, left + 8 * mm, by, main_w - 13 * mm, size=6.55, leading=7.45, color=muted, max_lines=2)
        y -= 27 * mm

    y -= 1 * mm
    y = section_title(left, y, 3, "Experience", main_w)
    for item in data.get("experience", []):
        if y < 28 * mm:
            break
        role = item.get("role", "") + ((" · " + item.get("organization", "")) if item.get("organization") else "")
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 7.4)
        c.drawString(left, y, fit_text(role, "Helvetica-Bold", 7.4, main_w - 30 * mm))
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 6.3)
        c.drawRightString(left + main_w, y, item.get("period", ""))
        y -= 4 * mm
        for bullet in item.get("bullets", [])[:2]:
            y = wrapped("• " + bullet, left + 2 * mm, y, main_w - 2 * mm, size=6.2, leading=7.0, color=muted, max_lines=2)
        y -= 1.5 * mm

    sy = section_title(x2, top, 4, "Skills", side_w)
    for group in data.get("skills", []):
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 7.0)
        c.drawString(x2, sy, group.get("group", ""))
        sy -= 4 * mm
        line = ""
        for item in group.get("items", []):
            token = item + "   "
            if stringWidth(line + token, "Helvetica", 6.35) > side_w:
                c.setFillColor(muted)
                c.setFont("Helvetica", 6.35)
                c.drawString(x2, sy, line.strip())
                sy -= 3.5 * mm
                line = ""
            line += token
        if line:
            c.setFillColor(muted)
            c.setFont("Helvetica", 6.35)
            c.drawString(x2, sy, line.strip())
            sy -= 3.5 * mm
        sy -= 1.3 * mm

    sy -= 1 * mm
    sy = section_title(x2, sy, 5, "Education", side_w)
    for item in data.get("education", []):
        sy = wrapped(item.get("degree", ""), x2, sy, side_w, font="Helvetica-Bold", size=7.1, leading=8.0, color=ink, max_lines=2)
        sy = wrapped(item.get("school", ""), x2, sy, side_w, size=6.25, leading=7.1, color=muted, max_lines=2)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 5.9)
        c.drawString(x2, sy, item.get("period", ""))
        sy -= 5 * mm

    sy = section_title(x2, sy, 6, "Learning", side_w)
    for item in data.get("learning", [])[:6]:
        c.setFillColor(accent)
        c.circle(x2 + 1.2 * mm, sy + 1, 1.05, stroke=0, fill=1)
        sy = wrapped(item, x2 + 4 * mm, sy, side_w - 4 * mm, size=6.2, leading=7.0, color=muted, max_lines=2)

    sy -= 1 * mm
    sy = section_title(x2, sy, 7, "Languages", side_w)
    for item in data.get("languages", []):
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 6.7)
        c.drawString(x2, sy, item.get("name", ""))
        dot_x = x2 + 30 * mm
        for i in range(5):
            c.setFillColor(accent if i < int(item.get("level", 0)) else HexColor("#dbe3ec"))
            c.circle(dot_x + i * 4.2 * mm, sy + 1.2, 1.45, stroke=0, fill=1)
        sy -= 5 * mm

    sy -= 1 * mm
    sy = section_title(x2, sy, 8, "Online", side_w)
    links = [
        ("github", m.get("github")),
        ("website", m.get("website")),
        ("certificates", m.get("certificates")),
    ]
    for label, url in links:
        if not url:
            continue
        shown = str(url).replace("https://", "").replace("http://", "")
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 5.8)
        c.drawString(x2, sy, label.upper())
        sy -= 3.2 * mm
        c.setFillColor(muted)
        c.setFont("Helvetica", 6.0)
        text = fit_text(shown, "Helvetica", 6.0, side_w)
        c.drawString(x2, sy, text)
        c.linkURL(str(url), (x2, sy - 1 * mm, x2 + side_w, sy + 2.5 * mm), relative=0)
        sy -= 4.4 * mm
    if m.get("availability"):
        c.setFillColor(soft)
        c.roundRect(x2, sy - 7 * mm, side_w, 7 * mm, 2.5 * mm, stroke=0, fill=1)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 5.8)
        c.drawString(x2 + 3 * mm, sy - 4.4 * mm, fit_text(m.get("availability"), "Helvetica-Bold", 5.8, side_w - 6 * mm))

    c.setFillColor(HexColor(theme["bg"]))
    c.roundRect(16 * mm, 11 * mm, W - 32 * mm, 13 * mm, 4 * mm, stroke=0, fill=1)
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 5.8)
    c.drawString(20 * mm, 19 * mm, "// HOW I WORK")
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 7.4)
    c.drawString(20 * mm, 14.5 * mm, fit_text(data.get("motto", ""), "Helvetica-Bold", 7.4, W - 40 * mm))

    c.setTitle(f'{m["name"]} - Resume')
    c.setAuthor(m["name"])
    c.setSubject(m["title"])
    c.save()


def build(clean: bool = True) -> dict:
    data = load_resume()
    if clean and DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(WEB, DIST, dirs_exist_ok=True)
    write_data_js(data, DIST / "js" / "data.js")
    patch_index(data, DIST / "index.html")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    (DIST / "data").mkdir(exist_ok=True)
    shutil.copy2(DATA, DIST / "data" / "resume.json")
    build_pdf(data, DIST / "resume.pdf")
    build_seo(data, DIST)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()
    try:
        data = build(clean=not args.no_clean)
        print(f"Built {len(make_layers(data))} 3D layers -> {DIST}")
        print(f"PDF -> {DIST / 'resume.pdf'}")
        print(f"SEO pages + sitemap -> {DIST / 'sitemap.xml'}")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
