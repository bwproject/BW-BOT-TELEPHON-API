(() => {
    const css = document.createElement('style');
    css.textContent = `
        .settings-btn{width:100%;margin-bottom:8px;background:#121b30;border:1px solid var(--line)}
        .settings-overlay{position:fixed;inset:0;background:#0009;display:none;align-items:center;justify-content:center;padding:18px;z-index:9999}
        .settings-overlay.open{display:flex}
        .settings-modal{width:min(560px,100%);max-height:min(760px,92vh);overflow:auto;background:#11182b;border:1px solid #ffffff18;border-radius:22px;padding:22px;box-shadow:0 25px 80px #000b}
        .settings-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}
        .settings-title h2{margin:0;font-size:19px}.settings-close{width:38px;height:38px;border-radius:11px;border:1px solid var(--line);background:#121b30;color:var(--text);font-size:20px}
        .settings-row{padding:14px 0;border-bottom:1px solid var(--line)}
        .settings-row:last-child{border-bottom:0}.settings-label{font-weight:750}.settings-help{font-size:12px;color:var(--muted);margin-top:5px;line-height:1.4}
        .settings-select,.settings-input,.settings-textarea{width:100%;margin-top:9px;border:1px solid var(--line);border-radius:12px;background:#0a1120;color:var(--text);padding:11px;outline:0}
        .settings-textarea{min-height:100px;resize:vertical}.settings-check{display:flex;align-items:center;gap:9px;margin-top:10px;color:var(--text)}
        .settings-actions{display:flex;gap:9px;margin-top:18px}.settings-actions .btn{flex:1}.settings-danger{background:var(--danger)}
        .storage-info{font-size:12px;color:var(--muted);margin-top:10px}
        @media(max-width:760px){.settings-modal{max-height:90vh;padding:18px}.settings-actions{flex-direction:column}}
    `;
    document.head.appendChild(css);

    function escSettings(value){
        if(typeof esc==='function')return esc(value);
        return String(value??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;').replace(/'/g,'&#039;');
    }

    let settings={download_mode:'open',auto_download:true,excluded_peers:[],ttl_hours:24,auto_cleanup:true};

    function hasAuth(){
        return !!(typeof TOKEN !== 'undefined' && TOKEN);
    }

    function injectSettings(){
        const foot=document.querySelector('.side-foot');
        if(!foot||document.getElementById('settingsButton'))return;
        const button=document.createElement('button');
        button.id='settingsButton';
        button.className='btn settings-btn';
        button.textContent='⚙ Настройки вложений';
        button.onclick=openSettings;
        foot.insertBefore(button,foot.firstChild);

        const overlay=document.createElement('div');
        overlay.id='settingsOverlay';
        overlay.className='settings-overlay';
        overlay.innerHTML=`
          <div class="settings-modal" role="dialog" aria-modal="true">
            <div class="settings-title"><h2>Настройки вложений</h2><button class="settings-close" onclick="closeMediaSettings()">×</button></div>
            <div class="settings-row">
              <div class="settings-label">Скачивание вложений</div>
              <div class="settings-help">Выберите, какие чаты автоматически загружать на сервер.</div>
              <select id="mediaDownloadMode" class="settings-select">
                <option value="open">Только открытый чат</option>
                <option value="all">Все диалоги</option>
              </select>
            </div>
            <div class="settings-row">
              <label class="settings-check"><input id="mediaAutoDownload" type="checkbox"> Автоматически загружать фото и видео</label>
              <div class="settings-help">При отключении вложения остаются с кнопкой ручной загрузки.</div>
            </div>
            <div class="settings-row">
              <div class="settings-label">Исключения</div>
              <div class="settings-help">По одному peer/ID/username в строке. Например: 123456789 или username.</div>
              <textarea id="mediaExcluded" class="settings-textarea" placeholder="username\n123456789"></textarea>
            </div>
            <div class="settings-row">
              <div class="settings-label">Автоудаление</div>
              <label class="settings-check"><input id="mediaAutoCleanup" type="checkbox"> Удалять старые файлы автоматически</label>
              <div class="settings-help">По умолчанию файлы старше 24 часов удаляются.</div>
              <input id="mediaTtl" class="settings-input" type="number" min="1" max="720" placeholder="24">
            </div>
            <div class="settings-row">
              <div class="settings-label">Хранилище</div>
              <div id="mediaStorage" class="storage-info">Загрузка…</div>
              <button class="btn settings-danger" style="margin-top:10px;width:100%" onclick="clearMediaCache()">🗑 Удалить скачанные файлы</button>
            </div>
            <div class="settings-actions"><button class="btn outline" onclick="closeMediaSettings()">Отмена</button><button class="btn" onclick="saveMediaSettings()">Сохранить</button></div>
            <div id="mediaSettingsStatus" class="status"></div>
          </div>`;
        overlay.addEventListener('click',e=>{if(e.target===overlay)closeMediaSettings()});
        document.body.appendChild(overlay);
    }

    async function refreshSettings(){
        if(!hasAuth()) return;
        try{
            const data=await api('/media-settings');
            settings={...settings,...data};
            window.TG_MEDIA_SETTINGS=settings;
            const mode=document.getElementById('mediaDownloadMode');
            const auto=document.getElementById('mediaAutoDownload');
            const ex=document.getElementById('mediaExcluded');
            const cleanup=document.getElementById('mediaAutoCleanup');
            const ttl=document.getElementById('mediaTtl');
            if(mode)mode.value=settings.download_mode||'open';
            if(auto)auto.checked=!!settings.auto_download;
            if(ex)ex.value=(settings.excluded_peers||[]).join('\n');
            if(cleanup)cleanup.checked=!!settings.auto_cleanup;
            if(ttl)ttl.value=settings.ttl_hours||24;
            const storage=document.getElementById('mediaStorage');
            if(storage){
                const mb=((Number(settings.storage_bytes||0))/1024/1024).toFixed(1);
                storage.textContent=`${settings.storage_files||0} файлов • ${mb} MB • автоудаление: ${settings.ttl_hours||24} ч.`;
            }
        }catch(e){console.error('media settings error',e)}
    }

    async function openSettings(){
        if(!hasAuth()) return;
        injectSettings();
        document.getElementById('settingsOverlay').classList.add('open');
        await refreshSettings();
    }

    window.closeMediaSettings=()=>{
        const x=document.getElementById('settingsOverlay');if(x)x.classList.remove('open');
    };

    window.saveMediaSettings=async()=>{
        const status=document.getElementById('mediaSettingsStatus');
        try{
            if(!hasAuth())throw Error('Сначала войдите в Telegram Web');
            const excluded=document.getElementById('mediaExcluded').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
            const data={
                download_mode:document.getElementById('mediaDownloadMode').value,
                auto_download:document.getElementById('mediaAutoDownload').checked,
                excluded_peers:excluded,
                auto_cleanup:document.getElementById('mediaAutoCleanup').checked,
                ttl_hours:Number(document.getElementById('mediaTtl').value||24)
            };
            await api('/media-settings',{method:'PUT',body:JSON.stringify(data)});
            settings={...settings,...data};window.TG_MEDIA_SETTINGS=settings;
            status.textContent='Настройки сохранены';status.className='status';
            setTimeout(()=>closeMediaSettings(),500);
        }catch(e){status.textContent=e.message;status.className='status error'}
    };

    window.clearMediaCache=async()=>{
        if(!hasAuth())return;
        if(!confirm('Удалить все скачанные вложения с сервера?'))return;
        const status=document.getElementById('mediaSettingsStatus');
        try{
            const r=await api('/media-cache',{method:'DELETE'});
            status.textContent=`Удалено файлов: ${r.removed_files||0}`;status.className='status';
            await refreshSettings();
        }catch(e){status.textContent=e.message;status.className='status error'}
    };

    injectSettings();

    // Do not call protected API endpoints while the login screen is shown.
    // The previous unconditional timer caused /media-settings -> 401 -> logout()
    // -> location.reload(), creating an endless refresh loop before login.
    if(hasAuth()) setTimeout(refreshSettings,500);

    // index.html dispatches this event immediately after successful login.
    window.addEventListener('telegram-web-auth-ready',()=>{
        setTimeout(refreshSettings,100);
    });
})();
