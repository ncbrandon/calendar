// The web page: same calendar as the wall, plus sampling, staff, media, settings, and export.
'use strict';

const TABS = { calendar: 'Calendar', sampling: 'Sampling', staff: 'Staff & pay', media: 'GIFs & videos', settings: 'Settings', export: 'Export' };
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
let boot, view, today = new Date().toISOString().slice(0, 10);
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const field = (label, input) => h('label', {}, label, input);
const card = (title, ...kids) => h('div', { class: 'card' }, h('h2', {}, title), kids);
const table = (heads, rows) => h('div', { class: 'tablewrap' }, h('table', {},
  h('thead', {}, h('tr', {}, heads.map((t) => h('th', { class: /cost|\$|total/i.test(t) ? 'num' : '' }, t)))), h('tbody', {}, rows)));
// A row of checkboxes for a list of numbers (weekdays or months).
function checks(labels, selected, offset = 0) {
  const boxes = labels.map((label, i) => h('input', { type: 'checkbox', checked: selected.includes(i + offset), value: i + offset }));
  const el = h('div', { class: 'checks' }, labels.map((label, i) => h('label', {}, boxes[i], label)));
  el.values = () => boxes.filter((b) => b.checked).map((b) => Number(b.value));
  return el;
}

function show(tab) {
  for (const name of Object.keys(TABS)) {
    $('#tab-' + name).classList.toggle('on', name === tab);
    $('#tabs').children[Object.keys(TABS).indexOf(name)].classList.toggle('on', name === tab);
  }
  history.replaceState(null, '', '#' + tab);
  ({ calendar: () => view.load(), sampling: renderSampling, staff: renderStaff, media: renderMedia, settings: renderSettings, export: renderExport })[tab]();
}

// ---- Sampling ---------------------------------------------------------------
let drafts = [];

