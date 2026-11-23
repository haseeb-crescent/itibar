import { arabic, el, link, readJson } from "./dom.js";

const CELL_X = 154;
const CELL_Y = 82;
const LEVEL_COLORS = [
  "#abb5aa", "#30785c", "#388268", "#488b74", "#579782", "#68a391", "#83af9d",
  "#95b8aa", "#a6c3b6", "#adc9bd", "#b7d1c6", "#c0d7ce", "#cbded5",
];

export async function mountGraph(panel, dataPromise = readJson("graph.json.gz")) {
  const canvas = panel.querySelector("canvas");
  const context = canvas.getContext("2d");
  const message = panel.querySelector(".graph-message");
  const info = panel.querySelector(".node-info");
  const off = panel.querySelector("[data-off-route]");
  const expand = panel.querySelector("[data-expand]");
  const count = panel.querySelector(".graph-count");
  const output = panel.querySelector(".kappa-display strong");
  const { nodes, edges, views, selection, off_route, thresholds } = await dataPromise;
  const pointers = new Map();
  let view, screen, w, h, scale, fitX, fitY, dx, dy, lastGesture;
  let expanded = false;
  let threshold = Number(panel.querySelector(":checked").value);
  let selected = -1;
  let moved = false;
  let resizeRatio = 1;
  let request = 0;

  function fit() {
    const positions = view[1];
    const x = positions.reduce((max, point) => Math.max(max, Math.abs(point[1])), 0) * CELL_X;
    const height = Math.max(0, view[0].length - 1) * CELL_Y;
    fitX = Math.min(1.24, (w - 34) / (x + CELL_X));
    fitY = Math.min(1.24, (h - 68) / (height + 35));
    scale = 1;
    dx = w / 2;
    dy = Math.max(36, (h - height * fitY) / 2);
    schedule();
  }

  function resize() {
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    resizeRatio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = w * resizeRatio;
    canvas.height = h * resizeRatio;
    fit();
  }

  function style() {
    const css = getComputedStyle(panel);
    return Object.fromEntries(["paper", "cut", "common", "graph-edge", "graph-inactive", "graph-grid", "graph-label"]
      .map(key => [key, css.getPropertyValue(`--${key}`).trim()]));
  }

  function schedule() {
    if (!request && view && w) request = requestAnimationFrame(draw);
  }

  function draw() {
    request = 0;
    const [bands, positions, drawnEdges] = view;
    const sx = scale * fitX;
    const sy = scale * fitY;
    const colors = style();
    context.setTransform(resizeRatio, 0, 0, resizeRatio, 0, 0);
    context.clearRect(0, 0, w, h);
    screen = new Map(positions.map(([i, x, y]) => [i, [dx + x * CELL_X * sx / 2, dy + y * CELL_Y * sy]]));
    const visible = (x, y, outside = 15) => x > -outside && y > -outside && x < w + outside && y < h + outside;
    context.lineWidth = 1;
    context.font = "11px system-ui";
    context.textAlign = "left";
    context.textBaseline = "alphabetic";
    for (let i = 0; i < bands.length; i++) {
      const y = dy + i * CELL_Y * sy;
      if (y < 5 || y > h) continue;
      context.strokeStyle = colors["graph-grid"];
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(w, y);
      context.stroke();
      if (sy * CELL_Y >= 21 || i === 0 || i === bands.length - 1) {
        context.fillStyle = colors["graph-label"];
        context.fillText(bands[i], 8, y - 5);
      }
    }
    const bit = 1 << threshold;
    for (const edge of drawnEdges) {
      const [u, v, mask, flags, weight, hidden] = typeof edge === "number" ? edges[edge] : edge;
      const [x1, y1] = screen.get(u);
      const [x2, y2] = screen.get(v);
      if (Math.max(x1, x2) < -15 || Math.min(x1, x2) > w + 15 || Math.max(y1, y2) < -15 || Math.min(y1, y2) > h + 15) continue;
      const allowed = mask & bit;
      context.globalAlpha = allowed ? (flags & 2 ? .32 : .52) : .16;
      context.strokeStyle = allowed ? (flags & 1 ? colors.cut : colors["graph-edge"]) : colors["graph-inactive"];
      context.lineWidth = Math.min(2.4, .75 + weight / 8);
      context.setLineDash(hidden || flags ? [4, 3] : []);
      context.beginPath();
      context.moveTo(x1, y1);
      context.bezierCurveTo(x1, y1 + (y2 - y1) / 2, x2, y2 - (y2 - y1) / 2, x2, y2);
      context.stroke();
    }
    context.setLineDash([]);
    const annotations = [];
    for (const [i, [x, y]] of screen) {
      if (!visible(x, y, 65)) continue;
      const [id, name, , level, , , flags, cuts, ordinal] = nodes[i];
      const muted = ordinal != null && ordinal < thresholds[threshold];
      const root = id === "P";
      const cut = Boolean(cuts & bit);
      const common = Boolean(flags & 2);
      const book = id.startsWith("b");
      const radius = Math.max(2.5, Math.min(6, CELL_X * sx / 4));
      context.globalAlpha = muted ? .64 : 1;
      context.fillStyle = muted ? colors["graph-inactive"] : (LEVEL_COLORS[level] || colors.paper);
      context.strokeStyle = cut ? colors.cut : common ? colors.common : colors["graph-edge"];
      context.lineWidth = cut || common || i === selected ? 2.1 : 1;
      context.beginPath();
      if (book) context.roundRect(x - radius, y - radius, radius * 2, radius * 2, 2);
      else context.arc(x, y, root ? radius + 2 : radius, 0, 2 * Math.PI);
      context.fill();
      context.stroke();
      if (cut && common) {
        context.strokeStyle = colors.common;
        context.beginPath();
        context.arc(x, y, radius + 2.7, 0, 2 * Math.PI);
        context.stroke();
      }

      // Give prominent nodes labels in the overview. Zoom reveals all labels.
      if (root || cut || common || i === selected || (sx * CELL_X > 85 && sy * CELL_Y > 28)) {
        annotations.push([i === selected ? 4 : root ? 3 : cut || common ? 2 : 1, name || id, x, y, radius]);
      }
    }
    const labels = [];
    context.globalAlpha = 1;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.direction = "rtl";
    for (const [priority, name, x, y, radius] of annotations.sort((a, b) => b[0] - a[0])) {
      context.font = `${priority === 4 ? 700 : 550} 15px "Noto Naskh", serif`;
      const maximum = priority > 1 ? 126 : Math.min(145, sx * CELL_X - 7);
      let label = name;
      while (label.length > 3 && context.measureText(label).width > maximum) label = label.slice(0, -2) + "…";
      const width = context.measureText(label).width + 9;
      const candidates = [[x - width / 2, y - radius - 21], [x + radius + 4, y - 9], [x - radius - width - 4, y - 9]];
      const box = candidates.find(([left, top]) => left >= 2 && left + width <= w - 2 && top > 1 && top < h - 18 &&
        !labels.some(([a, b, oldWidth]) => left < a + oldWidth + 3 && left + width + 3 > a && top < b + 20 && top + 20 > b));
      if (!box) continue;
      const [left, top] = box;
      labels.push([left, top, width]);
      context.fillStyle = colors.paper;
      context.beginPath();
      context.roundRect(left, top, width, 18, 3);
      context.fill();
      context.fillStyle = colors["graph-label"];
      context.fillText(label, left + width / 2, top + 10);
    }
    context.direction = "ltr";
    context.globalAlpha = 1;
  }

  function setView() {
    const base = off.checked ? 2 : 0;
    const overview = views[selection[base]];
    const full = views[selection[base + 1]];
    view = expanded ? full : overview;
    selected = -1;
    info.hidden = true;
    expand.hidden = full[1].length === overview[1].length;
    expand.textContent = expanded ? "Show overview" : "Show all nodes";
    expand.setAttribute("aria-pressed", String(expanded));
    count.textContent = view[1].length
      ? `${view[1].length.toLocaleString()} of ${full[1].length.toLocaleString()} nodes`
      : "";
    message.hidden = view[1].length > 0;
    message.textContent = off_route
      ? "No on-route nodes. Include off-route nodes to inspect the recorded bundle."
      : "No graph nodes.";
    if (w) fit();
  }

  function show(i) {
    if (i === selected) return;
    selected = i;
    const [id, name, death, level, label, layer, flags, cuts, ordinal] = nodes[i];
    const title = arabic(name || id);
    if (flags & 8) {
      const anchor = link(`${document.body.dataset.root}narrators/${id.slice(1)}/`);
      anchor.append(title);
      info.replaceChildren(anchor);
    } else {
      info.replaceChildren(title);
    }
    const details = [];
    if (death != null && death !== "" && death !== 0) details.push(`d. ${death} AH`);
    else if (id.startsWith("r")) details.push("Death year unrecorded");
    if (level) details.push(`Taqrīb level ${level}`);
    else if (id.startsWith("r")) details.push("Taqrīb level unrecorded");
    if (layer && !id.startsWith("b")) details.push(`Generation ${layer}`);
    if (cuts & (1 << threshold)) details.push("Cut vertex");
    if (flags & 2) details.push("Common link with everyone retained");
    if (ordinal != null && ordinal < thresholds[threshold]) details.push(flags & 4 ? "Below threshold · book role retained" : "Below threshold");
    if (details.length) info.append(el("span", details.join(" · "), "quiet"));
    if (label) {
      const text = el("span");
      text.append(arabic(label));
      info.append(text);
    }
    info.hidden = false;
    schedule();
  }

  function zoom(amount, x, y) {
    const next = Math.max(.14, Math.min(24, scale * amount));
    dx = x - (x - dx) * next / scale;
    dy = y - (y - dy) * next / scale;
    scale = next;
    schedule();
  }

  function point(event) {
    const box = canvas.getBoundingClientRect();
    return [event.clientX - box.left, event.clientY - box.top];
  }

  function hit(x, y) {
    if (!screen) return;
    let distance = 14;
    let closest;
    for (const [i, [xx, yy]] of screen) {
      const d = Math.hypot(x - xx, y - yy);
      if (d < distance) [distance, closest] = [d, i];
    }
    if (closest !== undefined) show(closest);
  }

  function gesture() {
    const [a, b] = pointers.values();
    return b ? [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.hypot(a[0] - b[0], a[1] - b[1])] : a;
  }

  canvas.addEventListener("pointerdown", event => {
    canvas.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, point(event));
    if (pointers.size === 1) moved = false;
    lastGesture = gesture();
  });
  canvas.addEventListener("pointermove", event => {
    if (!pointers.has(event.pointerId)) {
      if (event.pointerType === "mouse") hit(...point(event));
      return;
    }
    pointers.set(event.pointerId, point(event));
    const [x, y, d] = gesture();
    const [previousX, previousY, previousDistance] = lastGesture;
    if (d && previousDistance) zoom(d / previousDistance, previousX, previousY);
    if (d || Math.abs(x - previousX) + Math.abs(y - previousY) > 2) moved = true;
    dx += x - previousX;
    dy += y - previousY;
    lastGesture = [x, y, d];
    schedule();
  });
  function end(event) {
    if (event.type === "pointerup" && pointers.size === 1 && !moved) hit(...point(event));
    pointers.delete(event.pointerId);
    lastGesture = gesture();
  }
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("wheel", event => {
    event.preventDefault();
    zoom(event.deltaY < 0 ? 1.12 : 1 / 1.12, ...point(event));
  }, { passive: false });
  canvas.addEventListener("keydown", event => {
    const pan = { ArrowUp: [0, 36], ArrowDown: [0, -36], ArrowLeft: [36, 0], ArrowRight: [-36, 0] };
    if (event.key in pan) {
      dx += pan[event.key][0];
      dy += pan[event.key][1];
    } else if (event.key === "+" || event.key === "=" || event.key === "-") {
      zoom(event.key === "-" ? 1 / 1.23 : 1.23, w / 2, h / 2);
    } else if ((event.key === "[" || event.key === "]") && view[1].length) {
      const positions = view[1];
      const at = positions.findIndex(([i]) => i === selected);
      const offset = event.key === "]" ? 1 : -1;
      const [next] = positions[(Math.max(-1, at) + offset + positions.length) % positions.length];
      const [x, y] = screen.get(next);
      dx += Math.min(w - 45, Math.max(45, x)) - x;
      dy += Math.min(h - 28, Math.max(28, y)) - y;
      show(next);
    } else return;
    event.preventDefault();
    schedule();
  });
  for (const button of panel.querySelectorAll("[data-zoom]")) {
    button.addEventListener("click", () => {
      if (button.dataset.zoom === "fit") fit();
      else zoom(button.dataset.zoom === "in" ? 1.3 : 1 / 1.3, w / 2, h / 2);
    });
  }
  panel.querySelector(".thresholds").addEventListener("change", event => {
    threshold = Number(event.target.value);
    output.textContent = event.target.dataset.kappa;
    if (selected !== -1) {
      const i = selected;
      selected = -1;
      show(i);
    }
    schedule();
  });
  off.addEventListener("change", setView);
  expand.addEventListener("click", () => { expanded = !expanded; setView(); });
  setView();
  new ResizeObserver(resize).observe(canvas);
  document.fonts.load('15px "Noto Naskh"', "النبي").then(schedule, schedule);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", schedule);
}
