/*
 * Telegram Web · BW Telegram API
 * Vanilla JS client for the /api/telegramweb endpoints.
 *
 * The chat keeps the reading position stable while attachments are
 * downloading: every media frame reserves its final size from the
 * width/height returned by the API, and a scroll anchor is restored after
 * any DOM change that happens above the viewport.
 */
(() => {
'use strict';

/* ------------------------------------------------------------------ */
/* helpers                                                             */
/* ------------------------------------------------------------------ */

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
const API = '/api/telegramweb';
const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
}[c]));

const pad2 = (n) => String(n).padStart(2, '0');
const hm = (date) => `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;

function parseDate(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function dayKey(value) {
  const d = parseDate(value);
  if (!d) return 'unknown';
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function timeShort(value) {
  const d = parseDate(value);
  if (!d) return '';
  const now = new Date();
  if (sameDay(d, now)) return hm(d);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(d, yesterday)) return 'Вчера';
  if (d.getFullYear() === now.getFullYear()) {
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  }
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function dateLabel(value) {
  const d = parseDate(value);
  if (!d) return '';
  const now = new Date();
  if (sameDay(d, now)) return 'Сегодня';
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(d, yesterday)) return 'Вчера';
  if (d.getFullYear() === now.getFullYear()) {
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
  }
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

function fmtDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const m = Math.floor(total / 60);
  const s = total % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}:${pad2(m % 60)}:${pad2(s)}`;
  }
  return `${m}:${pad2(s)}`;
}

function fmtBytes(bytes) {
  const size = Number(bytes) || 0;
  if (!size) return '';
  const units = ['Б', 'КБ', 'МБ', 'ГБ'];
  let value = size;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value >= 10 || unit === 0 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

const AVATAR_COLORS = [
  ['#e17076', '#c8555c'], ['#faa774', '#e08b4e'], ['#a695e7', '#8a74d6'],
  ['#7bc862', '#5fae47'], ['#6ec9cb', '#4aa8ab'], ['#65aadd', '#4a8dc0'],
  ['#ee7aae', '#d15c94'],
];

function colorFor(seed) {
  const text = String(seed ?? '');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) % 100000;
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

function initialsFor(name) {
  const text = String(name || '?').trim();
  if (!text) return '?';
  const parts = text.split(/\s+/).slice(0, 2);
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function presenceLabel(presence) {
  if (!presence) return '';
  if (presence.online) return 'онлайн';
  if (presence.last_seen) {
    const d = parseDate(presence.last_seen);
    if (d) return `был(а) в сети ${d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })} в ${hm(d)}`;
  }
  return presence.label || '';
}

const URL_RE = /(https?:\/\/[^\s<]+|www\.[^\s<]+|@[A-Za-z0-9_]{3,})/g;

function linkify(text) {
  const source = String(text ?? '');
  let out = '';
  let last = 0;
  let match;
  URL_RE.lastIndex = 0;
  while ((match = URL_RE.exec(source)) !== null) {
    out += esc(source.slice(last, match.index));
    const raw = match[0];
    if (raw.startsWith('@')) {
      out += `<a href="https://t.me/${esc(raw.slice(1))}" target="_blank" rel="noopener noreferrer">${esc(raw)}</a>`;
    } else {
      const href = raw.startsWith('www.') ? `https://${raw}` : raw;
      out += `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(raw)}</a>`;
    }
    last = match.index + raw.length;
  }
  out += esc(source.slice(last));
  return out.replace(/\n/g, '<br>');
}

/* ------------------------------------------------------------------ */
/* state                                                               */
/* ------------------------------------------------------------------ */

const state = {
  token: localStorage.getItem('tw_token') || '',
  accountId: localStorage.getItem('tw_account_id') || 'default',
  me: null,
  dialogs: [],
  dialog: null,
  peer: null,
  chatGen: 0,
  messages: [],
  rows: new Map(),
  stick: true,
  unreadWhileAway: 0,
  olderState: 'idle',
  pollTimer: null,
  dialogsTimer: null,
  presenceTimer: null,
  sending: false,
  pendingFile: null,
  pendingPreview: null,
  searchQuery: '',
  avatarUrls: new Map(),
  avatarMisses: new Set(),
  mediaUrls: new Set(),
  mediaObserver: null,
  settings: null,
  lightboxUrl: null,
  lightboxId: null,
  lightboxName: null,
  pendingAccountId: '',
  dragDepth: 0,
};

const els = {};

function cacheEls() {
  const ids = [
    'loginScreen', 'loginForm', 'loginUser', 'loginPass', 'passToggle', 'loginBtn', 'loginStatus',
    'accountsScreen', 'accountsList', 'accountsStatus', 'addAccountBtn', 'logoutAccountsBtn',
    'addAccountScreen', 'addPhoneStep', 'addCodeStep', 'addPasswordStep',
    'addPhone', 'addCode', 'addPassword', 'addAccountStatus',
    'requestCodeBtn', 'submitCodeBtn', 'submitPasswordBtn', 'backToAccountsBtn',
    'app', 'sidebar', 'sideMenuBtn', 'sideMenu', 'menuSettings', 'menuAccounts', 'menuLogout',
    'search', 'dialogs', 'meRow', 'meAvatar', 'meName', 'meStatus',
    'chat', 'backBtn', 'peerBtn', 'chatAvatar', 'chatName', 'chatMeta', 'chatMenuBtn',
    'messages', 'messagesInner', 'chatEmpty', 'jumpDown', 'jumpCount',
    'composer', 'attachMenu', 'attachBtn', 'fileInput', 'composeBox', 'compose', 'sendBtn',
    'attachPreview', 'attachPreviewThumb', 'attachPreviewName', 'attachPreviewSize', 'attachPreviewRemove',
    'dropOverlay', 'lightbox', 'lightboxBody', 'lightboxClose', 'lightboxDownload',
    'settingsModal', 'settingsClose', 'settingsCancel', 'settingsSave', 'settingsStatus',
    'mediaDownloadMode', 'mediaAutoDownload', 'mediaExcluded', 'mediaAutoCleanup', 'mediaTtl',
    'mediaStorage', 'clearMediaCache', 'toast',
  ];
  ids.forEach((id) => { els[id] = document.getElementById(id); });
}

/* ------------------------------------------------------------------ */
/* api                                                                 */
/* ------------------------------------------------------------------ */

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function api(path, options = {}, { raw = false } = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  headers['X-Telegram-Account'] = state.accountId || 'default';

  let response;
  try {
    response = await fetch(API + path, { ...options, headers });
  } catch (error) {
    throw new ApiError('Нет связи с сервером', 0);
  }

  if (response.status === 401 && path !== '/auth/login') {
    signedOut('Сессия истекла, войдите заново');
    throw new ApiError('Сессия недействительна', 401);
  }
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      message = data.detail || data.error || message;
    } catch (error) { /* not json */ }
    throw new ApiError(message, response.status);
  }
  if (raw) return response;
  const type = response.headers.get('content-type') || '';
  if (type.includes('application/json')) return response.json();
  return response;
}

async function apiBlobUrl(path) {
  const response = await api(path, {}, { raw: true });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  state.mediaUrls.add(url);
  return url;
}

function toast(message, isError = false) {
  const el = els.toast;
  if (!el) return;
  el.textContent = message;
  el.className = `toast${isError ? ' error' : ''}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add('hidden'), 3800);
}

/* ------------------------------------------------------------------ */
/* auth                                                                */
/* ------------------------------------------------------------------ */

function showScreen(name) {
  ['loginScreen', 'accountsScreen', 'addAccountScreen', 'app'].forEach((id) => {
    els[id].classList.toggle('hidden', id !== name);
  });
  if (name !== 'app') els.app.classList.remove('chat-open');
  if (name === 'app') els.app.classList.toggle('no-chat', !state.peer);
}

function signedOut(message) {
  clearTimers();
  state.token = '';
  state.me = null;
  state.dialogs = [];
  state.dialog = null;
  state.peer = null;
  localStorage.removeItem('tw_token');
  localStorage.removeItem('tw_account_id');
  state.accountId = 'default';
  revokeMediaUrls();
  revokeAvatarUrls();
  showScreen('loginScreen');
  if (message) setStatus(els.loginStatus, message, true);
}

function setStatus(el, text, isError = false, isOk = false) {
  if (!el) return;
  el.textContent = text || '';
  el.className = `form-status${isError ? ' error' : ''}${isOk ? ' ok' : ''}`;
}

async function login(event) {
  if (event) event.preventDefault();
  const username = els.loginUser.value.trim();
  const password = els.loginPass.value;
  if (!username || !password) {
    setStatus(els.loginStatus, 'Введите логин и пароль', true);
    return;
  }
  els.loginBtn.disabled = true;
  setStatus(els.loginStatus, 'Вход…');
  try {
    const response = await fetch(`${location.origin}${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Ошибка авторизации');
    if (!data.token) throw new Error('Сервер не вернул токен');
    state.token = data.token;
    localStorage.setItem('tw_token', state.token);
    els.loginPass.value = '';
    setStatus(els.loginStatus, '');
    await start();
  } catch (error) {
    setStatus(els.loginStatus, error.message, true);
  } finally {
    els.loginBtn.disabled = false;
  }
}

