#!/usr/bin/env python3
"""Build every workshop in this repo into _site/, one Pages folder each.

  python3 build.py                        # all workshops -> _site/
  python3 build.py resops-commvault-docs  # just that one
  python3 build.py --mode room            # SOLO chapters as inherited stubs

A workshop is any top-level directory holding a workshop.md authored in the
dialect (theme/DIALECT.md), with its figures in images/ beside it. It builds
to _site/<dir>/index.html — the name matters, since Pages and http.server
both serve a directory by its index. _site/index.html lists what is here.

Each page is one self-contained file, so it opens from file:// with the
network off as well as over Pages.
"""

import argparse
import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from theme import parser, render  # noqa: E402

ASSETS = ROOT / "theme" / "assets"
ICONS = ASSETS / "icons"
OUT = ROOT / "_site"

CSS_ORDER = ["tokens.css", "base.css", "components.css", "layout.css"]
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp"}
IMAGE_WARN_BYTES = 300 * 1024

# Repo furniture, not workshops.
SKIP = {"theme", "_site", ".git", ".github"}


def workshops():
    """Top-level directories holding a workshop.md, in folder order."""
    found = []
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or d.name in SKIP or d.name.startswith("."):
            continue
        if (d / "workshop.md").is_file():
            found.append(d)
        else:
            print(f"warning: {d.name}/ has no workshop.md and is not built",
                  file=sys.stderr)
    return found


def inline_images(nodes_flat, md_dir):
    """Every ![caption](path) becomes part of the document. Missing file =
    hard error; big file = warning; unreferenced file in images/ = warning."""
    refs = [node[2] for node in nodes_flat if node[0] == "fig"]
    images = {}
    for ref in refs:
        path = md_dir / ref
        if not path.is_file():
            raise SystemExit(f"image not found: {ref} (looked in {path})")
        data = path.read_bytes()
        if len(data) > IMAGE_WARN_BYTES:
            print(f"warning: {ref} is {len(data) // 1024}KB; compress it "
                  "or the one-file guide gets heavy", file=sys.stderr)
        mime = MIME.get(path.suffix.lower())
        if not mime:
            raise SystemExit(f"unsupported image type: {ref}")
        if path.suffix.lower() == ".svg":
            # INLINED AS MARKUP, NOT AS A DATA URI. An <img src="data:..."> is
            # a separate document: CSS custom properties do not cross into it,
            # so the figures keep their light-mode hexes and render as bright
            # white cards on a dark page. As markup they are part of this
            # document and follow the tokens like everything else.
            images[ref] = ("svg", themed_svg(data.decode("utf-8")))
        else:
            images[ref] = ("uri", f"data:{mime};base64," +
                           base64.b64encode(data).decode("ascii"))
    img_dir = md_dir / "images"
    if img_dir.is_dir():
        for f in sorted(img_dir.iterdir()):
            if f.is_file() and f"images/{f.name}" not in refs:
                print(f"warning: {md_dir.name}/images/{f.name} is not "
                      "referenced by workshop.md", file=sys.stderr)
    return images


# The figures were drawn from the light palette, one hex per token, so the
# mapping is exact rather than approximate. It maps to --fig-*, NOT to the
# page tokens: a diagram keeps its own light palette in both themes.
FIGURE_TOKENS = {
    "#ffffff": "var(--fig-bg)",
    "#00053b": "var(--fig-ink)",
    "#707391": "var(--fig-muted)",
    "#eaeaea": "var(--fig-line)",
    "#844896": "var(--fig-accent)",
    "#30881c": "var(--fig-yes)",
    "#db2961": "var(--fig-no)",
}


def themed_svg(text):
    """Swap the baked palette for tokens, and drop the fixed pixel size.

    width/height on the root make the figure ignore its container: the CSS
    already sets max-width:100%, and a fixed width fights it at narrow
    viewports. viewBox alone scales."""
    for hexcode, token in FIGURE_TOKENS.items():
        text = text.replace(hexcode, token).replace(hexcode.upper(), token)
    text = re.sub(r'\s(width|height)="\d+"', "", text, count=2)
    return text.strip()


