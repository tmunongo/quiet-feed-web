/* Browser behavior stays here; edition and account state live on the server. */
(() => {
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  const showError = (message) => {
    const box = document.getElementById('request-error');
    if (box) { box.textContent = message; box.hidden = false; }
  };

  document.addEventListener('htmx:configRequest', (event) => {
    event.detail.headers['X-CSRF-Token'] = csrf();
  });
  document.addEventListener('htmx:beforeSwap', (event) => {
    if (event.detail.xhr.status === 400 || event.detail.xhr.status === 422) {
      event.detail.shouldSwap = true;
      event.detail.isError = false;
    }
  });
  document.addEventListener('htmx:responseError', () => showError('Could not save that change. Refresh the page and try again.'));
  document.addEventListener('htmx:sendError', () => showError('Could not reach Quiet Feed. Check your connection and try again.'));

  document.addEventListener('alpine:init', () => {
    Alpine.data('categoryState', () => ({
      collapsed: false,
      init() { this.collapsed = this.$el.dataset.collapsed === 'true'; },
      toggle() {
        this.collapsed = !this.collapsed;
        this.$el.dataset.collapsed = String(this.collapsed);
        const collapsed = Array.from(document.querySelectorAll('[data-category][data-collapsed="true"]')).map(el => el.dataset.category);
        fetch('/api/settings/collapsed-categories', {
          method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf() },
          body: JSON.stringify({ collapsed }), keepalive: true,
        }).catch(() => showError('Could not save your category preference.'));
      },
    }));
  });

  let disposeReader = () => {};
  function initializeReader() {
    disposeReader();
    const reader = document.querySelector('[data-reader]');
    if (!reader) return;
    let percent = Number(reader.dataset.scrollPercent);
    let offset = Number(reader.dataset.scrollOffset);
    let read = reader.dataset.read === 'true';
    let timer, dirty = false;
    const controller = new AbortController();
    const button = document.getElementById('toggle-read');
    const bar = document.getElementById('progress-bar');
    const updateButton = () => { button.textContent = read ? 'Mark unread' : 'Mark as read'; button.setAttribute('aria-pressed', String(read)); };
    const save = (payload) => fetch(`/article/${reader.dataset.progressId}/progress`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf() },
      body: JSON.stringify(payload), keepalive: true,
    }).catch(() => {});
    const flush = () => {
      clearTimeout(timer);
      if (!dirty) return;
      dirty = false;
      if (!read && percent >= 92) { read = true; updateButton(); }
      save({ scrollPercent: percent, scrollOffset: offset, read });
    };
    const scroll = () => {
      const height = document.documentElement.scrollHeight - window.innerHeight;
      offset = Math.max(0, Math.round(window.scrollY));
      percent = Math.max(percent, Math.min(100, height > 0 ? Math.round(offset / height * 100) : 100));
      bar.style.width = `${percent}%`;
      dirty = true;
      clearTimeout(timer);
      timer = setTimeout(flush, 600);
    };
    button.addEventListener('click', () => {
      clearTimeout(timer);
      read = !read;
      dirty = false;
      updateButton();
      save({ read, scrollPercent: percent, scrollOffset: offset });
    }, { signal: controller.signal });
    window.addEventListener('scroll', scroll, { passive: true, signal: controller.signal });
    window.addEventListener('pagehide', flush, { signal: controller.signal });
    document.addEventListener('visibilitychange', () => { if (document.hidden) flush(); }, { signal: controller.signal });
    const restore = () => requestAnimationFrame(() => window.scrollTo(0, offset));
    if (document.readyState === 'complete') restore();
    else window.addEventListener('load', restore, { once: true, signal: controller.signal });
    disposeReader = () => { flush(); controller.abort(); clearTimeout(timer); };
  }
  document.addEventListener('DOMContentLoaded', initializeReader);
  document.addEventListener('htmx:afterSwap', initializeReader);

  // Retire the root-scoped Svelte/Workbox worker before a later PWA release.
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(registrations => {
      for (const registration of registrations) {
        const worker = registration.active || registration.waiting;
        if (registration.scope === new URL('/', location.href).href && worker && new URL(worker.scriptURL).pathname === '/sw.js') {
          registration.update().catch(() => {});
        }
      }
    }).catch(() => {});
  }
})();