async function start() {
  state.accountId = 'default';
  localStorage.setItem('tw_account_id', state.accountId);
  showScreen('accountsScreen');
  await loadAccounts();
}

async function loadAccounts() {
  els.accountsList.innerHTML = '<div class="list-placeholder">Загрузка аккаунтов…</div>';
  try {
    const data = await api('/accounts');
    renderAccounts(data.accounts || []);
  } catch (error) {
    els.accountsList.innerHTML = `<div class="list-placeholder">Не удалось загрузить аккаунты<br><small>${esc(error.message)}</small></div>`;
    setStatus(els.accountsStatus, 'Проверьте соединение и попробуйте снова', true);
  }
}

function renderAccounts(accounts) {
  const box = els.accountsList;
  box.innerHTML = '';
  if (!accounts.length) {
    box.innerHTML = '<div class="list-placeholder">Аккаунтов пока нет</div>';
    setStatus(els.accountsStatus, 'Добавьте Telegram-аккаунт, чтобы начать');
    return;
  }
  accounts.forEach((account) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'account-item';
    button.disabled = !account.authorized;

    const avatar = document.createElement('span');
    avatar.className = 'avatar avatar-46';
    paintInitials(avatar, account.label || 'Telegram', account.id);

    const copy = document.createElement('span');
    copy.className = 'account-copy';
    const subtitle = [
      account.username ? `@${account.username}` : '',
      account.phone || '',
      account.authorized ? 'авторизован' : 'требуется вход',
    ].filter(Boolean).join(' · ');
    copy.innerHTML = `<span class="account-name">${esc(account.label || 'Telegram')}</span><span class="account-sub">${esc(subtitle)}</span>`;

    const mark = document.createElement('span');
    mark.className = `account-mark${account.authorized ? '' : ' off'}`;
    mark.textContent = account.authorized ? '●' : '○';

    button.append(avatar, copy, mark);
    button.addEventListener('click', () => selectAccount(account));
    box.appendChild(button);
    if (account.authorized) applyAvatar(avatar, account.id, account.label || 'Telegram');
  });
  const usable = accounts.filter((a) => a.authorized).length;
  setStatus(els.accountsStatus, usable
    ? 'Выберите аккаунт, чтобы открыть чаты'
    : 'Авторизуйте аккаунт, чтобы открыть чаты');
}

async function selectAccount(account) {
  if (!account.authorized) return;
  state.accountId = account.id;
  localStorage.setItem('tw_account_id', state.accountId);
  showScreen('app');
  els.meStatus.textContent = 'Подключение…';
  els.meStatus.classList.remove('danger');
  try {
    const status = await api('/tg/status');
    if (!status.authorized) throw new Error('Этот Telegram-аккаунт не авторизован');
    setMe(status.user);
    await refreshDialogs();
    updateComposerUi();
    startTimers();
  } catch (error) {
    toast(error.message, true);
    backToAccounts();
  }
}

function setMe(user) {
  state.me = user;
  if (!user) {
    els.meName.textContent = 'Telegram';
    els.meStatus.textContent = 'аккаунт подключён';
    return;
  }
  const name = `${user.first_name || ''} ${user.last_name || ''}`.trim()
    || user.username
    || 'Telegram';
  els.meName.textContent = name;
  els.meStatus.textContent = user.username ? `@${user.username}` : 'аккаунт подключён';
  els.meStatus.classList.remove('danger');
  paintInitials(els.meAvatar, name, user.id || user.username || 'me');
  applyAvatar(els.meAvatar, 'me', name);
}

function backToAccounts() {
  clearTimers();
  state.peer = null;
  state.dialog = null;
  state.dialogs = [];
  state.accountId = 'default';
  localStorage.setItem('tw_account_id', state.accountId);
  state.chatGen += 1;
  revokeMediaUrls();
  showScreen('accountsScreen');
  loadAccounts();
}

function showAddAccount() {
  state.pendingAccountId = '';
  state.accountId = 'default';
  showScreen('addAccountScreen');
  els.addPhoneStep.classList.remove('hidden');
  els.addCodeStep.classList.add('hidden');
  els.addPasswordStep.classList.add('hidden');
  setStatus(els.addAccountStatus, '');
  els.addPhone.focus();
}

async function requestAccountCode() {
  const phone = els.addPhone.value.trim();
  if (!phone) { setStatus(els.addAccountStatus, 'Введите номер телефона', true); return; }
  els.requestCodeBtn.disabled = true;
  setStatus(els.addAccountStatus, 'Отправляем код Telegram…');
  try {
    const result = await api('/accounts/add/send_code', {
      method: 'POST',
      body: JSON.stringify({ phone }),
    });
    state.pendingAccountId = result.account_id;
    state.accountId = result.account_id;
    els.addPhoneStep.classList.add('hidden');
    els.addCodeStep.classList.remove('hidden');
    els.addCode.focus();
    setStatus(els.addAccountStatus, 'Код отправлен. Введите его ниже.');
  } catch (error) {
    setStatus(els.addAccountStatus, error.message, true);
  } finally {
    els.requestCodeBtn.disabled = false;
  }
}

async function submitAccountCode() {
  const code = els.addCode.value.trim();
  if (!code) { setStatus(els.addAccountStatus, 'Введите код из Telegram', true); return; }
  els.submitCodeBtn.disabled = true;
  setStatus(els.addAccountStatus, 'Проверяем код…');
  try {
    const result = await api('/accounts/add/sign_in', {
      method: 'POST',
      body: JSON.stringify({ account_id: state.pendingAccountId, code }),
    });
    if (result.password_required) {
      els.addCodeStep.classList.add('hidden');
      els.addPasswordStep.classList.remove('hidden');
      els.addPassword.focus();
      setStatus(els.addAccountStatus, 'Для аккаунта требуется пароль 2FA.');
      return;
    }
    await finishAddAccount();
  } catch (error) {
    setStatus(els.addAccountStatus, error.message, true);
  } finally {
    els.submitCodeBtn.disabled = false;
  }
}

async function submitAccountPassword() {
  const password = els.addPassword.value;
  if (!password) { setStatus(els.addAccountStatus, 'Введите пароль 2FA', true); return; }
  els.submitPasswordBtn.disabled = true;
  setStatus(els.addAccountStatus, 'Проверяем пароль…');
  try {
    await api('/accounts/add/password', {
      method: 'POST',
      body: JSON.stringify({ account_id: state.pendingAccountId, password }),
    });
    await finishAddAccount();
  } catch (error) {
    setStatus(els.addAccountStatus, error.message, true);
  } finally {
    els.submitPasswordBtn.disabled = false;
  }
}

async function finishAddAccount() {
  state.accountId = 'default';
  state.pendingAccountId = '';
  els.addAccount.value = '';
  els.addPassword.value = '';
  showScreen('accountsScreen');
  await loadAccounts();
}

/* ------------------------------------------------------------------ */
/* avatars                                                             */
/* ------------------------------------------------------------------ */

function paintInitials(el, name, seed) {
  if (!el) return;
  const [from, to] = colorFor(seed ?? name);
  el.style.background = `linear-gradient(140deg, ${from}, ${to})`;
  el.textContent = initialsFor(name);
}

async function avatarUrl(peer) {
  const key = String(peer);
  if (state.avatarUrls.has(key)) return state.avatarUrls.get(key);
  if (state.avatarMisses.has(key)) return null;
  try {
    const response = await api(`/avatar/${encodeURIComponent(key)}`, {}, { raw: true });
    const blob = await response.blob();
    if (!blob.size) throw new Error('empty');
    const url = URL.createObjectURL(blob);
    state.avatarUrls.set(key, url);
    return url;
  } catch (error) {
    state.avatarMisses.add(key);
    return null;
  }
}

const avatarQueue = new Set();

