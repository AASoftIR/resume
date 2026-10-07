from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def compact(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return (cut or text[: limit - 1]).rstrip() + "…"


def seo_config(data: dict) -> dict:
    m = data.get("meta", {})
    raw = dict(data.get("seo", {}))
    raw.setdefault("site_url", "https://aasoftir.github.io/resume")
    raw["site_url"] = str(raw["site_url"]).rstrip("/")
    raw.setdefault("site_name", f'{m.get("name", "Resume")} · Software Developer')
    raw.setdefault("description", compact(data.get("profile", ""), 158))
    raw.setdefault("locale", "en_US")
    raw.setdefault("indexing", True)
    raw.setdefault("google_site_verification", "")
    raw.setdefault("bing_site_verification", "")
    raw.setdefault("keywords", [
        m.get("name", ""), "software developer", "web developer", "AI engineer",
        "Python", "JavaScript", "Linux", "portfolio", "resume",
    ])
    raw["keywords"] = [str(x).strip() for x in raw.get("keywords", []) if str(x).strip()]
    return raw


def person_schema(data: dict, site_url: str) -> dict:
    m = data["meta"]
    same_as = [x for x in [m.get("github"), m.get("website")] if x]
    person = {
        "@type": "Person",
        "@id": f"{site_url}/#person",
        "name": m.get("name"),
        "url": f"{site_url}/about/",
        "jobTitle": m.get("title"),
        "description": compact(data.get("profile", ""), 260),
        "email": f'mailto:{m.get("email")}' if m.get("email") else None,
        "telephone": m.get("phone") or None,
        "address": {"@type": "PostalAddress", "addressLocality": m.get("location")} if m.get("location") else None,
        "sameAs": same_as or None,
        "knowsAbout": [item for group in data.get("skills", []) for item in group.get("items", [])][:35],
        "affiliation": [
            {"@type": "CollegeOrUniversity", "name": x.get("school")}
            for x in data.get("education", []) if x.get("school")
        ] or None,
    }
    return {k: v for k, v in person.items() if v not in (None, "", [])}


def breadcrumb(site_url: str, items: list[tuple[str, str]]) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": f"{site_url}{path}"}
            for i, (name, path) in enumerate(items)
        ],
    }


def metadata(data: dict, *, title: str, description: str, canonical: str, page_type: str = "website", depth: int = 1, schema: dict | list | None = None) -> str:
    cfg = seo_config(data)
    m = data["meta"]
    root = "../" * depth
    robots = "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1" if cfg.get("indexing", True) else "noindex,nofollow"
    image = f'{cfg["site_url"]}/assets/og-card.png'
    keys = ", ".join(cfg.get("keywords", []))
    blocks = schema if isinstance(schema, list) else ([schema] if schema else [])
    graph = [person_schema(data, cfg["site_url"]), {
        "@type": "WebSite", "@id": f'{cfg["site_url"]}/#website', "url": f'{cfg["site_url"]}/',
        "name": cfg["site_name"], "inLanguage": m.get("language", "en"), "publisher": {"@id": f'{cfg["site_url"]}/#person'}
    }] + blocks
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/")
    verify = ""
    if cfg.get("google_site_verification"):
        verify += f'\n  <meta name="google-site-verification" content="{esc(cfg["google_site_verification"])}" />'
    if cfg.get("bing_site_verification"):
        verify += f'\n  <meta name="msvalidate.01" content="{esc(cfg["bing_site_verification"])}" />'
    return f'''  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}" />
  <meta name="author" content="{esc(m.get("name"))}" />
  <meta name="robots" content="{robots}" />
  <meta name="googlebot" content="{robots}" />
  <meta name="keywords" content="{esc(keys)}" />
  <meta name="theme-color" content="#0b1120" />
  <meta name="color-scheme" content="dark light" />
  <link rel="canonical" href="{esc(canonical)}" />
  <link rel="alternate" hreflang="{esc(m.get("language", "en"))}" href="{esc(canonical)}" />
  <link rel="alternate" hreflang="x-default" href="{esc(canonical)}" />
  <link rel="sitemap" type="application/xml" href="{root}sitemap.xml" />
  <link rel="alternate" type="application/pdf" href="{root}resume.pdf" title="{esc(m.get("name"))} resume PDF" />
  <link rel="icon" type="image/svg+xml" href="{root}favicon.svg" />
  <link rel="icon" type="image/png" sizes="192x192" href="{root}assets/icon-192.png" />
  <link rel="apple-touch-icon" href="{root}assets/icon-192.png" />
  <link rel="manifest" href="{root}site.webmanifest" />
  <link rel="me" href="{esc(m.get("github"))}" />
  <meta property="og:type" content="{esc(page_type)}" />
  <meta property="og:site_name" content="{esc(cfg["site_name"])}" />
  <meta property="og:title" content="{esc(title)}" />
  <meta property="og:description" content="{esc(description)}" />
  <meta property="og:url" content="{esc(canonical)}" />
  <meta property="og:image" content="{esc(image)}" />
  <meta property="og:image:secure_url" content="{esc(image)}" />
  <meta property="og:image:type" content="image/png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content="{esc(m.get("name"))} — {esc(m.get("title"))}" />
  <meta property="og:locale" content="{esc(cfg.get("locale", "en_US"))}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{esc(title)}" />
  <meta name="twitter:description" content="{esc(description)}" />
  <meta name="twitter:image" content="{esc(image)}" />
  <meta name="twitter:image:alt" content="{esc(m.get("name"))} — developer resume" />{verify}
  <script type="application/ld+json">{ld}</script>'''


