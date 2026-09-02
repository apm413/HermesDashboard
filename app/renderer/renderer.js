// renderer.js — клиентский JS чат-панели Hermes Dashboard
// Не требует сборки: vanilla ES2020 + web API.

const $ = (id) => document.getElementById(id);

const log = $('chat-log');
const form = $('chat-form');
const input = $('chat-text');
const suggest = $('chat-suggest');
const statusDot = $('backend-status');
const resizer = $('resizer');
const layout = document.querySelector('.layout');
const modelSelect = $('model-select');
const modelStatus = $('model-status');

let history = [];
let historyIdx = -1;
let commands = [];
let availableModels = [];
let ws = null;
let selectedModel = null;  // Будет загружено из localStorage или с сервера

// === Backend health check ===
async function checkHealth() {
  try {
    const r = await fetch('http://127.0.0.1:5557/chat/commands');
    statusDot.classList.toggle('offline', !r.ok);
    return r.ok;
  } catch (e) {
    statusDot.classList.add('offline');
    return false;
  }
}

// === Команды: подгрузить из backend ===
async function loadCommands() {
  try {
    const r = await fetch('http://127.0.0.1:5557/chat/commands');
    const j = await r.json();
    commands = (j.commands || []).map(c => c.cmd);
  } catch (e) {
    commands = ['help', 'tier1:once', 'tier1:seo', 'tier1:reddit', 'tier1:twitter', 'tier1:analytics',
                'video:demo', 'video:status', 'video:verify-keys', 'video:test-all',
                'budget', 'system', 'logs'];
  }
}

// === Сообщения в лог ===
function addMessage(text, type = 'bot', extra = {}) {
  const div = document.createElement('div');
  div.className = `msg ${type}`;

  if (type === 'exec-success' || type === 'exec-failed') {
    div.innerHTML = `<div>${escapeHtml(text)}</div>` +
                    `<pre class="cmd-block">${escapeHtml(extra.stdout || '')}${extra.stderr ? '\n— stderr —\n' + escapeHtml(extra.stderr) : ''}</pre>` +
                    `<span class="meta">${extra.duration_ms || 0}ms · exit ${extra.exit_code ?? '—'} · ${extra.argv?.join(' ') || ''}</span>`;
  } else {
    div.textContent = text;
  }
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

// === Send message ===
async function send(text) {
  if (!text || !text.trim()) return;
  text = text.trim();

  addMessage(text, 'user');
  history.push(text);
  historyIdx = history.length;

  // Локально: /help
  if (text === '/help' || text === 'help' || text === '?') {
    showHelp();
    return;
  }

  log.classList.add('thinking');
  $('chat-status').textContent = '…';
  try {
    const r = await fetch('http://127.0.0.1:5557/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, model: selectedModel }),
    });
    const j = await r.json();
    handleResponse(j);
  } catch (e) {
    addMessage(`Ошибка сети: ${e.message}. Backend на 5557 недоступен.`, 'error');
  } finally {
    log.classList.remove('thinking');
    $('chat-status').textContent = '⌨';
  }
}

function handleResponse(j) {
  if (!j.ok && !j.expected) {
    addMessage(j.error || 'Неизвестная ошибка', 'error');
    return;
  }
  if (j.type === 'exec') {
    const ok = j.exit_code === 0;
    addMessage(
      ok ? `✓ ${j.cmd}` : (j.expected ? `⚠ ${j.cmd} (exit ${j.exit_code})` : `✕ ${j.cmd} (exit ${j.exit_code})`),
      ok ? 'exec-success' : (j.expected ? 'exec-warning' : 'exec-failed'),
      j
    );
    if (j.hint) addMessage(j.hint, 'system');
  } else if (j.type === 'help') {
    showHelp();
  } else if (j.type === 'echo') {
    addMessage(j.echo, 'bot');
    if (j.hint) addMessage(j.hint, 'system');
  } else {
    addMessage(JSON.stringify(j), 'bot');
  }
}

