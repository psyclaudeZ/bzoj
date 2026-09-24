(() => {
  const key = 'bzoj.stopwatch.v1';
  const toggle = document.getElementById('timer-toggle');
  const reset = document.getElementById('timer-reset');
  let state = {elapsed: 0, startedAt: null};

  function restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(key));
      if (saved && Number.isFinite(saved.elapsed) && saved.elapsed >= 0 &&
          (saved.startedAt === null || (Number.isFinite(saved.startedAt) && saved.startedAt >= 0))) {
        state = saved;
      } else {
        state = {elapsed: 0, startedAt: null};
      }
    } catch {
      // Keep the timer usable if browser storage is unavailable.
    }
  }

  function elapsed() {
    return state.elapsed + (state.startedAt === null ? 0 : Math.max(0, Date.now() - state.startedAt));
  }

  function render() {
    const seconds = Math.floor(elapsed() / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor(seconds / 60) % 60;
    const pad = value => String(value).padStart(2, '0');
    toggle.textContent = `${hours ? pad(hours) + ':' : ''}${pad(minutes)}:${pad(seconds % 60)}`;
    const running = state.startedAt !== null;
    toggle.title = running ? 'Pause timer' : 'Start timer';
    toggle.setAttribute('aria-label', toggle.title);
    toggle.setAttribute('aria-pressed', String(running));
  }

  function save() {
    try { localStorage.setItem(key, JSON.stringify(state)); } catch {}
    render();
  }

  toggle.addEventListener('click', () => {
    restore();
    state = state.startedAt === null
      ? {elapsed: state.elapsed, startedAt: Date.now()}
      : {elapsed: elapsed(), startedAt: null};
    save();
  });
  reset.addEventListener('click', () => {
    state = {elapsed: 0, startedAt: null};
    save();
  });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) { restore(); render(); }
  });
  window.addEventListener('pageshow', () => { restore(); render(); });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) { restore(); render(); }
  });
  restore();
  render();
  setInterval(render, 250);
})();