async function applyAvatar(el, peer, name) {
  if (!el) return;
  const key = String(peer);
  const cached = state.avatarUrls.get(key);
  if (cached) {
    if (el.dataset.avatarKey !== key) {
      el.dataset.avatarKey = key;
      const dot = el.querySelector('.online-dot');
      el.innerHTML = `<img src="${cached}" alt="">`;
      if (dot) el.appendChild(dot);
    }
    return;
  }
  if (state.avatarMisses.has(key) || avatarQueue.has(key)) return;
  avatarQueue.add(key);
  const url = await avatarUrl(key);
  avatarQueue.delete(key);
  if (url && el.isConnected) {
    el.dataset.avatarKey = key;
    const dot = el.querySelector('.online-dot');
    el.innerHTML = `<img src="${url}" alt="">`;
    if (dot) el.appendChild(dot);
  }
}

function revokeAvatarUrls() {
  state.avatarUrls.forEach((url) => URL.revokeObjectURL(url));
  state.avatarUrls.clear();
  state.avatarMisses.clear();
}

/* ------------------------------------------------------------------ */
/* dialogs                                                             */
/* ------------------------------------------------------------------ */

const dialogAvatarObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    dialogAvatarObserver.unobserve(entry.target);
    const el = entry.target;
    const peer = el.dataset.avatarPeer;
    const name = el.dataset.avatarName || '';
    if (peer) applyAvatar(el, peer, name);
  });
}, { rootMargin: '200px 0px' });

async function refreshDialogs({ silent = false } = {}) {
  try {
    let list;
    try {
      list = await api('/dialogs-with-presence?limit=100');
    } catch (error) {
      if (error.status !== 404 && error.status !== 405) throw error;
      list = await api('/dialogs?limit=100');
    }
    if (!Array.isArray(list)) throw new Error('API вернул неверный список диалогов');
    list = list.map((dialog) => {
      if (dialog.kind) return dialog;
      const kind = dialog.type === 'User' ? 'user' : dialog.type === 'Channel' ? 'channel' : 'group';
      return { ...dialog, kind, is_user: kind === 'user' };
    });
    state.dialogs = list;
    if (state.dialog) {
      const fresh = list.find((item) => String(item.id) === String(state.dialog.id));
      if (fresh) {
        state.dialog = fresh;
        setChatHeader(fresh);
      }
    }
    renderDialogs();
  } catch (error) {
    if (!silent) {
      els.dialogs.innerHTML = `<div class="list-placeholder">Не удалось загрузить диалоги<br><small>${esc(error.message)}</small><br>
        <button class="btn-ghost" type="button" id="dialogRetry" style="width:auto;margin:12px auto 0;padding:8px 14px">Повторить</button></div>`;
      $('#dialogRetry')?.addEventListener('click', () => refreshDialogs());
    }
  }
}

function renderDialogs() {
  const query = state.searchQuery.trim().toLowerCase();
  const list = query
    ? state.dialogs.filter((d) => `${d.name || ''} ${d.username || ''} ${d.last_text || ''}`.toLowerCase().includes(query))
    : state.dialogs;

  const box = els.dialogs;
  box.innerHTML = '';
  if (!list.length) {
    box.innerHTML = `<div class="list-placeholder">${query ? 'Ничего не найдено' : 'Нет диалогов'}</div>`;
    return;
  }

  list.forEach((dialog) => {
    const active = state.dialog && String(dialog.id) === String(state.dialog.id);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `dialog${active ? ' active' : ''}`;
    button.dataset.id = String(dialog.id);

    const avatar = document.createElement('span');
    avatar.className = 'avatar';
    avatar.dataset.avatarPeer = String(dialog.id);
    avatar.dataset.avatarName = dialog.name || dialog.username || '';
    paintInitials(avatar, dialog.name || dialog.username || '?', dialog.id);
    const cachedAvatar = state.avatarUrls.get(String(dialog.id));
    if (cachedAvatar) {
      avatar.innerHTML = `<img src="${cachedAvatar}" alt="">`;
    } else if (!state.avatarMisses.has(String(dialog.id))) {
      dialogAvatarObserver.observe(avatar);
    }
    if (dialog.kind === 'user' && dialog.presence && dialog.presence.online) {
      const dot = document.createElement('span');
      dot.className = 'online-dot';
      avatar.appendChild(dot);
    }

    const unread = Number(dialog.unread) || 0;
    const preview = buildPreview(dialog);

    const body = document.createElement('span');
    body.className = 'dialog-body';
    body.innerHTML = `
      <span class="dialog-top">
        ${dialog.pinned ? '<svg class="icon" style="width:14px;height:14px"><use href="#i-pin"/></svg>' : ''}
        <span class="dialog-name">${esc(dialog.name || dialog.username || dialog.id)}</span>
        <span class="dialog-time">${esc(timeShort(dialog.last_date))}</span>
      </span>
      <span class="dialog-bottom">
        <span class="dialog-preview">${preview}</span>
        ${unread ? `<span class="unread${dialog.muted ? ' muted' : ''}">${unread > 99 ? '99+' : unread}</span>` : ''}
        ${!unread && dialog.muted ? '<span class="dialog-flags"><svg class="icon"><use href="#i-mute"/></svg></span>' : ''}
      </span>`;

    button.append(avatar, body);
    button.addEventListener('click', () => openChat(dialog));
    box.appendChild(button);
  });

  const activeEl = box.querySelector('.dialog.active');
  if (activeEl && !document.hidden) {
    const boxRect = box.getBoundingClientRect();
    const elRect = activeEl.getBoundingClientRect();
    if (elRect.top < boxRect.top || elRect.bottom > boxRect.bottom) {
      activeEl.scrollIntoView({ block: 'nearest' });
    }
  }
}

function buildPreview(dialog) {
  if (dialog.last_text) {
    const prefix = dialog.last_out ? '<span class="out-prefix">Вы: </span>' : '';
    return prefix + esc(dialog.last_text);
  }
  if (dialog.kind === 'channel') return 'канал';
  if (dialog.kind === 'group') return 'группа';
  return 'нет сообщений';
}

function setChatHeader(dialog) {
  if (!dialog) return;
  els.chatName.textContent = dialog.name || dialog.username || dialog.id;
  let status = '';
  if (dialog.is_user) status = presenceLabel(dialog.presence);
  else if (dialog.kind === 'channel') status = 'канал';
  else status = 'группа';
  els.chatMeta.textContent = status || (dialog.username ? `@${dialog.username}` : '');
  const online = Boolean(dialog.presence && dialog.presence.online && dialog.is_user);
  els.chatMeta.classList.toggle('online', online);
  els.chatAvatar.dataset.avatarKey = '';
  els.chatAvatar.innerHTML = '';
  paintInitials(els.chatAvatar, dialog.name || dialog.username || '?', dialog.id);
  applyAvatar(els.chatAvatar, dialog.id, dialog.name || '');
}

/* ------------------------------------------------------------------ */
/* messages: rendering                                                 */
/* ------------------------------------------------------------------ */

function messageSignature(message) {
  return JSON.stringify([message.id, message.out, message.text, message.date, message.read, message.edited, message.media, message.service]);
}

function metaHtml(message) {
  const time = message.date ? hm(parseDate(message.date) || new Date()) : '';
  const edited = message.edited ? '<span class="edited">изменено</span>' : '';
  const ticks = message.out
    ? `<span class="msg-ticks${message.read ? ' read' : ''}"><svg class="icon"><use href="#i-${message.read ? 'checks' : 'check'}"/></svg></span>`
    : '';
  return `${edited}<span class="msg-time">${esc(time)}</span>${ticks}`;
}

function frameSize(media) {
  const width = Number(media && media.width) || 0;
  const height = Number(media && media.height) || 0;
  if (!width || !height) return { auto: true, width: 0, ratio: '4 / 3' };
  const maxW = 420;
  const maxH = 420;
  const k = Math.min(1, maxW / width, maxH / height);
  return {
    auto: false,
    width: Math.max(120, Math.round(width * k)),
    ratio: `${width} / ${height}`,
  };
}