def inline_icons(needed):
    """Official Commvault icons from theme/assets/icons/, as data URIs.

    Data URI rather than inline markup because the source files share ids
    (`In_progress`, `COMPLETED_ICONS`) and a `.cls-1` class, so pasting
    several into one document produces duplicate ids and colliding CSS.
    They are the MIDNIGHT variants: the color budget reserves crocus for
    interaction, and an icon is content."""
    out = {}
    for name in sorted(needed):
        path = ICONS / f"{name}.svg"
        if not path.is_file():
            raise SystemExit(
                f"unknown icon @{name}: expected "
                f"{path.relative_to(ROOT)}. Official icons only.")
        out[name] = "data:image/svg+xml;base64," + \
            base64.b64encode(path.read_bytes()).decode("ascii")
    return out


def check_expected_output(workshop, where_prefix):
    """Every command must be followed by a ✓ expected-output box before the
    next command begins. "Never let someone get stuck" is a build rule,
    not authoring discipline. ✗ recovery rows stay author judgment: not
    every command has a failure mode worth inventing prose for."""
    def fail(cmd, where):
        first = cmd.split("\n")[0]
        raise SystemExit(
            f"{where_prefix}: {where}: command `{first}` has no ✓ "
            "expected-output box after it. Every command ships with what "
            "the participant should see, or the guide does not build. "
            "See theme/DIALECT.md.")

    def scan(nodes, where):
        pending = None
        for node in nodes:
            if node[0] == "cmd":
                if pending is not None:
                    fail(pending, where)
                pending = node[1]
            elif node[0] == "diag":
                if any(r["glyph"] == "✓" for r in node[1]):
                    pending = None
        if pending is not None:
            fail(pending, where)

    scan(workshop["overview"], "Overview page")
    scan(workshop["setup"], "Setup page")
    for ch in workshop["chapters"]:
        scan(ch["body"], f"chapter {ch['num']} ({ch['name']})")
    scan(workshop["close"], "close page")


def check_offline(page, where):
    """The whole point is a file that works with the network off."""
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', page)
    if external:
        raise SystemExit(f"{where}: external references would break "
                         f"offline: {external[:3]}")


def brand_uris():
    brand = {
        name: "data:image/png;base64," + base64.b64encode(
            (ASSETS / f"brand-{name}.png").read_bytes()).decode("ascii")
        for name in ("mark", "wordmark")
    }
    brand["favicon"] = brand["mark"]      # the tab gets the hexagon too
    return brand


def css(names):
    return "\n".join((ASSETS / n).read_text(encoding="utf-8") for n in names)


def build_workshop(folder, mode, brand, write=True):
    """One workshop folder -> (html, entry for the landing page).

    write=False still renders: the index needs the title and chapter count,
    and a broken workshop should fail the build either way."""
    md = folder / "workshop.md"
    nodes = parser.parse(md.read_text(encoding="utf-8"))
    ws = parser.group(nodes)
    parser.check(ws)
    check_expected_output(ws, folder.name)

    images = inline_images(nodes, folder)
    needed = {r["icon"] for n in nodes if n[0] == "deflist"
              for r in n[1] if r.get("icon")}
    needed |= {n[4] for n in nodes if n[0] == "chapter" and n[4]}

    page = render.render_document(ws, css(CSS_ORDER),
                                  (ASSETS / "app.js").read_text("utf-8"),
                                  images, brand, mode, inline_icons(needed))
    check_offline(page, folder.name)

    if write:
        dest = OUT / folder.name / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")
    return page, {"slug": folder.name, "title": ws["title"],
                  "standfirst": ws["standfirst"], "meta": ws["meta"],
                  "chapters": len(ws["chapters"])}