async function renderSampling() {
  const [docs, reqs, taskData, budget] = await Promise.all([api('/api/documents'), api('/api/requirements'), api('/api/tasks'), api('/api/sampling/budget')]);
  today = taskData.today;
  const root = $('#tab-sampling');
  const again = run(renderSampling);

  // Documents
  const file = h('input', { type: 'file', accept: '.pdf,.csv,.xlsx,.txt,.docx,.png,.jpg,.jpeg' });
  const kind = h('select', {}, [['permit', 'Wastewater permit'], ['schedule', 'Water sample schedule'], ['other', 'Other']].map(([v, t]) => h('option', { value: v }, t)));
  const upload = run(async () => {
    if (!file.files[0]) return toast('Choose a file first');
    const form = new FormData(); form.append('file', file.files[0]); form.append('kind', kind.value);
    await api('/api/documents', { method: 'POST', form }); again();
  });
  const read = (doc) => run(async () => {
    toast('Reading the document. A long permit can take a minute or two.', 60000);
    drafts = (await api(`/api/documents/${doc.id}/extract`, { method: 'POST' })).drafts;
    toast(`Found ${drafts.length} requirement(s). Review them below.`); again();
  });
  const docCard = card('Permit and schedule documents',
    h('p', { class: 'muted' }, 'Keep the permit and the state sample schedule here so anyone can open them. "Read requirements" turns a spreadsheet into draft requirements' +
      (boot.ai_enabled ? ', and uses Claude to read a PDF.' : '. Reading a PDF automatically is off until an Anthropic API key is set on the server.')),
    h('div', { class: 'inline' }, field('File', file), field('Type', kind), h('button', { class: 'primary', onclick: upload }, 'Upload')),
    docs.length ? table(['Document', 'Type', 'Uploaded', ''], docs.map((d) => h('tr', {},
      h('td', {}, h('a', { href: `/api/documents/${d.id}/file`, target: '_blank', style: 'color:var(--accent)' }, d.filename)), h('td', {}, d.kind), h('td', {}, d.uploaded_at.slice(0, 10)),
      h('td', {}, h('div', { class: 'inline' }, h('button', { class: 'small', onclick: read(d) }, 'Read requirements'),
        h('button', { class: 'small danger', onclick: run(async () => { if (confirm(`Delete ${d.filename}?`)) { await api('/api/documents/' + d.id, { method: 'DELETE' }); again(); } }) }, 'Delete')))))) : null);

  // Drafts waiting for review
  let draftCard = null;
  if (drafts.length) {
    const picks = drafts.map(() => h('input', { type: 'checkbox', checked: true }));
    const costs = drafts.map((d) => h('input', { type: 'text', inputMode: 'decimal', value: d.cost || '', style: 'width:6rem', placeholder: '0.00' }));
    draftCard = card('Drafts to review',
      h('p', { class: 'muted' }, 'Nothing here is on the calendar yet. Check each line against the document, fill in the lab cost, then add the ones that are right. You can edit any of them afterwards.'),
      table(['', 'Requirement', 'Program', 'Location', 'How often', 'Period starts', 'Per period', 'Months allowed', 'Cost each', 'Notes'], drafts.map((d, i) => h('tr', {},
        h('td', {}, picks[i]), h('td', {}, d.name), h('td', {}, d.program), h('td', {}, d.location), h('td', {}, boot.frequencies[d.frequency]), h('td', {}, d.anchor_date),
        h('td', {}, d.samples_per_period), h('td', {}, d.allowed_months.map((m) => MONTHS[m - 1]).join(', ') || 'any'), h('td', {}, costs[i]), h('td', { class: 'muted' }, d.notes)))),
      h('div', { class: 'actions' }, h('button', { onclick: () => { drafts = []; again(); } }, 'Discard drafts'),
        h('button', { class: 'primary', onclick: run(async () => {
          const chosen = drafts.map((d, i) => ({ ...d, cost: costs[i].value })).filter((d, i) => picks[i].checked);
          const res = await api('/api/requirements/bulk', { method: 'POST', body: { requirements: chosen } });
          drafts = []; toast(`Added ${res.added} requirement(s) and planned their dates.`); again();
        }) }, 'Add checked to calendar')));
  }

  // Requirements
  const importFile = h('input', { type: 'file', accept: '.csv,.xlsx', style: 'display:none', onchange: run(async () => {
    const form = new FormData(); form.append('file', importFile.files[0]);
    drafts = (await api('/api/requirements/import', { method: 'POST', form })).drafts; again();
  }) });
  const reqCard = card('Sampling requirements',
    h('p', { class: 'muted' }, 'One line per thing you must sample. The planner picks the pull dates: it keeps the cost level from one budget year to the next, uses only the months you allow, ' +
      `and finishes long windows at least ${boot.settings.deadline_buffer_months} months before the deadline so there is room for a resample.`),
    h('div', { class: 'inline', style: 'margin-bottom:.6rem' }, h('button', { class: 'primary', onclick: () => editRequirement({}) }, 'Add a requirement'),
      h('button', { onclick: () => importFile.click() }, 'Import spreadsheet'), importFile,
      h('a', { href: '/api/requirements/template.csv', style: 'color:var(--accent)' }, 'Download the spreadsheet template')),
    reqs.length ? table(['Requirement', 'Program', 'Location', 'How often', 'Period starts', 'Per period', 'Months allowed', 'Cost each', 'Order ahead', ''], reqs.map((r) => h('tr', { style: r.active ? '' : 'opacity:.5' },
      h('td', {}, r.name), h('td', {}, r.program), h('td', {}, r.location), h('td', {}, boot.frequencies[r.frequency]), h('td', {}, r.anchor_date), h('td', {}, r.samples_per_period),
      h('td', {}, r.allowed_months.map((m) => MONTHS[m - 1]).join(', ') || 'any'), h('td', { class: 'num' }, money(r.cost)), h('td', {}, r.lead_days ? r.lead_days + ' days' : 'no reminder'),
      h('td', {}, h('div', { class: 'inline' }, h('button', { class: 'small', onclick: () => editRequirement(r) }, 'Edit'),
        h('button', { class: 'small danger', onclick: run(async () => { if (confirm(`Delete "${r.name}" and all of its dates, including the record of samples already pulled?`)) { await api('/api/requirements/' + r.id, { method: 'DELETE' }); again(); } }) }, 'Delete')))))) : h('p', { class: 'muted' }, 'No requirements yet.'));

  // Tasks
  const status = (t) => t.status === 'pulled' ? ['pulled', 'pulled ' + (t.completed_date || '')] : (t.pull_date < today ? ['overdue', 'OVERDUE'] : [t.status, t.status]);
  const put = (t, body) => run(async () => { await api('/api/tasks/' + t.id, { method: 'PUT', body }); again(); });
  const upcoming = taskData.tasks.filter((t) => t.pull_date);
  const taskCard = card('Planned dates',
    h('div', { class: 'inline', style: 'margin-bottom:.6rem' }, h('button', { onclick: run(async () => {
      if (!confirm('Re-plan every future date that nobody has moved by hand or marked ordered?')) return;
      await api('/api/sampling/rebalance', { method: 'POST' }); again();
    }) }, 'Re-balance the plan'), h('span', { class: 'muted' }, 'Dates you move by hand are pinned and never re-planned.')),
    upcoming.length ? table(['Order bottles', 'Pull sample', 'Requirement', 'Window ends', 'Status', 'Cost', ''], upcoming.map((t) => {
      const [cls, text] = status(t);
      const when = h('input', { type: 'date', value: t.pull_date });
      return h('tr', {}, h('td', {}, t.order_date || '-'), h('td', {}, t.pull_date + (t.locked ? ' (pinned)' : '')), h('td', {}, t.name + (t.seq > 1 ? ' #' + t.seq : '')), h('td', {}, t.period_end),
        h('td', {}, h('span', { class: 'pill ' + cls }, text)), h('td', { class: 'num' }, money(t.cost)),
        h('td', {}, h('div', { class: 'inline' },
          t.status === 'planned' && h('button', { class: 'small', onclick: put(t, { status: 'ordered' }) }, 'Ordered'),
          t.status !== 'pulled' && h('button', { class: 'small', onclick: put(t, { status: 'pulled' }) }, 'Pulled'),
          t.status !== 'planned' && h('button', { class: 'small', onclick: put(t, { status: 'planned' }) }, 'Undo'),
          t.status !== 'pulled' && [when, h('button', { class: 'small', onclick: () => put(t, { pull_date: when.value })() }, 'Move')],
          t.locked && t.status === 'planned' ? h('button', { class: 'small', onclick: put(t, { unlock: true }) }, 'Unpin') : null)));
    })) : h('p', { class: 'muted' }, 'Nothing planned yet. Add a requirement above.'));

  // Budget
  const top = Math.max(1, ...budget.years.map((y) => y.total));
  const budgetCard = card('Cost by budget year',
    budget.years.length ? table(['Budget year', 'Samples', 'Already pulled $', 'Planned $', 'Total $', ''], budget.years.map((y) => h('tr', {},
      h('td', {}, boot.settings.fiscal_year_start_month > 1 ? 'FY ' + y.year : y.year), h('td', {}, y.count), h('td', { class: 'num' }, money(y.done)), h('td', { class: 'num' }, money(y.planned)),
      h('td', { class: 'num' }, money(y.total)), h('td', { style: 'width:35%' }, h('div', { class: 'bar', style: `width:${(100 * y.total / top).toFixed(1)}%` }))))) : h('p', { class: 'muted' }, 'No costs yet.'));

  root.replaceChildren(docCard, draftCard || '', reqCard, taskCard, budgetCard);
}

