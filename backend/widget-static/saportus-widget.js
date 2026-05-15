(function () {
  if (window.__SiteAssistantLoaded) return;
  window.__SiteAssistantLoaded = true;

  var script = document.currentScript;
  if (!script) {
    var scripts = document.getElementsByTagName('script');
    script = scripts[scripts.length - 1];
  }

  var HEADPHONES_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>';

  var btn = document.createElement('button');
  btn.id = 'sa-widget-btn';
  btn.setAttribute('aria-label', 'Открыть чат помощника');
  btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  document.body.appendChild(btn);


  var sessionId    = 'sess_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
  var isOpen       = false;
  var operatorMode = false;
  var operatorActive = false;
  var lastOperatorMsgId = 0;
  var pollTimer    = null;
  var baseUrl = script.getAttribute('data-base-url');




  async function startWidget() {
    try {
      const r = await fetch(baseUrl + "/api/widget-config");
      console.log('STATUS:', r.status, 'OK:', r.ok);
      if (!r.ok) {
        throw new Error('HTTP ' + r.status);
      }
      const botConfigData = await r.json();
      console.log('CONFIG DATA:', botConfigData);
      console.table(botConfigData);

      var botName = botConfigData.bot_name;
      var accent = botConfigData.accent_color;
      var welcome = botConfigData.welcome_message;
      var chatBg = botConfigData.chat_bg_color;
      var userBubbleBg = botConfigData.user_bubble_bg;
      var userTextColor = botConfigData.user_text_color;
      var botBubbleBg = botConfigData.bot_bubble_bg;
      var botTextColor = botConfigData.bot_text_color;

      console.log(botConfigData);


      var panel = document.createElement('div');
      panel.id = 'sa-widget-panel';
      panel.setAttribute('role', 'dialog');
      panel.innerHTML = `
          <div id="sa-widget-header">
            <div class="sa-avatar" id="sa-avatar">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-bot w-4 h-4">
                <path d="M12 8V4H8"></path>
                <rect width="16" height="12" x="4" y="8" rx="2"></rect>
                <path d="M2 14h2"></path><path d="M20 14h2"></path>
                <path d="M15 13v2"></path><path d="M9 13v2"></path>
              </svg>
            </div>
            <div>
              <div class="sa-name" id="sa-header-name">${botName}</div>
              <div class="sa-status" id="sa-header-status">Онлайн</div>
            </div>
            <button class="sa-close" aria-label="Закрыть">✕</button>
          </div>
          <div id="sa-widget-operator-bar">
            <div class="sa-op-dot"></div>
            <span id="sa-op-bar-text">Ожидание оператора...</span>
          </div>
          <div id="sa-widget-body">
            <div id="sa-widget-messages"></div>
            <div id="sa-widget-operator-overlay" class="visible">
              <button id="sa-operator-btn">${HEADPHONES_SVG} Связаться с оператором</button>
            </div>
          </div>
          <div id="sa-widget-input-area">
            <textarea id="sa-widget-input" placeholder="Напишите вопрос..." rows="1"></textarea>
            <button id="sa-widget-send">Отправить</button>
          </div>
        `;
      document.body.appendChild(panel);
      

      var messagesEl = document.getElementById('sa-widget-messages');
      var input = document.getElementById('sa-widget-input');
      var sendBtn = document.getElementById('sa-widget-send');
      var operatorBtn = document.getElementById('sa-operator-btn');
      var operatorOverlay = document.getElementById('sa-widget-operator-overlay');
      var operatorBar = document.getElementById('sa-widget-operator-bar');
      var opBarText = document.getElementById('sa-op-bar-text');
      var headerName = document.getElementById('sa-header-name');
      var headerStatus = document.getElementById('sa-header-status');
      var avatar = document.getElementById('sa-avatar');

      var style = document.createElement('style');
      style.textContent = `
          #sa-widget-btn { position:fixed; bottom:24px; right:24px; width:56px; height:56px; border-radius:50%; background:${accent}; border:none; cursor:pointer; z-index:999998; box-shadow:0 4px 16px rgba(0,0,0,0.2); display:flex; align-items:center; justify-content:center; transition:transform 0.2s,box-shadow 0.2s; }
          #sa-widget-btn:hover { transform:scale(1.08); box-shadow:0 6px 20px rgba(0,0,0,0.28); }
          #sa-widget-btn svg { width:26px; height:26px; fill:none; stroke:#fff; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
          #sa-widget-panel { position:fixed; bottom:92px; right:24px; width:380px; max-width:calc(100vw - 48px); height:540px; border-radius:16px; background:#fff; box-shadow:0 8px 40px rgba(0,0,0,0.18); z-index:999999; display:flex; flex-direction:column; overflow:hidden; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; transition:opacity 0.2s,transform 0.2s; opacity:0; transform:translateY(16px) scale(0.97); pointer-events:none; }
          #sa-widget-panel.open { opacity:1; transform:none; pointer-events:all; }
          #sa-widget-header { background:${accent}; color:#fff; padding:14px 18px; display:flex; align-items:center; gap:10px; flex-shrink:0; }
          #sa-widget-header .sa-avatar { width:34px; height:34px; border-radius:50%; background:rgba(255,255,255,0.25); display:flex; align-items:center; justify-content:center; font-size:17px; }
          #sa-widget-header .sa-name { font-weight:600; font-size:14px; }
          #sa-widget-header .sa-status { font-size:11px; opacity:0.85; }
          #sa-widget-header .sa-close { margin-left:auto; background:none; border:none; color:#fff; cursor:pointer; opacity:0.8; padding:4px; border-radius:6px; }
          #sa-widget-header .sa-close:hover { opacity:1; background:rgba(255,255,255,0.15); }
          #sa-widget-operator-bar { display:none; padding:7px 14px; background:#eef7ff; border-top:1px solid #c8e0f8; font-size:12px; color:#3a7bc8; flex-shrink:0; align-items:center; gap:8px; }
          #sa-widget-operator-bar.visible { display:flex; }
          #sa-widget-operator-bar .sa-op-dot { width:8px; height:8px; border-radius:50%; background:#3a7bc8; animation:sa-pulse 1.5s infinite; }
          @keyframes sa-pulse { 0%,100% { opacity:1; } 50% { opacity:0.35; } }
          #sa-widget-messages { flex:1; overflow-y:auto; padding:14px; display:flex; flex-direction:column; gap:9px; background:${chatBg}; padding-bottom: 3.5rem;}
          .sa-msg { max-width:82%; padding:9px 13px; border-radius:12px; font-size:13.5px; line-height:1.5; word-break:break-word; }
          .sa-msg.user { align-self:flex-end; background:${userBubbleBg}; color:${userTextColor}; border-bottom-right-radius:4px; }
          .sa-msg.bot { align-self:flex-start; background:${botBubbleBg}; color:${botTextColor}; border-bottom-left-radius:4px; box-shadow:0 1px 4px rgba(0,0,0,0.08); }
          .sa-msg.operator { align-self:flex-start; background:#eef7ff; color:#1a4a7a; border-bottom-left-radius:4px; box-shadow:0 1px 4px rgba(0,0,0,0.06); border-left:3px solid #3a8fe8; }
          .sa-msg.system { align-self:center; background:#f0f0f0; color:#666; font-size:12px; padding:5px 12px; border-radius:99px; font-style:italic; }
          .sa-msg.typing { color:#999; font-style:italic; }
          #sa-widget-body { flex:1; position:relative; overflow:hidden; display:flex; flex-direction:column; }
          #sa-widget-operator-overlay { display:none; position:absolute; bottom:0; left:0; right:0; padding:10px 14px; background:transparent; z-index:10; }
          #sa-widget-operator-overlay.visible { display:block; }
          #sa-operator-btn { width:100%; background:rgba(255,255,255,0.92); backdrop-filter:blur(4px); border:1px solid #ddd; border-radius:8px; padding:8px 12px; cursor:pointer; font-size:12.5px; color:#555; text-align:center; transition:all 0.15s; white-space:nowrap; display:flex; align-items:center; justify-content:center; gap:6px; box-shadow:0 2px 8px rgba(0,0,0,0.08); }
          #sa-operator-btn:hover { border-color:${accent}; color:${accent}; background:rgba(255,255,255,0.98); }
          #sa-widget-input-area { padding:10px 14px; border-top:1px solid #eee; display:flex; gap:8px; background:#fff; flex-shrink:0; }
          #sa-widget-input { flex:1; border:1px solid #ddd; border-radius:8px; padding:7px 11px; font-size:13.5px; outline:none; resize:none; height:38px; line-height:1.4; }
          #sa-widget-input:focus { border-color:${accent}; }
          #sa-widget-send { background:${accent}; color:#fff; border:none; border-radius:8px; padding:7px 13px; cursor:pointer; font-size:13.5px; font-weight:500; transition:background 0.15s; }
          #sa-widget-send:hover { filter:brightness(0.9); }
          #sa-widget-send:disabled { opacity:0.5; cursor:not-allowed; }
        `;
      

      document.head.appendChild(style);

      function addMessage(role, text) {
        var el = document.createElement('div');
        el.className = 'sa-msg ' + role;
        el.textContent = text;
        messagesEl.appendChild(el);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return el;
      }
      addMessage('bot', welcome);



      // AI chat
      async function sendAiMessage() {
        var text = input.value.trim();
        if (!text) return;
        input.value = '';
        input.style.height = '38px';
        sendBtn.disabled = true;
        addMessage('user', text);
        var typingEl = addMessage('bot typing', '...');
        try {
          var r = await fetch(baseUrl + "/api/chat", {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, session_id: sessionId })
          });
          var data = await r.json();
          typingEl.remove();
          if (!r.ok) {
            addMessage('bot', 'Извините, не могу ответить прямо сейчас. Попробуйте позже.');
          } else {
            addMessage('bot', data.reply || 'Извините, не могу ответить прямо сейчас.');
          }
        } catch (e) {
          typingEl.remove();
          addMessage('bot', 'Ошибка соединения с сервером.');
        }
        sendBtn.disabled = false;
        input.focus();
      }

      // Operator mode
      async function sendOperatorMessage() {
        var text = input.value.trim();
        if (!text) return;
        input.value = '';
        input.style.height = '38px';
        sendBtn.disabled = true;
        addMessage('user', text);
        try {
          await fetch(baseUrl + '/api/operator/user-message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, message: text })
          });
        } catch (e) {}
        sendBtn.disabled = false;
        input.focus();
      }

      function startOperatorPoll() {
        if (pollTimer) return;
        pollTimer = setInterval(async function () {
          try {
            var r = await fetch(baseUrl + "/api/operator/poll/" + sessionId + '?last_id=' + lastOperatorMsgId);
            var data = await r.json();

            if (data.status === 'active' && !operatorActive) {
              operatorActive = true;
              opBarText.textContent = 'Оператор подключён';
              avatar.innerHTML = HEADPHONES_SVG;
              avatar.style.color = '#fff';
              headerName.textContent = 'Оператор';
              headerStatus.textContent = 'Онлайн';
              operatorOverlay.classList.remove('visible');
            }

            if (data.messages && data.messages.length) {
              data.messages.forEach(function (m) {
                addMessage('operator', m.content);
                lastOperatorMsgId = m.id;
              });
            }

            if (data.status === 'closed') {
              clearInterval(pollTimer);
              pollTimer = null;
              addMessage('system', 'Оператор завершил сеанс. Чат снова с AI-помощником.');
              operatorMode = false;
              operatorActive = false;
              operatorBar.classList.remove('visible');
              operatorOverlay.classList.add('visible');
              operatorBtn.disabled = false;
              operatorBtn.innerHTML = HEADPHONES_SVG + ' Связаться с оператором';
              avatar.innerHTML = '🤖';
              avatar.style.color = '';
              headerName.textContent = botName;
              headerStatus.textContent = 'Онлайн';
            }
          } catch (e) {}
        }, 3000);
      }

      operatorBtn.addEventListener('click', async function () {
        if (operatorMode) return;
        operatorMode = true;
        operatorBtn.disabled = true;
        operatorBtn.innerHTML = '⏳ Запрос отправлен...';
        operatorBar.classList.add('visible');
        opBarText.textContent = 'Ожидание оператора...';
        addMessage('system', 'Запрос на подключение оператора отправлен. Ожидайте ответа.');
        try {
          await fetch(baseUrl + '/api/operator/request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: 'Пользователь запрашивает оператора', session_id: sessionId })
          });
        } catch (e) {}
        startOperatorPoll();
      });

      sendBtn.addEventListener('click', function () {
        if (operatorMode) sendOperatorMessage(); else sendAiMessage();
      });

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          if (operatorMode) sendOperatorMessage(); else sendAiMessage();
        }
      });

      input.addEventListener('input', function () {
        this.style.height = '38px';
        this.style.height = Math.min(this.scrollHeight, 100) + 'px';
      });

      btn.addEventListener('click', function () {
        isOpen = !isOpen;
        if (isOpen) {
          panel.classList.add('open');
          input.focus();
          btn.innerHTML = '<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
        } else {
          panel.classList.remove('open');
          btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
        }
      });

      panel.querySelector('.sa-close').addEventListener('click', function () {
        isOpen = false;
        panel.classList.remove('open');
        btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
      });
    } catch (e) {
      console.error('loadConfig error:', e);
      throw e;
    }
  }
  startWidget();





})();
