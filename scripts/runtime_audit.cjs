#!/usr/bin/env node
"use strict";

/** Collect reproducible browser evidence without turning heuristics into findings. */

const fs = require("fs");
const path = require("path");

const DEFAULT_VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 375, height: 812, isMobile: true, hasTouch: true },
];

function usage() {
  return `Usage:
  node runtime_audit.cjs --base-url <url> --manifest <routes.json> --output <dir> [options]

Options:
  --node-modules <dir>      Directory containing playwright and optional axe-core
  --executable-path <file>  Chrome/Edge/Chromium executable; auto-detected when omitted
  --storage-state <file>    Playwright storage state for authenticated routes
  --axe-script <file>       Local axe.min.js; auto-detected from node_modules when possible
  --headed                  Show the browser
  --trace                   Save a Playwright trace for each route and viewport
  --full-page               Capture full-page screenshots
  --wait-ms <number>        Additional wait after DOMContentLoaded (default: 300)
  --runs <number>           Repeat each route/viewport for median lab signals (default: 1, max: 10)
  --fail-on-navigation-error  Exit 1 when any navigation fails
  --fail-on-budget          Exit 1 when a manifest-defined performance budget is exceeded
  --dry-run                 Validate inputs and print the execution plan only
  --help                    Show this help

Manifest example:
  {"routes":[{"id":"home","path":"/"},{"id":"search","path":"/search","viewports":[{"name":"mobile","width":375,"height":812}]}]}
`;
}

