// Скрипт для плагина Scripter в Figma: строит страницы «Актуальная версия»
// из кадров (SVG) и переходов, которые раздаёт tools/serve_export.py.
// Запуск в Scripter:  eval(await (await fetch("http://127.0.0.1:8765/build.js")).text())

(async () => {
const BASE = "http://127.0.0.1:8765/";
const GAP = 160;       // расстояние между кадрами
const COLUMNS = 4;     // кадров в ряду
const THEME_TITLES = {
  light: "Актуальная версия — светлая",
  dark: "Актуальная версия — тёмная",
};
const START_POINTS = {
  "01": "Вход в программу",
  "03": "Главное окно",
  "13": "Настройки",
  "24": "Поиск",
};

async function getJson(path) {
  const response = await fetch(BASE + path);
  return await response.json();
}
async function getText(path) {
  const response = await fetch(BASE + path);
  return await response.text();
}

async function setReactions(node, reactions) {
  if (node.setReactionsAsync) await node.setReactionsAsync(reactions);
  else node.reactions = reactions;
}

function pageFor(title) {
  let page = figma.root.children.find((p) => p.name === title);
  if (page) {
    // страница уже есть: чистим, чтобы не плодить копии кадров
    for (const child of [...page.children]) child.remove();
  } else {
    page = figma.createPage();
    page.name = title;
  }
  return page;
}

async function buildTheme(theme, manifest, only) {
  const data = manifest[theme];
  const page = pageFor(THEME_TITLES[theme]);
  if (figma.setCurrentPageAsync) await figma.setCurrentPageAsync(page);
  else figma.currentPage = page;

  const nodes = {};
  let index = 0;
  for (const frame of data.frames) {
    if (only && !only.includes(frame.id)) continue;
    const svg = await getText(frame.svg);
    const node = figma.createNodeFromSvg(svg);
    node.name = frame.name;
    node.resize(frame.width, frame.height);
    node.clipsContent = true;
    node.x = (index % COLUMNS) * (frame.width + GAP);
    node.y = Math.floor(index / COLUMNS) * (frame.height + GAP);
    page.appendChild(node);
    nodes[frame.id] = node;
    index += 1;
    print(theme + ": " + frame.name);
  }

  let linkCount = 0;
  for (const link of data.links) {
    const from = nodes[link.from];
    const to = nodes[link.to];
    if (!from || !to) continue;
    const [x, y, w, h] = link.rect;
    const hotspot = figma.createRectangle();
    hotspot.name = "Переход: " + link.label;
    hotspot.resize(Math.max(w, 1), Math.max(h, 1));
    hotspot.x = x;
    hotspot.y = y;
    hotspot.fills = [];
    hotspot.strokes = [];
    from.appendChild(hotspot);
    await setReactions(hotspot, [
      {
        trigger: { type: "ON_CLICK" },
        actions: [
          {
            type: "NODE",
            destinationId: to.id,
            navigation: "NAVIGATE",
            transition: {
              type: "DISSOLVE",
              easing: { type: "EASE_OUT" },
              duration: 0.2,
            },
            preserveScrollPosition: false,
          },
        ],
      },
    ]);
    linkCount += 1;
  }

  const starts = [];
  for (const [id, name] of Object.entries(START_POINTS)) {
    if (nodes[id]) starts.push({ nodeId: nodes[id].id, name });
  }
  try {
    page.flowStartingPoints = starts;
  } catch (error) {
    print("Стартовые точки флоу не заданы: " + error);
  }
  print(theme + ": кадров " + Object.keys(nodes).length + ", переходов " + linkCount);
}

const manifest = await getJson("manifest.json");
const only = typeof ONLY !== "undefined" ? ONLY : null;
for (const theme of typeof THEMES !== "undefined" ? THEMES : ["light", "dark"]) {
  await buildTheme(theme, manifest, only);
}
figma.notify("Макет обновлён");
})();