# The landing page lives here rather than in theme/render.py: it is about
# the repo, not about the dialect.
INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" href="{favicon}">
<script>
/* Before the stylesheet, so the first paint is already the right theme.
   Same storage key as a guide page. */
try {{
  var t = JSON.parse(localStorage.getItem('resops-guide') || '{{}}').theme;
  if (t === 'dark' || t === 'light') {{
    document.documentElement.setAttribute('data-theme', t);
  }}
}} catch (e) {{}}
</script>
<style>
{css}
</style>
</head>
<body class="index">
<header class="index-mast">
  <div class="index-mast-inner">
    <div class="index-brandrow">
      <img class="index-wordmark" src="{wordmark}" alt="Commvault">
      <button id="theme" type="button" class="index-theme"
        aria-label="Switch to dark theme" aria-pressed="false">{sun}{moon}</button>
    </div>
    <p class="kicker">Workshops</p>
    <h1>{title}</h1>
    <p class="index-standfirst">{blurb}</p>
  </div>
</header>
<main class="index-main">
  <ul class="index-list">
{cards}
  </ul>
</main>
<footer class="index-foot">
  <p>Each workshop is one self-contained page: it opens offline, prints,
     and follows the reader's light or dark preference.</p>
</footer>
<script>
{js}
</script>
</body>
</html>
"""

CARD = """    <li class="index-card"><a href="{slug}/">
      <span class="index-card-title">{title}</span>
      <span class="index-card-blurb">{standfirst}</span>
      <span class="index-card-meta">{chapters} chapters{meta}</span>
    </a></li>"""

SITE_TITLE = "Cloud Natives Resilience"
SITE_BLURB = ("Hands-on workshops in resilience operations: proving a cloud "
              "workload comes back, and that what comes back is clean.")


def build_index(entries, brand):
    cards = "\n".join(
        CARD.format(slug=e["slug"], title=render.esc(e["title"]),
                    standfirst=render.inline(e["standfirst"]),
                    chapters=e["chapters"],
                    meta=" · " + render.inline(e["meta"]).replace(
                        "<strong>", "").replace("</strong>", "")
                    if e["meta"] else "")
        for e in entries)
    page = INDEX.format(title=SITE_TITLE, blurb=SITE_BLURB, cards=cards,
                        favicon=brand["favicon"], wordmark=brand["wordmark"],
                        sun=render.SUN_SVG, moon=render.MOON_SVG,
                        css=css(["tokens.css", "base.css", "index.css"]),
                        js=(ASSETS / "index.js").read_text("utf-8"))
    check_offline(page, "index")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    return page


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("only", nargs="*", metavar="WORKSHOP",
                    help="folder names to build; default is all of them")
    ap.add_argument("--mode", default="solo", choices=("solo", "room"),
                    help="solo renders every chapter; room renders "
                         "SOLO-tagged chapters as inherited stubs")
    args = ap.parse_args()

    found = workshops()
    if not found:
        raise SystemExit("no workshops found: a workshop is a top-level "
                         "directory holding a workshop.md")
    names = {d.name for d in found}
    for want in args.only:
        if want not in names:
            raise SystemExit(f"no workshop {want!r}; have: "
                             f"{', '.join(sorted(names))}")

    # Every workshop is visited even when this run names one: the index is
    # the only navigation, so a subset would drop the others from it.
    brand = brand_uris()
    entries = []
    for folder in found:
        write = not args.only or folder.name in args.only
        page, entry = build_workshop(folder, args.mode, brand, write)
        entries.append(entry)
        if write:
            n = page.count('<section class="page"')
            print(f"wrote _site/{folder.name}/index.html "
                  f"({len(page) // 1024}KB, {n} pages, mode={args.mode})")

    index = build_index(entries, brand)
    print(f"wrote _site/index.html ({len(index) // 1024}KB, "
          f"{len(entries)} workshops)")


if __name__ == "__main__":
    main()