function showHelp() {
  if (!commands.length) {
    loadCommands().then(_ => showHelp());
    return;
  }
  const lines = ['Доступные команды:'];
  commands.forEach(c => {
    const meta = c.split(':');
    const desc = {
      'tier1:once': 'все tier1-агенты разом',
      'tier1:seo': 'SEO-куратор (tier1)',
      'tier1:reddit': 'пост в Reddit (mock)',
      'tier1:twitter': 'твит (mock)',
      'tier1:analytics': 'аналитика tier1',
      'video:demo': 'демо-сценарий HermeSvideo',
      'video:status': 'бюджет и ключи',
      'video:verify-keys': 'проверить API-ключи',
      'video:test-all': 'smoke-тест агентов',
      'budget': 'текущий бюджет',
      'system': 'CPU/RAM/Disk',
      'logs': 'последние логи',
      'help': 'эта справка',
    }[c] || '';
    lines.push(`  /${c.padEnd(20)} — ${desc}`);
  });
  lines.push('');
  lines.push('Префикс / не обязателен. Просто введи команду.');
  addMessage(lines.join('\n'), 'system');
}

// === Автокомплит ===
function updateSuggest() {
  const q = input.value.trim();
  if (!q.startsWith('/') && !q.match(/^[a-z]/i)) {
    suggest.classList.remove('open');
    return;
  }
  const prefix = q.replace(/^\//, '').toLowerCase();
  const matches = commands.filter(c => c.toLowerCase().startsWith(prefix)).slice(0, 8);
  if (matches.length === 0) {
    suggest.classList.remove('open');
    return;
  }
  suggest.innerHTML = matches.map(c => {
    const desc = {
      'tier1:once': 'все агенты', 'tier1:seo': 'SEO', 'tier1:reddit': 'Reddit',
      'tier1:twitter': 'Twitter', 'tier1:analytics': 'analytics',
      'video:demo': 'демо', 'video:status': 'статус', 'video:verify-keys': 'ключи',
      'video:test-all': 'тест', 'budget': 'бюджет', 'system': 'system', 'logs': 'логи', 'help': 'справка'
    }[c] || '';
    return `<div class="suggest-item" data-cmd="${c}"><span class="cmd">/${c}</span><span class="desc">${desc}</span></div>`;
  }).join('');
  suggest.classList.add('open');

  suggest.querySelectorAll('.suggest-item').forEach(el => {
    el.addEventListener('mousedown', (e) => {
      e.preventDefault();
      input.value = '/' + el.dataset.cmd + ' ';
      suggest.classList.remove('open');
      input.focus();
    });
  });
}

// === Events ===
form.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = input.value;
  input.value = '';
  suggest.classList.remove('open');
  send(text);
});

input.addEventListener('input', updateSuggest);
input.addEventListener('focus', updateSuggest);
input.addEventListener('blur', () => setTimeout(() => suggest.classList.remove('open'), 200));

input.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowUp') {
    if (history.length === 0) return;
    e.preventDefault();
    historyIdx = Math.max(0, historyIdx - 1);
    input.value = history[historyIdx] || '';
  } else if (e.key === 'ArrowDown') {
    if (history.length === 0) return;
    e.preventDefault();
    historyIdx = Math.min(history.length, historyIdx + 1);
    input.value = history[historyIdx] || '';
  } else if (e.key === 'Tab') {
    e.preventDefault();
    const first = suggest.querySelector('.suggest-item');
    if (first) {
      input.value = '/' + first.dataset.cmd + ' ';
      suggest.classList.remove('open');
    }
  } else if (e.key === 'Escape') {
    suggest.classList.remove('open');
  }
});

$('btn-reload').addEventListener('click', () => {
  const iframe = document.querySelector('.dashboard-iframe');
  if (iframe) iframe.contentWindow.location.reload();
});

$('btn-help').addEventListener('click', () => send('/help'));

