#!/usr/bin/env python3
"""hubgen — single generator for the arschul hub ecosystem.

Usage (run from the directory holding the cloned repos):

    python3 hubgen.py check              drift report: missing targets, orphans, dupes
    python3 hubgen.py build [--dry-run]  rewrite HUBGEN regions in every hub index
    python3 hubgen.py index              write arschul.github.io/data/search-index.json
    python3 hubgen.py verify             prove build is idempotent and byte-safe
    python3 hubgen.py all                check -> build -> index -> verify

Machine-owned regions are delimited in each hub's index.html:

    <!-- HUBGEN:cards start -->    ... <!-- HUBGEN:cards end -->
    <!-- HUBGEN:theme start -->    ... <!-- HUBGEN:theme end -->
    <!-- HUBGEN:backlink start --> ... <!-- HUBGEN:backlink end -->
    <!-- HUBGEN:head start -->     ... <!-- HUBGEN:head end -->

Anything outside a region is hand-written and never touched. A file with no
markers is left byte-identical — which is why Stage 0 is a no-op.
"""
from __future__ import annotations

import argparse
import fnmatch
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from collections import Counter, defaultdict

CATALOG = "catalog.json"
ROOT_REPO = "arschul.github.io"
ASSET_VERSION = "v2"          # bump to ship a new shared stylesheet/script
LINK_EXT = (".html", ".pdf", ".docx")

C = dict(red="\033[31m", yellow="\033[33m", green="\033[32m", dim="\033[2m", off="\033[0m")
if not sys.stdout.isatty():
    C = {k: "" for k in C}


# ------------------------------------------------------------------ utilities

def load_catalog(path=CATALOG):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def repo_files(repo, exts=LINK_EXT):
    out = set()
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if f.endswith(exts):
                out.add(os.path.relpath(os.path.join(root, f), repo).replace(os.sep, "/"))
    return out


def extract_links(path):
    """Every local link a page points at, from href/src, onclick helpers and JS data arrays."""
    src = open(path, encoding="utf-8", errors="replace").read()
    found = set()
    found |= set(re.findall(r'(?:href|src)="([^"]+)"', src))
    found |= set(re.findall(r"go(?:To)?(?:Link|Game|Tool)\(\s*['\"]([^'\"]+)['\"]", src))
    found |= set(re.findall(r"""['"]([^'"]*\.(?:html|pdf|docx))['"]""", src, re.I))
    found |= set(re.findall(r'(?:url=|location\.(?:replace\(|href\s*=\s*))["\']?([^"\'>\s)]+)', src, re.I))
    out = set()
    for l in found:
        if l.startswith(("http", "//", "mailto:", "tel:", "javascript:", "data:", "#")):
            continue
        l = urllib.parse.unquote(l.split("#")[0].split("?")[0]).strip()
        if l:
            out.add(l)
    return out


def resolve(base_dir, link):
    """Resolve a link relative to the page holding it. Directory links become index.html."""
    if link.endswith("/") or (not os.path.splitext(link)[1]):
        link = link.rstrip("/") + "/index.html"
    return os.path.normpath(os.path.join(base_dir, link)).replace(os.sep, "/")


REDIRECT_RE = re.compile(r'http-equiv=["\']?refresh|location\.(?:replace|href)', re.I)


def redirect_target(repo, rel):
    """If the file is a small redirect stub, return where it points, else None."""
    p = os.path.join(repo, rel)
    try:
        if os.path.getsize(p) > 2048:
            return None
        src = open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    if not REDIRECT_RE.search(src):
        return None
    m = re.search(r'url=([^"\'>\s]+)|location\.(?:replace\(|href\s*=\s*)["\']([^"\']+)', src, re.I)
    return (m.group(1) or m.group(2)) if m else "?"


def reachable(repo):
    """Every file reachable from the hub's index.html by following local links."""
    seen, stack = set(), ["index.html"]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        p = os.path.join(repo, cur)
        if not os.path.exists(p):
            continue
        seen.add(cur)
        if cur.endswith(".html"):
            base = os.path.dirname(cur)
            for l in extract_links(p):
                n = resolve(base, l)
                if not n.startswith(".."):
                    stack.append(n)
    return seen


def ignored(cat, repo, rel):
    full = f"{repo}/{rel}"
    return any(fnmatch.fnmatch(full, pat) or fnmatch.fnmatch(rel, pat) for pat in cat.get("ignore", []))


# ---------------------------------------------------------------------- check

