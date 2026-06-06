(function () {
    if (window.__SiteAssistantLoaded) return;
    window.__SiteAssistantLoaded = true;

    var script = document.currentScript;
    if (!script) {
        var scripts = document.getElementsByTagName('script');
        script = scripts[scripts.length - 1];
    }

    var HEADPHONES_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>';

    var sessionId = 'sess_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    var isOpen = false;
    var operatorMode = false;
    var operatorActive = false;
    var lastOperatorMsgId = 0;
    var pollTimer = null;
    var baseUrl = script.getAttribute('data-base-url');

    var host = document.createElement('div');
        host.id = 'sa-widget-host';
    document.body.appendChild(host);

    var shadow = host.attachShadow({ mode: 'open' });
        shadow.innerHTML = `
            <link rel="stylesheet" href="${baseUrl}/widget-static/saportus-widget.css">
        `;

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

            var btn = document.createElement('button');
            btn.id = 'sa-widget-btn';
            btn.setAttribute('aria-label', 'Открыть чат помощника');
            btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
            shadow.appendChild(btn);


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
            shadow.appendChild(btn);
            shadow.appendChild(panel);


            var messagesEl = shadow.getElementById('sa-widget-messages');
            var input = shadow.getElementById('sa-widget-input');
            var sendBtn = shadow.getElementById('sa-widget-send');
            var operatorBtn = shadow.getElementById('sa-operator-btn');
            var operatorOverlay = shadow.getElementById('sa-widget-operator-overlay');
            var operatorBar = shadow.getElementById('sa-widget-operator-bar');
            var opBarText = shadow.getElementById('sa-op-bar-text');
            var headerName = shadow.getElementById('sa-header-name');
            var headerStatus = shadow.getElementById('sa-header-status');
            var avatar = shadow.getElementById('sa-avatar');

            var style = document.createElement('style');
            style.textContent = `
                #sa-widget-btn { background:${accent}; }
                #sa-widget-header { background:${accent}; }
                #sa-widget-messages { background:${chatBg}; }
                .sa-msg.user { background:${userBubbleBg}; color:${userTextColor}; }
                .sa-msg.bot { background:${botBubbleBg}; color:${botTextColor}; }
                #sa-operator-btn:hover { border-color:${accent}; color:${accent}; }
                #sa-widget-input:focus { border-color:${accent}; }
                #sa-widget-send { background:${accent}; }
            `;
            shadow.appendChild(style);

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
                } catch (e) { }
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
                    } catch (e) { }
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
                } catch (e) { }
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
