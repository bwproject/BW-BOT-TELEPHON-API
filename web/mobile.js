(() => {
    const css = document.createElement('style');
    css.textContent = `
        .mobile-back {
            display:none;
            width:42px;
            height:42px;
            flex:0 0 42px;
            border:1px solid var(--line);
            border-radius:12px;
            background:#121b30;
            color:var(--text);
            font-size:22px;
            line-height:1;
        }
        .presence-line { color:var(--muted); }
        .presence-online { color:#5ee69b!important; }
        .dialog-sub.presence-online { color:#5ee69b; }
        .media-loading {
            min-height:74px;
            display:flex;
            align-items:center;
            justify-content:center;
            gap:8px;
            color:var(--muted);
            background:#0003;
            border-radius:12px;
            padding:14px;
        }
        .media-loading::before {
            content:'↓';
            width:30px;
            height:30px;
            display:grid;
            place-items:center;
            border:1px solid var(--line);
            border-radius:9px;
            font-weight:800;
        }
        .media-error { color:var(--danger); padding:12px; background:#0003; border-radius:12px; }
        .media-file { cursor:pointer; }
        @media(max-width:760px){
            .mobile-back { display:grid; place-items:center; }
            .chat-head { gap:9px; }
        }
    `;
    document.head.appendChild(css);

    function escLocal(value) {
        if (typeof esc === 'function') return esc(value);
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function formatPresence(p) {
        if (!p) return '';
        if (p.online || p.kind === 'online') return 'онлайн';
        if (p.last_seen) {
            const d = new Date(p.last_seen);
            if (!Number.isNaN(d.getTime())) {
                return 'был(а) в сети ' + d.toLocaleString('ru-RU', {
                    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                });
            }
        }
        return p.label || '';
    }

    function addBackButton() {
        const head = document.querySelector('.chat-head');
        if (!head || document.getElementById('mobileBack')) return;
        const button = document.createElement('button');
        button.id = 'mobileBack';
        button.className = 'mobile-back';
        button.type = 'button';
        button.title = 'Назад к диалогам';
        button.setAttribute('aria-label', 'Назад к диалогам');
        button.textContent = '‹';
        button.onclick = () => {
            const app = document.getElementById('app');
            app.classList.remove('chat-open');
            if (typeof poll !== 'undefined' && poll) { clearInterval(poll); poll = null; }
            if (typeof peer !== 'undefined') peer = null;
            document.getElementById('chatName').textContent = 'Выберите чат';
            document.getElementById('chatMeta').textContent = 'Ваши Telegram диалоги';
            const avatar = document.getElementById('chatAvatar');
            if (avatar) avatar.innerHTML = '?';
            if (typeof renderDialogs === 'function') renderDialogs();
        };
        head.insertBefore(button, head.firstChild);
    }

    async function loadDialogsWithPresence() {
        const box = document.getElementById('dialogs');
        if (!box) return;
        box.innerHTML = '<div class="empty" style="padding:25px">Загрузка диалогов…</div>';
        try {
            const data = await api('/dialogs-with-presence?limit=100');
            if (!Array.isArray(data)) throw Error('API вернул неверный список диалогов');
            dialogs = data;
            renderDialogsWithPresence();
        } catch (e) {
            box.innerHTML = '<div class="error-box">Не удалось загрузить диалоги<br><small>' +
                escLocal(e.message) +
                '</small><br><button class="btn" style="margin-top:14px" onclick="loadDialogs()">Повторить</button></div>';
            console.error('dialogs presence error', e);
        }
    }

    function renderDialogsWithPresence() {
        const search = document.getElementById('search');
        const box = document.getElementById('dialogs');
        if (!box || !search) return;
        const q = search.value.trim().toLowerCase();
        box.innerHTML = '';
        const filtered = dialogs.filter(d =>
            (d.name || '').toLowerCase().includes(q) ||
            (d.username || '').toLowerCase().includes(q)
        );
        if (!filtered.length) {
            box.innerHTML = '<div class="empty" style="padding:25px">Нет диалогов</div>';
            return;
        }
        filtered.forEach(d => {
            const el = document.createElement('div');
            el.className = 'dialog' + (String(d.id) === String(peer) ? ' active' : '');
            const avId = 'av-' + String(d.id).replace(/[^a-zA-Z0-9_-]/g, '_');
            const presence = d.presence || {};
            const presenceText = d.is_user ? formatPresence(presence) : (d.type || 'Telegram');
            const presenceClass = presence.online ? ' presence-online' : '';
            el.innerHTML =
                '<div id="' + avId + '" class="avatar">' + escLocal((d.name || '?')[0].toUpperCase()) + '</div>' +
                '<div class="dialog-main"><div class="dialog-name">' +
                    escLocal(d.name || d.username || d.id) +
                '</div><div class="dialog-sub' + presenceClass + '">' +
                    escLocal(d.username ? '@' + d.username : presenceText) +
                '</div></div>' +
                (d.unread ? '<span class="badge">' + d.unread + '</span>' : '');
            el.onclick = () => openChatWithPresence(d);
            box.appendChild(el);
            if (typeof setAvatar === 'function') setAvatar(avId, String(d.id));
        });
    }

    function filterDialogsWithPresence() { renderDialogsWithPresence(); }

    async function openChatWithPresence(d) {
        peer = d.username || String(d.id);
        document.getElementById('app').classList.add('chat-open');
        document.getElementById('chatName').textContent = d.name || d.username || d.id;
        const presenceText = d.is_user ? formatPresence(d.presence) : (d.type || 'Telegram');
        document.getElementById('chatMeta').textContent = d.username
            ? '@' + d.username + (presenceText ? ' • ' + presenceText : '')
            : presenceText;
        document.getElementById('chatMeta').className = 'chat-meta' +
            ((d.presence && d.presence.online) ? ' presence-online' : '');
        if (typeof setAvatar === 'function') setAvatar('chatAvatar', String(d.id));
        renderDialogsWithPresence();
        if (poll) clearInterval(poll);
        document.getElementById('messages').innerHTML = '<div class="empty">Загрузка сообщений…</div>';
        await loadMessagesBetter(true);
        poll = setInterval(() => loadMessagesBetter(false), 4000);
        if (d.is_user) refreshCurrentPresence();
    }

    async function refreshCurrentPresence() {
        if (!peer) return;
        try {
            const data = await api('/presence?peer=' + encodeURIComponent(peer));
            const text = formatPresence(data.presence);
            const meta = document.getElementById('chatMeta');
            if (meta) {
                meta.textContent = data.username ? '@' + data.username + (text ? ' • ' + text : '') : text;
                meta.className = 'chat-meta' + ((data.presence && data.presence.online) ? ' presence-online' : '');
            }
            const current = dialogs.find(d => String(d.id) === String(peer) || d.username === peer);
            if (current) current.presence = data.presence;
            renderDialogsWithPresence();
        } catch (_) {}
    }

    /*
     * Media is deliberately loaded asynchronously.  The message list is
     * rendered immediately, while photos/videos/files download in parallel.
     * This prevents one slow attachment from blocking the whole chat.
     */
    async function loadMediaBetter(id, type) {
        const host = document.getElementById('media-' + id);
        if (!host || !peer) return;
        try {
            const beforeHeight = host.parentElement ? host.parentElement.parentElement.scrollHeight : 0;
            const response = await api('/media/' + encodeURIComponent(peer) + '/' + id);
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            if (!document.body.contains(host)) { URL.revokeObjectURL(url); return; }

            if (type === 'photo') {
                host.innerHTML = '<img src="' + url + '" alt="Telegram photo" loading="lazy">';
            } else if (type === 'video') {
                host.innerHTML = '<video controls preload="metadata" src="' + url + '"></video>';
            } else {
                host.innerHTML = '<a class="media-file" href="#" onclick="downloadMediaBetter(' + id + ');return false">📎 ' + escLocal(type) + ' • скачать</a>';
            }

            const box = document.getElementById('messages');
            if (box && !messageListWasAtBottom) {
                const afterHeight = box.scrollHeight;
                if (afterHeight !== beforeHeight) box.scrollTop += afterHeight - beforeHeight;
            }
        } catch (e) {
            if (host) host.innerHTML = '<div class="media-error">Не удалось загрузить вложение</div>';
        }
    }

    async function downloadMediaBetter(id) {
        if (!peer) return;
        try {
            const response = await api('/media/' + encodeURIComponent(peer) + '/' + id);
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'telegram-media-' + id;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 30000);
        } catch (e) {
            alert('Ошибка скачивания: ' + e.message);
        }
    }

    let messageListWasAtBottom = true;

    async function renderMessageBetter(box, m) {
        const el = document.createElement('div');
        el.className = 'bubble ' + (m.out ? 'out' : '');
        el.dataset.messageId = String(m.id);
        let h = '';
        if (m.media) {
            const type = m.media.type || 'media';
            const label = m.media.file_name || type;
            if (type === 'photo' || type === 'video') {
                h += '<div class="media media-loading" id="media-' + m.id + '">Загрузка вложения…</div>';
            } else {
                h += '<div class="media"><a class="media-file" href="#" onclick="downloadMediaBetter(' + m.id + ');return false">📎 ' + escLocal(label) + ' • скачать</a></div>';
            }
        }
        if (m.text) h += '<div class="bubble-text">' + escLocal(m.text) + '</div>';
        const tm = m.date ? new Date(m.date).toLocaleTimeString('ru-RU', {hour:'2-digit', minute:'2-digit'}) : '';
        h += '<div class="time">' + tm + '</div>';
        el.innerHTML = h;
        box.appendChild(el);
        if (m.media && (m.media.type === 'photo' || m.media.type === 'video')) {
            void loadMediaBetter(m.id, m.media.type);
        }
    }

    async function loadMessagesBetter(initial = false) {
        if (!peer) return;
        const box = document.getElementById('messages');
        if (!box) return;

        const oldScroll = box.scrollTop;
        const oldHeight = box.scrollHeight;
        messageListWasAtBottom = oldScroll + box.clientHeight >= oldHeight - 50;

        try {
            const ms = await api('/media-messages?peer=' + encodeURIComponent(peer) + '&limit=80');
            if (!Array.isArray(ms)) throw Error('API вернул неверный формат сообщений');

            box.innerHTML = '';
            if (!ms.length) {
                box.innerHTML = '<div class="empty">Нет сообщений</div>';
                return;
            }

            for (const m of ms.slice().reverse()) {
                await renderMessageBetter(box, m);
            }

            if (initial || messageListWasAtBottom) {
                requestAnimationFrame(() => { box.scrollTop = box.scrollHeight; });
            } else {
                const newHeight = box.scrollHeight;
                box.scrollTop = oldScroll + (newHeight - oldHeight);
            }
        } catch (e) {
            box.innerHTML = '<div class="error-box">Не удалось загрузить диалог<br><small>' +
                escLocal(e.message) +
                '</small><br><button class="btn" style="margin-top:14px" onclick="loadMessagesBetter(false)">Повторить</button></div>';
            console.error('messages error', e);
        }
    }

    // Use the improved implementations everywhere after this script is injected.
    window.loadDialogs = loadDialogsWithPresence;
    window.renderDialogs = renderDialogsWithPresence;
    window.filterDialogs = filterDialogsWithPresence;
    window.openChat = openChatWithPresence;
    window.loadMessages = loadMessagesBetter;
    window.renderMessage = renderMessageBetter;
    window.downloadMedia = downloadMediaBetter;
    window.send = window.send;

    addBackButton();

    setInterval(() => {
        if (peer) refreshCurrentPresence();
    }, 30000);
})();