function parseArgs(argv) {
  const args = {
    headed: false,
    trace: false,
    fullPage: false,
    waitMs: 300,
    runs: 1,
    failOnNavigationError: false,
    failOnBudget: false,
    dryRun: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    const next = () => {
      if (index + 1 >= argv.length) throw new Error(`${token} requires a value`);
      index += 1;
      return argv[index];
    };
    if (token === "--base-url") args.baseUrl = next();
    else if (token === "--manifest") args.manifest = next();
    else if (token === "--output") args.output = next();
    else if (token === "--node-modules") args.nodeModules = next();
    else if (token === "--executable-path") args.executablePath = next();
    else if (token === "--storage-state") args.storageState = next();
    else if (token === "--axe-script") args.axeScript = next();
    else if (token === "--wait-ms") args.waitMs = Number(next());
    else if (token === "--runs") args.runs = Number(next());
    else if (token === "--headed") args.headed = true;
    else if (token === "--trace") args.trace = true;
    else if (token === "--full-page") args.fullPage = true;
    else if (token === "--fail-on-navigation-error") args.failOnNavigationError = true;
    else if (token === "--fail-on-budget") args.failOnBudget = true;
    else if (token === "--dry-run") args.dryRun = true;
    else if (token === "--help" || token === "-h") args.help = true;
    else throw new Error(`unknown argument: ${token}`);
  }
  return args;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function safeName(value) {
  return String(value).replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "route";
}

function sanitizeUrl(value) {
  try {
    const url = new URL(value);
    for (const key of [...url.searchParams.keys()]) url.searchParams.set(key, "[redacted]");
    url.username = "";
    url.password = "";
    return url.toString();
  } catch {
    return String(value).slice(0, 500);
  }
}

function redact(value) {
  return String(value)
    .replace(/(bearer\s+)[a-z0-9._~+\/-]+/gi, "$1[redacted]")
    .replace(/((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[^\s,;]+/gi, "$1[redacted]")
    .slice(0, 1000);
}

function loadPackage(name, nodeModules) {
  if (nodeModules) {
    const candidate = path.resolve(nodeModules, ...name.split("/"));
    return require(candidate);
  }
  return require(name);
}

function resolveAxeScript(args) {
  if (args.axeScript) return path.resolve(args.axeScript);
  if (args.nodeModules) {
    const candidate = path.resolve(args.nodeModules, "axe-core", "axe.min.js");
    if (fs.existsSync(candidate)) return candidate;
  }
  try {
    return require.resolve("axe-core/axe.min.js");
  } catch {
    return null;
  }
}

function resolveBrowserExecutable(playwright, args) {
  if (args.executablePath) {
    const explicit = path.resolve(args.executablePath);
    if (!fs.existsSync(explicit)) throw new Error(`browser executable does not exist: ${explicit}`);
    return { path: explicit, source: "explicit" };
  }
  const candidates = [];
  try {
    candidates.push({ path: playwright.chromium.executablePath(), source: "playwright" });
  } catch {
    // Continue to system browser discovery.
  }
  if (process.platform === "win32") {
    const local = process.env.LOCALAPPDATA;
    candidates.push(
      { path: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", source: "system-chrome" },
      { path: "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe", source: "system-chrome" },
      { path: "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe", source: "system-edge" },
      { path: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", source: "system-edge" }
    );
    if (local) candidates.push({ path: path.join(local, "Google", "Chrome", "Application", "chrome.exe"), source: "system-chrome" });
  } else if (process.platform === "darwin") {
    candidates.push(
      { path: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", source: "system-chrome" },
      { path: "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", source: "system-edge" },
      { path: "/Applications/Chromium.app/Contents/MacOS/Chromium", source: "system-chromium" }
    );
  } else {
    candidates.push(
      { path: "/usr/bin/google-chrome", source: "system-chrome" },
      { path: "/usr/bin/google-chrome-stable", source: "system-chrome" },
      { path: "/usr/bin/chromium", source: "system-chromium" },
      { path: "/usr/bin/chromium-browser", source: "system-chromium" },
      { path: "/usr/bin/microsoft-edge", source: "system-edge" }
    );
  }
  const found = candidates.find((candidate) => candidate.path && fs.existsSync(candidate.path));
  if (!found) {
    throw new Error("no Playwright-managed or system Chrome/Edge/Chromium executable was found; pass --executable-path");
  }
  return found;
}

function validateManifest(manifest) {
  if (!manifest || typeof manifest !== "object" || !Array.isArray(manifest.routes) || manifest.routes.length === 0) {
    throw new Error("manifest.routes must be a non-empty array");
  }
  const ids = new Set();
  for (const [index, route] of manifest.routes.entries()) {
    if (!route || typeof route !== "object") throw new Error(`routes[${index}] must be an object`);
    if (typeof route.id !== "string" || !route.id.trim()) throw new Error(`routes[${index}].id is required`);
    if (ids.has(route.id)) throw new Error(`duplicate route id: ${route.id}`);
    ids.add(route.id);
    if (typeof route.path !== "string" || !route.path.trim()) throw new Error(`routes[${index}].path is required`);
    validateBudgets(route.budgets, `routes[${index}].budgets`);
    const viewports = route.viewports || manifest.viewports || DEFAULT_VIEWPORTS;
    if (!Array.isArray(viewports) || viewports.length === 0) throw new Error(`routes[${index}] has no viewports`);
    for (const viewport of viewports) {
      if (!viewport || typeof viewport.name !== "string" || !Number.isInteger(viewport.width) || !Number.isInteger(viewport.height)) {
        throw new Error(`routes[${index}] has an invalid viewport`);
      }
    }
  }
  validateBudgets(manifest.budgets, "manifest.budgets");
}

function validateBudgets(budgets, label) {
  if (budgets === undefined) return;
  if (!budgets || typeof budgets !== "object" || Array.isArray(budgets)) throw new Error(`${label} must be an object`);
  const allowed = new Set(["lcpMs", "cls", "transferSize", "resourceCount", "longTaskTotalMs"]);
  for (const [key, value] of Object.entries(budgets)) {
    if (!allowed.has(key)) throw new Error(`${label}.${key} is not supported`);
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0) throw new Error(`${label}.${key} must be non-negative`);
  }
}

function installLabObservers() {
  window.__fsrLabSignals = {
    lcp: null,
    cls: 0,
    clsSession: { value: 0, startTime: 0, endTime: 0 },
    layoutShiftCount: 0,
    longTasks: { count: 0, totalMs: 0, maxMs: 0 },
    observerSupport: {},
  };
  const observe = (type, callback) => {
    try {
      const observer = new PerformanceObserver((list) => callback(list.getEntries()));
      observer.observe({ type, buffered: true });
      window.__fsrLabSignals.observerSupport[type] = true;
    } catch {
      window.__fsrLabSignals.observerSupport[type] = false;
    }
  };
  observe("largest-contentful-paint", (entries) => {
    const entry = entries[entries.length - 1];
    if (!entry) return;
    const element = entry.element;
    window.__fsrLabSignals.lcp = {
      value: entry.startTime,
      size: entry.size || null,
      element: element
        ? `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ""}${element.classList?.length ? `.${[...element.classList].slice(0, 3).join(".")}` : ""}`
        : null,
    };
  });
  observe("layout-shift", (entries) => {
    for (const entry of entries) {
      if (!entry.hadRecentInput) {
        const session = window.__fsrLabSignals.clsSession;
        const continuesSession =
          session.value > 0 && entry.startTime - session.endTime < 1000 && entry.startTime - session.startTime < 5000;
        if (continuesSession) {
          session.value += entry.value;
          session.endTime = entry.startTime;
        } else {
          session.value = entry.value;
          session.startTime = entry.startTime;
          session.endTime = entry.startTime;
        }
        window.__fsrLabSignals.cls = Math.max(window.__fsrLabSignals.cls, session.value);
        window.__fsrLabSignals.layoutShiftCount += 1;
      }
    }
  });
  observe("longtask", (entries) => {
    for (const entry of entries) {
      window.__fsrLabSignals.longTasks.count += 1;
      window.__fsrLabSignals.longTasks.totalMs += entry.duration;
      window.__fsrLabSignals.longTasks.maxMs = Math.max(window.__fsrLabSignals.longTasks.maxMs, entry.duration);
    }
  });
}

async function collectDomEvidence(page) {
  return page.evaluate(() => {
    const text = (element) => (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 160);
    const formControls = [...document.querySelectorAll("input, select, textarea")];
    const interactiveElements = [...document.querySelectorAll(
      "a[href], button, input, select, textarea, summary, [role='button'], [role='link'], [tabindex]"
    )];
    const missingLabels = formControls.filter((control) => {
      if (control.getAttribute("aria-label") || control.getAttribute("aria-labelledby")) return false;
      if (control.closest("label")) return false;
      const id = control.getAttribute("id");
      return !id || !document.querySelector(`label[for="${CSS.escape(id)}"]`);
    });
    const images = [...document.images];
    const ids = [...document.querySelectorAll("[id]")].map((node) => node.id).filter(Boolean);
    const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
    const buttonsWithoutName = [...document.querySelectorAll("button, [role='button']")].filter((node) => {
      return !(node.getAttribute("aria-label") || node.getAttribute("aria-labelledby") || text(node));
    });
    const headings = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")].map((node) => ({
      level: Number(node.tagName.slice(1)),
      text: text(node),
    }));
    const focusables = document.querySelectorAll(
      "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
    ).length;
    const parseColor = (value) => {
      const match = String(value).match(/^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+))?\s*\)$/i);
      if (!match) return null;
      return {
        r: Math.max(0, Math.min(255, Number(match[1]))),
        g: Math.max(0, Math.min(255, Number(match[2]))),
        b: Math.max(0, Math.min(255, Number(match[3]))),
        a: match[4] === undefined ? 1 : Math.max(0, Math.min(1, Number(match[4]))),
      };
    };
    const composite = (front, back) => ({
      r: front.r * front.a + back.r * (1 - front.a),
      g: front.g * front.a + back.g * (1 - front.a),
      b: front.b * front.a + back.b * (1 - front.a),
      a: 1,
    });
    const channel = (value) => {
      const normalized = value / 255;
      return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
    };
    const luminance = (color) => 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
    const ratio = (first, second) => {
      const high = Math.max(luminance(first), luminance(second));
      const low = Math.min(luminance(first), luminance(second));
      return (high + 0.05) / (low + 0.05);
    };
    const describe = (node) => {
      if (node.id) return `${node.tagName.toLowerCase()}#${CSS.escape(node.id)}`;
      const classes = [...node.classList].slice(0, 2).map((value) => `.${CSS.escape(value)}`).join("");
      return `${node.tagName.toLowerCase()}${classes}`;
    };
    const backgroundFor = (node) => {
      const layers = [];
      for (let current = node; current; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.backgroundImage !== "none" || Number(style.opacity) < 1) {
          return { color: null, reason: "non-solid background or element opacity" };
        }
        const color = parseColor(style.backgroundColor);
        if (!color) return { color: null, reason: "unparsed background color" };
        if (color.a > 0) layers.push(color);
      }
      let result = { r: 255, g: 255, b: 255, a: 1 };
      for (const layer of layers.reverse()) result = composite(layer, result);
      return { color: result, reason: null };
    };
    const contrast = {
      schemaVersion: "contrast-evidence-1.0",
      method: "WCAG 2.x relative luminance (sRGB) with alpha compositing over solid ancestor backgrounds",
      formula: "ratio=(Llighter+0.05)/(Ldarker+0.05); sRGB<=0.04045 ? sRGB/12.92 : ((sRGB+0.055)/1.055)^2.4",
      thresholds: { normalText: 4.5, largeText: 3.0, largeTextDefinition: ">=24px, or >=18.66px and font-weight >=700" },
      inspectedTextNodes: 0,
      skippedTextNodes: 0,
      violationCount: 0,
      violationSamples: [],
      limitations: [
        "Evidence heuristic only: pseudo-elements, canvas/SVG text, blend modes, filters, images, gradients, overlays, and dynamic states require separate inspection.",
        "A reported sample is not a finding until visually corroborated at the same route, viewport, and state.",
      ],
    };
    for (const node of [...document.querySelectorAll("body *")].slice(0, 5000)) {
      const ownText = [...node.childNodes]
        .filter((child) => child.nodeType === Node.TEXT_NODE)
        .map((child) => child.textContent || "")
        .join(" ")
        .trim()
        .replace(/\s+/g, " ");
      if (!ownText) continue;
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0 || rect.width <= 0 || rect.height <= 0) continue;
      const foreground = parseColor(style.color);
      const background = backgroundFor(node);
      if (!foreground || !background.color) {
        contrast.skippedTextNodes += 1;
        continue;
      }
      contrast.inspectedTextNodes += 1;
      const effectiveForeground = composite(foreground, background.color);
      const fontSizePx = Number.parseFloat(style.fontSize);
      const numericWeight = Number.parseInt(style.fontWeight, 10);
      const fontWeight = Number.isFinite(numericWeight) ? numericWeight : style.fontWeight === "bold" ? 700 : 400;
      const threshold = fontSizePx >= 24 || (fontSizePx >= 18.66 && fontWeight >= 700) ? 3 : 4.5;
      const measured = Math.round(ratio(effectiveForeground, background.color) * 100) / 100;
      if (measured + 0.005 < threshold) {
        contrast.violationCount += 1;
        if (contrast.violationSamples.length < 50) {
          contrast.violationSamples.push({
            selector: describe(node),
            text: ownText.slice(0, 120),
            computedForeground: style.color,
            computedBackground: `rgb(${Math.round(background.color.r)}, ${Math.round(background.color.g)}, ${Math.round(background.color.b)})`,
            fontSizePx,
            fontWeight,
            ratio: measured,
            threshold,
          });
        }
      }
    }
    const navigation = performance.getEntriesByType("navigation")[0];
    const resources = performance.getEntriesByType("resource");
    const paints = Object.fromEntries(performance.getEntriesByType("paint").map((entry) => [entry.name, Math.round(entry.startTime)]));
    const lab = window.__fsrLabSignals || null;
    const resourceTypes = {};
    for (const resource of resources) {
      const type = resource.initiatorType || "other";
      if (!resourceTypes[type]) resourceTypes[type] = { count: 0, transferSize: 0 };
      resourceTypes[type].count += 1;
      resourceTypes[type].transferSize += resource.transferSize || 0;
    }
    return {
      document: {
        title: document.title,
        language: document.documentElement.lang || null,
        h1Count: document.querySelectorAll("h1").length,
        mainCount: document.querySelectorAll("main").length,
        headings,
      },
      layout: {
        viewportWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      },
      controls: {
        formControlTotal: formControls.length,
        interactiveElementTotal: interactiveElements.length,
        missingLabelCount: missingLabels.length,
        missingLabelSamples: missingLabels.slice(0, 10).map((node) => node.outerHTML.slice(0, 240)),
        focusableCount: focusables,
        buttonWithoutNameCount: buttonsWithoutName.length,
      },
      contrast,
      images: {
        total: images.length,
        missingAltCount: images.filter((image) => !image.hasAttribute("alt")).length,
        missingDimensionsCount: images.filter((image) => !image.getAttribute("width") || !image.getAttribute("height")).length,
      },
      dom: {
        duplicateIds,
        nodeCount: document.getElementsByTagName("*").length,
      },
      performanceSnapshot: {
        navigation: navigation
          ? {
              domContentLoaded: Math.round(navigation.domContentLoadedEventEnd),
              loadEvent: Math.round(navigation.loadEventEnd),
              transferSize: navigation.transferSize,
              encodedBodySize: navigation.encodedBodySize,
            }
          : null,
        resourceCount: resources.length,
        transferSize: resources.reduce((total, item) => total + (item.transferSize || 0), 0),
        resourceTypes,
        labSignals: lab
          ? {
              firstContentfulPaintMs: paints["first-contentful-paint"] ?? null,
              lcpMs: lab.lcp ? Math.round(lab.lcp.value) : null,
              lcpElement: lab.lcp ? lab.lcp.element : null,
              cls: Math.round(lab.cls * 10000) / 10000,
              layoutShiftCount: lab.layoutShiftCount,
              longTasks: {
                count: lab.longTasks.count,
                totalMs: Math.round(lab.longTasks.totalMs),
                maxMs: Math.round(lab.longTasks.maxMs),
              },
              observerSupport: lab.observerSupport,
            }
          : null,
        note: "Single-run browser lab signals only; INP requires interactions and field conclusions require RUM.",
      },
    };
  });
}

