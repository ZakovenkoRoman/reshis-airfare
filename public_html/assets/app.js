const byId = id => document.getElementById(id);
const forecastForm = byId("forecast-form");
const results = document.querySelector(".results");
const forecastError = byId("forecast-error");
const canvas = byId("demand-chart");
const format = new Intl.NumberFormat("ru-RU");
let currentForecast;

async function api(path, options) {
  const unavailable = "Сервис временно недоступен. Попробуйте ещё раз.";
  const response = await fetch(new URL(path, document.baseURI), options)
    .catch(() => { throw new Error(unavailable); });
  const json = await response.json().catch(() => { throw new Error(unavailable); });
  if (!response.ok) throw new Error(json.error || unavailable);
  return json;
}

function showError(element, error) {
  element.hidden = !error;
  element.textContent = error?.message || "";
}

function drawChart() {
  if (!currentForecast) return;
  const { scenarios, seats } = currentForecast;
  const { width, height } = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  const pixelWidth = Math.round(width * scale);
  const pixelHeight = Math.round(height * scale);
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.font = "12px sans-serif";
  ctx.textBaseline = "middle";

  const left = 56;
  const right = width - 19;
  const bottom = height - 43;
  const top = 16;
  const step = Math.max(50, Math.ceil(Math.max(seats, ...scenarios.map(s => s.demand)) / 250) * 50);
  const x = i => left + i * (right - left) / 8;
  const y = n => bottom - n * (bottom - top) / (step * 5);

  ctx.textAlign = "right";
  for (let i = 0; i <= 5; i++) {
    const n = i * step;
    ctx.strokeStyle = "#dce7e0";
    ctx.beginPath();
    ctx.moveTo(left, y(n));
    ctx.lineTo(right, y(n));
    ctx.stroke();
    ctx.fillStyle = "#546966";
    ctx.fillText(format.format(n), left - 8, y(n));
  }

  ctx.strokeStyle = "#ad582c";
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(left, y(seats));
  ctx.lineTo(right, y(seats));
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.strokeStyle = "#287357";
  const line = new Path2D();
  scenarios.forEach((item, i) => line.lineTo(x(i), y(item.demand)));
  const area = new Path2D(line);
  area.lineTo(right, bottom);
  area.lineTo(left, bottom);
  area.closePath();
  ctx.fillStyle = "#28735712";
  ctx.fill(area);
  ctx.stroke(line);
  ctx.textAlign = "center";
  scenarios.forEach((item, i) => {
    ctx.fillStyle = "#287357";
    ctx.beginPath();
    ctx.arc(x(i), y(item.demand), i === 4 ? 5 : 3, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = "#546966";
    if (width > 420 || i % 2 === 0) {
      ctx.fillText(format.format(item.quantile), x(i), bottom + 17);
    }
  });
  ctx.fillText("Квантиль", (left + right) / 2, bottom + 35);
}

function renderForecast(data) {
  currentForecast = data;
  byId("flight").textContent = data.route;
  byId("flight-date").textContent = data.date.split("-").reverse().join(".");
  for (const key of ["seats", "sales", "free"]) byId(key).textContent = format.format(data[key]);
  byId("chart-price").textContent = format.format(data.price) + " ₽";
  byId("demand-summary").textContent = "Медианный спрос: " + format.format(data.demand) + " чел.";
  byId("capacity-legend").textContent = "Вместимость: " + format.format(data.seats) + " мест";
  byId("scenarios").replaceChildren(...data.scenarios.map(scenario => {
    const row = document.createElement("tr");
    for (const key of ["quantile", "demand", "sales"]) {
      row.insertCell().textContent = format.format(scenario[key]);
    }
    return row;
  }));
  drawChart();
}

async function loadForecast(preview = false) {
  const button = byId("forecast-submit");
  const label = byId("forecast-submit-label");
  button.disabled = true;
  label.textContent = "Рассчитываем…";
  results.setAttribute("aria-busy", "true");
  showError(forecastError);
  try {
    const query = new URLSearchParams(new FormData(forecastForm));
    if (preview) query.set("preview", "1");
    renderForecast(await api("api/forecast?" + query));
  } catch (error) {
    showError(forecastError, error);
  } finally {
    button.disabled = false;
    label.textContent = "Рассчитать прогноз";
    results.setAttribute("aria-busy", "false");
  }
}

forecastForm.addEventListener("submit", event => {
  event.preventDefault();
  loadForecast();
});
byId("base-price").addEventListener("click", () => {
  forecastForm.elements.price.value = forecastForm.elements.route.selectedOptions[0].dataset.price;
});
new ResizeObserver(drawChart).observe(canvas);
loadForecast(true);

const dialog = byId("auth");
const authForm = byId("auth-form");
const accountButton = byId("account-button");
const authError = byId("auth-error");
const authSubmit = byId("auth-submit");
let session = {};
let authMode = "login";

function renderSession(data) {
  session = data;
  byId("account-name").textContent = data.login || "";
  accountButton.textContent = data.login ? "Выйти" : "Войти";
}

function setAuthMode(mode) {
  authMode = mode;
  const registering = mode === "register";
  byId("auth-title").textContent = registering ? "Регистрация" : "Вход";
  authSubmit.textContent = registering ? "Зарегистрироваться" : "Войти";
  byId("auth-toggle").textContent = registering ? "Уже есть аккаунт" : "Создать аккаунт";
  authForm.elements.password.autocomplete = registering ? "new-password" : "current-password";
  showError(authError);
}

async function changeSession(action, body = {}) {
  if (!session.csrf) renderSession(await api("api/session"));
  renderSession(await api("api/session/" + action, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf },
    body: JSON.stringify(body),
  }));
}

accountButton.addEventListener("click", async () => {
  if (!session.login) {
    authForm.reset();
    setAuthMode("login");
    dialog.showModal();
    return;
  }
  accountButton.disabled = true;
  try {
    await changeSession("logout");
    showError(byId("account-error"));
  } catch (error) {
    showError(byId("account-error"), error);
  } finally {
    accountButton.disabled = false;
  }
});
byId("auth-close").addEventListener("click", () => dialog.close());
byId("auth-toggle").addEventListener("click", () => setAuthMode(authMode === "login" ? "register" : "login"));
authForm.addEventListener("submit", async event => {
  event.preventDefault();
  authSubmit.disabled = true;
  showError(authError);
  try {
    await changeSession(authMode, Object.fromEntries(new FormData(authForm)));
    dialog.close();
    authForm.reset();
  } catch (error) {
    showError(authError, error);
  } finally {
    authSubmit.disabled = false;
  }
});
api("api/session").then(renderSession).catch(error => showError(byId("account-error"), error));
