#!/usr/bin/env python3
"""Stage 0 one-off: assemble catalog.json from the live hubs + hand-authored metadata.

Run once from the directory holding the cloned repos. After this, catalog.json is
the source of truth and is edited by hand; hubgen.py reads it.
"""
import json, os, re, sys
from bs4 import BeautifulSoup

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = sys.argv[2] if len(sys.argv) > 2 else "catalog.json"

# ---------------------------------------------------------------- hand-authored
# path: (levels, skills, mode, prep, minutes, extra keywords)
# levels [] == level-agnostic (teacher supplies the content) -> matches every level filter
GAMES = {
 "airtight/airtight.html":            ("A2 B1 B2","speaking listening","team","none",25,"alibi interrogation detective past continuous contradiction suspects"),
 "alphabet/alphabet.html":            ("","vocabulary speaking","team","none",10,"letters categories warm-up brainstorm"),
 "animal-guess-game/animal-guess-game.html": ("","vocabulary speaking","team","none",10,"animals yes/no questions guessing twenty questions"),
 "backandforth/backandforth.html":    ("","vocabulary speaking","team","none",10,"categories alternating warm-up quick fire"),
 "bingo/bingo.html":                  ("","listening vocabulary","whole-class","setup",15,"word list caller grid custom words"),
 "bluff/bluff.html":                  ("","speaking","team","none",15,"invent definitions lying persuasion"),
 "boardgame/boardgame.html":          ("A1 A2 B1 B2","grammar","team","none",30,"cefr quest board game tokens dice grammar quiz"),
 "chain/chain.html":                  ("","vocabulary","team","none",10,"word chain last letter warm-up"),
 "city/city.html":                    ("A1 A2 B1","listening","team","none",20,"directions prepositions of place map navigation streets compass"),
 "classroom-auction/classroom-auction.html": ("","speaking","team","none",20,"bidding stunts dares challenges"),
 "connect/connect.html":              ("","vocabulary","team","none",20,"word building letters pressure power-ups"),
 "control-deck/control-deck.html":    ("","listening","team","none",15,"commands dials sliders imperatives following instructions"),
 "deal-no-deal/deal-no-deal.html":    ("","speaking","whole-class","none",20,"briefcase banker probability prizes money"),
 "deep-cover/deep-cover.html":        ("A1 A2 B1 B2","vocabulary speaking","team","none",25,"codenames spy word association clue grid spymaster"),
 "emoji/emoji.html":                  ("A1 A2","vocabulary","team","none",10,"memory what changed observation"),
 "emoji-logic/emoji-logic.html":      ("","reading","team","print",25,"einstein riddle zebra puzzle logic grid deduction prepositions"),
 "escape/escape.html":                ("","reading","team","none",25,"escape room puzzles clues locks"),
 "escape2/escape2.html":              ("","reading","team","none",25,"escape room puzzles clues locks sequel"),
 "family-feud-efl/family-feud-efl.html": ("","speaking","team","none",30,"feud survey fast money buzzer"),
 "grammar-boom/grammar-boom.html":    ("A1 A2 B1 B2","grammar","team","none",20,"baamboozle tiles quiz fate flip"),
 "herd-up/herd-up.html":              ("","vocabulary speaking","team","none",10,"consensus think alike group thinking"),
 "hex-duel/hex-duel.html":            ("","vocabulary","team","none",20,"territory hexagons conquest chaos mode"),
 "hot-seat/hot-seat.html":            ("A1 A2 B1 B2","speaking","team","none",15,"taboo describe forbidden words definitions"),
 "interrupt/interrupt.html":          ("A1 A2 B1 B2","speaking","team","none",20,"storytelling steal turn narrative cards"),
 "inventions/inventions.html":        ("","reading speaking","team","none",20,"history facts trivia technology"),
 "jeopardy/jeopardy.html":            ("","grammar vocabulary","team","setup",30,"buzzer categories quiz board"),
 "last-one-standing/last-one-standing.html": ("","vocabulary speaking","team","none",10,"elimination choose differently"),
 "leftright/leftright.html":          ("","speaking","whole-class","none",10,"luck chance warm-up pass"),
 "letter-battle/letter-battle.html":  ("","vocabulary","solo","none",20,"lexicon duel word battle waves charge bar"),
 "linking-park/linking-park.html":    ("A1 A2 B1 B2","writing reading","team","none",20,"connectors transitions discourse markers linking words paragraphs"),
 "mastermind/mastermind.html":        ("","vocabulary","team","none",15,"code breaking deduction colors pegs"),
 "minefield/minefield.html":          ("A1 A2 B1 B2","grammar","team","none",20,"tiles mines treasure steal swap"),
 "mistake-hunters/mistake-hunters.html": ("A1 A2 B1 B2 C1","grammar","team","none",25,"error correction find the mistake steal proofreading"),
 "orbit/orbit.html":                  ("","speaking","team","none",15,"four in a row marbles strategy"),
 "order-up/order-up.html":            ("","vocabulary reading","team","none",20,"ranking ordering sequence hard mode"),
 "perfect-fit/perfect-fit.html":      ("","vocabulary","team","none",15,"shapes slots timer race"),
 "problem-solvers/problem-solvers.html": ("","speaking","team","none",20,"creative solutions absurd problems pitching"),
 "record-breaker/record-breaker.html":("","listening speaking","team","none",15,"guess the number records estimation"),
 "resistance/resistance.html":        ("","speaking","team","none",30,"social deduction liar bluffing missions"),
 "ring-memory/ring-memory.html":      ("","vocabulary","team","none",10,"ring of gems memory pairs rotation"),
 "hangman/hangman.html":              ("","vocabulary","whole-class","setup",10,"save the cheese word guessing letters hangman spelling"),
 "scattergories/scattergories.html":  ("","vocabulary writing","team","none",15,"categories letters quick thinking"),
 "scrambler/scrambler.html":          ("A1 A2 B1 B2","grammar reading","team","none",20,"sentence order unscramble word order drag and drop"),
 "sentence-auction/sentence-auction.html": ("A1 A2 B1 B2","grammar","team","none",25,"bidding correct sentences error spotting money"),
 "song-word-race/song-word-race.html":("","listening speaking","team","none",15,"songs singing race music"),
 "sound-off/sound-off.html":          ("A1 A2 B1 B2","listening speaking","team","none",20,"minimal pairs pronunciation phonemes"),
 "bee/bee.html":                      ("A1 A2 B1 B2","listening","team","none",25,"spelling bee tournament dictation"),
 "stairs/stairs.html":                ("","grammar vocabulary","team","none",20,"progressive levels climb"),
 "stop-twist/stop-twist.html":        ("","vocabulary writing","team","none",15,"stop categories letters speed"),
 "adventure/adventure.html":          ("A2 B1","reading","whole-class","none",30,"the lost signal branching choose your own adventure sci-fi endings story"),
 "categories/categories.html":        ("A1 A2 B1 B2","vocabulary speaking","team","none",15,"think on your feet categories clock brainstorm"),
 "topten/topten.html":                ("","speaking","team","none",20,"ranking discussion opinions"),
 "toptwenty/toptwenty.html":          ("","speaking","team","none",20,"rank it ranking lists guessing trivia"),
 "trivia-teams/trivia-teams.html":    ("A1 A2 B1 B2","reading","team","none",25,"trivia badges general knowledge"),
 "truorfalse/truorfalse.html":        ("A1 A2 B1 B2","reading","team","none",15,"facts true false fact or fake"),
 "tictactoe/tictactoe.html":          ("","grammar speaking","team","setup",15,"tic tac toe boards strategy"),
 "unscramble/unscramble.html":        ("A1 A2 B1 B2","vocabulary","team","none",15,"anagram letters categories word scramble"),
 "vocab-toolkit/vocab-toolkit.html":  ("","vocabulary","whole-class","setup",20,"word list word search bingo anagram custom multi-activity"),
 "wave/wave.html":                    ("","speaking","team","none",10,"energy warm-up"),
 "wheel/wheel.html":                  ("A1 A2 B1 B2","speaking","whole-class","none",15,"spinner wheel of fortune random prizes"),
 "word-buzz/word-buzz.html":          ("A1 A2 B1 B2","vocabulary listening","team","none",15,"buzzer speed first to say"),
 "word-gap-game/word-gap-game.html":  ("A1 A2 B1 B2 C1","grammar vocabulary","team","none",20,"word gap cloze gap fill chips distractors focus mode fun mode"),
 "teacher-wordle/teacher-wordle.html":("A1 A2 B1 B2","vocabulary","solo","none",10,"word quest wordle guessing dictionary letters"),
 "wordsearch/wordsearch.html":        ("","vocabulary","whole-class","setup",15,"word search puzzle beat the clock custom words"),
}

