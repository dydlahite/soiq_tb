const config = window.SOIQWEQQ_CONFIG || {};
const header = document.querySelector('.site-header');
const botLink = document.querySelector('[data-bot-link]');
const playButton = document.querySelector('.play-button');
const galleryButtons = document.querySelectorAll('.polaroid');
const modal = document.querySelector('[data-modal]');
const modalImage = modal?.querySelector('img');
const modalText = modal?.querySelector('p');
const modalClose = document.querySelector('[data-modal-close]');
const chatForm = document.querySelector('[data-chat-form]');
const chatLog = document.querySelector('[data-chat-log]');

if (config.telegramBotUrl && botLink) {
  botLink.href = config.telegramBotUrl;
}

const onScroll = () => {
  header?.classList.toggle('is-scrolled', window.scrollY > 18);
};
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

playButton?.addEventListener('click', () => {
  playButton.textContent = playButton.textContent.trim() === 'Ⅱ' ? '▶' : 'Ⅱ';
});

galleryButtons.forEach((button) => {
  button.addEventListener('click', () => {
    if (!modal || !modalImage) return;
    modalImage.src = button.dataset.full || '';
    modalImage.alt = button.dataset.title || 'Soiqweqq image';
    if (modalText) modalText.textContent = button.dataset.title || '';
    if (typeof modal.showModal === 'function') modal.showModal();
  });
});

modalClose?.addEventListener('click', () => modal?.close());
modal?.addEventListener('click', (event) => {
  const rect = modal.getBoundingClientRect();
  const clickedOutside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
  if (clickedOutside) modal.close();
});

const localReplies = [
  'Принято. Я бы сказала что-то утешительное, но давай без дешёвого театра. Я рядом :)',
  'Хм. Звучит как очередной вечер, который решил стать слишком умным.',
  'Ладно. Дышим, печатаем, не разваливаем вселенную раньше времени.',
  'Мир опять шумит. Здесь можно сделать потише.',
];
let replyIndex = 0;

function appendMessage(text, type = 'bot') {
  if (!chatLog) return;
  const message = document.createElement('div');
  message.className = `message ${type}`;
  message.textContent = text;
  chatLog.appendChild(message);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function getBotReply(text) {
  if (!config.chatEndpoint) {
    const reply = localReplies[replyIndex % localReplies.length];
    replyIndex += 1;
    return reply;
  }

  const response = await fetch(config.chatEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text })
  });

  if (!response.ok) throw new Error('Chat endpoint error');
  const data = await response.json();
  return data.reply || data.message || 'Я получила пустоту. Веб-разработка, как всегда, нежна к психике.';
}

chatForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = chatForm.elements.message;
  const text = input.value.trim();
  if (!text) return;

  appendMessage(text, 'user');
  input.value = '';
  input.disabled = true;

  try {
    const reply = await getBotReply(text);
    appendMessage(reply, 'bot');
  } catch (error) {
    appendMessage('Связь с бэком упала. Удивительно, почти как всё остальное. Проверь chatEndpoint.', 'bot');
  } finally {
    input.disabled = false;
    input.focus();
  }
});