function editRequirement(r) {
  const v = (k, d = '') => r[k] ?? d;
  const f = {
    name: h('input', { type: 'text', value: v('name') }), location: h('input', { type: 'text', value: v('location') }),
    program: h('select', {}, ['drinking', 'wastewater', 'other'].map((p) => h('option', { value: p }, p))),
    frequency: h('select', {}, Object.entries(boot.frequencies).map(([k, t]) => h('option', { value: k }, t))),
    anchor_date: h('input', { type: 'date', value: v('anchor_date', today.slice(0, 4) + '-01-01') }), end_date: h('input', { type: 'date', value: v('end_date') }),
    samples_per_period: h('input', { type: 'number', min: 1, value: v('samples_per_period', 1) }), cost: h('input', { type: 'number', min: 0, step: '0.01', value: v('cost', 0) }),
    lead_days: h('input', { type: 'number', min: 0, value: v('lead_days', 14) }), lab: h('input', { type: 'text', value: v('lab') }),
    notes: h('textarea', { rows: 2 }, v('notes')), months: checks(MONTHS, v('allowed_months', []), 1),
    active: h('input', { type: 'checkbox', checked: v('active', 1) == 1 }),
  };
  f.program.value = v('program', 'drinking'); f.frequency.value = v('frequency', 'triennial');
  const close = () => overlay.remove();
  const overlay = h('div', { class: 'overlay', onclick: close }, h('div', { class: 'dialog', onclick: (e) => e.stopPropagation() },
    h('h2', {}, r.id ? 'Edit requirement' : 'Add a requirement'),
    h('div', { class: 'form' },
      h('label', { class: 'wide' }, 'Name (analyte or group)', f.name), field('Program', f.program), field('Sampling location', f.location), field('Lab', f.lab),
      field('How often', f.frequency), field('First day of the current period', f.anchor_date), field('Samples in each period', f.samples_per_period),
      field('Cost of each sample ($)', f.cost), field('Order bottles this many days ahead (0 = no reminder)', f.lead_days), field('Stop after (optional)', f.end_date),
      h('label', { class: 'wide' }, 'Months when it may be pulled (none checked = any month)', f.months),
      h('label', { class: 'wide' }, 'Notes', f.notes), h('label', { style: 'flex-direction:row;align-items:center' }, f.active, ' Active')),
    h('div', { class: 'actions' }, h('button', { onclick: close }, 'Cancel'), h('button', { class: 'primary', onclick: run(async () => {
      const body = { id: r.id, allowed_months: f.months.values(), active: f.active.checked ? 1 : 0 };
      for (const k of ['name', 'location', 'program', 'frequency', 'anchor_date', 'end_date', 'samples_per_period', 'cost', 'lead_days', 'lab', 'notes']) body[k] = f[k].value;
      await api('/api/requirements', { method: 'POST', body }); close(); renderSampling();
    }) }, 'Save'))));
  document.body.append(overlay);
}

