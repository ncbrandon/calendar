// On-screen keyboard for the touch screens. It appears whenever a text box is tapped.
// Turned on by <body data-kbd="1"> (the wall screens) or by adding ?kbd=1 to the web page address.
'use strict';

const Keyboard = (() => {
  const LETTERS = [['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'], ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
    ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', "'"], ['SHIFT', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', 'BKSP'],
    ['SYM', '-', 'SPACE', '/', 'HIDE', 'ENTER']];
  const SYMBOLS = [['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'], ['!', '@', '#', '$', '%', '&', '*', '(', ')', '?'],
    ['+', '=', '_', ':', ';', '"', '<', '>', '[', ']'], ['SHIFT', '~', '\\', '|', '{', '}', '^', '`', ',', '.', 'BKSP'],
    ['SYM', '-', 'SPACE', '/', 'HIDE', 'ENTER']];
  const LABEL = { SHIFT: 'Shift', BKSP: '⌫', SYM: '#+=', SPACE: 'space', HIDE: 'Hide', ENTER: 'Enter' };
  let el = null, target = null, shift = true, symbols = false;

  const typable = (t) => t && ((t.tagName === 'TEXTAREA') || (t.tagName === 'INPUT' && ['text', 'search', 'password', ''].includes(t.type || '')));

  function insert(text) {
    const s = target.selectionStart ?? target.value.length, e = target.selectionEnd ?? s;
    target.setRangeText(text, s, e, 'end');
    target.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function press(key) {
    if (!target) return;
    if (key === 'SHIFT') shift = !shift;
    else if (key === 'SYM') symbols = !symbols;
    else if (key === 'HIDE') { target.blur(); return hide(); }
    else if (key === 'BKSP') {
      const s = target.selectionStart, e = target.selectionEnd;
      if (s !== e) target.setRangeText('', s, e, 'end');
      else if (s > 0) target.setRangeText('', s - 1, s, 'end');
      target.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (key === 'ENTER') {
      if (target.tagName === 'TEXTAREA') insert('\n');
      else target.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    } else {
      insert(key === 'SPACE' ? ' ' : (shift && !symbols ? key.toUpperCase() : key));
      // Capital only for the first letter of a sentence, like a phone.
      if (shift && key !== 'SPACE') shift = false;
    }
    draw();
  }

  function draw() {
    const rows = symbols ? SYMBOLS : LETTERS;
    el.replaceChildren(...rows.map((row) => {
      const div = document.createElement('div');
      div.className = 'krow';
      for (const key of row) {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = LABEL[key] || (shift && !symbols ? key.toUpperCase() : key);
        if (LABEL[key]) b.classList.add(key === 'SPACE' ? 'space' : 'w2');
        if ((key === 'SHIFT' && shift) || (key === 'SYM' && symbols)) b.classList.add('on');
        // pointerdown + preventDefault keeps the text box focused while keys are tapped.
        b.addEventListener('pointerdown', (ev) => { ev.preventDefault(); press(key); });
        div.append(b);
      }
      return div;
    }));
  }

  function show(t) {
    target = t;
    shift = t.value.length === 0;
    symbols = false;
    draw();
    el.classList.add('on');
    document.body.classList.add('kbd-open');
    setTimeout(() => t.scrollIntoView({ block: 'center', behavior: 'smooth' }), 50);
  }

  function hide() {
    if (!el) return;
    el.classList.remove('on');
    document.body.classList.remove('kbd-open');
    target = null;
  }

  function attach() {
    if (el) return;
    el = document.createElement('div');
    el.id = 'kbd';
    el.addEventListener('pointerdown', (ev) => ev.preventDefault());
    document.body.append(el);
    document.addEventListener('focusin', (ev) => { if (typable(ev.target)) show(ev.target); else if (!el.contains(ev.target)) hide(); });
  }

  return { attach, hide };
})();

window.Keyboard = Keyboard;
document.addEventListener('DOMContentLoaded', () => {
  if (document.body.dataset.kbd === '1' || new URLSearchParams(location.search).get('kbd') === '1') Keyboard.attach();
});
