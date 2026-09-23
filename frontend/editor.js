import {EditorState} from '@codemirror/state';
import {EditorView, drawSelection, highlightSpecialChars, keymap, lineNumbers} from '@codemirror/view';
import {bracketMatching, defaultHighlightStyle, indentUnit, syntaxHighlighting} from '@codemirror/language';
import {python} from '@codemirror/lang-python';
import {defaultKeymap, history, historyKeymap, indentWithTab, isolateHistory} from '@codemirror/commands';

const source = document.getElementById('source');
const view = new EditorView({
  parent: source.parentElement,
  state: EditorState.create({
    doc: source.value,
    extensions: [
      python(),
      lineNumbers(),
      highlightSpecialChars(),
      drawSelection(),
      bracketMatching(),
      history(),
      indentUnit.of('    '),
      EditorState.tabSize.of(4),
      syntaxHighlighting(defaultHighlightStyle),
      keymap.of([indentWithTab, ...defaultKeymap, ...historyKeymap]),
      EditorView.contentAttributes.of({'aria-labelledby': 'editor-title', spellcheck: 'false'}),
      EditorView.updateListener.of(update => {
        if (update.docChanged) source.value = update.state.doc.toString();
      }),
      EditorView.theme({
        '&': {height: '100%', width: '100%', minWidth: '0', backgroundColor: '#fdfdfe'},
        '&.cm-focused': {outline: 'none'},
        '.cm-scroller': {
          overflow: 'auto',
          fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
          fontSize: '13px', lineHeight: '1.8',
        },
        '.cm-content': {padding: '20px 0'},
        '.cm-line': {padding: '0 16px'},
        '.cm-gutters': {backgroundColor: '#fdfdfe', color: '#8993a1', borderRight: '1px solid #e1e5eb'},
        '.cm-lineNumbers .cm-gutterElement': {minWidth: '48px', padding: '0 12px'},
      }),
    ],
  }),
});

source.hidden = true;
document.getElementById('line-numbers').hidden = true;
document.getElementById('editor-title').addEventListener('click', () => view.focus());
source.form.addEventListener('submit', () => { source.value = view.state.doc.toString(); });
window.addEventListener('pageshow', () => {
  // Browsers may restore the form value when navigating back to the editor.
  if (source.value !== view.state.doc.toString()) {
    view.dispatch({changes: {from: 0, to: view.state.doc.length, insert: source.value}});
  }
});

const importButton = document.getElementById('import-parent');
if (importButton?.dataset.url) {
  importButton.hidden = false;
  const status = document.getElementById('import-status');
  importButton.addEventListener('click', async () => {
    const originalDoc = view.state.doc;
    importButton.disabled = true;
    status.hidden = true;
    try {
      const response = await fetch(importButton.dataset.url, {cache: 'no-store'});
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Could not import the parent submission.');
      if (view.state.doc !== originalDoc) throw new Error('Code changed while loading. Click import again to replace it.');
      view.dispatch({
        changes: {from: 0, to: view.state.doc.length, insert: result.source},
        selection: {anchor: 0},
        annotations: isolateHistory.of('full'),
        scrollIntoView: true,
      });
      view.focus();
    } catch (error) {
      status.textContent = error instanceof TypeError || error instanceof SyntaxError
        ? 'Could not import the parent submission. Try again.' : error.message;
      status.hidden = false;
    } finally {
      importButton.disabled = false;
    }
  });
}