def nav(root: str, active: str) -> str:
    links = [
        ("3D", "", "home"), ("About", "about/", "about"), ("Projects", "projects/", "projects"),
        ("Experience", "experience/", "experience"), ("Skills", "skills/", "skills"),
        ("Education", "education/", "education"), ("Contact", "contact/", "contact"), ("PDF", "resume.pdf", "pdf"),
    ]
    return '<nav class="site-nav" aria-label="Primary">' + "".join(
        f'<a href="{root}{href}" class="{"on" if key == active else ""}"{" target=\"_blank\"" if key == "pdf" else ""}>{label}</a>'
        for label, href, key in links
    ) + "</nav>"


def page_shell(data: dict, *, title: str, description: str, canonical_path: str, active: str, body: str, depth: int = 1, schema: dict | list | None = None, page_type: str = "website") -> str:
    cfg = seo_config(data)
    m = data["meta"]
    root = "../" * depth
    canonical = f'{cfg["site_url"]}{canonical_path}'
    return f'''<!doctype html>
<html lang="{esc(m.get("language", "en"))}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
{metadata(data, title=title, description=description, canonical=canonical, page_type=page_type, depth=depth, schema=schema)}
  <link rel="preload" href="{root}assets/fonts/Inter.woff2" as="font" type="font/woff2" crossorigin />
  <link rel="preload" href="{root}assets/fonts/SpaceGrotesk.woff2" as="font" type="font/woff2" crossorigin />
  <link rel="stylesheet" href="{root}css/pages.css" />
</head>
<body>
<header class="site-head"><a class="identity" href="{root}"><span>$_</span><div><strong>{esc(m.get("name"))}</strong><small>{esc(m.get("title"))}</small></div></a>{nav(root, active)}</header>
<main>{body}</main>
<footer><div><strong>{esc(m.get("name"))}</strong><p>{esc(data.get("motto", ""))}</p></div><div class="footer-links"><a href="{root}">Enter 3D resume</a><a href="{root}resume.pdf">PDF</a><a href="{esc(m.get("github"))}" rel="me noopener" target="_blank">GitHub</a></div></footer>
</body>
</html>'''


def render_about(data: dict) -> str:
    m = data["meta"]
    skills = [item for group in data.get("skills", []) for item in group.get("items", [])][:16]
    schema = {
        "@type": "ProfilePage", "@id": f'{seo_config(data)["site_url"]}/about/#page',
        "url": f'{seo_config(data)["site_url"]}/about/', "name": f'{m["name"]} — About',
        "mainEntity": {"@id": f'{seo_config(data)["site_url"]}/#person'}
    }
    body = f'''<section class="hero"><div><p class="eyebrow">PROFILE / ABOUT</p><h1>{esc(m["name"])}</h1><p class="lead">{esc(m["title"])}</p><div class="hero-actions"><a class="primary" href="../">Enter 3D experience</a><a href="../resume.pdf">Resume PDF</a></div></div><aside class="status"><span>Based in</span><b>{esc(m.get("location"))}</b><span>Currently</span><b>{esc(m.get("availability"))}</b></aside></section>
<section class="content-grid"><article class="card wide"><p class="eyebrow">PROFESSIONAL SUMMARY</p><h2>Building useful software end to end.</h2><p>{esc(data.get("profile"))}</p></article><article class="card"><p class="eyebrow">CORE STACK</p><div class="tags">{''.join(f'<span>{esc(x)}</span>' for x in skills)}</div></article><article class="card"><p class="eyebrow">HOW I WORK</p><blockquote>{esc(data.get("motto"))}</blockquote></article></section>'''
    return page_shell(data, title=f'{m["name"]} — Software Developer', description=compact(data.get("profile"), 158), canonical_path="/about/", active="about", body=body, schema=schema)