// ---- Staff, pay, holidays -----------------------------------------------------
async function renderStaff() {
  const year = Number(today.slice(0, 4));
  const [staff, hol, fresh] = await Promise.all([api('/api/employees'), api('/api/holidays?year=' + year), api('/api/bootstrap')]);
  boot = fresh;
  const s = boot.settings, again = run(renderStaff);
  const rowFor = (e) => {
    const f = { name: h('input', { type: 'text', value: e.name || '' }), color: h('input', { type: 'color', value: e.color || '#4f8cc9', style: 'padding:0;width:3rem;height:2.2rem' }),
      rot: h('input', { type: 'checkbox', checked: !!e.in_rotation }), active: h('input', { type: 'checkbox', checked: e.active !== 0 }), sort: h('input', { type: 'number', value: e.sort ?? staff.length, style: 'width:4.5rem' }) };
    return h('tr', {}, h('td', {}, f.name), h('td', {}, f.color), h('td', {}, f.rot), h('td', {}, f.sort), h('td', {}, f.active),
      h('td', {}, h('button', { class: 'small primary', onclick: run(async () => {
        await api('/api/employees', { method: 'POST', body: { id: e.id, name: f.name.value, color: f.color.value, in_rotation: f.rot.checked, sort: Number(f.sort.value), active: f.active.checked ? 1 : 0 } });
        toast('Saved'); again();
      }) }, e.id ? 'Save' : 'Add')));
  };
  const daySelect = (value, none) => { const el = h('select', {}, none ? h('option', { value: '' }, none) : null, DAYS.map((d, i) => h('option', { value: i }, d))); el.value = value ?? ''; return el; };
  const rot = daySelect(s.rotation_start_weekday), pay = daySelect(s.pay_week_start), payday = daySelect(s.payday_weekday, 'Do not show');
  const federal = h('input', { type: 'checkbox', checked: s.federal_holidays });
  const skip = hol.federal_names.map((n) => h('input', { type: 'checkbox', checked: !s.holiday_exclude.includes(n), value: n }));
  const extra = hol.extra_names.map((n) => h('input', { type: 'checkbox', checked: (s.holiday_extra || []).includes(n), value: n }));
  const hd = h('input', { type: 'date' }), he = h('input', { type: 'date' }), hn = h('input', { type: 'text', placeholder: 'Holiday' });
  const hy = h('input', { type: 'checkbox' });
  const span = (c) => (c.end_date ? `${c.date} to ${c.end_date}` : c.date) + (c.yearly ? ', every year' : '');
  $('#tab-staff').replaceChildren(
    card('Employees',
      h('p', { class: 'muted' }, 'People with "In rotation" checked take turns automatically, in the order shown. Anyone else (Brandon) only appears when picked from a day\'s dropdown.'),
      table(['Name', 'Color', 'In rotation', 'Order', 'Active', ''], [...staff.map(rowFor), rowFor({})])),
    card('On-call week and pay week',
      h('div', { class: 'inline' }, field('On-call week starts on', rot), field('Pay week begins on', pay), field('Payday', payday),
        h('button', { class: 'primary', onclick: run(async () => {
          await api('/api/settings', { method: 'PUT', body: { rotation_start_weekday: Number(rot.value), pay_week_start: Number(pay.value), payday_weekday: payday.value === '' ? null : Number(payday.value) } });
          toast('Saved'); again();
        }) }, 'Save')),
      h('p', { class: 'muted' }, 'To start or change the rotation, open the calendar and pick a name on the first day of an on-call week. That person gets the whole week and the others follow in turn.')),
    card(`Holidays in ${year}`,
      h('div', { class: 'inline' }, h('label', { style: 'flex-direction:row;align-items:center' }, federal, ' Show US federal holidays'),
        h('button', { class: 'small primary', onclick: run(async () => {
          await api('/api/settings', { method: 'PUT', body: { federal_holidays: federal.checked, holiday_exclude: skip.filter((b) => !b.checked).map((b) => b.value), holiday_extra: extra.filter((b) => b.checked).map((b) => b.value) } }); toast('Saved'); again();
        }) }, 'Save holiday choices')),
      h('div', { class: 'checks', style: 'margin:.6rem 0' }, hol.federal_names.map((n, i) => h('label', {}, skip[i], n))),
      h('p', { class: 'muted' }, 'Extra days off you also get (these follow the calendar every year):'),
      h('div', { class: 'checks', style: 'margin:.6rem 0' }, hol.extra_names.map((n, i) => h('label', {}, extra[i], n))),
      table(['Date', 'Holiday', ''], hol.all.map((x) => { const mine = hol.custom.find((c) => c.id === x.id); return h('tr', {}, h('td', {}, x.date), h('td', {}, x.name),
        h('td', {}, mine && [h('span', { class: 'muted' }, span(mine) + '  '), h('button', { class: 'small danger', onclick: run(async () => { await api('/api/holidays/' + mine.id, { method: 'DELETE' }); again(); }) }, 'Remove')])); })),
      h('p', { class: 'muted', style: 'margin-top:1rem' }, 'Add your own. Leave the name empty and it is just called "Holiday". Fill in a last day for several days off in a row.'),
      h('div', { class: 'inline' }, field('First day', hd), field('Last day (optional)', he), field('Name', hn),
        h('label', { style: 'flex-direction:row;align-items:center' }, hy, ' Same dates every year'),
        h('button', { class: 'primary', onclick: run(async () => { await api('/api/holidays', { method: 'POST', body: { date: hd.value, end_date: he.value || null, name: hn.value, yearly: hy.checked } }); again(); }) }, 'Add holiday'))));
}

