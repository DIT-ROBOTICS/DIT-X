/*
 * Brand theme for Mermaid diagrams.
 *
 * Material for MkDocs lazy-loads Mermaid on pages that contain a diagram and
 * calls mermaid.initialize() with its own themeCSS, which colours everything
 * through --md-mermaid-* custom properties (set per colour scheme in
 * stylesheets/dit.css, so diagrams follow the light/dark toggle live).
 *
 * This script runs before Material's bundle starts mounting components. It
 * watches the global `mermaid` binding, and when Mermaid arrives it wraps
 * initialize() to merge our layout, font and shape settings on top of
 * Material's configuration. Material's lazy loading is left untouched.
 */
(function () {
  "use strict";

  var FONT =
    '"Inter", "PingFang TC", "Noto Sans CJK TC", "Noto Sans TC", ' +
    '"Microsoft JhengHei", sans-serif';

  // Injected into every diagram's stylesheet after Material's rules.
  var EXTRA_CSS = [
    // Rounded, hairline nodes.
    ".node rect, .node polygon, .node path, .node circle { stroke-width: 1px; }",
    ".node rect { rx: 10px; ry: 10px; }",
    ".nodeLabel, .nodeLabel p { font-weight: 500; line-height: 1.45; }",
    ".nodeLabel small { font-weight: 400; opacity: 0.7; }",
    // Subgraphs read as soft panels, not boxes.
    ".cluster rect { rx: 14px; ry: 14px; stroke-width: 1px;" +
      " fill: var(--dit-mermaid-cluster-bg) !important;" +
      " stroke: var(--dit-mermaid-cluster-border) !important; }",
    ".cluster .nodeLabel, .cluster span, .cluster-label span {" +
      " color: var(--dit-mermaid-cluster-fg) !important; font-weight: 600;" +
      " font-size: 0.9em; letter-spacing: 0.02em; }",
    // Lighter edges and pill-shaped edge labels.
    ".flowchart-link, .edgePath .path { stroke-width: 1.4px; }",
    // Edge labels: no font-size/padding changes here, Mermaid measures the
    // text before this CSS applies and would clip it.
    ".edgeLabel, .edgeLabel p { color: var(--md-default-fg-color--light) !important; }",
    // Mermaid paints a half-transparent .labelBkg behind the label that
    // peeks out as a 1px frame; Material already paints the label itself.
    ".labelBkg { background-color: transparent !important; }",
    // Sequence diagrams.
    "rect.actor { rx: 10px; ry: 10px; stroke-width: 1px; }",
    "text.actor > tspan { font-weight: 600; }",
    ".note { rx: 8px; ry: 8px; stroke-width: 1px; }",
    ".actor-line { stroke-dasharray: 3 4; }",
    ".loopLine { stroke-width: 1px; stroke-dasharray: 4 3; }",
    ".labelBox { stroke-width: 0; }",
    ".messageLine0, .messageLine1 { stroke-width: 1.4px; }",
  ].join("\n");

  var CONFIG = {
    theme: "base",
    fontFamily: FONT,
    themeVariables: {
      fontFamily: FONT,
      fontSize: "15px",
      primaryColor: "#e6f9fd",
      primaryBorderColor: "#7fd3e6",
      primaryTextColor: "#1d2130",
      secondaryColor: "#f3ecff",
      tertiaryColor: "#fdeef8",
      lineColor: "#8b92a5",
      noteBkgColor: "#fdf4ff",
      noteBorderColor: "#f0abfc",
    },
    flowchart: {
      curve: "basis",
      padding: 16,
      nodeSpacing: 36,
      rankSpacing: 52,
      diagramPadding: 8,
      wrappingWidth: 360,
    },
    sequence: {
      actorMargin: 64,
      boxMargin: 12,
      noteMargin: 12,
      messageMargin: 40,
      mirrorActors: false,
    },
  };

  function merge(base, extra) {
    var out = {};
    var key;
    for (key in base || {}) out[key] = base[key];
    for (key in extra) out[key] = extra[key];
    return out;
  }

  var fontsPromise;
  function fontsReady() {
    if (!fontsPromise) {
      var fonts = document.fonts;
      var loads = fonts
        ? Promise.all([
            fonts.load('400 15px "Inter"'),
            fonts.load('500 15px "Inter"'),
            fonts.load('700 15px "Inter"'),
            fonts.load('400 15px "Noto Sans TC"', "\u4e2d"),
            fonts.load('700 15px "Noto Sans TC"', "\u4e2d"),
          ])
        : Promise.resolve();
      var timeout = new Promise(function (resolve) {
        setTimeout(resolve, 3000);
      });
      fontsPromise = Promise.race([loads, timeout]).catch(function () {});
    }
    return fontsPromise;
  }

  function patch(mermaid) {
    if (!mermaid || mermaid.__ditThemed || typeof mermaid.initialize !== "function") {
      return mermaid;
    }
    var initialize = mermaid.initialize.bind(mermaid);
    mermaid.initialize = function (config) {
      config = config || {};
      var merged = merge(config, CONFIG);
      merged.themeVariables = merge(config.themeVariables, CONFIG.themeVariables);
      merged.flowchart = merge(config.flowchart, CONFIG.flowchart);
      merged.sequence = merge(config.sequence, CONFIG.sequence);
      merged.themeCSS = (config.themeCSS || "") + "\n" + EXTRA_CSS;
      return initialize(merged);
    };
    // Mermaid sizes every box from text measured at render time. If the web
    // fonts are still loading, it measures the fallback font and the labels
    // overflow once Inter / Noto Sans TC arrive, so wait for them (bounded).
    var render = mermaid.render.bind(mermaid);
    mermaid.render = function () {
      var args = arguments;
      return fontsReady().then(function () {
        return render.apply(null, args);
      });
    };
    mermaid.__ditThemed = true;
    return mermaid;
  }

  if (typeof window.mermaid !== "undefined") {
    patch(window.mermaid);
    return;
  }

  var current;
  Object.defineProperty(window, "mermaid", {
    configurable: true,
    enumerable: true,
    get: function () {
      return current;
    },
    set: function (value) {
      current = patch(value);
    },
  });
})();