function mediaFrameHtml(message) {
  const media = message.media;
  const kind = media.type || 'document';
  const size = frameSize(media);
  const isVideo = kind === 'video' || kind === 'round' || kind === 'gif';
  const classes = ['media-frame'];
  if (size.auto && kind !== 'sticker') classes.push('auto');
  if (kind === 'sticker') classes.push('sticker-frame');
  const style = size.auto ? '' : ` style="--w:${size.width}px;--ar:${size.ratio}"`;
  const play = isVideo && kind !== 'gif'
    ? '<button class="media-play" type="button" aria-label="Воспроизвести"><span><svg class="icon"><use href="#i-play"/></svg></span></button>'
    : '';
  const badge = kind !== 'gif' && kind !== 'sticker' && media.duration
    ? `<span class="media-badge"><svg class="icon"><use href="#i-video"/></svg>${esc(fmtDuration(media.duration))}</span>`
    : '';
  return `<div class="${classes.join(' ')}"${style} data-media-id="${message.id}" data-media-kind="${kind}" data-state="idle">${play}${badge}</div>`;
}

function mimeIcon(mime, kind) {
  const value = String(mime || '');
  if (kind === 'image' || value.startsWith('image/')) return '<svg class="icon"><use href="#i-image"/></svg>';
  if (value.startsWith('video/')) return '<svg class="icon"><use href="#i-video"/></svg>';
  if (value.startsWith('audio/')) return '<svg class="icon"><use href="#i-mic"/></svg>';
  return '<svg class="icon"><use href="#i-file"/></svg>';
}

function documentHtml(message) {
  const media = message.media;
  const name = media.file_name || 'Файл';
  const size = fmtBytes(media.size);
  return `<div class="doc" data-media-id="${message.id}">
    <span class="doc-icon">${mimeIcon(media.mime_type, media.type)}</span>
    <span class="doc-copy">
      <span class="doc-name">${esc(name)}</span>
      <span class="doc-size">${esc([size, media.mime_type].filter(Boolean).join(' · '))}</span>
    </span>
    <button class="doc-dl" type="button" data-action="download" aria-label="Скачать"><svg class="icon"><use href="#i-download"/></svg></button>
  </div>`;
}

function waveformHtml(seed, bars = 32) {
  let value = Math.abs(Number(seed) || 1) % 2147483647 || 1;
  let out = '';
  for (let i = 0; i < bars; i += 1) {
    value = (value * 1103515245 + 12345) % 2147483648;
    const height = 18 + (value % 82);
    out += `<i style="--h:${height}%"></i>`;
  }
  return out;
}

function audioHtml(message) {
  const media = message.media;
  const voice = media.type === 'voice';
  const title = voice ? '' : (media.file_name || 'Аудио');
  const duration = fmtDuration(media.duration || 0);
  return `<div class="audio-player" data-media-id="${message.id}" data-media-kind="${media.type}" data-state="idle">
    <button class="audio-play" type="button" aria-label="Воспроизвести"><svg class="icon"><use href="#i-play"/></svg></button>
    <div class="audio-main">
      ${title ? `<div class="audio-title">${esc(title)}</div>` : ''}
      <div class="audio-wave">${waveformHtml(message.id)}</div>
      <div class="audio-time">0:00 / ${esc(duration)}</div>
    </div>
  </div>`;
}

function mediaBlockHtml(message) {
  const media = message.media;
  if (!media) return '';
  const kind = media.type || 'document';
  if (kind === 'photo' || kind === 'image' || kind === 'video' || kind === 'gif' || kind === 'round' || kind === 'sticker') {
    return `<div class="media">${mediaFrameHtml(message)}</div>`;
  }
  if (kind === 'voice' || kind === 'audio') {
    return `<div class="media">${audioHtml(message)}</div>`;
  }
  return `<div class="media">${documentHtml(message)}</div>`;
}