def cmd_check(cat, args):
    problems, notes = [], []
    hubs = cat["hubs"]
    by_hub = defaultdict(list)
    for it in cat["items"]:
        by_hub[it["hub"]].append(it)

    # 1. duplicate ids / paths
    ids = Counter((i["hub"], i["id"]) for i in cat["items"])
    for k, n in ids.items():
        if n > 1:
            problems.append(f"duplicate id {k[0]}/{k[1]} ({n}x)")
    paths = Counter((i["hub"], i["path"]) for i in cat["items"])
    for k, n in paths.items():
        if n > 1 and k[1]:
            problems.append(f"duplicate path {k[0]}/{k[1]} ({n}x)")

    # 2. catalog entries whose target file does not exist
    for it in cat["items"]:
        if it["hub"] == "root":
            continue
        repo = hubs[it["hub"]]["repo"]
        rel = it["path"].split("#")[0]
        if not rel:
            continue
        if not os.path.exists(os.path.join(repo, rel)):
            problems.append(f"missing target: {repo}/{rel}  (item {it['id']})")

    # 3. files on disk with no catalog entry
    stale = set(cat.get("stale", []))
    unlisted = set(cat.get("unlisted", []))
    for hub, meta in hubs.items():
        repo = meta["repo"]
        if not os.path.isdir(repo):
            notes.append(f"repo not cloned, skipped: {repo}")
            continue
        catalogued = {i["path"].split("#")[0] for i in by_hub[hub]} | {"index.html"}
        catalogued |= {p for p in repo_files(repo) if os.path.basename(p) == "index.html"}
        live = reachable(repo)
        for rel in sorted(repo_files(repo)):
            if rel in catalogued or ignored(cat, repo, rel):
                continue
            full = f"{repo}/{rel}"
            tgt = redirect_target(repo, rel)
            if tgt:
                notes.append(f"{C['dim']}redirect{C['off']}  {full} -> {tgt}")
                continue
            if full in stale:
                problems.append(f"stale copy, delete: {full}")
            elif full in unlisted:
                problems.append(f"unlisted live file, needs a card or retiring: {full}")
            elif rel in live:
                problems.append(f"reachable but uncatalogued: {full}")
            else:
                problems.append(f"orphan (unreachable, uncatalogued): {full}")

    # 4. vocabulary conformance
    v = cat["vocabularies"]
    for it in cat["items"]:
        for lv in it.get("levels", []):
            if lv not in v["levels"]:
                problems.append(f"bad level {lv!r} on {it['id']}")
        for sk in it.get("skills", []):
            if sk not in v["skills"]:
                problems.append(f"bad skill {sk!r} on {it['id']}")
        if it.get("mode") and it["mode"] not in v["modes"]:
            problems.append(f"bad mode {it['mode']!r} on {it['id']}")
        if it.get("prep") and it["prep"] not in v["preps"]:
            problems.append(f"bad prep {it['prep']!r} on {it['id']}")

    for n in notes:
        print(n)
    print()
    if problems:
        for p in problems:
            print(f"{C['red']}✗{C['off']} {p}")
        print(f"\n{len(problems)} problem(s), {len(notes)} note(s)")
    else:
        print(f"{C['green']}✓ no drift{C['off']}  ({len(cat['items'])} items, {len(notes)} redirects)")
    return 1 if problems and not args.soft else 0


# ---------------------------------------------------------------------- build

def esc(s):
    return html.escape(s or "", quote=True)


def bucket(minutes):
    for lo, hi, label in [(0, 9, "short"), (10, 25, "medium"), (26, 9999, "long")]:
        if lo <= (minutes or 0) <= hi:
            return label
    return "medium"


