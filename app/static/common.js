// Shared by the wall screens and the web page: helpers, the month grid, and the day dialog.
'use strict';

const $ = (sel, root = document) => root.querySelector(sel);

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className = v;
    else if (k === 'style') el.style.cssText = v;
    else if (k in el && k !== 'list') el[k] = v;
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
  return el;
}

async function api(path, { method = 'GET', body, form } = {}) {
  const opts = { method, headers: {} };
  if (form) opts.body = form;
  else if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
  const res = await fetch(path, opts);
  if (res.status === 401) { location.href = '/login'; throw new Error('Sign in first'); }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) { /* not JSON */ }
    throw new Error(detail);
  }
  return (res.headers.get('content-type') || '').includes('json') ? res.json() : res.text();
}

function toast(message, ms = 3500) {
  document.querySelectorAll('.toast').forEach((t) => t.remove());
  const el = h('div', { class: 'toast' }, message);
  document.body.append(el);
  setTimeout(() => el.remove(), ms);
}

const run = (fn) => async (...args) => { try { await fn(...args); } catch (e) { toast(e.message); } };
const ymOf = (iso) => iso.slice(0, 7);
function ymAdd(ym, n) {
  const [y, m] = ym.split('-').map(Number);
  const d = new Date(y, m - 1 + n, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}
const longDate = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
const money = (n) => '$' + Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const BADGE = { order: 'ORDER', pull: 'PULL', deadline: 'DUE' };
const shortTitle = (item) => item.title.replace(/^(Order bottles|Pull sample|DEADLINE): /, '');

class MonthView {
  // opts: { nav: bool, onNav(delta), onToday(), source: 'touch' | 'web', categories: [] }
  constructor(root, opts = {}) {
    this.root = root; this.opts = opts; this.ym = null; this.data = null; this.showToday = false;
    this.selected = null;   // the day whose week is enlarged, or null for the whole month
    this.swipedAt = 0;
    if (opts.nav) this.bindSwipe();
  }

  // Swipe left = later, swipe right = earlier. One finger moves a month, two fingers move a year.
  bindSwipe() {
    const live = new Map();
    let fingers = 0;
    const end = (e, cancelled) => {
      const s = live.get(e.pointerId);
      if (!s) return;
      live.delete(e.pointerId);
      const dx = e.clientX - s.x, dy = e.clientY - s.y, used = fingers;
      if (!live.size) fingers = 0;
      if (cancelled || this.openDate || Date.now() - s.t > 900) return;
      if (Math.abs(dx) < Math.max(70, this.root.clientWidth * 0.06) || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      if (Date.now() - this.swipedAt < 500) return;          // the other finger of the same swipe
      this.swipedAt = Date.now();
      this.opts.onNav((dx < 0 ? 1 : -1) * (used >= 2 ? 12 : 1));
    };
    this.root.addEventListener('pointerdown', (e) => {
      if (e.target.closest('select, button, input')) return;
      live.set(e.pointerId, { x: e.clientX, y: e.clientY, t: Date.now() });
      fingers = Math.max(fingers, live.size);
    });
    window.addEventListener('pointerup', (e) => end(e, false));
    window.addEventListener('pointercancel', (e) => end(e, true));
  }

  // background = a refresh nobody asked for (another screen changed something).
  // It must not wipe out a dialog someone is typing in, so it waits until the dialog closes.
  async load(ym, { background = false } = {}) {
    if (background && this.openDate && (!ym || ym === this.ym)) { this.stale = true; return; }
    if (ym && ym !== this.ym && this.openDate) this.closeDay(false);
    const slide = ym && this.ym && ym !== this.ym ? (ym > this.ym ? 'next' : 'prev') : null;
    if (slide) this.selected = null;
    this.stale = false;
    this.ym = ym || this.ym;
    this.data = await api('/api/month?ym=' + this.ym);
    this.render(slide);
    if (this.openDate) this.openDay(this.openDate);
  }

  render(slide = null) {
    const d = this.data, o = this.opts;
    const head = h('div', { class: 'month-head' },
      o.nav && h('button', { class: 'nav year', 'aria-label': 'Previous year', onclick: () => o.onNav(-12) }, '«'),
      o.nav && h('button', { class: 'nav', 'aria-label': 'Previous month', onclick: () => o.onNav(-1) }, '‹'),
      h('div', { class: 'month-title' }, d.title),
      o.nav && this.showToday && h('button', { class: 'todaybtn', onclick: () => o.onToday() }, 'Back to today'),
      o.nav && h('button', { class: 'nav', 'aria-label': 'Next month', onclick: () => o.onNav(1) }, '›'),
      o.nav && h('button', { class: 'nav year', 'aria-label': 'Next year', onclick: () => o.onNav(12) }, '»'));
    const grid = this.grid = h('div', { class: 'grid' }, d.days.map((day) => this.cell(day)));
    this.weekdays = h('div', { class: 'weekdays' }, ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((n) => h('div', {}, n)));
    const month = h('div', { class: 'month' + (slide ? ' slide-' + slide : '') }, !o.headTarget && head, this.weekdays, grid);
    if (o.headTarget) o.headTarget.replaceChildren(head);
    this.root.replaceChildren(month);
    this.applyFocus();
    this.fit(grid);
  }

  // Tap a day: its week grows to fill most of the screen. select(null) puts the whole month back.
  select(date) {
    this.selected = date;
    this.applyFocus();
    // Re-check what fits once the rows have finished moving (the timer covers a skipped animation).
    const grid = this.grid, refit = () => { if (grid === this.grid) this.fit(grid); };
    grid.ontransitionend = (e) => { if (e.target === grid) refit(); };
    clearTimeout(this.fitTimer);
    this.fitTimer = setTimeout(refit, 700);
  }

  applyFocus() {
    const days = this.data.days, grid = this.grid;
    const i = days.findIndex((x) => x.date === this.selected);
    if (i < 0) this.selected = null;
    const week = i < 0 ? -1 : Math.floor(i / 7);
    const tracks = (n, big, size, rest) => Array.from({ length: n }, (_, k) => (i < 0 ? '1fr' : k === big ? size : rest)).join(' ');
    grid.classList.toggle('focus', i >= 0);
    grid.style.gridTemplateRows = tracks(days.length / 7, week, '3.4fr', '.42fr');
    grid.style.gridTemplateColumns = this.weekdays.style.gridTemplateColumns = tracks(7, i % 7, '2.2fr', '1fr');
    [...grid.children].forEach((el, n) => {
      const row = Math.floor(n / 7);
      el.classList.toggle('wk', row === week);
      el.classList.toggle('mini', i >= 0 && row !== week);
      el.classList.toggle('sel', n === i);
    });
  }

  cell(day) {
    const d = this.data;
    // Orange outline: somebody changed this day by hand. That means an added item, an on-call person picked
    // for just this day in place of the rotation, or a sample pull moved to this day.
    const cls = ['day', !day.in_month && 'out', day.date === d.today && 'today', day.weekday >= 5 && 'weekend', day.holiday && 'holiday',
      (day.oncall.source === 'override' || day.items.some((it) => it.type === 'event' || (it.type === 'pull' && it.locked))) && 'changed'];
    const tags = [];
    if (day.pay.includes('start')) tags.push(h('span', { class: 'tag' }, 'PAY WK BEGINS'));
    if (day.pay.includes('end')) tags.push(h('span', { class: 'tag' }, 'PAY WK ENDS'));
    if (day.pay.includes('payday')) tags.push(h('span', { class: 'tag payday' }, 'PAYDAY'));
    const items = day.items.map((it) => h('div', {
      class: ['chip', it.type, it.done && 'done', it.overdue && 'overdue'].filter(Boolean).join(' '),
    }, BADGE[it.type] ? h('b', {}, BADGE[it.type]) : (it.time ? h('b', {}, it.time) : null), shortTitle(it),
    (it.type === 'event' ? it.notes : it.location) && h('small', {}, it.type === 'event' ? it.notes : it.location)));
    const tap = (e) => {
      if (e.target.closest('select') || Date.now() - this.swipedAt < 500) return;   // a swipe is not a tap
      if (e.target.closest('.back')) return this.select(null);
      if (this.selected === day.date) this.openDay(day.date); else this.select(day.date);
    };
    return h('div', { class: cls.filter(Boolean).join(' '), onclick: tap },
      h('div', { class: 'dhead' }, h('span', { class: 'dnum' }, Number(day.date.slice(8))),
        day.items.length ? h('span', { class: 'count' }, day.items.length) : null, h('span', { class: 'tags' }, tags)),
      day.holiday && h('div', { class: 'hol' }, day.holiday),
      h('div', { class: 'items' }, items),
      h('div', { class: 'selbar' }, h('button', { class: 'primary' }, '＋ Add or edit'), h('button', { class: 'back' }, 'Whole month')),
      this.oncallSelect(day));
  }

  oncallSelect(day) {
    const d = this.data, emp = d.employees.find((e) => e.id === day.oncall.employee_id);
    const sel = h('select', {
      class: 'oncall' + (emp ? '' : ' empty') + (day.oncall.source === 'override' ? ' override' : ''),
      'aria-label': 'On call ' + day.date,
      style: emp ? `background:${emp.color}` : '',
      onchange: run(async () => {
        await api('/api/oncall', { method: 'POST', body: { date: day.date, employee_id: sel.value || null } });
        await this.load();
      }),
    },
      h('option', { value: '' }, emp ? '↺ Auto (rotation)' : 'On call…'),
      d.employees.map((e) => h('option', { value: e.id }, e.name)));
    sel.value = emp ? emp.id : '';
    return sel;
  }

  // Hide chips that do not fit and say how many are hidden.
  fit(grid) {
    for (const box of grid.querySelectorAll('.items')) {
      box.querySelectorAll('.more').forEach((m) => m.remove());
      const chips = [...box.children];
      chips.forEach((c) => { c.style.display = ''; });
      let hidden = 0, more = null;
      while (box.scrollHeight > box.clientHeight + 1 && chips.length - hidden > 0) {
        hidden += 1;
        chips[chips.length - hidden].style.display = 'none';
        if (!more) { more = h('div', { class: 'chip more' }); box.append(more); }
        more.textContent = `+${hidden} more`;
      }
    }
  }

  // ---- Day dialog ----------------------------------------------------------
  closeDay(reload = true) {
    this.openDate = null;
    document.querySelectorAll('.overlay').forEach((o) => o.remove());
    if (window.Keyboard) Keyboard.hide();
    if (reload && this.stale) run(() => this.load())();
  }

  openDay(date, editing = null) {
    const day = this.data.days.find((x) => x.date === date);
    document.querySelectorAll('.overlay').forEach((o) => o.remove());
    if (!day) { this.openDate = null; return; }
    this.openDate = date;
    const d = this.data, emp = d.employees.find((e) => e.id === day.oncall.employee_id);
    const act = (fn) => run(async () => { await fn(); await this.load(); });
    const task = (it, body) => act(() => api('/api/tasks/' + it.task_id, { method: 'PUT', body }));

    const rows = day.items.map((it) => {
      if (it.type === 'event') {
        return h('div', { class: 'row event' + (it.done ? ' done' : '') },
          h('div', { class: 'grow' }, h('span', {}, (it.time ? it.time + '  ' : '') + it.title),
            h('div', { class: 'sub' }, [it.category, it.end_date && `through ${it.end_date}`, it.notes].filter(Boolean).join(' · '))),
          h('button', { class: 'small', onclick: act(() => api('/api/events/' + it.id, { method: 'PUT', body: { done: !it.done } })) }, it.done ? 'Not done' : 'Done'),
          h('button', { class: 'small', onclick: () => this.openDay(date, it) }, 'Edit'),
          h('button', { class: 'small danger', onclick: act(() => api('/api/events/' + it.id, { method: 'DELETE' })) }, 'Delete'));
      }
      const sub = [it.location, it.cost ? money(it.cost) : null, `window ends ${it.period_end}`, it.overdue && 'OVERDUE', it.locked ? 'date set by hand' : null];
      const buttons = [];
      if (it.type === 'order') buttons.push(h('button', { class: 'small', onclick: task(it, { status: it.status === 'planned' ? 'ordered' : 'planned' }) }, it.status === 'planned' ? 'Mark ordered' : 'Not ordered'));
      if (it.type === 'pull') {
        buttons.push(h('button', { class: 'small', onclick: task(it, it.status === 'pulled' ? { status: 'ordered' } : { status: 'pulled', completed_date: date }) }, it.status === 'pulled' ? 'Not pulled' : 'Mark pulled'));
        if (it.status !== 'pulled') {
          const when = h('input', { type: 'date', value: it.pull_date });
          buttons.push(when, h('button', { class: 'small', onclick: () => when.value && task(it, { pull_date: when.value })() }, 'Move'));
          if (it.locked) buttons.push(h('button', { class: 'small', onclick: task(it, { unlock: true }) }, 'Auto-plan'));
        }
      }
      return h('div', { class: `row ${it.type}` + (it.done ? ' done' : '') },
        h('div', { class: 'grow' }, h('span', {}, it.title), h('div', { class: 'sub' }, sub.filter(Boolean).join(' · '))), buttons);
    });

    const e = editing || {};
    const f = {
      title: h('input', { type: 'text', value: e.title || '', placeholder: 'What is happening?', autocomplete: 'off' }),
      category: h('select', {}, (this.opts.categories || ['general']).map((c) => h('option', { value: c }, c))),
      time: h('input', { type: 'time', value: e.time || '' }),
      end: h('input', { type: 'date', value: e.end_date || '', min: date }),
      notes: h('textarea', { rows: 2, placeholder: 'Notes (optional)' }, e.notes || ''),
    };
    f.category.value = e.category || 'general';
    const save = run(async () => {
      const body = { title: f.title.value, date: e.date || date, end_date: f.end.value || null, time: f.time.value || null,
        category: f.category.value, notes: f.notes.value, source: this.opts.source || 'web' };
      if (!body.title.trim()) { toast('Type a title first'); f.title.focus(); return; }
      await api(editing ? '/api/events/' + editing.id : '/api/events', { method: editing ? 'PUT' : 'POST', body });
      if (window.Keyboard) Keyboard.hide();
      await this.load();
    });
    f.title.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') save(); });

    const holidayBtn = day.holiday_id
      ? h('button', { class: 'close holbtn', onclick: act(() => api('/api/holidays/' + day.holiday_id, { method: 'DELETE' })) }, 'Remove holiday')
      : !day.holiday && h('button', { class: 'close holbtn', onclick: act(() => api('/api/holidays', { method: 'POST', body: { date } })) }, 'Mark as holiday');
    const dialog = h('div', { class: 'dialog', onclick: (ev) => ev.stopPropagation() },
      h('button', { class: 'close', onclick: () => this.closeDay() }, 'Close'), holidayBtn,
      h('h2', {}, longDate(date)),
      h('div', { class: 'muted' }, [day.holiday, emp ? `On call: ${emp.name}` : 'Nobody on call yet',
        day.pay.includes('start') && 'Pay week begins', day.pay.includes('end') && 'Pay week ends', day.pay.includes('payday') && 'Payday'].filter(Boolean).join(' · ')),
      h('h3', {}, 'On this day'),
      rows.length ? rows : h('div', { class: 'muted' }, 'Nothing scheduled.'),
      h('h3', {}, editing ? 'Edit event' : 'Add an event'),
      h('div', { class: 'form' },
        h('label', { class: 'wide' }, 'Title', f.title),
        h('label', {}, 'Category', f.category), h('label', {}, 'Time (optional)', f.time), h('label', {}, 'Lasts through (optional)', f.end),
        h('label', { class: 'wide' }, 'Notes', f.notes)),
      h('div', { class: 'actions' },
        editing && h('button', { onclick: () => this.openDay(date) }, 'Cancel edit'),
        h('button', { class: 'primary', onclick: save }, editing ? 'Save changes' : 'Add to calendar')));
    document.body.append(h('div', { class: 'overlay', onclick: () => this.closeDay() }, dialog));
  }
}
