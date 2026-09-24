export function bindExecution(form, getSource) {
  const panel = form.closest('.editor-panel');
  const buttons = [...form.querySelectorAll('button[type="submit"]')];
  let running = false;

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (running) return;
    running = true;
    const url = event.submitter?.getAttribute('formaction') || form.action;
    const source = getSource();
    buttons.forEach(button => { button.disabled = true; });

    let output = panel.querySelector('.results');
    if (!output) {
      output = document.createElement('section');
      output.className = 'results';
      output.setAttribute('aria-labelledby', 'result-title');
      panel.append(output);
    }
    output.innerHTML = '<div class="panel-heading"><h2 id="result-title"></h2></div>' +
      '<div class="result-content"><p role="status">Running…</p></div>';
    output.querySelector('h2').textContent = new URL(url, location.href).pathname.endsWith('/test')
      ? 'Sample results' : 'Output';
    output.setAttribute('aria-busy', 'true');
    panel.classList.add('has-results');

    try {
      const response = await fetch(url, {
        method: 'POST',
        body: new URLSearchParams({source}),
      });
      if (response.headers.get('content-type')?.includes('text/html')) {
        const page = new DOMParser().parseFromString(await response.text(), 'text/html');
        const result = page.querySelector('.editor-panel .results');
        if (!result) throw new Error('Could not display the result. Check History before submitting again.');
        output.replaceWith(result);
        if (response.redirected) {
          window.history.replaceState(null, '', response.url);
        } else {
          window.history.replaceState(null, '', form.action.replace(/\/submit$/, ''));
        }
      } else {
        const error = await response.json();
        throw new Error(typeof error.detail === 'string' ? error.detail : 'Could not run code.');
      }
    } catch (error) {
      const message = document.createElement('p');
      message.className = 'error';
      message.setAttribute('role', 'alert');
      message.textContent = error instanceof TypeError
        ? 'Connection lost. Check History before submitting again.' : error.message;
      output.querySelector('.result-content').replaceChildren(message);
    } finally {
      output.removeAttribute('aria-busy');
      buttons.forEach(button => { button.disabled = false; });
      running = false;
    }
  });
}