function evaluateBudgets(dom, budgets) {
  if (!budgets || Object.keys(budgets).length === 0) return { status: "not_configured", checks: [] };
  const performance = dom?.performanceSnapshot;
  const values = {
    lcpMs: performance?.labSignals?.lcpMs ?? null,
    cls: performance?.labSignals?.cls ?? null,
    transferSize: performance?.transferSize ?? null,
    resourceCount: performance?.resourceCount ?? null,
    longTaskTotalMs: performance?.labSignals?.longTasks?.totalMs ?? null,
  };
  const checks = Object.entries(budgets).map(([metric, maximum]) => {
    const actual = values[metric];
    return {
      metric,
      maximum,
      actual,
      status: actual === null ? "unavailable" : actual <= maximum ? "passed" : "exceeded",
    };
  });
  return {
    status: checks.some((item) => item.status === "exceeded") ? "exceeded" : checks.some((item) => item.status === "unavailable") ? "partial" : "passed",
    checks,
  };
}

function median(values) {
  const numeric = values.filter((value) => typeof value === "number" && Number.isFinite(value)).sort((a, b) => a - b);
  if (!numeric.length) return null;
  const middle = Math.floor(numeric.length / 2);
  return numeric.length % 2 ? numeric[middle] : Math.round(((numeric[middle - 1] + numeric[middle]) / 2) * 10000) / 10000;
}

