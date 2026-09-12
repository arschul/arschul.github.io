#!/usr/bin/env python3
"""lint_copy — find British spellings in user-facing copy across the hub repos.

Flags, does not rewrite. Some hits are deliberate: an EFL site legitimately
teaches the US/UK contrast, and a file that does so must keep its British forms.
Run `lint_copy.py report` first, classify, then `lint_copy.py fix --apply`.
"""
import os
import re
import sys
import json
from collections import defaultdict

# british -> american. Word-boundary matched, case preserved on the first letter.
PAIRS = {
    "organise": "organize", "organised": "organized", "organising": "organizing",
    "organisation": "organization", "organisations": "organizations",
    "recognise": "recognize", "recognised": "recognized", "recognising": "recognizing",
    "realise": "realize", "realised": "realized", "realising": "realizing",
    "analyse": "analyze", "analysed": "analyzed", "analysing": "analyzing",
    "apologise": "apologize", "apologised": "apologized",
    "memorise": "memorize", "memorised": "memorized", "memorising": "memorizing",
    "summarise": "summarize", "summarised": "summarized", "summarising": "summarizing",
    "emphasise": "emphasize", "emphasised": "emphasized",
    "specialise": "specialize", "specialised": "specialized",
    "categorise": "categorize", "categorised": "categorized",
    "prioritise": "prioritize", "prioritised": "prioritized",
    "customise": "customize", "customised": "customized",
    "programme": "program", "programmes": "programs",
    "colour": "color", "colours": "colors", "coloured": "colored", "colourful": "colorful",
    "favourite": "favorite", "favourites": "favorites",
    "behaviour": "behavior", "behaviours": "behaviors",
    "neighbour": "neighbor", "neighbours": "neighbors", "neighbourhood": "neighborhood",
    "flavour": "flavor", "flavours": "flavors",
    "humour": "humor", "labour": "labor", "harbour": "harbor",
    "honour": "honor", "honours": "honors",
    "centre": "center", "centres": "centers", "centred": "centered",
    "metre": "meter", "metres": "meters",
    "litre": "liter", "litres": "liters", "fibre": "fiber",
    "catalogue": "catalog", "catalogues": "catalogs",
        "whilst": "while", "amongst": "among",
    "learnt": "learned", "spelt": "spelled", "dreamt": "dreamed", "burnt": "burned",
    "grey": "gray",
    "licence": "license", "defence": "defense", "offence": "offense", "pretence": "pretense",
    "practise": "practice", "practises": "practices", "practising": "practicing",
    "travelling": "traveling", "travelled": "traveled", "traveller": "traveler",
    "labelled": "labeled", "labelling": "labeling",
    "cancelled": "canceled", "cancelling": "canceling",
    "modelling": "modeling", "modelled": "modeled",
    "jewellery": "jewelry", "moustache": "mustache", "storey": "story",
    "aluminium": "aluminum", "cheque": "check", "kerb": "curb", "tyre": "tire",
    "pyjamas": "pajamas", "plough": "plow", "draught": "draft",
    "aeroplane": "airplane", "maths": "math",
}
# words that are legitimately British inside a lesson about the US/UK contrast
# Checked on the hit's own line, not the whole file: an EFL site mentions
# "American English" all over the place without every page being a contrast lesson.
CONTRAST_MARKERS = re.compile(
    r"\bbritish\b|\bbrit\.|\bUK\b|\bBrE\b|\bAmE\b|american (?:spelling|english)"
    r"|british (?:spelling|english)", re.I)

SKIP_DIRS = {".git", "node_modules"}
# generated artifacts: fix the source, then regenerate
SKIP_FILES = {"search-index.json", "lint_hits.json"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".ico", ".woff", ".woff2", ".ttf"}
# never touch: urls, css identifiers, js identifiers, attribute names
INERT = re.compile(
    r"https?://\S+"                       # urls
    r"|--[\w-]+"                          # css custom properties
    r"|[\w-]*colou?r\s*:"                 # css color declarations
    r"|\.[\w-]*colou?r[\w-]*"             # css class names
    r"|[\w$]+\.[\w$]+"                    # member access
    r"|(?:var|let|const|function)\s+\w+",
    re.I)