TOOLS = {
 "teacher-dashboard/teacher-dashboard.html": ("","admin","teacher","none",0,"classes roll call grades reports attendance students observations"),
 "aura-tracker/aura-tracker.html":    ("","admin","whole-class","none",5,"behavior points vibes tracker"),
 "Dialog Practice/dialog-practice.html": ("A1 A2 B1 B2","listening speaking","whole-class","none",20,"dialog simulator tts conversations dialogues role play"),
 "before-after-writing/before-after-writing.html": ("A1 A2 B1 B2","writing","team","none",25,"editing revision improve paragraphs find mode"),
 "efl-classroom-toolkit/efl-classroom-toolkit.html": ("","admin","whole-class","none",5,"timer random picker groups noise class management"),
 "competition/competition.html":      ("","admin","team","setup",15,"league duels tournament scoring"),
 "dictation/dictation.html":          ("A1 A2 B1 B2","listening writing","solo","none",15,"dictation typing spelling tts"),
 "reading/reader.html":               ("A1 A2 B1 B2","reading","solo","none",25,"efl reader graded passages comprehension highlighting topics"),
 "first-class/first-class.html":      ("A1 A2 B1 B2","speaking","whole-class","none",40,"rules icebreaker start of term day one policies phones homework"),
 "ideadeck/ideadeck.html":            ("A1 A2 B1 B2","speaking","solo","none",20,"idea deck pitch presentation prompts"),
 "listening-cloze/listening-cloze.html": ("A1 A2 B1 B2","listening","whole-class","none",20,"gap fill cloze tts weak forms replay"),
 "pronunciation-trainer/pronunciation-trainer.html": ("A1 A2 B1 B2","speaking listening","whole-class","none",20,"phonemic chart ipa minimal pairs connected speech accent us uk"),
 "irregular/irregular.html":          ("A1 A2 B1","grammar","solo","none",10,"irregular verbs flashcards past participle"),
 "mad-libs-efl/mad-libs-efl.html":    ("A1 A2 B1 B2 C1","grammar writing","whole-class","none",15,"mad libs parts of speech silly stories nouns verbs adjectives"),
 "efl-oral-assessment/efl-oral-assessment.html": ("","assessment","teacher","none",0,"rubric oral scoring speaking assessment"),
 "placement-test.html":               ("","assessment","teacher","none",20,"placement interview levels new students starter"),
 "pop-quiz/pop-quiz.html":            ("A1 A2 B1 B2","grammar","team","none",15,"pop quiz generator grammarhub match fill unscramble"),
 "questions/questions.html":          ("A1 A2 B1 B2","speaking","whole-class","none",15,"question bank discussion conversation starters"),
 "efl-recipe-challenge/efl-recipe-challenge.html": ("A1 A2 B1","speaking writing","team","none",25,"recipe rumble food cooking ingredients pitch kitchen"),
 "reportcards/reportcards.html":      ("","assessment","teacher","none",0,"report cards grades comments student assessment"),
 "roleplay-spinner/roleplay-spinner.html": ("A1 A2 B1 B2","speaking","team","none",15,"improv scenarios role play situations"),
 "story-spark/story-spark.html":      ("A1 A2 B1 B2","writing","solo","none",25,"creative writing prompts character plot twist"),
 "thermometer/thermometer.html":      ("A1 A2 B1 B2","admin","whole-class","none",5,"english only l1 monitoring portuguese behavior"),
 "spinner/spinner.html":              ("","speaking","whole-class","none",10,"this or that would you rather dilemmas discussion"),
 "toefl-correction/toefl-correction.html": ("","assessment","teacher","none",5,"toefl itp score conversion calculator sections"),
 "writing-scaffold/writing-scaffold.html": ("A1 A2 B1 B2 C1","writing","solo","none",30,"sentence starters connectors word bank prompts"),
}

