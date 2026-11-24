// The story view: generations as rows of named people and labelled groups, links drawn behind them.
// Everything shown comes from story.json.gz, written by src/itibar/site/story.py and view.py.
import { el, readJson } from "./dom.js";
import { glossary } from "./glossary.js";

const THRESHOLDS = ["all", "above_matruk", "saduq_up", "thiqa_up"];
const COLORS = ["#1f6feb", "#c2410c", "#15803d", "#a21caf", "#b45309", "#0e7490", "#be123c", "#4d7c0f",
  "#7c3aed", "#0f766e", "#9a3412", "#1d4ed8"];
const SVG = "http://www.w3.org/2000/svg";

function html(target, markup, root) {
  target.innerHTML = markup.replaceAll("@root/", root);
}

function displayName(person) {
  return person?.short || person?.en || person?.ar || "";
}

// The Common Era year(s) of an AH year (as vocab.ce in Python).
function died(person) {
  if (person.dr) return `d. ${person.dr} AH (as recorded)`;
  if (!person.d) return "";
  const start = 622.537 + (person.d - 1) * 0.970224;
  const first = Math.floor(start), last = Math.floor(start + 0.970224);
  return `d. ${person.d} AH (${first === last ? first : `${first}–${last}`} CE)`;
}

const LABELS = { all: "Everyone", above_matruk: "Excluding abandoned narrators", saduq_up: "Truthful and above", thiqa_up: "Trustworthy only" };

function controls(section, root) {
  const canvas = section.querySelector("[data-story-canvas]");
  const bar = el("div", "", "tree-controls");
  const filter = el("fieldset", "", "filter");
  const legend = el("legend", "Count ");
  const term = el("a", "narrators", "term");
  term.href = `${root}glossary/#reliability-filter`;
  legend.append(term);
  filter.append(legend);
  THRESHOLDS.forEach((key, i) => {
    const label = el("label");
    const input = el("input");
    input.type = "radio";
    input.name = "filter";
    input.value = key;
    input.checked = i === 0;
    label.append(input, el("span", LABELS[key]));
    filter.append(label);
  });
  const toggle = el("button", "Show the independent lines", "toggle");
  toggle.type = "button";
  toggle.dataset.lines = "";
  toggle.setAttribute("aria-pressed", "false");
  bar.append(filter, toggle);
  const sentence = el("p", "", "filter-sentence");
  sentence.id = "lines";
  sentence.setAttribute("aria-live", "polite");
  const legendList = el("ol", "", "line-legend");
  legendList.hidden = true;
  const panel = el("aside", "", "person-panel");
  panel.hidden = true;
  panel.setAttribute("aria-live", "polite");
  canvas.before(bar, sentence);
  canvas.after(legendList, panel);
  return { canvas, sentence, legend: legendList, panel, toggle };
}