def files(root):
    for repo in sorted(os.listdir(root)):
        p = os.path.join(root, repo)
        if not os.path.isdir(p):
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                if os.path.splitext(f)[1].lower() in SKIP_EXT or f in SKIP_FILES:
                    continue
                yield repo, os.path.join(dirpath, f)


def scan(root):
    pat = re.compile(r"\b(" + "|".join(sorted(PAIRS, key=len, reverse=True)) + r")\b", re.I)
    hits = defaultdict(list)
    for repo, path in files(root):
        try:
            src = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        masked = INERT.sub(lambda m: " " * len(m.group(0)), src)
        for m in pat.finditer(masked):
            word = m.group(1)
            line = src.count("\n", 0, m.start()) + 1
            ls = src.rfind("\n", 0, m.start()) + 1
            le = src.find("\n", m.end())
            around = src[ls:le if le > -1 else len(src)]
            # a deliberate US/UK contrast on this line protects the hit
            contrast = bool(CONTRAST_MARKERS.search(around))
            st = max(0, m.start() - 45)
            ctx = re.sub(r"\s+", " ", src[st:m.end() + 45])
            hits[path].append(dict(word=word, line=line, pos=m.start(),
                                   ctx=ctx, contrast=contrast, repo=repo))
    return hits


def report(root):
    hits = scan(root)
    total = sum(len(v) for v in hits.values())
    by_word = defaultdict(int)
    flagged = 0
    for path, hs in sorted(hits.items()):
        prot = sum(1 for h in hs if h["contrast"])
        marks = f"  [{prot} protected by a US/UK contrast on the line]" if prot else ""
        print(f"\n{path}  ({len(hs)}){marks}")
        for h in hs[:6]:
            by_word[h["word"].lower()] += 1
            print(f"   L{h['line']:<5} {h['word']:<14} …{h['ctx']}…")
        if len(hs) > 6:
            print(f"   … {len(hs) - 6} more")
        for h in hs:
            by_word[h["word"].lower()] += 0
            if h["contrast"]:
                flagged += 1
    print(f"\n{total} hits in {len(hits)} files; {flagged} sit in files that discuss the US/UK contrast")
    print("by word:", dict(sorted(by_word.items(), key=lambda kv: -kv[1])))
    json.dump({p: hs for p, hs in hits.items()}, open("lint_hits.json", "w"), indent=1)


def fix(root, apply=False, skip_contrast=True, only=None):
    hits = scan(root)
    changed = 0
    for path, hs in sorted(hits.items()):
        if only and not any(path.startswith(o) for o in only):
            continue
        hs = [h for h in hs if not (skip_contrast and h["contrast"])]
        if not hs:
            continue
        src = open(path, encoding="utf-8").read()
        out, last = [], 0
        for h in sorted(hs, key=lambda x: x["pos"]):
            repl = PAIRS[h["word"].lower()]
            if h["word"][0].isupper():
                repl = repl[0].upper() + repl[1:]
            if h["word"].isupper():
                repl = repl.upper()
            out.append(src[last:h["pos"]])
            out.append(repl)
            last = h["pos"] + len(h["word"])
        out.append(src[last:])
        new = "".join(out)
        if new != src:
            changed += 1
            print(f"{'fixed ' if apply else 'would fix '}{path}  ({len(hs)})")
            if apply:
                open(path, "w", encoding="utf-8").write(new)
    print(f"\n{changed} file(s) {'changed' if apply else 'to change'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    root = os.environ.get("HUB_ROOT", ".")
    if cmd == "report":
        report(root)
    elif cmd == "fix":
        fix(root, apply="--apply" in sys.argv)
