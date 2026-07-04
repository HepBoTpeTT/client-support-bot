/* ─────────────────────────────────────────────────────────
   Saportus Widget Core v2
   Общая логика для JS-виджета и iframe-виджета.
   Загружается автоматически — не требует отдельного <script>.
   ───────────────────────────────────────────────────────── */

(function (global) {
    'use strict';

    // ── SVG-иконки ──────────────────────────────────────────
    var BOT_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>';
    var CHAT_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
    var CLOSE_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    var HEADPHONES_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z"/><path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>';

    // ── HTML панели ──────────────────────────────────────────
    function buildPanelHTML(botName) {
        return '<div id="sa-widget-header">'
            + '<div class="sa-avatar" id="sa-avatar">' + BOT_SVG + '</div>'
            + '<div>'
            + '<div class="sa-name" id="sa-header-name">' + botName + '</div>'
            + '<div class="sa-status" id="sa-header-status">Онлайн</div>'
            + '</div>'
            + '<button class="sa-close" aria-label="Закрыть">' + CLOSE_SVG + '</button>'
            + '</div>'
            + '<div id="sa-widget-operator-bar">'
            + '<div class="sa-op-dot"></div>'
            + '<span id="sa-op-bar-text">Ожидание оператора...</span>'
            + '</div>'
            + '<div id="sa-widget-body">'
            + '<div id="sa-widget-messages"></div>'
            + '<div id="sa-widget-operator-overlay" class="visible">'
            + '<button id="sa-operator-btn">' + HEADPHONES_SVG + ' Связаться с оператором</button>'
            + '</div>'
            + '</div>'
            + '<div id="sa-widget-input-area">'
            + '<textarea id="sa-widget-input" placeholder="Задайте вопрос..." rows="1"></textarea>'
            + '<button id="sa-widget-send">Отправить</button>'
            + '</div>';
    }

    // ── CSS темы ─────────────────────────────────────────────
    function buildThemeCSS(cfg) {
        var a = cfg.accent_color || '#01696f';
        return '#sa-widget-btn{background:' + a + '}'
            + '#sa-widget-header{background:' + a + '}'
            + '#sa-widget-messages{background:' + (cfg.chat_bg_color || '#f8f9fb') + '}'
            + '.sa-msg.user{background:' + (cfg.user_bubble_bg || a) + ';color:' + (cfg.user_text_color || '#fff') + '}'
            + '.sa-msg.bot{background:' + (cfg.bot_bubble_bg || '#fff') + ';color:' + (cfg.bot_text_color || '#222') + '}'
            + '#sa-operator-btn:hover{border-color:' + a + ';color:' + a + '}'
            + '#sa-widget-input:focus{border-color:' + a + '}'
            + '#sa-widget-send{background:' + a + '}';
    }

    // ── Добавить сообщение ───────────────────────────────────
    function addMessage(messagesEl, role, text) {
        var el = document.createElement('div');
        el.className = 'sa-msg ' + role;
        if (role === 'bot typing') {
            el.innerHTML = '<span class="sa-typing-dots" aria-label="Бот печатает">'
                + '<span></span><span></span><span></span></span>';
        } else {
            el.textContent = text;
        }
        messagesEl.appendChild(el);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return el;
    }

    // ── Иконка кнопки ────────────────────────────────────────
    function setBtnIcon(btn, isOpen) {
        btn.innerHTML = isOpen ? CLOSE_SVG : CHAT_SVG;
    }

    // ── Ядро виджета ─────────────────────────────────────────
    // options:
    //   baseUrl   {string}   — URL бэкенда
    //   root      {Element}  — Shadow DOM root или document
    //   styleEl   {Element}  — <style> для темы
    //   onReady   {Function}
    //   onError   {Function}
    function initWidget(options) {
        var baseUrl  = options.baseUrl;
        var root     = options.root;
        var styleEl  = options.styleEl;

        var STORAGE_KEY = 'saportus_session_id';
        var sessionId = localStorage.getItem(STORAGE_KEY);
        if (!sessionId) {
            sessionId = 'sess_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
            localStorage.setItem(STORAGE_KEY, sessionId);
        }
        
        var isOpen         = false;
        var operatorMode   = false;
        var operatorActive = false;
        var operatorWs     = null;
        var botName        = 'Помощник';

        function $id(id) {
            return root.getElementById ? root.getElementById(id) : root.querySelector('#' + id);
        }

        fetch(baseUrl + '/api/widget-config')
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (cfg) {
                botName = cfg.bot_name || 'Помощник';

                // Кнопка открытия
                var btn = document.createElement('button');
                btn.id = 'sa-widget-btn';
                btn.setAttribute('aria-label', 'Открыть чат помощника');
                setBtnIcon(btn, false);
                root.appendChild(btn);

                // Панель
                var panel = document.createElement('div');
                panel.id = 'sa-widget-panel';
                panel.setAttribute('role', 'dialog');
                panel.innerHTML = buildPanelHTML(botName);
                root.appendChild(panel);

                // Тема
                styleEl.textContent = buildThemeCSS(cfg);

                var messagesEl      = $id('sa-widget-messages');
                var input           = $id('sa-widget-input');
                var sendBtn         = $id('sa-widget-send');
                var operatorBtn     = $id('sa-operator-btn');
                var operatorOverlay = $id('sa-widget-operator-overlay');
                var operatorBar     = $id('sa-widget-operator-bar');
                var opBarText       = $id('sa-op-bar-text');
                var headerName      = $id('sa-header-name');
                var headerStatus    = $id('sa-header-status');
                var avatar          = $id('sa-avatar');
                var closeBtn        = panel.querySelector('.sa-close');

                // ── WebSocket оператора ──────────────────────
                function connectOperatorWS() {
                    if (operatorWs) return;
                    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
                    var host  = baseUrl.replace(/^https?:\/\//, '');
                    operatorWs = new WebSocket(proto + '//' + host + '/ws/chat/' + sessionId);

                    operatorWs.onmessage = function (e) {
                        try {
                            var msg = JSON.parse(e.data);

                            if (msg.type === 'operator_message') {
                                addMessage(messagesEl, 'operator', msg.content);
                            }

                            if (msg.type === 'status_update') {
                                if (msg.status === 'active' && !operatorActive) {
                                    operatorActive = true;
                                    opBarText.textContent = 'Оператор подключён';
                                    avatar.innerHTML = HEADPHONES_SVG;
                                    avatar.style.color = '#fff';
                                    headerName.textContent = 'Оператор';
                                    headerStatus.textContent = 'Онлайн';
                                    operatorOverlay.classList.remove('visible');
                                }
                                if (msg.status === 'closed') {
                                    // operatorWs.close();
                                    // operatorWs = null;
                                    addMessage(messagesEl, 'system', 'Оператор завершил сеанс. Чат снова с AI-помощником.');
                                    operatorMode   = false;
                                    operatorActive = false;
                                    operatorBar.classList.remove('visible');
                                    operatorOverlay.classList.add('visible');
                                    operatorBtn.disabled = false;
                                    operatorBtn.innerHTML = HEADPHONES_SVG + ' Связаться с оператором';
                                    avatar.innerHTML = BOT_SVG;
                                    avatar.style.color = '';
                                    headerName.textContent = botName;
                                    headerStatus.textContent = 'Онлайн';
                                }
                            }
                        } catch (_) {}
                    };

                    operatorWs.onclose = function () {
                        operatorWs = null;
                        if (operatorMode) setTimeout(connectOperatorWS, 3000);
                    };

                    operatorWs.onerror = function () {
                        if (operatorWs) operatorWs.close();
                    };
                }

                // ── Отправка AI-сообщения ────────────────────
                function sendAiMessage() {
                    var text = input.value.trim();
                    if (!text) return;
                    input.value = '';
                    addMessage(messagesEl, 'user', text);
                    var typingEl = addMessage(messagesEl, 'bot typing', '');
                    fetch(baseUrl + '/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: text, session_id: sessionId })
                    })
                        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
                        .then(function (res) {
                            typingEl.classList.remove('typing');
                            typingEl.textContent = res.ok
                                ? (res.d.reply || 'Извините, не могу ответить прямо сейчас.')
                                : 'Извините, не могу ответить прямо сейчас. Попробуйте позже.';
                        })
                        .catch(function () {
                            typingEl.classList.remove('typing');
                            typingEl.textContent = 'Ошибка соединения с сервером.';
                        })
                        .finally(function () { input.focus(); });
                }

                // ── Отправка сообщения оператору ─────────────
                function sendOperatorMessage() {
                    var text = input.value.trim();
                    if (!text) return;
                    input.value = '';
                    addMessage(messagesEl, 'user', text);
                    fetch(baseUrl + '/api/operator/user-message', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ session_id: sessionId, message: text })
                    }).catch(function () {}).finally(function () { input.focus(); });
                }

                // ── Обработчики событий ──────────────────────
                operatorBtn.addEventListener('click', function () {
                    if (operatorMode) return;
                    operatorMode = true;
                    operatorBtn.disabled = true;
                    operatorBtn.innerHTML = '⏳ Запрос отправлен...';
                    operatorBar.classList.add('visible');
                    opBarText.textContent = 'Ожидание оператора...';
                    addMessage(messagesEl, 'system', 'Запрос на подключение оператора отправлен. Ожидайте ответа.');
                    fetch(baseUrl + '/api/operator/request', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: 'Пользователь запрашивает оператора', session_id: sessionId })
                    }).catch(function () {});
                    connectOperatorWS();
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

                btn.addEventListener('click', function () {
                    isOpen = !isOpen;
                    panel.classList.toggle('open', isOpen);
                    setBtnIcon(btn, isOpen);
                    if (isOpen) input.focus();
                });

                closeBtn.addEventListener('click', function () {
                    isOpen = false;
                    panel.classList.remove('open');
                    setBtnIcon(btn, false);
                });

                // Приветствие
                addMessage(messagesEl, 'bot', cfg.welcome_message || 'Здравствуйте! Чем могу помочь?');

                if (options.onReady) options.onReady();
            })
            .catch(function (e) {
                console.error('[Saportus] init error:', e);
                if (options.onError) options.onError(e);
            });
    }

    // ── Публичный API ────────────────────────────────────────
    global.SaportusCore = {
        initWidget:    initWidget,
        addMessage:    addMessage,
        setBtnIcon:    setBtnIcon,
        buildThemeCSS: buildThemeCSS,
        BOT_SVG:       BOT_SVG,
        CHAT_SVG:      CHAT_SVG,
        CLOSE_SVG:     CLOSE_SVG,
        HEADPHONES_SVG: HEADPHONES_SVG,
    };

})(window);
