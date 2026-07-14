const state = { query: "", category: "all" };
const items = globalThis.VIBEEDIT_CATALOG.items;
const categories = ["all", ...new Set(items.map((item) => item.category))];
const catalog = document.querySelector("#catalog");
const template = document.querySelector("#card-template");

for (const category of categories) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = category.toUpperCase();
  button.setAttribute("aria-pressed", category === state.category ? "true" : "false");
  button.addEventListener("click", () => {
    state.category = category;
    for (const sibling of button.parentElement.children) sibling.setAttribute("aria-pressed", sibling === button ? "true" : "false");
    render();
  });
  document.querySelector("#filters").append(button);
}

document.querySelector("#search").addEventListener("input", (event) => {
  state.query = event.currentTarget.value.trim().toLowerCase();
  render();
});

function render() {
  const visible = items.filter((item) => {
    const matchesCategory = state.category === "all" || item.category === state.category;
    const matchesQuery = !state.query || JSON.stringify(item).toLowerCase().includes(state.query);
    return matchesCategory && matchesQuery;
  });
  catalog.replaceChildren(...visible.map(card));
  document.querySelector("#count").textContent = `${String(visible.length).padStart(2, "0")} / ${String(items.length).padStart(2, "0")}`;
  document.querySelector("#empty").hidden = visible.length > 0;
}

function card(item, index) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.style.animationDelay = `${index * 45}ms`;
  node.querySelector(".category").textContent = item.category.toUpperCase();
  node.querySelector(".version").textContent = `V${item.version}`;
  node.querySelector("h2").textContent = item.name.toUpperCase();
  node.querySelector(".description").textContent = item.description;
  node.querySelector(".parameters").textContent = JSON.stringify(item.parameters, null, 2);
  node.querySelector(".compatibility").textContent = `${item.platforms.join(" / ")} · ${item.backends.join(" / ")}`.toUpperCase();
  node.querySelector(".requirements").textContent = requirements(item.requirements);
  node.querySelector(".prompt").textContent = item.prompts[0] || "No prompt supplied.";
  node.querySelector(".python-code").textContent = item.examples.python;
  node.querySelector(".javascript-code").textContent = item.examples.javascript;
  const preview = node.querySelector(".preview");
  preview.classList.toggle("verified", item.preview.status === "verified");
  if (item.preview.status === "verified" && item.preview.uri) {
    const media = document.createElement(item.preview.mediaType?.startsWith("audio/") ? "audio" : "video");
    media.src = `../catalog/${item.preview.uri}`;
    media.controls = true;
    media.preload = "metadata";
    if (media.tagName === "VIDEO") {
      media.muted = true;
      media.playsInline = true;
    }
    preview.append(media);
  } else {
    preview.textContent = `${item.preview.status.toUpperCase()} / ${item.preview.note || "NO MEDIA"}`;
  }
  const identifier = node.querySelector(".identifier");
  identifier.textContent = item.id;
  identifier.addEventListener("click", () => copy(identifier, item.id));
  for (const value of item.tags) {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = value.toUpperCase();
    node.querySelector(".tags").append(tag);
  }
  const promptButton = node.querySelector(".copy-prompt");
  promptButton.addEventListener("click", () => copy(promptButton, item.prompts[0] || ""));
  const pythonButton = node.querySelector(".copy-python");
  pythonButton.addEventListener("click", () => copy(pythonButton, item.examples.python));
  const javascriptButton = node.querySelector(".copy-javascript");
  javascriptButton.addEventListener("click", () => copy(javascriptButton, item.examples.javascript));
  return node;
}

async function copy(button, value) {
  try {
    if (!navigator.clipboard?.writeText) throw new Error("clipboard API unavailable");
    await navigator.clipboard.writeText(value);
  } catch {
    const field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.append(field);
    field.select();
    document.execCommand("copy");
    field.remove();
  }
  const label = button.textContent;
  button.textContent = "COPIED";
  setTimeout(() => { button.textContent = label; }, 900);
}

function requirements(value) {
  const assets = value.assets.length ? `ASSETS: ${value.assets.join(", ")}` : "ASSETS: NONE";
  const models = value.models.length ? `MODELS: ${value.models.join(", ")}` : "MODELS: NONE";
  return `${assets} · ${models}`;
}

render();
