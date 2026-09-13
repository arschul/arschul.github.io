/* leaf.v1.js — theme continuity for the ~265 pages below the hub indexes.
 *
 * Leaf pages are bespoke: ten different localStorage keys between them and 158
 * with no theme concept at all. This does not restyle anything. It only makes the
 * theme choice follow you off the hub, and rebinds an existing toggle to the
 * shared key. A page with no toggle simply inherits the theme and shows none.
 *
 * Deferred, so it runs after the page's own inline theme code and wins without
 * anyone having to edit 265 files by hand.
 */
(function () {
  "use strict";
  var KEY = "arschul:theme";
  var LEGACY = ["hub-theme", "theme", "gh-theme", "adv-theme", "reviews-theme",
                "worksheets-theme", "vocab-theme", "toefl-theme", "stc-theme",
                "wheelquest-theme", "wba-theme", "airtight-theme", "efl-reader-theme"];
  var ORDER = ["dark", "light", "system"];
  var FACE = { dark: "\u{1F319}", light: "\u2600\uFE0F", system: "\u{1F5A5}\uFE0F" };
  var LABEL = { dark: "Dark theme", light: "Light theme", system: "Match system theme" };

  function read() {
    try {
      var v = localStorage.getItem(KEY);
      if (v) return v;
      for (var i = 0; i < LEGACY.length; i++) {
        var o = localStorage.getItem(LEGACY[i]);
        if (o === "light" || o === "dark") { write(o); return o; }
      }
    } catch (e) {}
    return "dark";
  }
  function write(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function effective(v) {
    return v !== "system" ? v
      : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }
  function paint(v) {
    document.documentElement.setAttribute("data-theme", effective(v));
    var b = document.querySelectorAll("#theme-btn, .theme-toggle, .theme-btn, [data-hub-theme-toggle]");
    for (var i = 0; i < b.length; i++) {
      if (!b[i].children.length) b[i].textContent = FACE[v] || FACE.dark;
      b[i].title = LABEL[v] || LABEL.dark;
      b[i].setAttribute("aria-label", LABEL[v] || LABEL.dark);
    }
  }
  function cycle() {
    var n = ORDER[(ORDER.indexOf(read()) + 1) % ORDER.length];
    write(n); paint(n); return n;
  }
  // the page's own inline toggleTheme was defined during parsing; this replaces it,
  // and onclick="toggleTheme()" resolves from window at click time, so it just works
  window.toggleTheme = cycle;
  window.hub = window.hub || {};
  window.hub.theme = { get: read, set: function (v) { write(v); paint(v); }, cycle: cycle };
  try {
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      if (read() === "system") paint("system");
    });
  } catch (e) {}
  addEventListener("storage", function (e) { if (e.key === KEY) paint(read()); });
  paint(read());
})();