function aggregateResults(results) {
  const groups = new Map();
  for (const result of results) {
    const key = `${result.routeId}\u0000${result.viewport.name}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(result);
  }
  return [...groups.values()].map((items) => ({
    routeId: items[0].routeId,
    viewport: items[0].viewport.name,
    runs: items.length,
    successfulRuns: items.filter((item) => item.navigation.status === "completed").length,
    medians: {
      navigationElapsedMs: median(items.map((item) => item.navigation.elapsedMs)),
      firstContentfulPaintMs: median(items.map((item) => item.dom?.performanceSnapshot?.labSignals?.firstContentfulPaintMs)),
      lcpMs: median(items.map((item) => item.dom?.performanceSnapshot?.labSignals?.lcpMs)),
      cls: median(items.map((item) => item.dom?.performanceSnapshot?.labSignals?.cls)),
      transferSize: median(items.map((item) => item.dom?.performanceSnapshot?.transferSize)),
      longTaskTotalMs: median(items.map((item) => item.dom?.performanceSnapshot?.labSignals?.longTasks?.totalMs)),
    },
    budgetStatus: items.some((item) => item.budgets.status === "exceeded") ? "exceeded" : items.some((item) => item.budgets.status === "partial") ? "partial" : items[0].budgets.status,
  }));
}

async function runAxe(page, axeScript) {
  if (!axeScript) return { status: "not_run", reason: "axe-core was not available" };
  await page.addScriptTag({ path: axeScript });
  const result = await page.evaluate(async () => {
    const output = await window.axe.run(document, { resultTypes: ["violations", "incomplete"] });
    const compact = (item) => ({
      id: item.id,
      impact: item.impact,
      help: item.help,
      helpUrl: item.helpUrl,
      nodeCount: item.nodes.length,
      targets: item.nodes.slice(0, 10).map((node) => node.target),
    });
    return { violations: output.violations.map(compact), incomplete: output.incomplete.map(compact) };
  });
  return { status: "completed", ...result };
}

async function auditOne(browser, args, manifest, route, viewport, axeScript, outputDir, runNumber) {
  const contextOptions = {
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: Boolean(viewport.isMobile),
    hasTouch: Boolean(viewport.hasTouch),
  };
  if (args.storageState) contextOptions.storageState = path.resolve(args.storageState);
  if (manifest.colorScheme) contextOptions.colorScheme = manifest.colorScheme;
  if (manifest.reducedMotion) contextOptions.reducedMotion = manifest.reducedMotion;
  const context = await browser.newContext(contextOptions);
  await context.addInitScript(installLabObservers);
  const artifactBase = `${safeName(route.id)}-${safeName(viewport.name)}${args.runs > 1 ? `-run-${String(runNumber).padStart(2, "0")}` : ""}`;
  const result = {
    routeId: route.id,
    run: runNumber,
    url: sanitizeUrl(new URL(route.path, args.baseUrl).toString()),
    viewport,
    navigation: { status: "not_run" },
    console: [],
    pageErrors: [],
    requestFailures: [],
    responseErrors: [],
    dom: null,
    axe: { status: "not_run", reason: "navigation did not complete" },
    budgets: { status: "not_run", checks: [] },
    artifacts: {},
  };
  if (args.trace) await context.tracing.start({ screenshots: true, snapshots: true, sources: false });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      result.console.push({ type: message.type(), text: redact(message.text()) });
    }
  });
  page.on("pageerror", (error) => result.pageErrors.push(redact(error.message)));
  page.on("requestfailed", (request) => {
    result.requestFailures.push({ url: sanitizeUrl(request.url()), error: redact(request.failure()?.errorText || "unknown") });
  });
  page.on("response", (response) => {
    if (response.status() >= 400) result.responseErrors.push({ url: sanitizeUrl(response.url()), status: response.status() });
  });

  try {
    const started = Date.now();
    const response = await page.goto(new URL(route.path, args.baseUrl).toString(), {
      waitUntil: route.waitUntil || manifest.waitUntil || "domcontentloaded",
      timeout: route.timeoutMs || manifest.timeoutMs || 30000,
    });
    const waitMs = route.waitMs ?? manifest.waitMs ?? args.waitMs;
    if (waitMs > 0) await page.waitForTimeout(waitMs);
    result.navigation = {
      status: "completed",
      httpStatus: response ? response.status() : null,
      elapsedMs: Date.now() - started,
      finalUrl: sanitizeUrl(page.url()),
    };
    result.dom = await collectDomEvidence(page);
    result.budgets = evaluateBudgets(result.dom, { ...(manifest.budgets || {}), ...(route.budgets || {}) });
    result.axe = await runAxe(page, axeScript);
    const screenshot = `${artifactBase}.png`;
    await page.screenshot({ path: path.join(outputDir, screenshot), fullPage: args.fullPage });
    result.artifacts.screenshot = screenshot;
  } catch (error) {
    result.navigation = { status: "failed", error: redact(error.stack || error.message || error) };
  } finally {
    if (args.trace) {
      const trace = `${artifactBase}.zip`;
      await context.tracing.stop({ path: path.join(outputDir, trace) });
      result.artifacts.trace = trace;
    }
    await context.close();
  }
  return result;
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`error: ${error.message}\n\n${usage()}`);
    return 2;
  }
  if (args.help) {
    console.log(usage());
    return 0;
  }
  for (const key of ["baseUrl", "manifest", "output"]) {
    if (!args[key]) {
      console.error(`error: --${key.replace(/[A-Z]/g, (value) => `-${value.toLowerCase()}`)} is required`);
      return 2;
    }
  }
  if (!Number.isFinite(args.waitMs) || args.waitMs < 0) {
    console.error("error: --wait-ms must be a non-negative number");
    return 2;
  }
  if (!Number.isInteger(args.runs) || args.runs < 1 || args.runs > 10) {
    console.error("error: --runs must be an integer from 1 to 10");
    return 2;
  }
  let manifest;
  try {
    manifest = readJson(path.resolve(args.manifest));
    validateManifest(manifest);
    new URL(args.baseUrl);
  } catch (error) {
    console.error(`error: ${error.message}`);
    return 2;
  }
  const plan = manifest.routes.flatMap((route) =>
    (route.viewports || manifest.viewports || DEFAULT_VIEWPORTS).flatMap((viewport) =>
      Array.from({ length: args.runs }, (_, index) => ({
        routeId: route.id,
        run: index + 1,
        url: sanitizeUrl(new URL(route.path, args.baseUrl).toString()),
        viewport,
        budgets: { ...(manifest.budgets || {}), ...(route.budgets || {}) },
      }))
    )
  );
  if (args.dryRun) {
    console.log(JSON.stringify({ valid: true, dryRun: true, plan }, null, 2));
    return 0;
  }

  let playwright;
  try {
    playwright = loadPackage("playwright", args.nodeModules);
  } catch (error) {
    console.error(`error: Playwright is unavailable. Install it in the project or pass --node-modules. ${error.message}`);
    return 2;
  }
  const axeScript = resolveAxeScript(args);
  if (axeScript && !fs.existsSync(axeScript)) {
    console.error(`error: axe script does not exist: ${axeScript}`);
    return 2;
  }
  const outputDir = path.resolve(args.output);
  fs.mkdirSync(outputDir, { recursive: true });
  const browserExecutable = resolveBrowserExecutable(playwright, args);
  const browser = await playwright.chromium.launch({
    headless: !args.headed,
    executablePath: browserExecutable.path,
  });
  const results = [];
  try {
    for (const route of manifest.routes) {
      const viewports = route.viewports || manifest.viewports || DEFAULT_VIEWPORTS;
      for (const viewport of viewports) {
        for (let runNumber = 1; runNumber <= args.runs; runNumber += 1) {
          results.push(await auditOne(browser, args, manifest, route, viewport, axeScript, outputDir, runNumber));
        }
      }
    }
  } finally {
    await browser.close();
  }
  const output = {
    schemaVersion: "runtime-audit-1.2",
    generatedAt: new Date().toISOString(),
    baseUrl: sanitizeUrl(args.baseUrl),
    environment: {
      browser: "chromium",
      browserExecutableSource: browserExecutable.source,
      headless: !args.headed,
      axe: axeScript ? { status: "available", source: path.basename(axeScript) } : { status: "unavailable" },
      runs: args.runs,
      note: "Performance values are repeatable browser lab signals. LCP/CLS are diagnostic; INP requires interactions and field conclusions require RUM.",
    },
    aggregates: aggregateResults(results),
    results,
  };
  const outputFile = path.join(outputDir, "runtime-audit.json");
  fs.writeFileSync(outputFile, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  const failed = results.filter((item) => item.navigation.status === "failed").length;
  const budgetExceeded = results.filter((item) => item.budgets.status === "exceeded").length;
  console.log(JSON.stringify({ ok: failed === 0 && budgetExceeded === 0, output: outputFile, checks: results.length, navigationFailures: failed, budgetExceedances: budgetExceeded }, null, 2));
  if (failed && args.failOnNavigationError) return 1;
  if (budgetExceeded && args.failOnBudget) return 1;
  return 0;
}

main()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    console.error(`error: ${error.stack || error.message || error}`);
    process.exitCode = 1;
  });