// === Resizer ===
let dragging = false;
resizer.addEventListener('mousedown', () => { dragging = true; resizer.classList.add('dragging'); });
window.addEventListener('mouseup', () => { dragging = false; resizer.classList.remove('dragging'); });
window.addEventListener('mousemove', (e) => {
  if (!dragging) return;
  const w = window.innerWidth;
  const chatW = Math.max(280, Math.min(700, w - e.clientX));
  layout.style.gridTemplateColumns = `1fr 4px ${chatW}px`;
});

// === Загрузка моделей для dropdown ===
async function loadModels() {
  try {
    const r = await fetch('http://127.0.0.1:5557/chat/models');
    if (!r.ok) return;
    const data = await r.json();
    availableModels = data.models || [];
    const defaultId = data.default || 'minimax/minimax-m2.7:free';

    // Сначала попробуем восстановить выбор из localStorage
    const saved = localStorage.getItem('hermes.chat.model');

    modelSelect.innerHTML = '';

    // Группируем: free сверху, paid ниже
    const free = availableModels.filter(m => m.free);
    const paid = availableModels.filter(m => !m.free);

    if (free.length > 0) {
      const group = document.createElement('optgroup');
      group.label = `🆓 Бесплатные (${free.length})`;
      for (const m of free) {
        const opt = document.createElement('option');
        opt.value = m.id;
        const ctx = typeof m.context === 'number' ? `${(m.context / 1024).toFixed(0)}k` : '';
        opt.textContent = `${m.name || m.id} ${ctx ? `[${ctx}]` : ''}`.trim();
        if (m.id === saved || (!saved && m.id === defaultId)) opt.selected = true;
        group.appendChild(opt);
      }
      modelSelect.appendChild(group);
    }
    if (paid.length > 0) {
      const group = document.createElement('optgroup');
      group.label = `💳 Платные (${paid.length})`;
      for (const m of paid) {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = (m.name || m.id).substring(0, 50);
        if (m.id === saved) opt.selected = true;
        group.appendChild(opt);
      }
      modelSelect.appendChild(group);
    }

    // Статус провайдеров
    const providers = data.providers || [];
    const active = providers.filter(p => p.status === 'active');
    if (active.length > 0) {
      modelStatus.textContent = '●';
      modelStatus.classList.remove('offline');
      const names = active.map(p => p.name).join(', ');
      modelStatus.title = `Активные провайдеры: ${names}`;
    } else {
      modelStatus.textContent = '○';
      modelStatus.classList.add('offline');
      modelStatus.title = 'Нет активных AI-провайдеров. Добавь OPENROUTER_API_KEY в ~/.hermes/.env';
    }

    selectedModel = modelSelect.value || defaultId;
    localStorage.setItem('hermes.chat.model', selectedModel);
  } catch (e) {
    console.warn('loadModels failed:', e);
    modelStatus.classList.add('offline');
    modelStatus.title = 'Ошибка загрузки моделей: ' + e.message;
  }
}

modelSelect.addEventListener('change', () => {
  selectedModel = modelSelect.value;
  try { localStorage.setItem('hermes.chat.model', selectedModel); } catch (e) {}
  const m = availableModels.find(m => m.id === selectedModel);
  if (m) {
    addMessage(`Модель: ${m.name || m.id}${m.free ? ' (free)' : ''}`, 'system');
  }
});

// === Init ===
(async () => {
  await loadCommands();
  const ok = await checkHealth();
  addMessage(
    ok ? 'Backend на 127.0.0.1:5557 — онлайн. Введи /help.'
        : 'Backend недоступен. Убедись что .venv создан и start.bat отработал.',
    'system'
  );
  setInterval(checkHealth, 5000);
  input.focus();

  // Загрузить модели асинхронно (не блокировать init)
  loadModels().then(() => {
    if (selectedModel) {
      const m = availableModels.find(m => m.id === selectedModel);
      const label = m ? (m.name || m.id) : selectedModel;
      addMessage(`AI-модель: ${label}${m && m.free ? ' (free)' : ''}`, 'system');
    }
  });
})();
