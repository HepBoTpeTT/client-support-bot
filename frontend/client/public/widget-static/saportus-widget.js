/* ─────────────────────────────────────────────────────────
   Saportus Widget — JS / Shadow DOM обёртка
   Пользователь вставляет одну строку:
     <script src=".../saportus-widget.js" data-base-url="..."></script>
   Core загружается автоматически.
   ───────────────────────────────────────────────────────── */

(function () {
    'use strict';

    if (window.__SaportusLoaded) return;
    window.__SaportusLoaded = true;

    var script = document.currentScript
        || (function () {
            var s = document.getElementsByTagName('script');
            return s[s.length - 1];
        })();

    var baseUrl = (script.getAttribute('data-base-url') || '').replace(/\/$/, '');
    if (!baseUrl) {
        console.error('[Saportus] data-base-url не указан');
        return;
    }

    // Создаём Shadow DOM host
    var host = document.createElement('div');
    host.id = 'sa-widget-host';
    document.body.appendChild(host);
    var shadow = host.attachShadow({ mode: 'open' });

    // CSS в Shadow DOM (единый файл)
    var cssLink = document.createElement('link');
    cssLink.rel = 'stylesheet';
    cssLink.href = baseUrl + '/widget-static/saportus-widget.css';
    shadow.appendChild(cssLink);

    // <style> для динамической темы
    var styleEl = document.createElement('style');
    shadow.appendChild(styleEl);

    // Загружаем core.js и инициализируем виджет
    var coreScript = document.createElement('script');
    coreScript.src = baseUrl + '/widget-static/saportus-widget-core.js';
    coreScript.onload = function () {
        window.SaportusCore.initWidget({
            baseUrl:  baseUrl,
            root:     shadow,
            styleEl:  styleEl,
            onReady:  function () { console.debug('[Saportus] widget ready'); },
            onError:  function (e) { console.error('[Saportus] widget error:', e); },
        });
    };
    coreScript.onerror = function () {
        console.error('[Saportus] не удалось загрузить core.js');
    };
    document.head.appendChild(coreScript);
})();