def render_projects(data: dict) -> str:
    cfg = seo_config(data); m = data["meta"]
    cards = []
    items = []
    for pos, p in enumerate(data.get("projects", []), 1):
        desc = compact(" ".join(p.get("bullets", [])), 175)
        href = f'{esc(p.get("id"))}/'
        cards.append(f'''<article class="project-card"><div class="project-top"><p class="eyebrow">PROJECT {pos:02d}</p><span class="status-pill">{esc(p.get("status"))}</span></div><h2><a href="{href}">{esc(p.get("title"))}</a></h2><p>{esc(desc)}</p><div class="tags">{''.join(f'<span>{esc(x)}</span>' for x in p.get("stack", [])[:7])}</div><a class="text-link" href="{href}">Open case page →</a></article>''')
        items.append({"@type": "ListItem", "position": pos, "url": f'{cfg["site_url"]}/projects/{p.get("id")}/', "name": p.get("title")})
    schema = [{"@type": "CollectionPage", "name": f'{m["name"]} Projects', "url": f'{cfg["site_url"]}/projects/'}, {"@type": "ItemList", "itemListElement": items}]
    body = f'''<section class="page-intro"><p class="eyebrow">SELECTED WORK</p><h1>Projects</h1><p>Practical software across web, AI automation and Linux tooling. Each project has its own crawlable page while the 3D resume remains the interactive overview.</p></section><section class="project-grid">{"".join(cards)}</section>'''
    return page_shell(data, title=f'Projects — {m["name"]}', description=f'Selected software projects by {m["name"]}: web applications, AI-integrated tools, automation and Linux software.', canonical_path="/projects/", active="projects", body=body, schema=schema)


def render_project(data: dict, p: dict) -> str:
    cfg = seo_config(data); m = data["meta"]; pid = p["id"]
    desc = compact(" ".join(p.get("bullets", [])), 158)
    repo = p.get("repo")
    links = f'<a class="primary" href="{esc(repo)}" target="_blank" rel="noopener">Repository / project ↗</a>' if repo else '<span class="disabled-link">Private / in progress</span>'
    body = f'''<section class="page-intro project-detail"><p class="eyebrow">PROJECT / {esc(p.get("status", ""))}</p><h1>{esc(p.get("title"))}</h1><p>{esc(desc)}</p><div class="hero-actions">{links}<a href="../../?layer={esc(pid)}">Open this layer in 3D</a></div></section><section class="content-grid"><article class="card wide"><p class="eyebrow">WHAT IT DOES</p><ul class="impact">{''.join(f'<li>{esc(x)}</li>' for x in p.get("bullets", []))}</ul></article><article class="card"><p class="eyebrow">STACK</p><div class="tags">{''.join(f'<span>{esc(x)}</span>' for x in p.get("stack", []))}</div></article><article class="card"><p class="eyebrow">STATUS</p><h2>{esc(p.get("status"))}</h2><p>Part of {esc(m.get("name"))}'s selected engineering portfolio.</p></article></section>'''
    software = {"@type": "SoftwareSourceCode", "name": p.get("title"), "description": desc, "url": f'{cfg["site_url"]}/projects/{pid}/', "author": {"@id": f'{cfg["site_url"]}/#person'}, "programmingLanguage": p.get("stack", [])}
    if repo:
        parsed_repo = urlparse(str(repo))
        parts = [x for x in parsed_repo.path.split("/") if x]
        if parsed_repo.netloc.lower().endswith("github.com") and len(parts) >= 2:
            software["codeRepository"] = repo
    schema = [software, breadcrumb(cfg["site_url"], [("Home", "/"), ("Projects", "/projects/"), (p.get("title", "Project"), f"/projects/{pid}/")])]
    return page_shell(data, title=f'{p.get("title")} — {m["name"]}', description=desc, canonical_path=f'/projects/{pid}/', active="projects", body=body, depth=2, schema=schema, page_type="article")