function buildRow(message) {
  const row = document.createElement('div');
  row.dataset.id = String(message.id);
  row.dataset.sig = messageSignature(message);
  row.dataset.mediaSig = JSON.stringify(message.media || null);
  row.dataset.date = message.date || '';
  row.__message = message;

  if (message.service) {
    row.className = 'msg-row service-row';
    row.innerHTML = `<div class="service-pill">${esc(message.service)}</div>`;
    return row;
  }

  row.className = `msg-row ${message.out ? 'out' : 'in'}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  const hasMedia = Boolean(message.media);
  if (hasMedia) bubble.classList.add('has-media');
  if (hasMedia && !message.text) bubble.classList.add('media-only');
  if (hasMedia && message.media.type === 'sticker') bubble.classList.add('sticker-bubble');

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = initialsFor(message.sender_name || '?');
  if (!message.out && state.dialog && state.dialog.kind !== 'user') {
    row.appendChild(avatar);
  }

  if (hasMedia) bubble.insertAdjacentHTML('beforeend', mediaBlockHtml(message));

  if (message.text) {
    const text = document.createElement('div');
    text.className = 'msg-text';
    text.innerHTML = linkify(message.text);
    bubble.appendChild(text);
  }

  if (!message.out && state.dialog && state.dialog.kind !== 'user' && message.sender_name) {
    const author = document.createElement('div');
    author.className = 'msg-author';
    author.textContent = message.sender_name;
    author.style.color = colorFor(message.sender_id || message.sender_name)[0];
    bubble.insertBefore(author, bubble.firstChild);
  }

  const meta = document.createElement('div');
  meta.className = `msg-meta${hasMedia && !message.text ? ' overlay' : ''}`;
  meta.innerHTML = metaHtml(message);
  bubble.appendChild(meta);

  row.appendChild(bubble);
  return row;
}

function layoutPass() {
  const inner = els.messagesInner;
  const rows = Array.from(inner.querySelectorAll('.msg-row'));
  $$('.date-sep', inner).forEach((node) => node.remove());

  let previous = null;
  let group = [];
  const closeGroup = () => {
    if (group.length) {
      const last = group[group.length - 1];
      last.classList.add('group-last');
      if (last.classList.contains('in') && state.dialog && state.dialog.kind !== 'user') {
        last.classList.add('show-avatar');
      }
    }
    group = [];
  };

  rows.forEach((row) => {
    row.classList.remove('group-first', 'group-follow', 'group-last', 'show-avatar', 'show-author');
    const message = row.__message;
    if (!message) return;

    const newDay = !previous || dayKey(previous.date) !== dayKey(message.date);
    if (newDay) {
      const separator = document.createElement('div');
      separator.className = 'date-sep';
      separator.innerHTML = `<span>${esc(dateLabel(message.date))}</span>`;
      inner.insertBefore(separator, row);
    }

    const sameAuthor = previous && previous.sender_id === message.sender_id && previous.out === message.out;
    const closeInTime = previous && message.date && previous.date
      && Math.abs(new Date(message.date) - new Date(previous.date)) < 5 * 60 * 1000;
    const continuous = previous && !newDay && sameAuthor && closeInTime
      && !message.service && !previous.service;

    if (!continuous) closeGroup();
    group.push(row);

    if (!continuous) row.classList.add('group-first');
    else row.classList.add('group-follow');

    const isGroupChat = state.dialog && state.dialog.kind !== 'user';
    if (isGroupChat) {
      if (!continuous && !message.out && message.sender_name) row.classList.add('show-author');
      if (!message.out && message.sender_name) {
        const avatar = row.querySelector('.msg-avatar');
        if (avatar) {
          avatar.dataset.avatarPeer = String(message.sender_id || '');
          avatar.dataset.avatarName = message.sender_name;
          paintInitials(avatar, message.sender_name, message.sender_id || message.sender_name);
        }
      }
    }

    previous = message;
  });

  closeGroup();
  updateJump();
}

/* ------------------------------------------------------------------ */
/* messages: scroll                                                    */
/* ------------------------------------------------------------------ */

function distanceFromBottom() {
  const box = els.messages;
  return box.scrollHeight - box.scrollTop - box.clientHeight;
}

function scrollToBottom(smooth = false) {
  const box = els.messages;
  box.scrollTo({ top: box.scrollHeight, behavior: smooth && !prefersReduced ? 'smooth' : 'auto' });
  state.stick = true;
  state.unreadWhileAway = 0;
  updateJump();
}

function updateJump() {
  const visible = state.messages.length > 0 && !state.stick;
  els.jumpDown.classList.toggle('hidden', !visible);
  const count = state.unreadWhileAway;
  els.jumpCount.textContent = count > 99 ? '99+' : String(count);
  els.jumpCount.classList.toggle('hidden', count === 0);
}

function captureAnchor() {
  if (state.stick) return null;
  const top = els.messages.getBoundingClientRect().top;
  const children = Array.from(els.messagesInner.children);
  for (const child of children) {
    // date separators are position:sticky — their rect is pinned to the top
    // edge, so it cannot serve as a measure of how far content moved.
    if (child.classList.contains('date-sep')) continue;
    const rect = child.getBoundingClientRect();
    if (rect.bottom > top + 1) return { el: child, top: rect.top };
  }
  return null;
}

function restoreAnchor(anchor) {
  if (!anchor || !anchor.el.isConnected) return;
  if (state.stick) { scrollToBottom(false); return; }
  const delta = anchor.el.getBoundingClientRect().top - anchor.top;
  if (delta) els.messages.scrollTop += delta;
}

function onMessagesScroll() {
  const atBottom = distanceFromBottom() < 90;
  if (atBottom !== state.stick) {
    state.stick = atBottom;
    if (atBottom) state.unreadWhileAway = 0;
  }
  updateJump();
  if (els.messages.scrollTop < 180) loadOlder();
}

function initScrollWatcher() {
  els.messages.addEventListener('scroll', onMessagesScroll, { passive: true });
  if ('ResizeObserver' in window) {
    state.resizeObserver = new ResizeObserver(() => {
      if (state.stick) els.messages.scrollTop = els.messages.scrollHeight;
    });
    state.resizeObserver.observe(els.messagesInner);
  }
}

/* ------------------------------------------------------------------ */
/* messages: loading                                                   */
/* ------------------------------------------------------------------ */

function emptyPlaceholder(title, subtitle) {
  const inner = els.messagesInner;
  inner.innerHTML = '';
  state.messages = [];
  state.rows.clear();
  const div = document.createElement('div');
  div.className = 'chat-empty';
  div.innerHTML = `<div class="chat-empty-icon"><svg class="icon"><use href="#i-plane"/></svg></div>
    <div class="chat-empty-title">${esc(title)}</div>
    <div class="chat-empty-sub">${esc(subtitle || '')}</div>`;
  inner.appendChild(div);
  updateJump();
}

function errorPlaceholder(title, message, retry) {
  const inner = els.messagesInner;
  inner.innerHTML = '';
  state.messages = [];
  state.rows.clear();
  const div = document.createElement('div');
  div.className = 'chat-empty';
  div.innerHTML = `<div class="chat-empty-title">${esc(title)}</div>
    <div class="chat-empty-sub">${esc(message || '')}</div>`;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn-ghost';
  button.style.cssText = 'width:auto;margin-top:10px;padding:8px 16px';
  button.textContent = 'Повторить';
  button.addEventListener('click', retry);
  div.appendChild(button);
  inner.appendChild(div);
  updateJump();
}

function chatMessagesUrl(limit, offsetId) {
  const params = new URLSearchParams({ peer: state.peer, limit: String(limit) });
  if (offsetId) params.set('offset_id', String(offsetId));
  return `/media-messages?${params.toString()}`;
}

function resetChatTransient() {
  state.chatGen += 1;
  state.messages = [];
  state.rows.clear();
  state.olderState = 'idle';
  state.unreadWhileAway = 0;
  state.stick = true;
  if (state.mediaObserver) state.mediaObserver.disconnect();
  revokeMediaUrls();
}

async function openChat(dialog) {
  closeMenus();
  const peer = dialog.username || String(dialog.id);
  state.dialog = dialog;
  state.peer = peer;
  const gen = (resetChatTransient(), state.chatGen);
  els.app.classList.add('chat-open');
  els.app.classList.remove('no-chat');
  setChatHeader(dialog);
  els.dialogs.querySelector('.dialog.active')?.classList.remove('active');
  const row = els.dialogs.querySelector(`.dialog[data-id="${CSS.escape(String(dialog.id))}"]`);
  if (row) row.classList.add('active');
  emptyPlaceholder('Загрузка сообщений…', dialog.name || '');
  updateComposerUi();
  startTimers();
  els.compose.placeholder = 'Сообщение';

  try {
    const list = await api(chatMessagesUrl(60));
    if (gen !== state.chatGen) return;
    const ordered = (Array.isArray(list) ? list : []).slice().sort((a, b) => a.id - b.id);
    if (!ordered.length) {
      emptyPlaceholder('Нет сообщений', 'Напишите первое сообщение');
      return;
    }
    els.messagesInner.innerHTML = '';
    for (const message of ordered) appendMessage(message, false);
    layoutPass();
    scrollToBottom(false);
    void markRead();
    if (dialog.is_user) refreshPresence();
  } catch (error) {
    if (gen !== state.chatGen) return;
    errorPlaceholder('Не удалось загрузить диалог', error.message, () => openChat(dialog));
  }
}

function appendMessage(message, animate) {
  const row = buildRow(message);
  if (!animate) row.style.animation = 'none';
  state.messages.push(message);
  state.rows.set(message.id, row);
  els.messagesInner.appendChild(row);
  observeMediaRow(row);
}

function prependMessages(messages) {
  const fragment = document.createDocumentFragment();
  messages.forEach((message) => {
    const row = buildRow(message);
    row.style.animation = 'none';
    state.rows.set(message.id, row);
    fragment.appendChild(row);
  });
  state.messages = [...messages, ...state.messages];
  els.messagesInner.insertBefore(fragment, els.messagesInner.firstChild);
  messages.forEach((message) => {
    const row = state.rows.get(message.id);
    if (row) observeMediaRow(row);
  });
}

function patchRow(row, message) {
  const signature = messageSignature(message);
  if (row.dataset.sig === signature) return false;
  const mediaSignature = JSON.stringify(message.media || null);
  if (row.dataset.mediaSig === mediaSignature) {
    row.__message = message;
    row.dataset.sig = signature;
    const text = row.querySelector('.msg-text');
    if (message.text) {
      if (text) text.innerHTML = linkify(message.text);
      else {
        const div = document.createElement('div');
        div.className = 'msg-text';
        div.innerHTML = linkify(message.text);
        row.querySelector('.msg-meta')?.before(div);
      }
    } else if (text) {
      text.remove();
    }
    const bubble = row.querySelector('.bubble');
    if (bubble) {
      const mediaOnlyNow = Boolean(message.media) && !message.text;
      bubble.classList.toggle('media-only', mediaOnlyNow);
      const meta = bubble.querySelector('.msg-meta');
      if (meta) {
        meta.className = `msg-meta${mediaOnlyNow ? ' overlay' : ''}`;
        meta.innerHTML = metaHtml(message);
      }
    }
    return true;
  }
  const fresh = buildRow(message);
  fresh.style.animation = 'none';
  row.replaceWith(fresh);
  state.rows.set(message.id, fresh);
  observeMediaRow(fresh);
  return true;
}

async function syncMessages(gen) {
  if (!state.peer) return;
  const peer = state.peer;
  const wasAtBottom = state.stick;
  let list;
  try {
    list = await api(chatMessagesUrl(60));
  } catch (error) {
    if (error.status === 401) return;
    return;
  }
  if (gen !== state.chatGen || peer !== state.peer) return;
  if (!Array.isArray(list)) return;
  const ordered = list.slice().sort((a, b) => a.id - b.id);
  const ids = new Set(ordered.map((m) => m.id));
  const minId = ordered.length ? ordered[0].id : 0;

  let changed = false;
  for (const [id, row] of Array.from(state.rows.entries())) {
    if (id >= minId && !ids.has(id)) {
      row.remove();
      state.rows.delete(id);
      state.messages = state.messages.filter((m) => m.id !== id);
      changed = true;
    }
  }

  let added = 0;
  for (const message of ordered) {
    const row = state.rows.get(message.id);
    if (row) {
      if (patchRow(row, message)) changed = true;
    } else {
      appendMessage(message, true);
      added += 1;
      changed = true;
    }
  }
  if (!changed) return;

  const anchor = wasAtBottom ? null : captureAnchor();
  layoutPass();
  if (wasAtBottom) {
    scrollToBottom(false);
  } else if (added) {
    state.unreadWhileAway += added;
    restoreAnchor(anchor);
  }
  updateJump();
  if (wasAtBottom) void markRead();
}

async function loadOlder() {
  if (state.olderState !== 'idle' || !state.peer || !state.messages.length) return;
  const oldest = state.messages[0].id;
  const gen = state.chatGen;
  state.olderState = 'loading';
  const anchor = captureAnchor();
  try {
    const list = await api(chatMessagesUrl(40, oldest));
    if (gen !== state.chatGen) return;
    const fresh = (Array.isArray(list) ? list : [])
      .filter((m) => !state.rows.has(m.id))
      .sort((a, b) => a.id - b.id);
    if (!fresh.length) {
      state.olderState = 'done';
      return;
    }
    prependMessages(fresh);
    layoutPass();
    restoreAnchor(anchor);
    state.olderState = 'idle';
  } catch (error) {
    state.olderState = 'idle';
  }
}

async function markRead() {
  if (!state.peer) return;
  try {
    await api('/read', { method: 'POST', body: JSON.stringify({ peer: state.peer }) });
    if (state.dialog && state.dialog.unread) {
      state.dialog.unread = 0;
      const source = state.dialogs.find((d) => String(d.id) === String(state.dialog.id));
      if (source) source.unread = 0;
      renderDialogs();
    }
  } catch (error) { /* read receipts are best-effort */ }
}

async function refreshPresence() {
  if (!state.peer || !state.dialog || !state.dialog.is_user) return;
  try {
    const data = await api(`/presence?peer=${encodeURIComponent(state.peer)}`);
    if (!state.dialog || String(data.peer) !== String(state.peer)) return;
    state.dialog.presence = data.presence;
    setChatHeader(state.dialog);
    const source = state.dialogs.find((d) => String(d.id) === String(state.dialog.id));
    if (source) source.presence = data.presence;
    renderDialogs();
  } catch (error) { /* ignore */ }
}

/* ------------------------------------------------------------------ */
/* media                                                               */
/* ------------------------------------------------------------------ */

function mediaPath(messageId) {
  return `/media/${encodeURIComponent(state.peer)}/${messageId}`;
}

function observeMediaRow(row) {
  const frames = $$('[data-state="idle"]', row);
  frames.forEach((frame) => {
    if (state.mediaObserver) state.mediaObserver.observe(frame);
  });
}

function initMediaObserver() {
  state.mediaObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      state.mediaObserver.unobserve(entry.target);
      const frame = entry.target;
      if (frame.dataset.mediaKind === 'voice' || frame.dataset.mediaKind === 'audio') return;
      void loadFrame(frame);
    });
  }, { root: els.messages, rootMargin: '800px 0px 500px 0px' });
}

function mediaUnavailable(frame) {
  frame.classList.remove('loading');
  frame.dataset.state = 'error';
  frame.classList.add('error');
  frame.innerHTML = '<div class="media-error">Не удалось загрузить вложение<button type="button" data-action="retry">Повторить</button></div>';
}

async function loadFrame(frame) {
  if (!frame.isConnected) return;
  const status = frame.dataset.state;
  if (status === 'loading' || status === 'done' || status === 'thumb') return;
  const id = Number(frame.dataset.mediaId);
  const kind = frame.dataset.mediaKind;
  const gen = state.chatGen;
  const peer = state.peer;
  frame.dataset.state = 'loading';
  frame.classList.add('loading');

  const isVideo = kind === 'video' || kind === 'round';

  if (isVideo) {
    frame.dataset.state = 'thumb';
    try {
      const response = await api(`/thumb/${encodeURIComponent(peer)}/${id}`, {}, { raw: true });
      const blob = await response.blob();
      if (!frame.isConnected || gen !== state.chatGen) return;
      const url = URL.createObjectURL(blob);
      state.mediaUrls.add(url);
      frame.style.backgroundImage = `url("${url}")`;
      frame.style.backgroundSize = 'cover';
      frame.style.backgroundPosition = 'center';
    } catch (error) {
      frame.dataset.state = 'idle';
    }
    frame.classList.remove('loading');
    return;
  }

  try {
    const url = await apiBlobUrl(mediaPath(id));
    if (!frame.isConnected || gen !== state.chatGen) {
      URL.revokeObjectURL(url);
      state.mediaUrls.delete(url);
      return;
    }
    const anchor = captureAnchor();
    if (kind === 'gif' || kind === 'round') {
      frame.innerHTML = `<video src="${url}" autoplay loop muted playsinline></video>`;
    } else {
      frame.innerHTML = `<img src="${url}" alt="">`;
    }
    frame.classList.remove('loading');
    frame.dataset.state = 'done';
    frame.dataset.url = url;
    // Frames without API dimensions only get their height once the file
    // decodes; compensate the resulting shift, not the insertion.
    if (frame.classList.contains('auto')) {
      const media = frame.querySelector('img, video');
      if (media && media.decode) await media.decode().catch(() => {});
    }
    restoreAnchor(anchor);
  } catch (error) {
    mediaUnavailable(frame);
  }
}

async function playVideo(frame) {
  if (frame.dataset.videoUrl) {
    const video = frame.querySelector('video');
    if (video) { video.play().catch(() => {}); return; }
  }
  const id = Number(frame.dataset.mediaId);
  const gen = state.chatGen;
  const button = frame.querySelector('.media-play');
  if (button) button.style.opacity = '.5';
  try {
    const url = await apiBlobUrl(mediaPath(id));
    if (!frame.isConnected || gen !== state.chatGen) return;
    const anchor = captureAnchor();
    frame.innerHTML = `<video src="${url}" controls autoplay playsinline></video>`;
    frame.dataset.state = 'done';
    frame.dataset.videoUrl = url;
    frame.classList.remove('loading');
    restoreAnchor(anchor);
  } catch (error) {
    if (button) button.style.opacity = '';
    toast(`Не удалось воспроизвести видео: ${error.message}`, true);
  }
}

async function openLightbox(id, kind, name) {
  try {
    const url = await apiBlobUrl(mediaPath(id));
    els.lightboxBody.innerHTML = kind === 'video'
      ? `<video src="${url}" controls autoplay playsinline></video>`
      : `<img src="${url}" alt="">`;
    state.lightboxUrl = url;
    state.lightboxId = id;
    state.lightboxName = name || null;
    els.lightbox.classList.remove('hidden');
  } catch (error) {
    toast(`Не удалось открыть вложение: ${error.message}`, true);
  }
}

function closeLightbox() {
  if (els.lightbox.classList.contains('hidden')) return;
  els.lightbox.classList.add('hidden');
  els.lightboxBody.innerHTML = '';
  const video = els.lightboxBody.querySelector('video');
  if (video) video.pause();
  if (state.lightboxUrl) {
    URL.revokeObjectURL(state.lightboxUrl);
    state.mediaUrls.delete(state.lightboxUrl);
    state.lightboxUrl = null;
  }
}

async function downloadMedia(messageId, name) {
  try {
    const response = await api(mediaPath(messageId), {}, { raw: true });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = name || `telegram-${messageId}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  } catch (error) {
    toast(`Не удалось скачать файл: ${error.message}`, true);
  }
}

