/* hub.v1.js — shared behavior for the arschul hub ecosystem.
 *
 * Stage 1 scope: one theme state for all eight hubs.
 * Stage 2 adds the filter/search engine below the theme block.
 *
 * All hubs are served from arschul.github.io, so they share one localStorage
 * origin. Before this file, six different keys meant the theme reset every time
 * you crossed hubs.
 */
(function () {
  "use strict";

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
    return "dark";                                   // projector default
  }

  function write(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }

  function effective(v) {
    if (v !== "system") return v;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function paint(v) {
    document.documentElement.setAttribute("data-theme", effective(v));
    var btns = document.querySelectorAll("#theme-btn, [data-hub-theme-toggle], .hub-theme-toggle");
    for (var i = 0; i < btns.length; i++) {
      btns[i].textContent = FACE[v] || FACE.dark;
      btns[i].title = LABEL[v] || LABEL.dark;
      btns[i].setAttribute("aria-label", LABEL[v] || LABEL.dark);
    }
  }

  function cycle() {
    var next = ORDER[(ORDER.indexOf(read()) + 1) % ORDER.length];
    write(next);
    paint(next);
    return next;
  }

  // Hubs still carry onclick="toggleTheme()" in their markup; keep that contract.
  window.toggleTheme = cycle;
  window.hub = window.hub || {};
  window.hub.theme = { get: read, set: function (v) { write(v); paint(v); }, cycle: cycle };

  // Follow the OS only while the user has chosen "system".
  try {
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      if (read() === "system") paint("system");
    });
  } catch (e) {}

  // A second tab changing the theme should not leave this one out of step.
  addEventListener("storage", function (e) { if (e.key === KEY) paint(read()); });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { paint(read()); });
  } else {
    paint(read());
  }
})();