# files that exist on purpose but must never get a card
REDIRECTS_EXPECTED = True          # verified structurally by hubgen check
IGNORE = [
  "*/README.md",
  "tools/teacher-dashboard/teacher-dashboard-tests.html",   # test harness
  "games/future-projects/*",                                 # concepts, not shipped
]
# real files, reachable by nobody, that are stale copies superseded elsewhere
STALE = [
  "games/perfect-fit.html",                        # superseded by games/perfect-fit/perfect-fit.html
  "games/teacher-dashboard/teacher-dashboard.html",# old copy; live one is tools/
]
# real files, reachable by nobody, that look like finished games with no card
UNLISTED = [
  "games/battle-pets/battle-pets.html",
  "games/compass-quest/compass-quest.html",
  "games/whats-that/whats-that.html",
]

SKILL_SET = ["speaking","listening","reading","writing","grammar","vocabulary","admin","assessment"]
MODE_SET  = ["team","solo","whole-class","teacher"]
PREP_SET  = ["none","print","setup"]


def slug(p):
    base = os.path.splitext(os.path.basename(p))[0]
    d = os.path.dirname(p)
    return (d.split("/")[0] if d else base).lower().replace(" ", "-")


def cards_from(repo, cls, attr):
    soup = BeautifulSoup(open(os.path.join(ROOT, repo, "index.html")), "lxml")
    out = []
    for d in soup.select("." + cls):
        path = d.get("data-" + attr) or ""
        if not path:
            b = d.find("button") or d
            m = re.search(r"'([^']+)'", str(b.get("onclick") or d.get("onclick") or ""))
            path = m.group(1) if m else ""
        h, p, ic = d.find(["h3", "h4"]), d.find("p"), d.select_one(".icon")
        out.append(dict(
            path=path.replace("%20", " "),
            title=h.get_text(strip=True) if h else "",
            blurb=re.sub(r"\s+", " ", p.get_text(" ", strip=True)) if p else "",
            icon=ic.get_text(strip=True) if ic else "",
            legacy_kw=d.get("data-name", ""),
            featured="featured" in " ".join(d.get("class", [])),
        ))
    return out


