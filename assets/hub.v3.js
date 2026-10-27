/* hub.v2.js — shared behavior for the arschul hub ecosystem.
 *
 * v2 = v1 theme control + the card filter/search engine.
 * v1 stays live and unmodified; hubs opt in by bumping their asset link.
 */
(function () {
  "use strict";

  /* ------------------------------------------------------------ theme */

  var KEY = "arschul:theme";
  var LEGACY = ["hub-theme", "theme", "gh-theme", "adv-theme", "reviews-theme", "worksheets-theme"];
  var ORDER = ["dark", "light", "system"];
  var FACE = { dark: "\u{1F319}", light: "\u2600\uFE0F", system: "\u{1F5A5}\uFE0F" };
  var LABEL = { dark: "Dark theme", light: "Light theme", system: "Match system theme" };

  function read() {
    try {
      var v = localStorage.getItem(KEY);
      if (v) return v;
      for (var i = 0; i < LEGACY.length; i++) {
        var old = localStorage.getItem(LEGACY[i]);
        if (old === "light" || old === "dark") { write(old); return old; }
      }
    } catch (e) {}
    return "dark";
  }

  function write(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }

  function effective(v) {
    if (v !== "system") return v;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function paint(v) {
    document.documentElement.setAttribute("data-theme", effective(v));
    var btns = document.querySelectorAll("#theme-btn, [data-hub-theme-toggle], .hub-theme-toggle, .theme-toggle");
    for (var i = 0; i < btns.length; i++) {
      var b = btns[i];
      // Game Hub and Tool Hub swap two child <span>s via CSS — leave their markup alone.
      if (!b.children.length) b.textContent = FACE[v] || FACE.dark;
      b.title = LABEL[v] || LABEL.dark;
      b.setAttribute("aria-label", LABEL[v] || LABEL.dark);
    }
  }

  function cycle() {
    var next = ORDER[(ORDER.indexOf(read()) + 1) % ORDER.length];
    write(next);
    paint(next);
    return next;
  }

  window.toggleTheme = cycle;
  window.hub = window.hub || {};
  window.hub.theme = { get: read, set: function (v) { write(v); paint(v); }, cycle: cycle };

  try {
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      if (read() === "system") paint("system");
    });
  } catch (e) {}
  addEventListener("storage", function (e) { if (e.key === KEY) paint(read()); });

  /* ----------------------------------------------------------- filters */

  var FACETS = [
    { key: "new",    attr: "data-new",    name: "New", single: true },
    { key: "levels", attr: "data-levels", name: "Level" },
    { key: "skills", attr: "data-skills", name: "Skill" },
    { key: "mode",   attr: "data-mode",   name: "Mode" },
    { key: "prep",   attr: "data-prep",   name: "Prep" },
    { key: "time",   attr: "data-time",   name: "Time" }
  ];
  var TIME_LABEL = { short: "under 10 min", medium: "10–25 min", long: "25+ min" };
  var ANY = "__any__";
  var PREP_LABEL = { none: "no prep", print: "printing", setup: "setup" };
  var LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1"];
  var NEW_DAYS = 14;
  var UPDATED_DAYS = 14;

  function values(cards, attr) {
    var seen = {};
    for (var i = 0; i < cards.length; i++) {
      var raw = (cards[i].getAttribute(attr) || "").trim();
      if (!raw) continue;
      var parts = raw.split(/\s+/);
      for (var j = 0; j < parts.length; j++) seen[parts[j]] = 1;
    }
    var out = Object.keys(seen);
    if (attr === "data-levels") {
      out.sort(function (a, b) { return LEVEL_ORDER.indexOf(a) - LEVEL_ORDER.indexOf(b); });
      // level-agnostic cards (teacher supplies the content) get their own chip
      for (var k = 0; k < cards.length; k++) {
        if (!(cards[k].getAttribute(attr) || "").trim()) { out.push(ANY); break; }
      }
    } else if (attr === "data-time") {
      var o = ["short", "medium", "long"];
      out.sort(function (a, b) { return o.indexOf(a) - o.indexOf(b); });
    } else {
      out.sort();
    }
    return out;
  }

  function label(key, v) {
    if (key === "new") return "added in the last 2 weeks";
    if (v === ANY) return "any level";
    if (key === "time") return TIME_LABEL[v] || v;
    if (key === "prep") return PREP_LABEL[v] || v;
    return v;
  }

  function readHash() {
    var state = {};
    var h = location.hash.replace(/^#/, "");
    if (!h) return state;
    h.split("&").forEach(function (pair) {
      var kv = pair.split("=");
      if (kv.length !== 2) return;
      var k = decodeURIComponent(kv[0]);
      if (k === "sort") return;
      if (k === "q") { state.q = decodeURIComponent(kv[1].replace(/\+/g, " ")); return; }
      state[k] = decodeURIComponent(kv[1]).split(",").filter(Boolean);
    });
    return state;
  }

  function writeHash(state) {
    var parts = [];
    FACETS.forEach(function (f) {
      if (state[f.key] && state[f.key].length) {
        parts.push(encodeURIComponent(f.key) + "=" + state[f.key].map(encodeURIComponent).join(","));
      }
    });
    if (state.q) parts.push("q=" + encodeURIComponent(state.q));
    var next = parts.length ? "#" + parts.join("&") : " ";
    history.replaceState(null, "", next === " " ? location.pathname + location.search : next);
  }

  function initFilters() {
    var grid = document.querySelector(".hub-grid");
    if (!grid) return;
    var cards = [].slice.call(grid.querySelectorAll(".hub-card"));
    if (!cards.length) return;

    var toolbar = document.querySelector(".hub-toolbar");
    var search = document.querySelector(".hub-search");
    var empty = document.querySelector(".hub-empty");
    var count = document.querySelector(".hub-count");
    var clear = document.querySelector(".hub-clear");
    var state = readHash();

    // "new" = data-added (YYYY-MM-DD, from the catalog) within NEW_DAYS of today;
    // "updated" = data-updated within UPDATED_DAYS, for cards that are not already new.
    // Computed here so badges and shelves expire on their own without a rebuild.
    var now = new Date();
    var today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    function recent(c, attr, days) {
      var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(c.getAttribute(attr) || "");
      if (!m) return false;
      var age = (today - Date.UTC(+m[1], +m[2] - 1, +m[3])) / 864e5;
      return age >= 0 && age <= days;
    }
    function addBadge(c, cls, text) {
      var badge = document.createElement("span");
      badge.className = cls;
      badge.textContent = text;
      c.insertBefore(badge, c.firstChild);
    }
    var newCount = 0, updatedCount = 0;
    cards.forEach(function (c, idx) {
      c.setAttribute("data-order", idx);
      if (recent(c, "data-added", NEW_DAYS)) {
        c.setAttribute("data-new", "yes");
        addBadge(c, "hub-new-badge", "New");
        newCount++;
      } else if (recent(c, "data-updated", UPDATED_DAYS)) {
        c.setAttribute("data-recent-update", "yes");
        addBadge(c, "hub-new-badge hub-new-badge--updated", "Updated");
        updatedCount++;
      }
    });

    // poster hubs get streaming-style shelves above the toolbar (hidden while filtering)
    var shelves = [];
    function buildShelf(label, titleHtml, flag, dateAttr) {
      var shelf = document.createElement("section");
      shelf.className = "hub-shelf";
      shelf.setAttribute("aria-label", label);
      var h = document.createElement("h2");
      h.className = "hub-shelf__title";
      h.innerHTML = titleHtml;
      var shelfRow = document.createElement("div");
      shelfRow.className = "hub-shelf__row";
      cards.filter(function (c) { return c.hasAttribute(flag); })
        .sort(function (a, b) { return (b.getAttribute(dateAttr) || "").localeCompare(a.getAttribute(dateAttr) || ""); })
        .forEach(function (c) {
          var k = c.cloneNode(true);
          k.removeAttribute("data-id");
          var img = k.querySelector("img");
          if (img) img.loading = "eager";
          shelfRow.appendChild(k);
        });
      // < > buttons instead of a scrollbar (swipe/trackpad still work)
      var track = document.createElement("div");
      track.className = "hub-shelf__track";
      function arrow(dir) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "hub-shelf__nav hub-shelf__nav--" + (dir < 0 ? "prev" : "next");
        b.setAttribute("aria-label", dir < 0 ? "Previous games" : "Next games");
        b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' +
          (dir < 0 ? "M15 4l-8 8 8 8" : "M9 4l8 8-8 8") + '"/></svg>';
        b.addEventListener("click", function () {
          var step = Math.max(shelfRow.clientWidth * 0.9, 200);
          var smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          shelfRow.scrollBy({ left: dir * step, behavior: smooth ? "smooth" : "auto" });
        });
        return b;
      }
      var prevBtn = arrow(-1), nextBtn = arrow(1);
      function syncArrows() {
        var max = shelfRow.scrollWidth - shelfRow.clientWidth;
        var atStart = shelfRow.scrollLeft <= 8, atEnd = shelfRow.scrollLeft >= max - 8;
        prevBtn.hidden = atStart || max <= 8;
        nextBtn.hidden = atEnd || max <= 8;
        track.classList.toggle("is-start", atStart);
        track.classList.toggle("is-end", atEnd || max <= 8);
      }
      shelfRow.addEventListener("scroll", syncArrows, { passive: true });
      window.addEventListener("resize", syncArrows);
      track.appendChild(prevBtn);
      track.appendChild(shelfRow);
      track.appendChild(nextBtn);
      shelf.appendChild(h);
      shelf.appendChild(track);
      var anchor = toolbar || grid;
      anchor.parentNode.insertBefore(shelf, anchor);
      syncArrows();
      Array.prototype.forEach.call(shelfRow.querySelectorAll("img"), function (im) {
        if (!im.complete) im.addEventListener("load", syncArrows);
      });
      shelves.push(shelf);
    }
    if (grid.classList.contains("hub-grid--posters")) {
      if (newCount) buildShelf("New games", "<span>Latest</span> Games", "data-new", "data-added");
      if (updatedCount) buildShelf("Recently updated games", "Recently <span>Updated</span>", "data-recent-update", "data-updated");
    }

    function sortCards(newFirst) {
      var sorted = cards.slice().sort(function (a, b) {
        if (newFirst) {
          var fa = a.classList.contains("is-featured"), fb = b.classList.contains("is-featured");
          if (fa !== fb) return fa ? -1 : 1;
          var na = a.hasAttribute("data-new"), nb = b.hasAttribute("data-new");
          if (na !== nb) return na ? -1 : 1;
        }
        return a.getAttribute("data-order") - b.getAttribute("data-order");
      });
      sorted.forEach(function (c) { grid.appendChild(c); });
    }

    // build chip rows for every facet that actually has more than one value
    var row = toolbar && toolbar.querySelector(".hub-toolbar__row--facets");
    if (row) {
      FACETS.forEach(function (f) {
        var vals = values(cards, f.attr);
        if (vals.length < (f.single ? 1 : 2)) return;
        var wrap = document.createElement("div");
        wrap.className = "hub-facet";
        var nm = document.createElement("span");
        nm.className = "hub-facet__name";
        nm.textContent = f.name;
        wrap.appendChild(nm);
        vals.forEach(function (v) {
          var b = document.createElement("button");
          b.type = "button";
          b.className = "hub-filter";
          b.textContent = label(f.key, v);
          b.setAttribute("data-facet", f.key);
          b.setAttribute("data-value", v);
          b.setAttribute("aria-pressed", String(!!(state[f.key] && state[f.key].indexOf(v) > -1)));
          b.addEventListener("click", function () {
            var on = b.getAttribute("aria-pressed") === "true";
            b.setAttribute("aria-pressed", String(!on));
            state[f.key] = state[f.key] || [];
            state[f.key] = on
              ? state[f.key].filter(function (x) { return x !== v; })
              : state[f.key].concat([v]);
            apply();
          });
          wrap.appendChild(b);
        });
        row.appendChild(wrap);
      });
    }

    if (row && newCount) {
      var NF_KEY = "arschul:newFirst";
      var nf = false;
      try { nf = localStorage.getItem(NF_KEY) === "1"; } catch (e) {}
      var tog = document.createElement("button");
      tog.type = "button";
      tog.className = "hub-filter hub-sort-toggle";
      tog.textContent = "\u2195 New first";
      tog.title = "Show games added in the last 2 weeks at the top";
      tog.setAttribute("aria-pressed", String(nf));
      tog.addEventListener("click", function () {
        nf = tog.getAttribute("aria-pressed") !== "true";
        tog.setAttribute("aria-pressed", String(nf));
        try { localStorage.setItem(NF_KEY, nf ? "1" : "0"); } catch (e) {}
        sortCards(nf);
      });
      var first = row.querySelector(".hub-facet");
      if (first) first.appendChild(tog); else row.insertBefore(tog, row.firstChild);
      if (nf) sortCards(true);
    }

    if (search && state.q) search.value = state.q;

    function matches(card) {
      for (var i = 0; i < FACETS.length; i++) {
        var f = FACETS[i];
        var want = state[f.key];
        if (!want || !want.length) continue;
        var have = (card.getAttribute(f.attr) || "").split(/\s+/).filter(Boolean);
        // a card with no levels is level-agnostic: it answers to the "any level"
        // chip only, so picking B1 no longer returns almost the whole hub
        if (f.key === "levels" && !have.length) have = [ANY];
        var hit = want.some(function (w) { return have.indexOf(w) > -1; });
        if (!hit) return false;
      }
      var q = (state.q || "").trim().toLowerCase();
      if (q) {
        var hay = (card.getAttribute("data-search") || "") + " " + card.textContent.toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    }

    function apply() {
      var shown = 0;
      cards.forEach(function (c) {
        var ok = matches(c);
        c.hidden = !ok;
        if (ok) shown++;
      });
      if (count) {
        count.textContent = shown === cards.length
          ? cards.length + " items"
          : shown + " of " + cards.length;
      }
      if (empty) empty.hidden = shown !== 0;
      var any = !!(state.q && state.q.trim()) || FACETS.some(function (f) {
        return state[f.key] && state[f.key].length;
      });
      if (clear) clear.hidden = !any;
      shelves.forEach(function (sh) { sh.hidden = any; });
      writeHash(state);
    }

    if (search) {
      search.addEventListener("input", function () { state.q = search.value; apply(); });
    }
    if (clear) {
      clear.addEventListener("click", function () {
        state = {};
        if (search) search.value = "";
        [].forEach.call(document.querySelectorAll(".hub-filter[data-facet]"), function (b) {
          b.setAttribute("aria-pressed", "false");
        });
        apply();
        if (search) search.focus();
      });
    }

    document.addEventListener("keydown", function (e) {
      var tag = (document.activeElement && document.activeElement.tagName) || "";
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") {
        e.preventDefault();
        if (search) search.focus();
      } else if (e.key === "Escape" && document.activeElement === search) {
        state.q = "";
        search.value = "";
        apply();
      }
    });

    apply();
  }

  function boot() { paint(read()); initFilters(); }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