def render_cards(cat, hub):
    """Filter toolbar + card grid. Cards are real anchors with filterable data attributes."""
    items = [i for i in cat["items"] if i["hub"] == hub and i.get("status", "live") == "live"]
    items.sort(key=lambda i: (not i.get("featured", False), i["title"].lower()))
    rows = []
    for i in items:
        cls = "hub-card" + (" is-featured" if i.get("featured") else "")
        attrs = [
            f'class="{cls}"',
            f'href="{urllib.parse.quote(i["path"], safe="/#?&=")}"',
            f'data-id="{esc(i["id"])}"',
            f'data-levels="{esc(" ".join(i.get("levels", [])))}"',
            f'data-skills="{esc(" ".join(i.get("skills", [])))}"',
            f'data-mode="{esc(i.get("mode",""))}"',
            f'data-prep="{esc(i.get("prep",""))}"',
            f'data-time="{bucket(i.get("minutes"))}"',
            f'data-search="{esc(" ".join([i["title"], i.get("blurb",""), " ".join(i.get("keywords",[]))]).lower())}"',
        ]
        icon = f'<span class="hub-card__icon" aria-hidden="true">{i["icon"]}</span>\n        ' if i.get("icon") else ""
        chips = "".join(f'<span class="hub-chip hub-chip--level">{l}</span>' for l in i.get("levels", []))
        if i.get("mode"):
            chips += f'<span class="hub-chip hub-chip--mode">{esc(i["mode"])}</span>'
        if i.get("prep") and i["prep"] != "none":
            chips += f'<span class="hub-chip hub-chip--prep">{esc(i["prep"])}</span>'
        rows.append(
            f'      <a {" ".join(attrs)}>\n'
            f'        {icon}<h3 class="hub-card__title">{esc(i["title"])}</h3>\n'
            f'        <p class="hub-card__blurb">{esc(i.get("blurb",""))}</p>\n'
            f'        <div class="hub-card__meta">{chips}</div>\n'
            f'      </a>'
        )
    noun = dict(games="games", tools="tools").get(hub, "items")
    return (
        '  <div class="hub-toolbar">\n'
        '    <div class="hub-toolbar__row">\n'
        f'      <input type="search" class="hub-search" id="searchInput" placeholder="Search {noun} — press / to jump here" aria-label="Search {noun}" autocomplete="off">\n'
        '    </div>\n'
        '    <div class="hub-toolbar__row hub-toolbar__row--facets">\n'
        '      <button type="button" class="hub-clear" hidden>Clear all</button>\n'
        '    </div>\n'
        '    <div class="hub-toolbar__row"><span class="hub-count"></span></div>\n'
        '  </div>\n'
        '  <div class="hub-grid">\n' + "\n".join(rows) + '\n  </div>\n'
        f'  <p class="hub-empty" hidden>Nothing matches those filters. <button type="button" class="hub-clear">Clear all</button></p>'
    )


def render_theme():
    """Pre-paint theme boot. Duplicated into every file on purpose — generated, never hand-written."""
    return (
        '  <script>\n'
        '    (function(){try{var k="arschul:theme",v=localStorage.getItem(k);\n'
        '      if(!v){var old=["hub-theme","theme","gh-theme","adv-theme","reviews-theme","worksheets-theme"];\n'
        '        for(var i=0;i<old.length;i++){var o=localStorage.getItem(old[i]);if(o){v=o;break;}}\n'
        '        v=v||"dark";localStorage.setItem(k,v);}\n'
        '      var m=(v==="system")?(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):v;\n'
        '      document.documentElement.setAttribute("data-theme",m);}catch(e){}})();\n'
        '  </script>'
    )


def render_backlink(cat, hub):
    if hub == "root":
        return ""
    root = cat["hubs"]["root"]
    cfg = cat["hubs"][hub].get("backlink") or {}
    label = cfg.get("label", "\u2190 " + root["title"])
    cls = ("hub-backlink " + cfg["class"]).strip() if cfg.get("class") else "hub-backlink"
    title = f' title="{esc(cfg["title"])}"' if cfg.get("title") else ""
    return f'  <a class="{cls}" href="{root["url"]}"{title}>{label}</a>'


def render_head(cat, hub):
    """Meta block, favicon, shared assets, and this hub's mapping onto the --hub-* contract."""
    h = cat["hubs"][hub]
    root = cat["hubs"]["root"]["url"].rstrip("/")
    desc = h.get("description") or f'{h["title"]} — Phil Young\'s English School, Curitiba.'
    t = h.get("tokens", {})
    lines = [
        f'  <meta name="description" content="{esc(desc)}">',
        f'  <link rel="icon" href="{root}/assets/favicon.svg" type="image/svg+xml">',
        f'  <meta property="og:type" content="website">',
        f'  <meta property="og:title" content="{esc(h["title"])}">',
        f'  <meta property="og:description" content="{esc(desc)}">',
        f'  <meta property="og:url" content="{h["url"]}">',
        f'  <link rel="stylesheet" href="{root}/assets/hub.{ASSET_VERSION}.css">',
        f'  <script defer src="{root}/assets/hub.{ASSET_VERSION}.js"></script>',
    ]
    if t:
        pairs = [("bg", "bg"), ("surface", "surface"), ("ink", "ink"), ("ink-soft", "ink_soft"),
                 ("rule", "rule"), ("accent", "accent"), ("radius", "radius")]
        decls = "".join(f"--hub-{css}:var({t[key]});" for css, key in pairs if t.get(key))
        if t.get("display"):
            decls += f'--hub-font-display:{t["display"]};'
        if t.get("ui"):
            decls += f'--hub-font-ui:{t["ui"]};'
        lines.append(f'  <style>:root{{{decls}}}</style>')
    return "\n".join(lines)


REGION_RE = "<!--\\s*HUBGEN:{name} start\\s*-->(.*?)<!--\\s*HUBGEN:{name} end\\s*-->"


def replace_region(src, name, body):
    pat = re.compile(REGION_RE.format(name=name), re.S)
    if not pat.search(src):
        return src, False
    repl = f"<!-- HUBGEN:{name} start -->\n{body}\n<!-- HUBGEN:{name} end -->"
    return pat.sub(lambda _: repl, src, count=1), True