function revokeMediaUrls() {
  state.mediaUrls.forEach((url) => URL.revokeObjectURL(url));
  state.mediaUrls.clear();
}

/* ------------------------------------------------------------------ */
/* audio player                                                        */
/* ------------------------------------------------------------------ */

const audioState = new WeakMap();

async function toggleAudio(host) {
  let player = audioState.get(host);
  if (!player) {
    player = { audio: null, url: null };
    audioState.set(host, player);
  }
  const button = $('.audio-play', host);
  try {
    if (!player.audio) {
      const url = await apiBlobUrl(mediaPath(Number(host.dataset.mediaId)));
      player.url = url;
      player.audio = new Audio(url);
      player.audio.preload = 'auto';
      player.audio.addEventListener('timeupdate', () => paintAudio(host, player));
      player.audio.addEventListener('ended', () => {
        player.audio.currentTime = 0;
        paintAudio(host, player);
        setPlayIcon(button, false);
      });
      player.audio.addEventListener('pause', () => setPlayIcon(button, false));
      player.audio.addEventListener('play', () => setPlayIcon(button, true));
    }
    if (player.audio.paused) await player.audio.play();
    else player.audio.pause();
  } catch (error) {
    toast('Не удалось воспроизвести аудио', true);
  }
}

function setPlayIcon(button, playing) {
  if (!button) return;
  button.innerHTML = `<svg class="icon"><use href="#i-${playing ? 'pause' : 'play'}"/></svg>`;
}

function paintAudio(host, player) {
  const audio = player.audio;
  if (!audio) return;
  const duration = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : 0;
  const current = audio.currentTime || 0;
  const progress = duration ? current / duration : 0;
  const bars = $$('.audio-wave i', host);
  bars.forEach((bar, index) => {
    bar.classList.toggle('played', index / bars.length <= progress);
  });
  const time = $('.audio-time', host);
  if (time) time.textContent = `${fmtDuration(current)} / ${fmtDuration(duration)}`;
}

function seekAudio(host, event) {
  const player = audioState.get(host);
  if (!player || !player.audio || !player.audio.duration) return;
  const wave = $('.audio-wave', host);
  const rect = wave.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
  player.audio.currentTime = ratio * player.audio.duration;
  paintAudio(host, player);
}

