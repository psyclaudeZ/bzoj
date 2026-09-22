const tabs = [...document.querySelectorAll('.statement-tabs [role="tab"]')];
const historyTab = document.getElementById('history-tab');
const historyPanel = document.getElementById('history-panel');
let pendingHistory;

function activateTab(selected) {
  for (const tab of tabs) {
    const active = tab === selected;
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
    document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
  }
}

async function showHistory(url) {
  pendingHistory?.abort();
  const request = new AbortController();
  pendingHistory = request;
  activateTab(historyTab);
  historyPanel.setAttribute('aria-busy', 'true');
  historyPanel.innerHTML = '<p class="empty-list">Loading submissions…</p>';
  try {
    const response = await fetch(url, {signal: request.signal});
    if (!response.ok) throw new Error('History request failed');
    const html = await response.text();
    if (request.signal.aborted) return;
    historyPanel.innerHTML = html;
    historyPanel.scrollTop = 0;
  } catch (error) {
    if (error.name !== 'AbortError') {
      historyPanel.innerHTML = '<p class="empty-list" role="alert">Could not load history. Select History to retry.</p>';
    }
  } finally {
    if (pendingHistory === request) historyPanel.removeAttribute('aria-busy');
  }
}

for (const tab of tabs) {
  tab.addEventListener('click', () => {
    if (tab === historyTab) showHistory(tab.dataset.historyUrl);
    else activateTab(tab);
  });
  tab.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1) : tabs.find(item => item !== tab);
    next.focus();
    next.click();
  });
}

document.addEventListener('click', event => {
  const link = event.target.closest('a[data-history-link]');
  if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  showHistory(link.href);
  historyTab.focus();
});