def build_hub(hub, repo, cls, attr, meta):
    items = []
    for c in cards_from(repo, cls, attr):
        m = meta.get(c["path"])
        if m is None:
            raise SystemExit(f"no metadata authored for {hub}/{c['path']}")
        lv, sk, mode, prep, mins, kw = m
        assert mode in MODE_SET and prep in PREP_SET, c["path"]
        skills = sk.split()
        assert all(s in SKILL_SET for s in skills), c["path"]
        items.append(dict(
            id=slug(c["path"]), hub=hub, path=c["path"], title=c["title"],
            blurb=c["blurb"], icon=c["icon"], levels=lv.split(), skills=skills,
            mode=mode, prep=prep, minutes=mins,
            keywords=sorted(set(kw.split())), status="live",
            featured=c["featured"] or None,
        ))
    return items


def build_grammar():
    soup = BeautifulSoup(open(os.path.join(ROOT, "grammar", "index.html")), "lxml")
    items = []
    for card in soup.select(".topic-card"):
        lvl = card.select_one(".cefr-badge")
        h, p = card.find("h3"), card.find("p")
        level = lvl.get_text(strip=True).upper() if lvl else ""
        title = h.get_text(strip=True) if h else ""
        blurb = re.sub(r"\s+", " ", p.get_text(" ", strip=True)) if p else ""
        for a in card.select("a[href]"):
            href = a["href"]
            kind = "slides" if "_slides" in href else "activities"
            items.append(dict(
                id=os.path.splitext(os.path.basename(href))[0].replace("_", "-"),
                hub="grammar", path=href, title=f"{title} — {kind.title()}",
                blurb=blurb, icon="", levels=[level] if level else [],
                skills=["grammar"], mode="whole-class" if kind == "slides" else "solo",
                prep="none", minutes=25 if kind == "slides" else 20,
                keywords=sorted(set(re.findall(r"[a-z]+", (title + " " + blurb).lower()))),
                status="live", topic=title, kind=kind,
            ))
    return items


def build_vocab():
    src = open(os.path.join(ROOT, "vocab", "data", "manifest.js"), encoding="utf-8").read()
    items = []
    for lvl in re.finditer(r"id:\s*'(\w+)'.*?themes:\s*\[(.*?)\]", src, re.S):
        level = lvl.group(1).upper()
        for th in re.finditer(r"slug:\s*'([^']+)',\s*title:\s*'([^']+)'", lvl.group(2)):
            s, t = th.group(1), th.group(2).replace("\\u0026", "&")
            items.append(dict(
                id=f"vocab-{level.lower()}-{s}", hub="vocab",
                path=f"index.html#/{level.lower()}/{s}", title=f"{t} ({level})",
                blurb=f"{level} vocabulary set — study, games, flashcards and board mode.",
                icon="", levels=[level], skills=["vocabulary"], mode="whole-class",
                prep="none", minutes=20,
                keywords=sorted(set(re.findall(r"[a-z]+", t.lower()))) + ["vocabulary", "theme"],
                status="live",
            ))
    return items