/* ------------------------------------------------------------------ */
/* composer                                                            */
/* ------------------------------------------------------------------ */

function autoGrow() {
  const el = els.compose;
  el.style.height = 'auto';
  el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
}

function hasSomethingToSend() {
  return Boolean(state.peer) && !state.sending
    && (els.compose.value.trim().length > 0 || Boolean(state.pendingFile));
}

function updateComposerUi() {
  const empty = !els.compose.value.trim() && !state.pendingFile;
  els.sendBtn.disabled = !state.peer || state.sending || empty;
  els.sendBtn.classList.toggle('sending', state.sending);
  els.compose.disabled = !state.peer;
}

function clearPendingFile() {
  state.pendingFile = null;
  if (state.pendingPreview) {
    URL.revokeObjectURL(state.pendingPreview);
    state.pendingPreview = null;
  }
  els.fileInput.value = '';
  els.attachPreview.classList.add('hidden');
  els.attachPreviewThumb.innerHTML = '';
  updateComposerUi();
}

function setPendingFile(file) {
  if (!file) return;
  clearPendingFile();
  state.pendingFile = file;
  els.attachPreview.classList.remove('hidden');
  els.attachPreviewName.textContent = file.name || 'Вложение';
  els.attachPreviewSize.textContent = [fmtBytes(file.size), file.type].filter(Boolean).join(' · ');
  els.attachPreviewThumb.innerHTML = '';
  if (String(file.type || '').startsWith('image/')) {
    const url = URL.createObjectURL(file);
    state.pendingPreview = url;
    els.attachPreviewThumb.innerHTML = `<img src="${url}" alt="">`;
  } else {
    els.attachPreviewThumb.innerHTML = mimeIcon(file.type, 'document');
  }
  updateComposerUi();
  els.compose.focus();
}

function setProgress(row, ratio) {
  const bar = row.querySelector('.upload-progress span');
  if (bar) bar.style.width = `${Math.round(Math.min(1, Math.max(0, ratio)) * 100)}%`;
}

function pendingBubble(text, file) {
  const row = document.createElement('div');
  row.className = 'msg-row out pending';
  row.dataset.temp = '1';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  let mediaHtml = '';
  if (file && String(file.type || '').startsWith('image/')) {
    mediaHtml = `<div class="media"><div class="media-frame auto"><img src="${state.pendingPreview}" alt=""></div></div>`;
  } else if (file) {
    mediaHtml = documentHtml({
      media: { file_name: file.name, size: file.size, type: 'document', mime_type: file.type },
      id: 'tmp',
    });
  }
  if (mediaHtml) bubble.classList.add('has-media');
  if (mediaHtml && !text) bubble.classList.add('media-only');
  bubble.innerHTML = `${mediaHtml}
    ${text ? `<div class="msg-text">${esc(text)}</div>` : ''}
    <div class="msg-meta">${metaHtml({ out: true, date: new Date().toISOString(), read: false })}</div>
    ${file ? '<div class="upload-progress"><span></span></div>' : ''}`;
  row.appendChild(bubble);
  els.messagesInner.appendChild(row);
  const img = row.querySelector('img');
  if (img) img.addEventListener('load', () => { if (state.stick) scrollToBottom(false); }, { once: true });
  scrollToBottom(false);
  return row;
}