export async function mountStory(section, root) {
  const { canvas, sentence, legend, panel, toggle } = controls(section, root);
  const data = await readJson("./story.json.gz");
  const terms = await glossary(root).catch(() => null);
  const chips = [];
  let bit = 0;
  let showLines = false;

  // Rows and chips.
  const frame = el("div", "", "story-frame");
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "story-links");
  svg.setAttribute("aria-hidden", "true");
  frame.append(svg);
  for (const row of data.rows) {
    const line = el("div", "", row.band ? "srow band" : "srow");
    const label = el("div", row.label, "srow-label");
    const items = el("div", "", "srow-items");
    for (const index of row.i) {
      const item = data.items[index];
      const chip = el("button", "", `chip k-${item.k}`);
      chip.type = "button";
      chip.dataset.item = index;
      if (item.k === "prophet") {
        chip.append(el("span", "The Prophet", "chip-name"));
        const ar = el("span", "ﷺ", "chip-ar");
        ar.lang = "ar";
        chip.append(ar);
      } else if (item.p) {
        const person = data.people[item.p] || {};
        const name = el("span", displayName(person), "chip-name");
        if (!person.short && !person.en) { name.lang = "ar"; name.dir = "rtl"; }
        chip.append(name);
        if (person.level) chip.append(el("span", "", `dot lv${person.level}`));
        for (const role of person.roles || []) {
          if (role === "cl") chip.append(el("span", "spreads here", "role"));
          if (role === "cut0") chip.append(el("span", "bottleneck", "role cut"));
          if (role === "scut" && !(person.roles || []).includes("cut0")) {
            const mark = el("span", "single line", "role cut");
            mark.title = `In the classical account, every chain through ${person.scope} passes through this narrator`;
            chip.append(mark);
          }
        }
        chip.setAttribute("aria-label", `${displayName(person)}${person.d ? ", " + died(person) : ""}: details`);
      } else {
        chip.append(el("span", item.label, "chip-name"));
        chip.setAttribute("aria-label", `${item.label}: list`);
      }
      const marks = el("span", "", "line-marks");
      chip.append(marks);
      chip.addEventListener("click", () => open(index, chip));
      chips[index] = chip;
      items.append(chip);
    }
    line.append(label, items);
    frame.append(line);
  }
  canvas.replaceChildren(frame);

  const maxChains = Math.max(1, ...data.links.map(link => link[2]));
  function width(chains) {
    return 1 + 6 * Math.log(1 + chains) / Math.log(1 + maxChains);
  }

  function centre(index, edge) {
    const box = chips[index].getBoundingClientRect();
    const origin = frame.getBoundingClientRect();
    const x = box.left + box.width / 2 - origin.left;
    const y = edge === "top" ? box.top - origin.top : edge === "bottom" ? box.bottom - origin.top : box.top + box.height / 2 - origin.top;
    return [x, y];
  }

  function curve([x1, y1], [x2, y2]) {
    const dy = Math.max(18, (y2 - y1) / 2);
    return `M${x1},${y1} C${x1},${y1 + dy} ${x2},${y2 - dy} ${x2},${y2}`;
  }

  function draw() {
    const box = frame.getBoundingClientRect();
    svg.setAttribute("width", box.width);
    svg.setAttribute("height", box.height);
    svg.replaceChildren();
    for (const [a, b, chains, mask] of data.links) {
      if (!chips[a] || !chips[b]) continue;
      const path = document.createElementNS(SVG, "path");
      const kept = (mask >> bit) & 1;
      path.setAttribute("d", curve(centre(a, "bottom"), centre(b, "top")));
      path.setAttribute("class", kept ? "link" : "link dropped");
      path.setAttribute("stroke-width", kept ? width(chains) : 1);
      svg.append(path);
    }
    if (!showLines) return;
    const lines = data.lines[THRESHOLDS[bit]] || [];
    lines.forEach((items, n) => {
      const offset = (n - (lines.length - 1) / 2) * 3;
      const points = items.filter(i => chips[i]).map(i => centre(i, "middle")).map(([x, y]) => [x + offset, y]);
      if (points.length < 2) return;
      let d = `M${points[0][0]},${points[0][1]}`;
      for (let i = 1; i < points.length; i++) d += " " + curve(points[i - 1], points[i]).slice(curve(points[i - 1], points[i]).indexOf("C"));
      const path = document.createElementNS(SVG, "path");
      path.setAttribute("d", d);
      path.setAttribute("class", "line");
      path.setAttribute("stroke", COLORS[n % COLORS.length]);
      svg.append(path);
    });
  }

  function update() {
    const key = THRESHOLDS[bit];
    const info = data.th[key];
    html(sentence, info.text, root);
    data.items.forEach((item, index) => {
      const chip = chips[index];
      if (!chip) return;
      const kept = item.a[bit];
      chip.classList.toggle("dropped", kept === 0 && item.k !== "prophet");
      const note = chip.querySelector(".kept");
      if (note) note.remove();
      if ((item.k === "group" || item.k === "band" || item.k === "books") && kept !== item.n && kept > 0) {
        chip.append(el("span", `${kept.toLocaleString()} at this step`, "kept"));
      }
      chip.querySelector(".line-marks").replaceChildren();
    });
    legend.replaceChildren();
    legend.hidden = !showLines;
    if (showLines) {
      const lines = data.lines[key] || [];
      lines.forEach((items, n) => {
        for (const i of items) {
          const mark = el("span", "", "mark");
          mark.style.background = COLORS[n % COLORS.length];
          chips[i]?.querySelector(".line-marks").append(mark);
        }
        const entry = el("li");
        const swatch = el("span", "", "swatch");
        swatch.style.background = COLORS[n % COLORS.length];
        entry.append(swatch, el("span", (info.nodes[n] || []).map(node => displayName(data.people[node])).filter(Boolean).join(" → ")));
        legend.append(entry);
      });
      if (info.total > lines.length) legend.append(el("li", `…and ${info.total - lines.length} more independent lines, not drawn.`, "quiet"));
      if (!lines.length) legend.append(el("li", "No line reaches the books at this step.", "quiet"));
    }
    toggle.setAttribute("aria-pressed", String(showLines));
    toggle.textContent = showLines ? "Hide the independent lines" : "Show the independent lines";
    draw();
  }

  // The side panel.
  function personDetails(node, person) {
    const box = el("div", "", "panel-person");
    const heading = el("h3", person.en || person.short || "");
    if (!person.en && !person.short) { heading.textContent = person.ar; heading.lang = "ar"; heading.dir = "rtl"; }
    const ar = el("p", person.ar, "panel-ar");
    ar.lang = "ar";
    ar.dir = "rtl";
    box.append(heading);
    if (person.en || person.short) box.append(ar);
    if (person.book) {
      box.append(el("p", `${(person.chains || 0).toLocaleString()} ${person.chains === 1 ? "chain ends" : "chains end"} in this book.`));
      return box;
    }
    const facts = el("dl", "", "panel-facts");
    const add = (label, value) => {
      if (!value) return;
      facts.append(el("dt", label));
      const dd = el("dd");
      if (value instanceof Node) dd.append(value); else dd.textContent = value;
      facts.append(dd);
    };
    add("Died", died(person));
    add("Lived", (person.places || []).join(", "));
    if (person.gen) add("Generation", terms?.generations?.[person.gen]?.name || `Generation ${person.gen}`);
    const level = terms?.levels?.[person.level];
    if (level) {
      const rating = el("span");
      rating.append(el("span", level.badge || level.name, `badge lv${person.level}`), " ");
      const label = el("bdi", person.label || level.arabic);
      label.lang = "ar";
      rating.append(label, el("span", ` — ${level.meaning}`, "quiet"));
      add("Rating", rating);
    } else if (person.level === 0) add("Rating", "not rated in the dataset");
    const roles = [];
    if (person.chains) roles.push(`${person.chains.toLocaleString()} ${person.chains === 1 ? "chain passes" : "chains pass"} through ${node.startsWith("u") ? "this companion" : "this narrator"}`);
    if (person.students) roles.push(`passes it to ${person.students.toLocaleString()} ${person.students === 1 ? "student" : "students"}`);
    for (const role of person.roles || []) {
      if (role === "cl") roles.push("the point where it begins to spread (common link)");
      if (role === "scut") roles.push(`in the classical account (the chains through ${person.scope}), every chain passes through ${node.startsWith("u") ? "this companion" : "him"}`);
      const cut = /^cut(\d)$/.exec(role);
      if (cut) roles.push(`a bottleneck — every line passes through ${node.startsWith("u") ? "this companion" : "him"} — ${["with everyone counted", "excluding abandoned narrators", "with truthful narrators and above", "with trustworthy narrators only"][Number(cut[1])]}`);
    }
    add("In this report", roles.join("; "));
    box.append(facts);
    if (person.rid) {
      const more = el("a", "Narrator page →");
      more.href = `${root}narrators/${person.rid}/`;
      box.append(el("p", "", "panel-link"));
      box.lastChild.append(more);
    }
    return box;
  }

  function open(index, chip) {
    const item = data.items[index];
    panel.replaceChildren();
    const close = el("button", "Close", "panel-close");
    close.type = "button";
    close.addEventListener("click", () => { panel.hidden = true; chip.focus(); });
    panel.append(close);
    if (item.k === "prophet") {
      panel.append(el("h3", "The Prophet ﷺ"), el("p", `${item.c.toLocaleString()} chains begin with him, through his companions.`));
    } else if (item.p) {
      panel.append(personDetails(item.p, data.people[item.p] || {}));
    } else {
      panel.append(el("h3", item.label));
      const list = el("ul", "", "panel-members");
      for (const node of item.m || []) {
        const person = data.people[node] || {};
        const entry = el("li");
        const button = el("button", displayName(person), "member");
        button.type = "button";
        if (!person.short && !person.en) { button.lang = "ar"; button.dir = "rtl"; }
        button.addEventListener("click", () => {
          panel.replaceChildren(close, personDetails(node, person));
          const back = el("button", "← Back to the list", "panel-back");
          back.type = "button";
          back.addEventListener("click", () => open(index, chip));
          panel.append(back);
          panel.querySelector("h3")?.focus();
        });
        entry.append(button, el("span", ` ${person.chains || 0} ${person.chains === 1 ? "chain" : "chains"}`, "quiet"));
        list.append(entry);
      }
      panel.append(list);
      if (item.n > (item.m || []).length) panel.append(el("p", `…and ${(item.n - item.m.length).toLocaleString()} more. The full graph below shows every one.`, "quiet"));
    }
    panel.hidden = false;
    const heading = panel.querySelector("h3");
    heading.tabIndex = -1;
    heading.focus();
  }
  panel.addEventListener("keydown", event => {
    if (event.key === "Escape") panel.hidden = true;
  });

  // The same tree as a list, for screen readers and for reading.
  const outline = section.querySelector(".outline");
  if (outline) {
    const list = outline.querySelector("ol");
    for (const row of data.rows) {
      const entry = el("li");
      entry.append(el("strong", `${row.label}: `));
      row.i.forEach((index, n) => {
        const item = data.items[index];
        if (n) entry.append("; ");
        if (item.k === "prophet") entry.append("the Prophet");
        else if (item.p) {
          const person = data.people[item.p] || {};
          const name = displayName(person);
          if (person.rid) {
            const anchor = el("a", name);
            anchor.href = `${root}narrators/${person.rid}/`;
            entry.append(anchor);
          } else entry.append(name);
        } else entry.append(item.label);
        entry.append(` (${item.c.toLocaleString()} ${item.c === 1 ? "chain" : "chains"})`);
      });
      list.append(entry);
    }
    outline.hidden = false;
  }

  section.querySelector(".filter").addEventListener("change", event => {
    bit = THRESHOLDS.indexOf(event.target.value);
    update();
  });
  toggle.addEventListener("click", () => { showLines = !showLines; update(); });
  new ResizeObserver(() => draw()).observe(frame);
  // A view can be linked: ?filter=thiqa_up&lines=1
  const params = new URLSearchParams(location.search);
  if (THRESHOLDS.includes(params.get("filter"))) {
    bit = THRESHOLDS.indexOf(params.get("filter"));
    section.querySelector(`input[value="${params.get("filter")}"]`).checked = true;
  }
  showLines = params.get("lines") === "1";
  update();
}