def node_check(path):
    """Parse every inline <script> with node --check. Returns list of failures."""
    if shutil.which("node") is None:
        return ["node not on PATH — script validation skipped"]
    src = open(path, encoding="utf-8", errors="replace").read()
    fails = []
    for n, m in enumerate(re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", src, re.S | re.I)):
        body = m.group(1)
        if not body.strip():
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
            t.write(body)
            tmp = t.name
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        os.unlink(tmp)
        if r.returncode:
            fails.append(f"{path} script #{n+1}: {r.stderr.strip().splitlines()[-1] if r.stderr else 'parse error'}")
    return fails


def cmd_build(cat, args):
    changed, skipped, fails = [], [], []
    for hub, meta in cat["hubs"].items():
        idx = os.path.join(meta["repo"], "index.html")
        if not os.path.exists(idx):
            continue
        src = orig = open(idx, encoding="utf-8").read()
        hit = False
        for name, body in [("cards", render_cards(cat, hub)), ("theme", render_theme()),
                           ("backlink", render_backlink(cat, hub)), ("head", render_head(cat, hub))]:
            src, ok = replace_region(src, name, body)
            hit = hit or ok
        if not hit:
            skipped.append(idx)
            continue
        if src == orig:
            continue
        if args.dry_run:
            changed.append(idx + " (dry run)")
            continue
        tmp = idx + ".hubgen"
        open(tmp, "w", encoding="utf-8").write(src)
        f = node_check(tmp)
        if f:
            os.unlink(tmp)
            fails += f
            continue
        os.replace(tmp, idx)
        changed.append(idx)

    for c in changed:
        print(f"{C['green']}rewrote{C['off']} {c}")
    for s in skipped:
        print(f"{C['dim']}no HUBGEN markers, untouched: {s}{C['off']}")
    for f in fails:
        print(f"{C['red']}✗ JS validation failed, not written:{C['off']} {f}")
    return 1 if fails else 0


# ---------------------------------------------------------------------- index

def cmd_index(cat, args):
    out = []
    for i in cat["items"]:
        if i["hub"] == "root" or i.get("status", "live") != "live":
            continue
        base = cat["hubs"][i["hub"]]["url"]
        out.append(dict(
            t=i["title"], u=base + urllib.parse.quote(i["path"], safe="/#?&="),
            h=i["hub"], lv=i.get("levels", []), sk=i.get("skills", []),
            m=i.get("mode", ""), p=i.get("prep", ""),
            k=" ".join([i.get("blurb", "")] + i.get("keywords", [])).lower()[:180],
        ))
    d = os.path.join(ROOT_REPO, "data")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "search-index.json")
    json.dump(dict(version=cat["version"], items=out), open(p, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"{C['green']}wrote{C['off']} {p}  ({len(out)} entries, {os.path.getsize(p)//1024} kB)")
    return 0


# --------------------------------------------------------------------- verify

def cmd_verify(cat, args):
    """Build is safe if: (a) running it changes nothing twice in a row, and
    (b) files without markers come out byte-identical."""
    before = {}
    for meta in cat["hubs"].values():
        idx = os.path.join(meta["repo"], "index.html")
        if os.path.exists(idx):
            before[idx] = open(idx, "rb").read()

    class A:
        dry_run = False
    cmd_build(cat, A())
    once = {p: open(p, "rb").read() for p in before}
    cmd_build(cat, A())
    twice = {p: open(p, "rb").read() for p in before}

    bad = [p for p in before if once[p] != twice[p]]
    untouched = [p for p in before if before[p] == twice[p]]
    print()
    if bad:
        for p in bad:
            print(f"{C['red']}✗ not idempotent:{C['off']} {p}")
        return 1
    print(f"{C['green']}✓ idempotent{C['off']} — second build byte-identical to the first")
    print(f"{C['dim']}  {len(untouched)}/{len(before)} hub indexes unchanged from the live version{C['off']}")
    for p in before:
        for f in node_check(p):
            print(f"{C['red']}✗ {f}{C['off']}")
            return 1
    print(f"{C['green']}✓ all inline scripts parse{C['off']}")
    return 0


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "build", "index", "verify", "all"])
    ap.add_argument("--catalog", default=CATALOG)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--soft", action="store_true", help="report drift but exit 0")
    args = ap.parse_args()
    cat = load_catalog(args.catalog)

    if args.command == "all":
        rc = cmd_check(cat, args)
        print()
        rc |= cmd_build(cat, args)
        rc |= cmd_index(cat, args)
        rc |= cmd_verify(cat, args)
        return rc
    return dict(check=cmd_check, build=cmd_build, index=cmd_index, verify=cmd_verify)[args.command](cat, args)


if __name__ == "__main__":
    sys.exit(main())
