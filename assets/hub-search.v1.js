/* hub-search.v1.js — cross-hub search, Classroom Hub only.
 *
 * Loaded only by the root hub, so the other seven pay nothing for it.
 * The index (~90 kB, ~15 kB gzipped) is fetched on the first keystroke, not on
 * page load: opening the Classroom Hub to click through to a game should not
 * wait on a file it may never use.
 */
(function () {
  "use strict";

  var INDEX_URL = "https://arschul.github.io/data/search-index.json";
  var HUB_NAME = {
    games: "Game Hub", tools: "Tool Hub", grammar: "Grammar Hub",
    advanced: "Advanced Hub", reviews: "Review Hub",
    worksheets: "Worksheets", vocab: "Vocab Hub"
  };
  var HUB_ORDER = ["grammar", "games", "tools", "worksheets", "reviews", "vocab", "advanced"];
  var PER_HUB = 6;

  var items = null, loading = null, active = -1;

  function load() {
    if (items) return Promise.resolve(items);
    if (loading) return loading;
    loading = fetch(INDEX_URL)
      .then(function (r) {
        if (!r.ok) throw new Error("index " + r.status);
        return r.json();
      })
      .then(function (d) { items = d.items || []; return items; });
    return loading;
  }

  function score(it, terms) {
    var title = it.t.toLowerCase();
    var hay = title + " " + (it.k || "");
    var s = 0;
    for (var i = 0; i < terms.length; i++) {
      var t = terms[i];
      if (hay.indexOf(t) === -1) return 0;            // every term must appear somewhere
      if (title.indexOf(t) === 0) s += 12;
      else if (title.indexOf(t) > -1) s += 8;
      else s += 2;
    }
    if (title === terms.join(" ")) s += 20;
    return s;
  }

  function group(hits) {
    var by = {};
    hits.forEach(function (h) { (by[h.it.h] = by[h.it.h] || []).push(h); });
    return HUB_ORDER.filter(function (k) { return by[k]; }).map(function (k) {
      return { hub: k, hits: by[k] };
    });
  }

  function render(panel, q) {
    var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) { panel.innerHTML = ""; panel.hidden = true; return; }

    var hits = [];
    for (var i = 0; i < items.length; i++) {
      var s = score(items[i], terms);
      if (s) hits.push({ it: items[i], s: s });
    }
    hits.sort(function (a, b) { return b.s - a.s || a.it.t.localeCompare(b.it.t); });

    panel.hidden = false;
    active = -1;

    if (!hits.length) {
      panel.innerHTML = '<p class="xhub-none">Nothing matches “' +
        q.replace(/</g, "&lt;") + '”. Try a grammar topic, a game name, or a class code.</p>';
      return;
    }

    var html = ['<p class="xhub-total">' + hits.length + " result" + (hits.length === 1 ? "" : "s") + "</p>"];
    group(hits).forEach(function (g) {
      html.push('<section class="xhub-group"><h3 class="xhub-group__name">' +
        (HUB_NAME[g.hub] || g.hub) + ' <span class="xhub-group__count">' + g.hits.length + "</span></h3><ul class=\"xhub-list\">");
      g.hits.slice(0, PER_HUB).forEach(function (h) {
        var chips = (h.it.lv || []).map(function (l) {
          return '<span class="hub-chip hub-chip--level">' + l + "</span>";
        }).join("");
        html.push('<li><a class="xhub-hit" href="' + h.it.u + '">' +
          '<span class="xhub-hit__title">' + h.it.t.replace(/</g, "&lt;") + "</span>" +
          '<span class="xhub-hit__meta">' + chips + "</span></a></li>");
      });
      if (g.hits.length > PER_HUB) {
        html.push('<li class="xhub-more">' + (g.hits.length - PER_HUB) + " more in " + (HUB_NAME[g.hub] || g.hub) + "</li>");
      }
      html.push("</ul></section>");
    });
    panel.innerHTML = html.join("");
  }

  function init() {
    var input = document.querySelector(".xhub-search");
    var panel = document.querySelector(".xhub-results");
    var cards = document.querySelector(".xhub-hidden-when-searching");
    if (!input || !panel) return;

    var pending = null;

    function run() {
      var q = input.value.trim();
      if (cards) cards.hidden = !!q;
      if (!q) { panel.innerHTML = ""; panel.hidden = true; return; }
      load().then(function () { render(panel, q); }).catch(function () {
        panel.hidden = false;
        panel.innerHTML = '<p class="xhub-none">Search is unavailable right now — the hub links below still work.</p>';
      });
    }

    input.addEventListener("input", function () {
      clearTimeout(pending);
      pending = setTimeout(run, 90);
    });

    // warm the index as soon as the box is focused, so the first keystroke is instant
    input.addEventListener("focus", function () { load().catch(function () {}); }, { once: true });

    input.addEventListener("keydown", function (e) {
      var hits = panel.querySelectorAll(".xhub-hit");
      if (e.key === "Enter" && hits.length) {
        e.preventDefault();
        (hits[active > -1 ? active : 0]).click();
      } else if (e.key === "ArrowDown" && hits.length) {
        e.preventDefault();
        active = Math.min(active + 1, hits.length - 1);
        move(hits);
      } else if (e.key === "ArrowUp" && hits.length) {
        e.preventDefault();
        active = Math.max(active - 1, 0);
        move(hits);
      } else if (e.key === "Escape") {
        input.value = "";
        run();
      }
    });

    function move(hits) {
      for (var i = 0; i < hits.length; i++) hits[i].classList.toggle("is-active", i === active);
      if (hits[active] && hits[active].scrollIntoView) hits[active].scrollIntoView({ block: "nearest" });
    }

    document.addEventListener("keydown", function (e) {
      var tag = (document.activeElement && document.activeElement.tagName) || "";
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") {
        e.preventDefault();
        input.focus();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