// ---- GIFs and videos ----------------------------------------------------------
async function renderMedia() {
  const media = await api('/api/media'), again = run(renderMedia);
  const del = (m) => run(async () => { if (confirm(`Delete ${m.title}?`)) { await api('/api/media/' + m.id, { method: 'DELETE' }); again(); } });
  const send = (fields, file) => run(async () => {
    if (!file.files[0]) return toast('Choose a file first');
    const form = new FormData(); form.append('file', file.files[0]);
    for (const [k, val] of Object.entries(fields())) form.append(k, val);
    toast('Uploading…', 600000); await api('/api/media', { method: 'POST', form }); toast('Uploaded'); again();
  });
  const gf = h('input', { type: 'file', accept: '.gif,.webp,.png,.jpg,.jpeg' });
  const cond = h('select', {}, h('option', { value: 'any' }, 'Any weather (fallback)'), Object.entries(boot.conditions).map(([k, t]) => h('option', { value: k }, t)));
  const vf = h('input', { type: 'file', accept: '.mp4,.webm,.mov,.m4v' }), vt = h('input', { type: 'text', placeholder: 'e.g. Safety week' });
  const vs = h('input', { type: 'date' }), ve = h('input', { type: 'date' }), vi = h('input', { type: 'number', min: 1, value: 30, style: 'width:6rem' });
  const vscreen = h('select', {}, [['both', 'Both screens'], ['left', 'Left screen'], ['right', 'Right screen']].map(([k, t]) => h('option', { value: k }, t)));
  const vm = h('input', { type: 'checkbox', checked: true });
  const gifs = media.filter((m) => m.kind === 'gif'), videos = media.filter((m) => m.kind === 'video');
  $('#tab-media').replaceChildren(
    card('Weather GIFs',
      h('p', { class: 'muted' }, 'During work hours the wall shows a GIF that matches the weather outside right now, next to the temperature. Upload a few for each kind of weather; "Any weather" ones are used when nothing matches. ' +
        (boot.settings.latitude == null ? 'Set your location under Settings to turn the weather on.' : '')),
      h('div', { class: 'inline' }, field('GIF or picture', gf), field('Show when it is', cond), h('button', { class: 'primary', onclick: send(() => ({ kind: 'gif', condition: cond.value }), gf) }, 'Upload')),
      gifs.length ? table(['', 'File', 'Weather', ''], gifs.map((m) => h('tr', {}, h('td', {}, h('img', { src: '/media/' + m.stored, style: 'height:3rem;border-radius:.3rem' })), h('td', {}, m.filename),
        h('td', {}, boot.conditions[m.condition] || 'Any weather'), h('td', {}, h('button', { class: 'small danger', onclick: del(m) }, 'Delete'))))) : null),
    card('Videos',
      h('p', { class: 'muted' }, 'A video plays full screen every so many minutes during work hours, between the dates you choose. A tap closes it. It waits if someone is using the screen.'),
      h('div', { class: 'inline' }, field('Video file (MP4 works best)', vf), field('Title', vt), field('First day', vs), field('Last day', ve), field('Every (minutes)', vi), field('Where', vscreen),
        h('label', { style: 'flex-direction:row;align-items:center' }, vm, ' Muted'),
        h('button', { class: 'primary', onclick: send(() => ({ kind: 'video', title: vt.value, start_date: vs.value, end_date: ve.value, interval_min: vi.value, screen: vscreen.value, muted: vm.checked ? '1' : '0' }), vf) }, 'Upload')),
      videos.length ? table(['Title', 'First day', 'Last day', 'Every', 'Where', 'Sound', 'On', ''], videos.map((m) => {
        const a = h('input', { type: 'date', value: m.start_date || '' }), b = h('input', { type: 'date', value: m.end_date || '' }), on = h('input', { type: 'checkbox', checked: !!m.active });
        return h('tr', {}, h('td', {}, m.title), h('td', {}, a), h('td', {}, b), h('td', {}, m.interval_min + ' min'), h('td', {}, m.screen), h('td', {}, m.muted ? 'muted' : 'sound on'), h('td', {}, on),
          h('td', {}, h('div', { class: 'inline' }, h('button', { class: 'small primary', onclick: run(async () => { await api('/api/media/' + m.id, { method: 'PUT', body: { start_date: a.value, end_date: b.value, active: on.checked } }); toast('Saved'); }) }, 'Save'),
            h('button', { class: 'small danger', onclick: del(m) }, 'Delete'))));
      })) : null));
}

