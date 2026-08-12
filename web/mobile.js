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
                    day: '2-digit',
                    month: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
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
            if (typeof poll !== 'undefined' && poll) {
                clearInterval(poll);
                poll = null;
            }
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
            renderDialogs();
        } catch (e) {
            box.innerHTML = '<div class="error-box">Не удалось загрузить диалоги<br><small>' +
                escLocal(e.message) +
                '</small><br><button class="btn" style="margin-top:14px" onclick="loadDialogs()">Повторить</button></div>';
            console.error('dialogs presence error', e);
        }
    }

    function renderDialogsWithPresence() {
        const q = document.getElementById('search').value.trim().toLowerCase();
        const box = document.getElementById('dialogs');
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
                '<div id="' + avId + '" class="avatar">' +
                    escLocal((d.name || '?')[0].toUpperCase()) +
                '</div>' +
                '<div class="dialog-main">' +
                    '<div class="dialog-name">' +
                        escLocal(d.name || d.username || d.id) +
                    '</div>' +
                    '<div class="dialog-sub' + presenceClass + '">' +
                        escLocal(d.username ? '@' + d.username : presenceText) +
                    '</div>' +
                '</div>' +
                (d.unread ? '<span class="badge">' + d.unread + '</span>' : '');

            el.onclick = () => openChatWithPresence(d);
            box.appendChild(el);

            if (typeof setAvatar === 'function') {
                setAvatar(avId, String(d.id));
            }
        });
    }

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
        await loadMessages();
        poll = setInterval(loadMessages, 4000);

        // Refresh presence while the chat is open.
        if (d.is_user) refreshCurrentPresence();
    }

    async function refreshCurrentPresence() {
        if (!peer) return;
        try {
            const data = await api('/presence?peer=' + encodeURIComponent(peer));
            const text = formatPresence(data.presence);
            const meta = document.getElementById('chatMeta');
            if (meta) {
                meta.textContent = data.username
                    ? '@' + data.username + (text ? ' • ' + text : '')
                    : text;
                meta.className = 'chat-meta' +
                    ((data.presence && data.presence.online) ? ' presence-online' : '');
            }

            const current = dialogs.find(d => String(d.id) === String(peer) || d.username === peer);
            if (current) current.presence = data.presence;
            renderDialogsWithPresence();
        } catch (_) {}
    }

    // Replace the original dialog loader/rendering with the presence-aware version.
    window.loadDialogs = loadDialogsWithPresence;
    window.renderDialogs = renderDialogsWithPresence;
    window.openChat = openChatWithPresence;

    addBackButton();

    // Keep presence reasonably fresh without disturbing message polling.
    setInterval(() => {
        if (peer) refreshCurrentPresence();
    }, 30000);
})();
