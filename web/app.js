(() => {
  const panel = document.getElementById('chatPanel');
  const openChat = document.getElementById('openChat');
  const closeChat = document.getElementById('closeChat');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('messageInput');
  const messages = document.getElementById('messages');

  const sessionKey = 'soiqweqq_web_session_id';
  let sessionId = localStorage.getItem(sessionKey);
  if (!sessionId) {
    sessionId = 'web-' + Math.random().toString(16).slice(2) + Date.now().toString(16);
    localStorage.setItem(sessionKey, sessionId);
  }

  function openPanel() {
    if (panel) {
      panel.hidden = false;
      setTimeout(() => input?.focus(), 50);
    }
  }

  function closePanel() {
    if (panel) panel.hidden = true;
  }

  function addMessage(text, type = 'bot') {
    if (!messages) return null;
    const node = document.createElement('div');
    node.className = 'msg msg--' + type;
    node.textContent = text;
    messages.appendChild(node);
    messages.scrollTop = messages.scrollHeight;
    return node;
  }

  async function sendMessage(text) {
    addMessage(text, 'user');
    const typing = addMessage('...', 'bot msg--typing');

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });

      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      typing.remove();
      addMessage(data.answer || 'я зависла. великолепно.', 'bot');
    } catch (error) {
      typing.remove();
      addMessage('API пока не подключен. Дизайн жив, мозг еще на операционном столе. Проверь app_api.py и службу soiq-api.', 'bot msg--error');
    }
  }

  openChat?.addEventListener('click', openPanel);
  closeChat?.addEventListener('click', closePanel);

  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    const text = (input?.value || '').trim();
    if (!text) return;
    input.value = '';
    sendMessage(text);
  });

  if (document.body.classList.contains('chat-page')) {
    input?.focus();
  }
})();