// ---- Settings -----------------------------------------------------------------
async function renderSettings() {
  boot = await api('/api/bootstrap');
  const s = boot.settings;
  const text = (k, type = 'text', extra = {}) => h('input', { type, value: s[k] ?? '', ...extra });
  const f = { site_name: text('site_name'), latitude: text('latitude', 'number', { step: 'any' }), longitude: text('longitude', 'number', { step: 'any' }),
    work_start: text('work_start', 'time'), work_end: text('work_end', 'time'), wake_minutes: text('wake_minutes', 'number', { min: 1 }), idle_return_minutes: text('idle_return_minutes', 'number', { min: 1 }),
    gif_seconds: text('gif_seconds', 'number', { min: 5 }), sampling_day_min: text('sampling_day_min', 'number', { min: 1, max: 28 }), deadline_buffer_months: text('deadline_buffer_months', 'number', { min: 0, max: 24 }) };
  const unit = h('select', {}, h('option', { value: 'F' }, 'Fahrenheit'), h('option', { value: 'C' }, 'Celsius')); unit.value = s.temp_unit;
  const station = text('station_url', 'url', { placeholder: 'https://weather.example.org' });
  const shift = h('input', { type: 'checkbox', checked: s.pixel_shift !== false });
  const reading = h('span', { class: 'muted' });
  const check = run(async () => {
    reading.textContent = 'Checking...';
    const w = (await api('/api/weather')).weather;
    reading.textContent = !w ? 'No reading. Save a station address or a location first, then check again.'
      : `${w.temp}°${w.unit}, ${w.label}, wind ${w.wind_from || ''} ${w.wind_mph} mph` + (w.humidity != null ? `, ${w.humidity}% humidity` : '') + (w.rain_rate ? `, rain ${w.rain_rate} in/hr` : '')
        + (w.source === 'station' ? ' (from your weather station)' : ' (from Open-Meteo; the station is not answering or not set)');
  });
  const effect = h('select', {}, [['weather', 'Follow the weather right now (rain, snow, clouds, sun, stars, wind)'], ['auto', 'Follow the season (leaves, snow, petals, bubbles)'], ['leaves', 'Falling leaves'], ['snow', 'Snowflakes'], ['petals', 'Blossom petals'], ['bubbles', 'Bubbles'], ['off', 'Off']].map(([k, t]) => h('option', { value: k }, t))); effect.value = s.season_effect;
  const fy = h('select', {}, MONTHS.map((m, i) => h('option', { value: i + 1 }, m))); fy.value = s.fiscal_year_start_month;
  const workDays = checks(DAYS, s.work_days), pullDays = checks(DAYS, s.pull_weekdays);
  const num = (el) => (el.value === '' ? null : Number(el.value));
  $('#tab-settings').replaceChildren(
    card('Wall screens', h('div', { class: 'form' },
      h('label', { class: 'wide' }, 'Name shown on the export', f.site_name),
      h('label', { class: 'wide' }, 'Days the screens are on', workDays), field('Screens turn on at', f.work_start), field('Screens go dark at', f.work_end), field('A tap on a dark screen keeps it on for (minutes)', f.wake_minutes),
      field('Arrows return to this month after (minutes)', f.idle_return_minutes), field('Moving effect over the calendar', effect), field('Each weather GIF stays up for (seconds)', f.gif_seconds),
      h('label', { class: 'wide', style: 'flex-direction:row;align-items:center' }, shift, ' Shift the picture a few pixels every few minutes (helps prevent image retention)'))),
    card('Weather',
      h('p', { class: 'muted' }, 'Your own weather station: enter the address of its website if it runs WeeWX with the Belchertown skin. OpsBoard reads the temperature, wind, humidity and rain rate from it every few minutes, plus the sky cover if the site shows a forecast.'),
      h('div', { class: 'form' }, h('label', { class: 'wide' }, 'Weather station address', station)),
      h('p', { class: 'muted' }, 'Backup, or if you have no station: a location. Only these two numbers are sent to the free Open-Meteo weather service, and only when the station is not answering. Right-click your plant in Google Maps to copy them.'),
      h('div', { class: 'form' }, field('Latitude', f.latitude), field('Longitude', f.longitude), field('Temperature in', unit)),
      h('div', { class: 'inline', style: 'margin-top:.6rem' }, h('button', { onclick: check }, 'Check the weather now'), reading)),
    card('Sample planning', h('div', { class: 'form' },
      h('label', { class: 'wide' }, 'Days of the week samples may be pulled (so the lab has them before the weekend)', pullDays),
      field('Sampling day: first allowed weekday on or after day', f.sampling_day_min), field('Finish long windows this many months early', f.deadline_buffer_months), field('Budget year starts in', fy))),
    h('div', { class: 'actions' }, h('button', { class: 'primary', onclick: run(async () => {
      if (!workDays.values().length || !pullDays.values().length) return toast('Pick at least one day in each row of days');
      await api('/api/settings', { method: 'PUT', body: { site_name: f.site_name.value, latitude: num(f.latitude), longitude: num(f.longitude), temp_unit: unit.value,
        work_days: workDays.values(), work_start: f.work_start.value, work_end: f.work_end.value, wake_minutes: num(f.wake_minutes), idle_return_minutes: num(f.idle_return_minutes),
        station_url: station.value.trim(), pixel_shift: shift.checked, season_effect: effect.value, gif_seconds: num(f.gif_seconds), pull_weekdays: pullDays.values(), sampling_day_min: num(f.sampling_day_min),
        deadline_buffer_months: num(f.deadline_buffer_months), fiscal_year_start_month: Number(fy.value) } });
      boot = await api('/api/bootstrap'); $('#site').textContent = boot.settings.site_name; toast('Saved. The wall screens update within a few seconds.');
    }) }, 'Save settings')),
    card('Wall screen addresses', h('p', {}, 'Left screen: ', h('code', {}, location.origin + '/display?screen=left')), h('p', {}, 'Right screen: ', h('code', {}, location.origin + '/display?screen=right')),
      h('p', { class: 'muted' }, 'Add ?kbd=1 to this page\'s address to get the on-screen keyboard here too.')));
}