def render_experience(data: dict) -> str:
    m = data["meta"]
    items = []
    for x in data.get("experience", []):
        bullets = ''.join(f'<li>{esc(b)}</li>' for b in x.get("bullets", []))
        org = f' · {esc(x.get("organization"))}' if x.get("organization") else ''
        items.append(f'<article class="timeline-item"><span class="timeline-period">{esc(x.get("period"))}</span><div><h2>{esc(x.get("role"))}{org}</h2><ul class="impact">{bullets}</ul></div></article>')
    body = f'<section class="page-intro"><p class="eyebrow">WORK HISTORY</p><h1>Experience</h1><p>Roles and delivery experience behind the projects shown in the 3D resume.</p></section><section class="timeline">{"".join(items)}</section>'
    return page_shell(data, title=f'Experience — {m["name"]}', description=f'{m["name"]} software development experience, freelance work and engineering delivery history.', canonical_path="/experience/", active="experience", body=body, schema={"@type": "ProfilePage", "mainEntity": {"@id": f'{seo_config(data)["site_url"]}/#person'}})


def render_skills(data: dict) -> str:
    m = data["meta"]
    groups = ''.join(f'<article class="card"><p class="eyebrow">{esc(g.get("group"))}</p><div class="tags large">{"".join(f"<span>{esc(x)}</span>" for x in g.get("items", []))}</div></article>' for g in data.get("skills", []))
    body = f'<section class="page-intro"><p class="eyebrow">ENGINEERING TOOLKIT</p><h1>Skills</h1><p>Technologies I use to build, debug, ship and maintain software.</p></section><section class="content-grid">{groups}</section>'
    return page_shell(data, title=f'Skills — {m["name"]}', description=f'{m["name"]} technical skills across Python, JavaScript, web engineering, AI automation, databases, Linux and CI/CD.', canonical_path="/skills/", active="skills", body=body)


def render_education(data: dict) -> str:
    m = data["meta"]
    edu = ''.join(f'<article class="card"><p class="eyebrow">{esc(x.get("period"))}</p><h2>{esc(x.get("degree"))}</h2><p>{esc(x.get("school"))}</p></article>' for x in data.get("education", []))
    learning = ''.join(f'<li>{esc(x)}</li>' for x in data.get("learning", []))
    body = f'<section class="page-intro"><p class="eyebrow">EDUCATION / LEARNING</p><h1>Education</h1><p>Formal study plus the independent learning tracks that support my engineering work.</p></section><section class="content-grid">{edu}<article class="card wide"><p class="eyebrow">CONTINUOUS LEARNING</p><ul class="learning-list">{learning}</ul></article></section>'
    return page_shell(data, title=f'Education — {m["name"]}', description=f'{m["name"]} computer engineering education, courses and continuous software engineering learning.', canonical_path="/education/", active="education", body=body)


def render_contact(data: dict) -> str:
    cfg = seo_config(data); m = data["meta"]
    rows = [
        ("Email", f'mailto:{m.get("email")}', m.get("email")),
        ("GitHub", m.get("github"), str(m.get("github", "")).replace("https://", "")),
        ("Website", m.get("website"), str(m.get("website", "")).replace("https://", "")),
        ("Certificates", m.get("certificates"), str(m.get("certificates", "")).replace("https://", "")),
    ]
    contact = ''.join(f'<a class="contact-row" href="{esc(url)}"{(" target=\"_blank\" rel=\"noopener\"" if url and str(url).startswith("http") else "")}><span>{esc(label)}</span><strong>{esc(text)}</strong><b>↗</b></a>' for label,url,text in rows if url)
    langs = ', '.join(f'{x.get("name")} ({x.get("level")}/5)' for x in data.get("languages", []))
    body = f'''<section class="page-intro"><p class="eyebrow">LET'S BUILD SOMETHING USEFUL</p><h1>Contact</h1><p>{esc(m.get("availability"))}. The fastest way to reach me is email.</p></section><section class="contact-grid"><article class="card">{contact}</article><article class="card"><p class="eyebrow">LOCATION</p><h2>{esc(m.get("location"))}</h2><p>{esc(langs)}</p><div class="hero-actions"><a class="primary" href="mailto:{esc(m.get("email"))}">Email me</a><a href="../resume.pdf">Resume PDF</a></div></article></section>'''
    return page_shell(data, title=f'Contact — {m["name"]}', description=f'Contact {m["name"]}, {m["title"]}. {m.get("availability", "")}.', canonical_path="/contact/", active="contact", body=body, schema={"@type": "ContactPage", "mainEntity": {"@id": f'{cfg["site_url"]}/#person'}})