def build_reviews():
    soup = BeautifulSoup(open(os.path.join(ROOT, "reviews", "index.html")), "lxml")
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.startswith("http") or h in seen or not h.lower().endswith((".pdf", ".html")):
            continue
        seen.add(h)
        name = os.path.splitext(os.path.basename(h))[0].replace("_", " ")
        cls = os.path.dirname(h).replace("-", " ").title()
        is_key = "key" in name.lower()
        is_game = h.lower().endswith(".html")
        items.append(dict(
            id=os.path.splitext(os.path.basename(h))[0].lower().replace("_", "-"),
            hub="reviews", path=h,
            title=name.replace(" - Key", " — Answer Key"),
            blurb=f"{cls} test review {'answer key' if is_key else 'game' if is_game else 'worksheet'}.",
            icon="", levels=[], skills=["grammar"],
            mode="team" if is_game else "solo",
            prep="none" if is_game else "print",
            minutes=25, keywords=sorted(set(re.findall(r"[a-z0-9]+", (name + " " + cls).lower()))),
            status="live", klass=cls, kind="key" if is_key else "game" if is_game else "review",
        ))
    return items


def build_worksheets():
    src = open(os.path.join(ROOT, "worksheets", "index.html"), encoding="utf-8").read()
    arr = re.search(r"const worksheets = \[(.*?)\n  \];", src, re.S).group(1)
    items = []
    for blk in re.finditer(r"\{(.*?)\}", arr, re.S):
        b = blk.group(1)
        g = lambda k: (re.search(k + r':\s*"([^"]*)"', b) or [None, ""])[1]
        topics = re.findall(r'"([^"]+)"', (re.search(r"topics:\s*\[(.*?)\]", b, re.S) or [None, ""])[1])
        items.append(dict(
            id=os.path.splitext(g("file"))[0].lower().replace(" ", "-").replace("_", "-"),
            hub="worksheets", path=g("file"), title=f'{g("class")} — {g("title")}',
            blurb="Printable worksheet: " + ", ".join(topics) + ".",
            icon="", levels=[], skills=["grammar"], mode="solo", prep="print",
            minutes=30, keywords=sorted(set(re.findall(r"[a-z]+", " ".join(topics).lower()))),
            status="live", klass=g("class"), date=g("date"),
        ))
    return items


def build_advanced():
    soup = BeautifulSoup(open(os.path.join(ROOT, "advanced", "index.html")), "lxml")
    items = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.startswith("http"):
            continue
        h = h.lstrip("./") or "index.html"
        head = a.find(["h3", "h2"])
        p = a.find("p")
        if not head:
            continue
        items.append(dict(
            id=os.path.splitext(os.path.basename(h.rstrip("/")))[0] or h.strip("/"),
            hub="advanced", path=h, title=head.get_text(strip=True),
            blurb=re.sub(r"\s+", " ", p.get_text(" ", strip=True)) if p else "",
            icon="", levels=["C1"], skills=["grammar"], mode="whole-class",
            prep="none", minutes=40,
            keywords=sorted(set(re.findall(r"[a-z]+", head.get_text(" ", strip=True).lower()))),
            status="live",
        ))
    return items