// ---- Export -------------------------------------------------------------------
function renderExport() {
  const now = new Date(today + 'T12:00:00'), y = now.getFullYear(), m = now.getMonth();
  const a = h('input', { type: 'date' }), b = h('input', { type: 'date' }), out = h('pre', { class: 'preview' }, 'Pick a range, then Preview.');
  const set = (from, to) => { a.value = iso(from); b.value = iso(to); };
  const presets = { 'Last month': [new Date(y, m - 1, 1), new Date(y, m, 0)], 'This month': [new Date(y, m, 1), new Date(y, m + 1, 0)], 'Next 3 months': [now, new Date(y, m + 3, now.getDate())],
    'Last 12 months': [new Date(y - 1, m, now.getDate()), now], 'This year': [new Date(y, 0, 1), new Date(y, 11, 31)], 'Next 3 years': [now, new Date(y + 3, m, now.getDate())] };
  set(...presets['This month']);
  const url = (dl) => `/api/export.md?start=${a.value}&end=${b.value}${dl ? '&download=1' : ''}`;
  $('#tab-export').replaceChildren(card('Export to Markdown',
    h('p', { class: 'muted' }, 'A plain-text record of the on-call weeks, holidays, pay weeks, sampling dates, and events in any range: past, present, or future.'),
    h('div', { class: 'inline', style: 'margin-bottom:.6rem' }, Object.entries(presets).map(([name, range]) => h('button', { class: 'small', onclick: () => set(...range) }, name))),
    h('div', { class: 'inline' }, field('From', a), field('To', b), h('button', { onclick: run(async () => { out.textContent = await api(url(false)); }) }, 'Preview'),
      h('button', { class: 'primary', onclick: () => { location.href = url(true); } }, 'Download .md')), out));
}

// ---- Start --------------------------------------------------------------------
(async function start() {
  boot = await api('/api/bootstrap');
  $('#site').textContent = boot.settings.site_name;
  document.title = boot.settings.site_name;
  $('#tabs').replaceChildren(...Object.entries(TABS).map(([k, t]) => h('button', { onclick: () => run(show)(k) }, t)));
  const st = await api('/api/state');
  today = st.today;
  const home = ymOf(today);
  view = new MonthView($('#tab-calendar'), { nav: true, source: 'web', categories: boot.categories,
    onNav: (d) => { view.showToday = ymAdd(view.ym, d) !== home; run(() => view.load(ymAdd(view.ym, d)))(); },
    onToday: () => { view.showToday = false; run(() => view.load(home))(); } });
  view.ym = home;
  addEventListener('resize', () => view.data && view.render());
  // Pick up changes made on the wall screens.
  let seen = st.version;
  setInterval(async () => { try { const s = await api('/api/state'); if (s.version !== seen) { seen = s.version; if ($('#tab-calendar').classList.contains('on')) view.load(null, { background: true }); } } catch (e) { /* offline */ } }, 5000);
  run(show)(TABS[location.hash.slice(1)] ? location.hash.slice(1) : 'calendar');
})();
