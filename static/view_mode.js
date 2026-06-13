(function () {
    function applyView(mode) {
        document.documentElement.setAttribute('data-view', mode);
        try { localStorage.setItem('view-mode', mode); } catch (e) {}
        document.querySelectorAll('[data-view-target]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.viewTarget === mode);
            btn.setAttribute('aria-pressed', btn.dataset.viewTarget === mode);
        });
    }

    function currentView() {
        return document.documentElement.getAttribute('data-view') || 'grid';
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-view-target]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.viewTarget === currentView());
            btn.setAttribute('aria-pressed', btn.dataset.viewTarget === currentView());
            btn.addEventListener('click', () => applyView(btn.dataset.viewTarget));
        });
    });
})();