def render_cv(data: dict) -> str:
    m = data["meta"]
    body = f'''<section class="page-intro"><p class="eyebrow">PRINT / ATS VERSION</p><h1>Resume PDF</h1><p>The print-ready resume is generated from the same JSON source as the 3D site and these pages.</p><div class="hero-actions"><a class="primary" href="../resume.pdf">Open PDF ↗</a><a href="../resume.pdf" download>Download PDF</a></div></section><section class="pdf-frame"><object data="../resume.pdf" type="application/pdf"><p>Your browser cannot preview the PDF. <a href="../resume.pdf">Open it directly.</a></p></object></section>'''
    return page_shell(data, title=f'Resume PDF — {m["name"]}', description=f'View or download the current resume PDF for {m["name"]}, {m["title"]}.', canonical_path="/cv/", active="pdf", body=body)


def generate_images(data: dict, dist: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont
    assets = dist / "assets"; assets.mkdir(parents=True, exist_ok=True)
    m = data["meta"]
    def font(size: int, bold: bool = False):
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
        for p in paths:
            if Path(p).exists():
                return ImageFont.truetype(p, size=size)
        return ImageFont.load_default()

    img = Image.new("RGB", (1200, 630), "#07111f")
    d = ImageDraw.Draw(img)
    for i in range(0, 1200, 80): d.line((i,0,i,630), fill="#0d2033", width=1)
    for i in range(0, 630, 80): d.line((0,i,1200,i), fill="#0d2033", width=1)
    d.ellipse((820,-160,1320,340), fill="#17234b")
    d.ellipse((-180,330,370,880), fill="#073a46")
    d.rounded_rectangle((72, 70, 210, 112), radius=20, fill="#0e2a3d", outline="#22d3ee", width=2)
    d.text((98, 80), "$_ RESUME", font=font(18, True), fill="#67e8f9")
    d.text((72, 170), str(m.get("name")), font=font(66, True), fill="#f8fafc")
    title = compact(m.get("title", ""), 72)
    d.text((76, 260), title, font=font(28), fill="#b6c8dc")
    summary_font = font(21)
    summary = compact(data.get("profile", ""), 180)
    words = summary.split()
    lines, line = [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if d.textbbox((0, 0), candidate, font=summary_font)[2] <= 1020:
            line = candidate
        else:
            if line: lines.append(line)
            line = word
        if len(lines) == 2:
            break
    if line and len(lines) < 2: lines.append(line)
    for idx, ln in enumerate(lines[:2]):
        d.text((76, 350 + idx * 34), ln, font=summary_font, fill="#8fa5ba")
    d.text((76, 538), "3D resume  •  projects  •  experience  •  skills", font=font(18, True), fill="#22d3ee")
    img.save(assets / "og-card.png", optimize=True)

    icon = Image.new("RGB", (512, 512), "#07111f")
    di = ImageDraw.Draw(icon)
    di.rounded_rectangle((24,24,488,488), radius=110, fill="#0b1728", outline="#22d3ee", width=8)
    initials = "".join(x[0] for x in str(m.get("name", "A M")).split()[:2]).upper() or "AM"
    f = font(176, True); bb = di.textbbox((0,0), initials, font=f)
    di.text(((512-(bb[2]-bb[0]))/2, (512-(bb[3]-bb[1]))/2-18), initials, font=f, fill="#e2f9ff")
    di.rectangle((104,390,408,402), fill="#8b5cf6")
    icon.save(assets / "icon-512.png", optimize=True)
    icon.resize((192,192), Image.Resampling.LANCZOS).save(assets / "icon-192.png", optimize=True)
    icon.resize((64,64), Image.Resampling.LANCZOS).save(dist / "favicon.ico", format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64)])
    (dist / "favicon.svg").write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="15" fill="#07111f"/><rect x="4" y="4" width="56" height="56" rx="13" fill="none" stroke="#22d3ee"/><text x="32" y="39" text-anchor="middle" font-family="system-ui,sans-serif" font-size="22" font-weight="800" fill="#f8fafc">{esc(initials)}</text><path d="M17 49h30" stroke="#8b5cf6" stroke-width="3"/></svg>''', encoding="utf-8")


def patch_root(data: dict, index_path: Path) -> None:
    cfg = seo_config(data); m = data["meta"]
    text = index_path.read_text(encoding="utf-8")
    # Remove simple hand-written SEO that the generator replaces.
    patterns = [
        r"\s*<title>.*?</title>", r'\s*<meta name="description"[^>]*>', r'\s*<meta name="theme-color"[^>]*>',
        r'\s*<meta property="og:title"[^>]*>', r'\s*<meta property="og:description"[^>]*>', r'\s*<link rel="icon"[^>]*>',
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, count=1, flags=re.S)
    root_schema = {
        "@type": "ProfilePage", "@id": f'{cfg["site_url"]}/#profile', "url": f'{cfg["site_url"]}/',
        "name": cfg["site_name"], "mainEntity": {"@id": f'{cfg["site_url"]}/#person'}
    }
    seo = metadata(data, title=cfg["site_name"], description=cfg["description"], canonical=f'{cfg["site_url"]}/', depth=0, schema=root_schema)
    text = text.replace('<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />', '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />\n' + seo, 1)
    index_path.write_text(text, encoding="utf-8")


def build_seo(data: dict, dist: Path) -> list[str]:
    cfg = seo_config(data); m = data["meta"]
    generate_images(data, dist)
    patch_root(data, dist / "index.html")

    pages: list[tuple[str, str]] = [
        ("about/index.html", render_about(data)),
        ("projects/index.html", render_projects(data)),
        ("experience/index.html", render_experience(data)),
        ("skills/index.html", render_skills(data)),
        ("education/index.html", render_education(data)),
        ("contact/index.html", render_contact(data)),
        ("cv/index.html", render_cv(data)),
    ]
    for p in data.get("projects", []):
        pages.append((f'projects/{p["id"]}/index.html', render_project(data, p)))
    for rel, content in pages:
        path = dist / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")

    urls = [f'{cfg["site_url"]}/'] + [f'{cfg["site_url"]}/' + rel.removesuffix("index.html") for rel, _ in pages]
    sitemap_urls = urls + [f'{cfg["site_url"]}/resume.pdf']
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(
        f'  <url><loc>{esc(url)}</loc></url>\n' for url in sitemap_urls
    ) + '</urlset>\n'
    (dist / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    robots = ("User-agent: *\nAllow: /\n" if cfg.get("indexing", True) else "User-agent: *\nDisallow: /\n") + f'Sitemap: {cfg["site_url"]}/sitemap.xml\n'
    (dist / "robots.txt").write_text(robots, encoding="utf-8")
    (dist / "site.webmanifest").write_text(json.dumps({
        "name": cfg["site_name"], "short_name": m.get("name", "Resume"), "description": cfg["description"],
        "start_url": "./", "scope": "./", "display": "standalone", "background_color": "#07111f", "theme_color": "#0b1120",
        "icons": [{"src":"assets/icon-192.png","sizes":"192x192","type":"image/png"},{"src":"assets/icon-512.png","sizes":"512x512","type":"image/png"}],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dist / "humans.txt").write_text(f'{m.get("name")}\nRole: {m.get("title")}\nGitHub: {m.get("github")}\nSite: {cfg["site_url"]}/\nBuilt from data/resume.json.\n', encoding="utf-8")
    project_lines = "\n".join(f'- [{p.get("title")}]({cfg["site_url"]}/projects/{p.get("id")}/): {compact(" ".join(p.get("bullets", [])), 240)}' for p in data.get("projects", []))
    (dist / "llms.txt").write_text(f'''# {m.get("name")}\n\n> {cfg["description"]}\n\n## Canonical pages\n- [Profile]({cfg["site_url"]}/about/)\n- [Projects]({cfg["site_url"]}/projects/)\n- [Experience]({cfg["site_url"]}/experience/)\n- [Skills]({cfg["site_url"]}/skills/)\n- [Education]({cfg["site_url"]}/education/)\n- [Contact]({cfg["site_url"]}/contact/)\n- [Resume PDF]({cfg["site_url"]}/resume.pdf)\n\n## Selected projects\n{project_lines}\n''', encoding="utf-8")

    not_found = page_shell(data, title=f'Page not found — {m["name"]}', description='The requested resume page could not be found.', canonical_path="/404.html", active="", depth=0, body='<section class="page-intro error-page"><p class="eyebrow">404</p><h1>That page does not exist.</h1><p>The resume is still here.</p><div class="hero-actions"><a class="primary" href="./">Enter 3D resume</a><a href="projects/">Browse projects</a></div></section>')
    (dist / "404.html").write_text(not_found.replace('content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"', 'content="noindex,follow"'), encoding="utf-8")
    return urls