def build_advanced_subpages():
    """TOEFL error-correction pages and the C1 vocabulary themes, both one level down."""
    items = []
    tdir = os.path.join(ROOT, "advanced", "toefl")
    for f in sorted(os.listdir(tdir)):
        if not f.endswith(".html") or f == "index.html":
            continue
        src = open(os.path.join(tdir, f), encoding="utf-8", errors="replace").read()
        t = re.search(r"<title>([^<]*)</title>", src)
        title = (t.group(1).split("·")[0].strip() if t else f)
        is_quiz = f == "quiz.html"
        items.append(dict(
            id="toefl-" + os.path.splitext(f)[0], hub="advanced", path=f"toefl/{f}",
            title=("TOEFL Error Correction — " + title),
            blurb=("Build a custom quiz across every error family."
                   if is_quiz else
                   f"Thirty error-correction exercises on {title.lower()}, on screen plus a printable worksheet and key."),
            icon="", levels=["C1"], skills=["grammar"], mode="solo",
            prep="none" if is_quiz else "print", minutes=30,
            keywords=sorted(set(re.findall(r"[a-z]+", title.lower()))) + ["toefl", "error", "correction"],
            status="live", section="toefl",
        ))
    vsrc = open(os.path.join(ROOT, "advanced", "vocab", "index.html"), encoding="utf-8").read()
    for m in re.finditer(r"slug:\s*'([^']+)'\s*,\s*title:\s*'([^']+)'", vsrc):
        s, t = m.group(1), m.group(2)
        items.append(dict(
            id="c1-vocab-" + s, hub="advanced", path=f"vocab/theme.html#/{s}",
            title=f"C1 Vocabulary — {t}",
            blurb="Forty C1 items with collocations, usage notes, word families and a Portuguese-speaker pitfall.",
            icon="", levels=["C1"], skills=["vocabulary"], mode="whole-class",
            prep="none", minutes=25,
            keywords=sorted(set(re.findall(r"[a-z]+", t.lower()))) + ["c1", "vocabulary", "theme"],
            status="live", section="vocab",
        ))
    return items


def build_root():
    soup = BeautifulSoup(open(os.path.join(ROOT, "arschul.github.io", "index.html")), "lxml")
    items = []
    for a in soup.select("a.card, a.featured"):
        h2, p = a.find("h2"), a.find("p")
        if not h2:
            continue
        items.append(dict(
            id="hub-" + h2.get_text(strip=True).lower().replace(" ", "-"),
            hub="root", path=a["href"], title=h2.get_text(strip=True),
            blurb=re.sub(r"\s+", " ", p.get_text(" ", strip=True)) if p else "",
            icon="", levels=[], skills=[], mode="teacher", prep="none", minutes=0,
            keywords=[], status="live",
            featured="featured" in " ".join(a.get("class", [])) or None,
        ))
    return items


def main():
    items = []
    items += build_root()
    items += build_hub("games", "games", "game-card", "game", GAMES)
    items += build_hub("tools", "tools", "link-card", "tool", TOOLS)
    items += build_grammar()
    items += build_vocab()
    items += build_reviews()
    items += build_worksheets()
    items += build_advanced()
    items += build_advanced_subpages()

    for it in items:                       # drop empty optionals
        for k in [k for k, v in list(it.items()) if v is None]:
            del it[k]

    seen = {}
    for it in items:
        key = (it["hub"], it["id"])
        if key in seen:
            it["id"] = it["id"] + "-" + os.path.splitext(os.path.basename(it["path"]))[0][:8]
        seen[key] = 1

    catalog = dict(
        version=1,
        generated_by="build_catalog.py (Stage 0)",
        vocabularies=dict(levels=["A1", "A2", "B1", "B2", "C1"], skills=SKILL_SET,
                          modes=MODE_SET, preps=PREP_SET,
                          minutes_buckets=[[0, 9, "<10 min"], [10, 25, "10–25 min"], [26, 999, "25+ min"]],
                          notes="levels:[] means level-agnostic — matches every level filter."),
        hubs=dict(
            root=dict(repo="arschul.github.io", url="https://arschul.github.io/", title="Classroom Hub"),
            games=dict(repo="games", url="https://arschul.github.io/games/", title="Game Hub"),
            tools=dict(repo="tools", url="https://arschul.github.io/tools/", title="Tool Hub"),
            grammar=dict(repo="grammar", url="https://arschul.github.io/grammar/", title="Grammar Hub"),
            advanced=dict(repo="advanced", url="https://arschul.github.io/advanced/", title="Advanced Hub"),
            reviews=dict(repo="reviews", url="https://arschul.github.io/reviews/", title="Review Hub"),
            worksheets=dict(repo="worksheets", url="https://arschul.github.io/worksheets/", title="Worksheets"),
            vocab=dict(repo="vocab", url="https://arschul.github.io/vocab/", title="Vocab Hub"),
        ),
        ignore=IGNORE,
        stale=STALE,
        unlisted=UNLISTED,
        items=items,
    )
    json.dump(catalog, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {OUT}: {len(items)} items")
    from collections import Counter
    print(Counter(i["hub"] for i in items))


if __name__ == "__main__":
    main()
