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
    { key: "levels", attr: "data-levels", name: "Level" },
    { key: "skills", attr: "data-skills", name: "Skill" },
    { key: "mode",   attr: "data-mode",   name: "Mode" },
    { key: "prep",   attr: "data-prep",   name: "Prep" },
    { key: "time",   attr: "data-time",   name: "Time" }
  ];
  var TIME_LABEL = { short: "under 10 min", medium: "10–25 min", long: "25+ min" };
  var PREP_LABEL = { none: "no prep", print: "printing", setup: "setup" };
  var LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1"];

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
    } else if (attr === "data-time") {
      var o = ["short", "medium", "long"];
      out.sort(function (a, b) { return o.indexOf(a) - o.indexOf(b); });
    } else {
      out.sort();
    }
    return out;
  }

  function label(key, v) {
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

    // build chip rows for every facet that actually has more than one value
    var row = toolbar && toolbar.querySelector(".hub-toolbar__row--facets");
    if (row) {
      FACETS.forEach(function (f) {
        var vals = values(cards, f.attr);
        if (vals.length < 2) return;
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

    if (search && state.q) search.value = state.q;

    function matches(card) {
      for (var i = 0; i < FACETS.length; i++) {
        var f = FACETS[i];
        var want = state[f.key];
        if (!want || !want.length) continue;
        var have = (card.getAttribute(f.attr) || "").split(/\s+/).filter(Boolean);
        // levels:[] on a card means level-agnostic — it matches every level filter
        if (f.key === "levels" && !have.length) continue;
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
      writeHash(state);
    }

    if (search) {
      search.addEventListener("input", function () { state.q = search.value; apply(); });
    }
    if (clear) {
      clear.addEventListener("click", function () {
        state = {};
        if (search) search.value = "";
        [].forEach.call(document.querySelectorAll(".hub-filter"), function (b) {
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
