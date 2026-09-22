import {EditorState} from '@codemirror/state';
import {EditorView, drawSelection, highlightSpecialChars, keymap, lineNumbers} from '@codemirror/view';
import {bracketMatching, defaultHighlightStyle, indentUnit, syntaxHighlighting} from '@codemirror/language';
import {python} from '@codemirror/lang-python';
import {defaultKeymap, history, historyKeymap, indentWithTab} from '@codemirror/commands';

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
