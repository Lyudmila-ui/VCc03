const form = document.querySelector("#form");
const urlInput = document.querySelector("#url");
const submitButton = document.querySelector("#submit");
const statusNode = document.querySelector("#status");
const errorNode = document.querySelector("#error");
const logNode = document.querySelector("#log");
const logEmpty = document.querySelector("#log-empty");
const resultEmpty = document.querySelector("#result-empty");
const resultBody = document.querySelector("#result-body");

const steps = new Map();

form.addEventListener("submit", (event) => {
  event.preventDefault();
  startAnalysis(urlInput.value.trim());
});

checkHealth();

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      showError("Сервер анализа не отвечает.");
      return;
    }
    const data = await response.json();
    if (!data.has_key) {
      showError("На сервере не задан ключ DeepSeek. Впишите DEEPSEEK_API_KEY в файл .env и перезапустите контейнеры.");
    }
  } catch {
    showError("Сервер анализа не отвечает.");
  }
}

async function startAnalysis(url) {
  resetOutput();
  setBusy(true);
  setStatus("Запускаю разбор. Обычно это несколько минут.");
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ url }),
    });
    if (!response.ok || !response.body) {
      showError("Сервер не принял ссылку.");
      return;
    }
    await readSse(response, handleEvent);
  } catch {
    showError("Связь с сервером прервалась. Если разбор шёл долго, проверьте, что контейнеры ещё работают.");
  } finally {
    setBusy(false);
  }
}

function handleEvent(event) {
  const data = event.data || {};
  if (event.event === "status") {
    setStatus(data.message || "");
    return;
  }
  if (event.event === "plan") {
    renderPlan(data.steps || []);
    return;
  }
  if (event.event === "step") {
    updateStep(data);
    return;
  }
  if (event.event === "result") {
    showResult(data.text || "");
    return;
  }
  if (event.event === "error") {
    setStatus("");
    showError(data.message || "Разбор остановился.");
    return;
  }
}

function renderPlan(items) {
  logEmpty.hidden = true;
  items.forEach((item, index) => {
    const number = index + 1;
    const step = document.createElement("article");
    step.className = "step";
    step.dataset.index = String(number);
    step.innerHTML = `
      <header>
        <span class="n">${number}</span>
        <h3></h3>
        <span class="state">ждёт</span>
      </header>
      <div class="body prose" hidden></div>
    `;
    step.querySelector("h3").textContent = item.title || `Шаг ${number}`;
    logNode.appendChild(step);
    steps.set(number, step);
  });
}

function updateStep(data) {
  const step = steps.get(Number(data.index));
  if (!step) {
    return;
  }
  if (data.title) {
    step.querySelector("h3").textContent = data.title;
  }
  const state = step.querySelector(".state");
  const body = step.querySelector(".body");
  if (data.status === "running") {
    step.classList.add("is-running");
    state.textContent = "идёт";
    return;
  }
  step.classList.remove("is-running");
  state.textContent = "готово";
  body.hidden = false;
  body.innerHTML = renderProse(data.result || "");
  step.scrollIntoView({ block: "nearest" });
}

function showResult(text) {
  resultEmpty.hidden = true;
  resultBody.hidden = false;
  resultBody.innerHTML = renderProse(text);
}

function resetOutput() {
  hideError();
  steps.clear();
  logNode.querySelectorAll(".step").forEach((node) => node.remove());
  logEmpty.hidden = false;
  resultBody.hidden = true;
  resultBody.innerHTML = "";
  resultEmpty.hidden = false;
}

function setBusy(busy) {
  submitButton.disabled = busy;
  urlInput.disabled = busy;
}

function setStatus(message) {
  statusNode.textContent = message;
}

function showError(message) {
  errorNode.hidden = false;
  errorNode.textContent = message;
}

function hideError() {
  errorNode.hidden = true;
  errorNode.textContent = "";
}

async function readSse(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n");
    let splitAt = buffer.indexOf("\n\n");
    while (splitAt !== -1) {
      const raw = buffer.slice(0, splitAt);
      buffer = buffer.slice(splitAt + 2);
      const parsed = parseSseBlock(raw);
      if (parsed) {
        onEvent(parsed);
      }
      splitAt = buffer.indexOf("\n\n");
    }
  }
}

function parseSseBlock(raw) {
  let name = "message";
  const dataLines = [];
  for (const line of raw.split("\n")) {
    if (!line || line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("event:")) {
      name = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!dataLines.length) {
    return null;
  }
  try {
    return { event: name, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return { event: name, data: { message: dataLines.join("\n") } };
  }
}

function renderProse(raw) {
  const escaped = String(raw)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const lines = escaped.split("\n");
  let html = "";
  let listOpen = false;
  const closeList = () => {
    if (listOpen) {
      html += "</ul>";
      listOpen = false;
    }
  };
  for (const line of lines) {
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      closeList();
      const level = heading[1].length >= 3 ? 4 : 3;
      html += `<h${level}>${inline(heading[2])}</h${level}>`;
      continue;
    }
    const item = /^[-*]\s+(.*)$/.exec(line);
    if (item) {
      if (!listOpen) {
        html += "<ul>";
        listOpen = true;
      }
      html += `<li>${inline(item[1])}</li>`;
      continue;
    }
    closeList();
    if (!line.trim()) {
      continue;
    }
    html += `<p>${inline(line)}</p>`;
  }
  closeList();
  return html;
}

function inline(value) {
  return value.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}
