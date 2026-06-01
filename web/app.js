const TELEGRAM_BOT_URL = "https://t.me/soiqweqq_bot";

document.querySelectorAll("[data-telegram-link]").forEach((el) => {
  el.href = TELEGRAM_BOT_URL;
});

const chatWindow = document.getElementById("chatWindow");
const chatBody = document.getElementById("chatBody");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const closeChat = document.getElementById("closeChat");
const minimizeChat = document.getElementById("minimizeChat");
const emojiToggle = document.querySelector(".emoji-toggle");
const emojiPanel = document.getElementById("emojiPanel");
const statusDot = document.querySelector(".status-dot");
const statusText = document.querySelector(".status-text");

const sessionId = (() => {
  const key = "soiqweqq_web_session";
  let value = localStorage.getItem(key);
  if (!value) {
    value = `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(key, value);
  }
  return value;
})();

function krasTime() {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Asia/Krasnoyarsk",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

function setStatus(mode, text) {
  if (!statusDot || !statusText) return;
  statusDot.className = `status-dot status-${mode}`;
  statusText.textContent = text;
}

function openChat() {
  if (!chatWindow) return;
  chatWindow.classList.remove("hidden");
  setTimeout(() => chatInput?.focus(), 60);
}

function closeOrHideChat() {
  chatWindow?.classList.add("hidden");
  setStatus("offline", "не в сети");
}

document.querySelectorAll(".open-chat").forEach((button) => button.addEventListener("click", openChat));
closeChat?.addEventListener("click", closeOrHideChat);
minimizeChat?.addEventListener("click", () => chatWindow?.classList.add("hidden"));

emojiToggle?.addEventListener("click", () => emojiPanel?.classList.toggle("hidden"));
emojiPanel?.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button || !chatInput) return;
  chatInput.value += button.textContent;
  chatInput.focus();
});

function addMessage(role, text, extraClass = "") {
  if (!chatBody) return null;
  const message = document.createElement("div");
  message.className = `message ${role} ${extraClass}`.trim();
  const span = document.createElement("span");
  span.textContent = text;
  const time = document.createElement("time");
  time.textContent = krasTime();
  message.append(span, time);
  chatBody.appendChild(message);
  chatBody.scrollTop = chatBody.scrollHeight;
  return message;
}

function autosizeTextarea() {
  if (!chatInput) return;
  chatInput.style.height = "auto";
  chatInput.style.height = `${Math.min(chatInput.scrollHeight, 150)}px`;
}
chatInput?.addEventListener("input", autosizeTextarea);

chatInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm?.requestSubmit();
  }
});

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

async function sendMessage(text) {
  addMessage("user", text);
  chatInput.value = "";
  autosizeTextarea();

  setStatus("offline", "не в сети");
  await sleep(900 + Math.random() * 1700);
  const typing = addMessage("bot", "печатает…", "typing");
  setStatus("online", "онлайн");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
        client_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        client_time: new Date().toISOString(),
      }),
    });
    const data = await response.json();
    await sleep(data?.pre_typing_delay_ms || 900);
    typing?.remove();
    addMessage("bot", data?.answer || "мда. оно сломалось. неожиданно, но не удивительно.");
    setStatus("online", "онлайн");
  } catch (error) {
    typing?.remove();
    addMessage("bot", "сервер не ответил. великолепно. техника снова делает вид, что она живая.");
    setStatus("offline", "не в сети");
  }
}

chatForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = chatInput?.value.trim();
  if (!text) return;
  openChat();
  sendMessage(text);
});

let afkTimer = null;
function resetAfk() {
  clearTimeout(afkTimer);
  afkTimer = setTimeout(() => {
    if (!chatWindow?.classList.contains("hidden")) setStatus("afk", "afk");
  }, 180000);
}
["mousemove", "keydown", "touchstart", "click"].forEach((eventName) => document.addEventListener(eventName, resetAfk, { passive: true }));
resetAfk();