function uploadWithProgress(file, caption, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API}/send_file`);
    xhr.setRequestHeader('Authorization', `Bearer ${state.token}`);
    xhr.setRequestHeader('X-Telegram-Account', state.accountId || 'default');
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    });
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText || '{}')); } catch (error) { resolve({}); }
      } else {
        let message = `HTTP ${xhr.status}`;
        try { message = JSON.parse(xhr.responseText).detail || message; } catch (error) { /* noop */ }
        reject(new Error(message));
      }
    });
    xhr.addEventListener('error', () => reject(new Error('Ошибка сети')));
    const form = new FormData();
    form.append('dialog_id', state.peer);
    form.append('file', file, file.name || 'attachment');
    if (caption) form.append('caption', caption);
    xhr.send(form);
  });
}

async function sendMessage() {
  if (!hasSomethingToSend()) return;
  const text = els.compose.value.trim();
  const file = state.pendingFile;
  const gen = state.chatGen;
  state.sending = true;
  els.sendBtn.disabled = true;
  els.sendBtn.classList.add('sending');
  const pending = pendingBubble(text, file);
  try {
    if (file) {
      await uploadWithProgress(file, text, (ratio) => setProgress(pending, ratio));
    } else {
      await api('/send-text', { method: 'POST', body: JSON.stringify({ peer: state.peer, text }) });
    }
    els.compose.value = '';
    autoGrow();
    clearPendingFile();
    pending.remove();
    await syncMessages(gen);
    scrollToBottom(true);
  } catch (error) {
    pending.remove();
    toast(`Ошибка отправки: ${error.message}`, true);
  } finally {
    state.sending = false;
    updateComposerUi();
    els.compose.focus();
  }
}

/* ------------------------------------------------------------------ */
/* settings                                                            */
/* ------------------------------------------------------------------ */

function openSettings() {
  closeMenus();
  if (!state.token) return;
  els.settingsModal.classList.remove('hidden');
  setStatus(els.settingsStatus, '');
  loadSettings();
}

function closeSettings() {
  els.settingsModal.classList.add('hidden');
}

async function loadSettings() {
  try {
    const data = await api('/media-settings');
    state.settings = data;
    els.mediaDownloadMode.value = data.download_mode || 'open';
    els.mediaAutoDownload.checked = Boolean(data.auto_download);
    els.mediaExcluded.value = (data.excluded_peers || []).join('\n');
    els.mediaAutoCleanup.checked = Boolean(data.auto_cleanup);
    els.mediaTtl.value = data.ttl_hours || 24;
    const mb = (Number(data.storage_bytes || 0) / 1024 / 1024).toFixed(1);
    els.mediaStorage.textContent = `${data.storage_files || 0} файлов · ${mb} МБ · автоудаление через ${data.ttl_hours || 24} ч.`;
  } catch (error) {
    els.mediaStorage.textContent = error.message;
  }
}

async function saveSettings() {
  try {
    els.settingsSave.disabled = true;
    const payload = {
      download_mode: els.mediaDownloadMode.value,
      auto_download: els.mediaAutoDownload.checked,
      excluded_peers: els.mediaExcluded.value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean),
      auto_cleanup: els.mediaAutoCleanup.checked,
      ttl_hours: Number(els.mediaTtl.value || 24),
    };
    await api('/media-settings', { method: 'PUT', body: JSON.stringify(payload) });
    setStatus(els.settingsStatus, 'Настройки сохранены', false, true);
    setTimeout(closeSettings, 500);
  } catch (error) {
    setStatus(els.settingsStatus, error.message, true);
  } finally {
    els.settingsSave.disabled = false;
  }
}

async function clearMediaCache() {
  if (!window.confirm('Удалить все скачанные вложения с сервера?')) return;
  try {
    const result = await api('/media-cache', { method: 'DELETE' });
    setStatus(els.settingsStatus, `Удалено файлов: ${result.removed_files || 0}`, false, true);
    await loadSettings();
  } catch (error) {
    setStatus(els.settingsStatus, error.message, true);
  }
}

/* ------------------------------------------------------------------ */
/* menus                                                               */
/* ------------------------------------------------------------------ */

function closeMenus() {
  els.sideMenu.classList.add('hidden');
  els.sideMenuBtn.setAttribute('aria-expanded', 'false');
  els.attachMenu.classList.add('hidden');
}

function toggleSideMenu() {
  const hidden = els.sideMenu.classList.toggle('hidden');
  els.sideMenuBtn.setAttribute('aria-expanded', String(!hidden));
  if (!hidden) els.attachMenu.classList.add('hidden');
}

function toggleAttachMenu() {
  const hidden = els.attachMenu.classList.toggle('hidden');
  if (!hidden) {
    els.sideMenu.classList.add('hidden');
    els.sideMenuBtn.setAttribute('aria-expanded', 'false');
  }
}

/* ------------------------------------------------------------------ */
/* timers                                                              */
/* ------------------------------------------------------------------ */

function clearTimers() {
  clearInterval(state.pollTimer);
  clearInterval(state.dialogsTimer);
  clearInterval(state.presenceTimer);
  state.pollTimer = null;
  state.dialogsTimer = null;
  state.presenceTimer = null;
}

function stopChatTimers() {
  clearInterval(state.pollTimer);
  clearInterval(state.presenceTimer);
  state.pollTimer = null;
  state.presenceTimer = null;
}

function startTimers() {
  clearTimers();
  state.pollTimer = setInterval(() => {
    if (document.hidden || !state.peer) return;
    void syncMessages(state.chatGen);
  }, 4000);
  state.dialogsTimer = setInterval(() => {
    if (document.hidden) return;
    void refreshDialogs({ silent: true });
  }, 20000);
  state.presenceTimer = setInterval(() => {
    if (document.hidden) return;
    void refreshPresence();
  }, 30000);
}

/* ------------------------------------------------------------------ */
/* events                                                              */
/* ------------------------------------------------------------------ */

function bindEvents() {
  els.loginForm.addEventListener('submit', login);
  els.passToggle.addEventListener('click', () => {
    const visible = els.loginPass.type === 'text';
    els.loginPass.type = visible ? 'password' : 'text';
    els.passToggle.innerHTML = `<svg class="icon"><use href="#i-${visible ? 'eye' : 'eye-off'}"/></svg>`;
    els.loginPass.focus();
  });
  els.addAccountBtn.addEventListener('click', showAddAccount);
  els.logoutAccountsBtn.addEventListener('click', () => signedOut());
  els.backToAccountsBtn.addEventListener('click', backToAccounts);
  els.requestCodeBtn.addEventListener('click', requestAccountCode);
  els.submitCodeBtn.addEventListener('click', submitAccountCode);
  els.submitPasswordBtn.addEventListener('click', submitAccountPassword);

  els.sideMenuBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleSideMenu();
  });
  els.menuSettings.addEventListener('click', openSettings);
  els.menuAccounts.addEventListener('click', backToAccounts);
  els.menuLogout.addEventListener('click', () => signedOut());
  els.meRow.addEventListener('click', () => {
    els.sideMenu.classList.toggle('hidden');
    els.sideMenuBtn.setAttribute('aria-expanded', String(!els.sideMenu.classList.contains('hidden')));
  });

  els.search.addEventListener('input', () => {
    state.searchQuery = els.search.value;
    renderDialogs();
  });

  els.backBtn.addEventListener('click', () => {
    els.app.classList.remove('chat-open');
    els.app.classList.add('no-chat');
    stopChatTimers();
    state.peer = null;
    state.dialog = null;
    state.chatGen += 1;
    els.chatName.textContent = 'Telegram';
    els.chatMeta.textContent = 'Выберите чат слева';
    els.chatMeta.classList.remove('online');
    els.chatAvatar.innerHTML = '';
    paintInitials(els.chatAvatar, '?', 'empty');
    emptyPlaceholder('Выберите чат', 'и начните общение — история и вложения подтянутся автоматически');
    renderDialogs();
    updateComposerUi();
  });

  els.jumpDown.addEventListener('click', () => scrollToBottom(true));

  els.attachBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleAttachMenu();
  });
  $$('.attach-item', els.attachMenu).forEach((item) => {
    item.addEventListener('click', () => {
      els.fileInput.accept = item.dataset.accept || '*/*';
      els.fileInput.click();
      els.attachMenu.classList.add('hidden');
    });
  });
  els.fileInput.addEventListener('change', () => {
    const file = els.fileInput.files && els.fileInput.files[0];
    if (file) setPendingFile(file);
  });
  els.attachPreviewRemove.addEventListener('click', clearPendingFile);

  els.compose.addEventListener('input', () => { autoGrow(); updateComposerUi(); });
  els.compose.addEventListener('focus', () => els.composeBox.classList.add('focus'));
  els.compose.addEventListener('blur', () => els.composeBox.classList.remove('focus'));
  els.compose.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      sendMessage();
    }
  });
  els.compose.addEventListener('paste', (event) => {
    const items = Array.from(event.clipboardData?.items || []);
    const image = items.find((item) => item.kind === 'file' && item.type.startsWith('image/'));
    if (image) {
      const file = image.getAsFile();
      if (file) {
        event.preventDefault();
        setPendingFile(file);
      }
    }
  });
  els.sendBtn.addEventListener('click', sendMessage);

  els.chatMenuBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    openSettings();
  });

  els.messages.addEventListener('click', (event) => {
    const target = event.target;
    if (target.closest('[data-action="retry"]')) {
      const failed = target.closest('.media-frame');
      if (failed) {
        failed.dataset.state = 'idle';
        failed.classList.remove('error');
        failed.innerHTML = '';
        void loadFrame(failed);
        return;
      }
    }
    const frame = target.closest('.media-frame');
    if (frame) {
      const kind = frame.dataset.mediaKind;
      if (kind === 'video' || kind === 'round') {
        void playVideo(frame);
        return;
      }
      if (kind === 'photo' || kind === 'image') {
        void openLightbox(Number(frame.dataset.mediaId), 'photo', null);
        return;
      }
    }
    const audioPlay = target.closest('.audio-play');
    if (audioPlay) {
      void toggleAudio(audioPlay.closest('.audio-player'));
      return;
    }
    const wave = target.closest('.audio-wave');
    if (wave) {
      seekAudio(wave.closest('.audio-player'), event);
      return;
    }
    const docButton = target.closest('.doc-dl');
    if (docButton) {
      const doc = docButton.closest('.doc');
      const message = state.messages.find((m) => String(m.id) === String(doc?.dataset.mediaId));
      void downloadMedia(Number(doc?.dataset.mediaId), message?.media?.file_name || null);
      return;
    }
    const downloaded = target.closest('[data-action="download"]');
    if (downloaded) {
      const holder = downloaded.closest('[data-media-id]');
      const message = state.messages.find((m) => String(m.id) === String(holder?.dataset.mediaId));
      void downloadMedia(Number(holder?.dataset.mediaId), message?.media?.file_name || null);
    }
  });

  els.lightboxClose.addEventListener('click', closeLightbox);
  els.lightbox.addEventListener('click', (event) => {
    if (event.target === els.lightbox) closeLightbox();
  });
  els.lightboxDownload.addEventListener('click', () => {
    if (state.lightboxId) void downloadMedia(state.lightboxId, state.lightboxName);
  });

  els.settingsClose.addEventListener('click', closeSettings);
  els.settingsCancel.addEventListener('click', closeSettings);
  els.settingsSave.addEventListener('click', saveSettings);
  els.clearMediaCache.addEventListener('click', clearMediaCache);
  els.settingsModal.addEventListener('click', (event) => {
    if (event.target === els.settingsModal) closeSettings();
  });

  document.addEventListener('click', (event) => {
    if (!event.target.closest('#sideMenu') && !event.target.closest('#sideMenuBtn') && !event.target.closest('#chatMenuBtn')) {
      els.sideMenu.classList.add('hidden');
      els.sideMenuBtn.setAttribute('aria-expanded', 'false');
    }
    if (!event.target.closest('#attachMenu') && !event.target.closest('#attachBtn')) {
      els.attachMenu.classList.add('hidden');
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (!els.lightbox.classList.contains('hidden')) { closeLightbox(); return; }
    if (!els.settingsModal.classList.contains('hidden')) { closeSettings(); return; }
    closeMenus();
  });

  // drag & drop
  ['dragenter', 'dragover'].forEach((name) => {
    els.chat.addEventListener(name, (event) => {
      event.preventDefault();
      if (!state.peer) return;
      state.dragDepth += 1;
      els.dropOverlay.classList.remove('hidden');
    });
  });
  ['dragleave', 'dragend'].forEach((name) => {
    els.chat.addEventListener(name, (event) => {
      event.preventDefault();
      state.dragDepth = Math.max(0, state.dragDepth - 1);
      if (state.dragDepth === 0) els.dropOverlay.classList.add('hidden');
    });
  });
  els.chat.addEventListener('drop', (event) => {
    event.preventDefault();
    state.dragDepth = 0;
    els.dropOverlay.classList.add('hidden');
    const file = event.dataTransfer?.files?.[0];
    if (file && state.peer) setPendingFile(file);
  });

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && state.peer) {
      void syncMessages(state.chatGen);
      void refreshDialogs({ silent: true });
    }
  });
}

/* ------------------------------------------------------------------ */
/* boot                                                                */
/* ------------------------------------------------------------------ */

function init() {
  cacheEls();
  bindEvents();
  initScrollWatcher();
  initMediaObserver();

  if (!state.token) {
    showScreen('loginScreen');
    return;
  }
  showScreen('accountsScreen');
  start().catch(() => signedOut());
}

init();

})();
