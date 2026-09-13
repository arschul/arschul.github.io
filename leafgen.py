#!/usr/bin/env python3
"""Stage 6 — propagate theme continuity and a way home to every leaf page.

Three insertions, all inside a single marked region so a later pass can revise
them without re-scanning 265 bespoke files:

  <!-- HUBGEN:leaf start --> … <!-- HUBGEN:leaf end -->

  1. a pre-paint boot script (inline, so there is no flash of the wrong theme)
  2. a deferred <script src> for the shared leaf behavior
  3. a back-link, ONLY on pages that do not already have one

The toggle is never added. A page that has one gets it rebound to the shared
key by leaf.v1.js; a page without one just inherits the theme.
Idempotent: a file that already carries the region is skipped.
"""
import os
import re
import sys

ROOT_URL = "https://arschul.github.io"

BOOT = """<!-- HUBGEN:leaf start -->
<script>(function(){try{var k="arschul:theme",v=localStorage.getItem(k);
if(!v){var o=["hub-theme","theme","gh-theme","adv-theme","reviews-theme","worksheets-theme",
"vocab-theme","toefl-theme","stc-theme","wheelquest-theme","wba-theme","airtight-theme","efl-reader-theme"];
for(var i=0;i<o.length;i++){var x=localStorage.getItem(o[i]);if(x==="light"||x==="dark"){v=x;break;}}
v=v||"dark";localStorage.setItem(k,v);}
var m=(v==="system")?(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):v;
document.documentElement.setAttribute("data-theme",m);}catch(e){}})();</script>
<script defer src="{root}/assets/leaf.v1.js"></script>
<!-- HUBGEN:leaf end -->"""

# Self-contained: leaf pages do not load the shared stylesheet, so this carries
# its own styling and stays out of the way of full-bleed game layouts.
BACKLINK = """<!-- HUBGEN:leafback start -->
<a href="{root}/" style="position:fixed;left:10px;bottom:10px;z-index:2147483000;
display:inline-block;padding:5px 11px;border-radius:999px;font:500 12px/1.2 system-ui,sans-serif;
text-decoration:none;color:#c9d3e4;background:rgba(16,24,42,.82);border:1px solid rgba(160,180,210,.28);
backdrop-filter:blur(4px);opacity:.55;transition:opacity .2s" onmouseover="this.style.opacity=1"
onmouseout="this.style.opacity=.55" title="Classroom Hub">&#8592; Hub</a>
<!-- HUBGEN:leafback end -->"""

HAS_BACK = re.compile(
    r'href="(?:\.\./?|https://arschul\.github\.io/)[^"]*"[^>]*>[^<]{0,40}(?:hub|back|\u2190|\u2b05)'
    r'|(?:back|hub)[-_]?(?:link|btn|button)', re.I)


def leaves(root):
    for repo in ("games", "tools", "grammar", "advanced", "reviews", "vocab", "worksheets"):
        base = os.path.join(root, repo)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for f in filenames:
                if f.endswith(".html") and f != "index.html":
                    yield repo, os.path.join(dirpath, f)


def process(path, add_back):
    src = open(path, encoding="utf-8", errors="replace").read()
    if "HUBGEN:leaf start" in src:
        return None, "already done"
    m = re.search(r"<head[^>]*>", src, re.I)
    if not m:
        return None, "no <head>"
    out = src[:m.end()] + "\n" + BOOT.replace("{root}", ROOT_URL) + src[m.end():]

    if add_back and not HAS_BACK.search(src):
        b = re.search(r"<body[^>]*>", out, re.I)
        if b:
            out = out[:b.end()] + "\n" + BACKLINK.replace("{root}", ROOT_URL) + out[b.end():]
            return out, "boot + back-link"
        return out, "boot (no <body>)"
    return out, "boot"


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    apply = "--apply" in sys.argv
    counts = {}
    changed = []
    for repo, path in leaves(root):
        out, why = process(path, add_back=True)
        counts[why] = counts.get(why, 0) + 1
        if out and apply:
            open(path, "w", encoding="utf-8").write(out)
            changed.append(path)
    print(("applied to " if apply else "would change ") + str(sum(
        v for k, v in counts.items() if k.startswith("boot"))) + " pages")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
