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
const trackTitle = document.getElementById("trackTitle");
const trackArtist = document.getElementById("trackArtist");
const trackProgress = document.getElementById("trackProgress");

const sessionId = (() => {
  const key = "soiqweqq_web_session";
  let value = localStorage.getItem(key);
  if (!value) {
    value = `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(key, value);
  }
  return value;
})();

function openChat() {
  chatWindow?.classList.remove("hidden");
}

function closeChatWindow() {
  chatWindow?.classList.add("hidden");
  setOffline();
}

function setOnline() {
  statusDot?.classList.add("status-online");
  statusDot?.classList.remove("status-offline");
  if (statusText) statusText.textContent = "онлайн";
}

function setOffline() {
  statusDot?.classList.remove("status-online");
  statusDot?.classList.add("status-offline");
  if (statusText) statusText.textContent = "не в сети";
}

document.querySelectorAll(".open-chat").forEach((button) => {
  button.addEventListener("click", openChat);
});

closeChat?.addEventListener("click", closeChatWindow);
minimizeChat?.addEventListener("click", closeChatWindow);

emojiToggle?.addEventListener("click", () => {
  emojiPanel?.classList.toggle("hidden");
});

emojiPanel?.querySelectorAll("button").forEach((button) => {
  button.addEventListener("click", () => {
    chatInput.value += button.textContent;
    chatInput.focus();
  });
});

function messageTime() {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Asia/Krasnoyarsk",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

function addMessage(text, role = "bot") {
  const item = document.createElement("div");
  item.className = `message ${role}`;
  const span = document.createElement("span");
  span.textContent = text;
  item.appendChild(span);

  const time = document.createElement("small");
  time.className = "message-time";
  time.textContent = messageTime();
  item.appendChild(time);

  chatBody.appendChild(item);
  chatBody.scrollTop = chatBody.scrollHeight;
}

function addTyping() {
  const typing = document.createElement("div");
  typing.className = "message bot typing";
  typing.innerHTML = "<span>печатает<span class='dots'>...</span></span>";
  chatBody.appendChild(typing);
  chatBody.scrollTop = chatBody.scrollHeight;
  return typing;
}

async function sendMessage(text) {
  addMessage(text, "user");

  await new Promise((resolve) => setTimeout(resolve, 900 + Math.random() * 1400));
  setOnline();

  const typing = addTyping();

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
    await new Promise((resolve) => setTimeout(resolve, data.pre_typing_delay_ms || 1200));
    typing.remove();

    if (data?.ok) {
      const parts = String(data.answer || "").split(/\n{2,}/).filter(Boolean).slice(0, 4);
      for (const part of parts.length ? parts : [data.answer]) {
        addMessage(part.trim(), "bot");
        await new Promise((resolve) => setTimeout(resolve, 450 + Math.random() * 900));
      }
      setOnline();
    } else {
      addMessage(data?.answer || "что-то пошло не так. мда.", "bot");
    }
  } catch (error) {
    typing.remove();
    addMessage("сайт опять подавился проводами. попробуй еще раз.", "bot");
  }
}

chatForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  sendMessage(text);
});

chatInput?.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
});

chatInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm?.requestSubmit();
  }
});

async function loadTrackInfo() {
  try {
    const response = await fetch("/api/track", { cache: "no-store" });
    const data = await response.json();
    if (data?.ok) {
      if (trackTitle) trackTitle.textContent = data.title || "Неизвестно";
      if (trackArtist) trackArtist.textContent = data.artist || "Неизвестен";
      if (trackProgress) trackProgress.style.width = `${Math.max(0, Math.min(1, data.progress ?? .82)) * 100}%`;
    }
  } catch (_) {}
}

loadTrackInfo();
setInterval(loadTrackInfo, 60000);

document.querySelectorAll(".bulb, .photo-bulb").forEach((bulb) => {
  bulb.addEventListener("mouseenter", () => {
    bulb.style.animationDuration = `${1.1 + Math.random() * 1.2}s`;
  });
  bulb.addEventListener("mouseleave", () => {
    bulb.style.animationDuration = "";
  });
});
