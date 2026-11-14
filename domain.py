"""Pure calendar rules; dates are facility-local dates, never UTC timestamps."""
from datetime import date, timedelta
import calendar

PEOPLE = ['Jody', 'Marcus', 'Brandon']
ANCHOR = date(2026, 11, 12)
FACILITIES = ['P03', 'P04', 'P05', 'P07', 'P08', 'P10', 'P11', 'P12']

def parse_date(value):
    return date.fromisoformat(value)

def week_start(day):
    return day - timedelta(days=(day.weekday() - 3) % 7)

def worker(day, weeks=None, days=None):
    start = week_start(day)
    base = PEOPLE[((start - ANCHOR).days // 7) % 2]
    return (days or {}).get(day.isoformat(), (weeks or {}).get(start.isoformat(), base))

def bottle_order(day):
    # Wednesday in the calendar week before collection (Monday-based weeks).
    monday = day - timedelta(days=day.weekday())
    return monday - timedelta(days=5)

def month_add(day, amount):
    index = day.year * 12 + day.month - 1 + amount
    year, month0 = divmod(index, 12)
    return date(year, month0 + 1, min(day.day, calendar.monthrange(year, month0 + 1)[1]))

def shift_year(day, years):
    return day.replace(year=day.year + years, day=min(day.day, calendar.monthrange(day.year + years, day.month)[1]))

def event_occurrences(event, start, end):
    first, last = parse_date(event['date']), parse_date(event.get('end_date') or event['date'])
    repeat = event.get('repeat', 'none')
    until = parse_date(event['repeat_until']) if event.get('repeat_until') else end
    duration = last - first
    if duration.days > 366:
        raise ValueError('An event may span at most 366 days.')
    current = first
    if repeat == 'weekly' and start > current + duration:
        current += timedelta(weeks=max(0, ((start - duration - current).days // 7)))
    if repeat == 'yearly' and start.year > first.year:
        current = shift_year(first, max(0, start.year - first.year - 1))
    count = 0
    while current <= end and current <= until:
        for offset in range(duration.days + 1):
            day = current + timedelta(days=offset)
            if start <= day <= end:
                yield {**event, 'date': day.isoformat(), 'series_date': first.isoformat()}
        if repeat == 'none':
            break
        count += 1
        if repeat == 'weekly': current += timedelta(days=7)
        elif repeat == 'monthly': current = month_add(first, count)
        elif repeat == 'yearly': current = shift_year(first, current.year - first.year + 1)
        else: break

def holidays(year):
    def nth(month, weekday, n):
        first = date(year, month, 1)
        return first + timedelta(days=(weekday-first.weekday()) % 7 + 7*(n-1))
    def last(month, weekday):
        d = date(year, month, calendar.monthrange(year, month)[1])
        return d - timedelta(days=(d.weekday()-weekday) % 7)
    result = []
    for name, d in [('New Year’s Day', date(year,1,1)), ('Juneteenth',date(year,6,19)),('Independence Day',date(year,7,4)),('Veterans Day',date(year,11,11)),('Christmas Day',date(year,12,25))]:
        result.append((d,name))
        if d.weekday() == 5: result.append((d-timedelta(days=1),name+' (observed)'))
        if d.weekday() == 6: result.append((d+timedelta(days=1),name+' (observed)'))
    result += [(nth(1,0,3),'Martin Luther King Jr. Day'),(nth(2,0,3),'Washington’s Birthday'),(last(5,0),'Memorial Day'),(nth(9,0,1),'Labor Day'),(nth(10,0,2),'Columbus Day'),(nth(11,3,4),'Thanksgiving')]
    return result

def seed_requirements():
    rows=[]
    def add(facility, group, years, page, notes=''):
        end = date(2026 + years - 1,12,31)
        rows.append(dict(facility=facility, group=group, years=years,
            window_start='2026-01-01', window_end=end.isoformat(), reviewed=False,
            cost=None, planned=None, actual=None, stage='Verify records', notes=notes,
            source=f'Drinking Water Watch PDF, 2026-11-14, page(s) {page}',
            source_status='0 samples / schedule not satisfied in source snapshot', count=1))
    pages={'P03':'1–3, 14','P04':'3–4, 14','P05':'4–6, 14','P07':'6–7, 14–15','P08':'7–9, 15','P10':'9–10','P11':'10–12','P12':'12–14'}
    for f in FACILITIES:
        p=pages[f]
        for group in ['Inorganics','Secondaries','Nitrate','SOC','VOC']:
            years=1 if group=='Nitrate' or (f=='P05' and group in ['Inorganics','Secondaries','VOC']) else 3
            add(f,group,years,p, 'Laboratory panel task, not one bottle per analyte. Confirm panel coverage and approved collection constraints.')
        if f in ['P04','P10','P11','P12']:
            add(f,'Radiological panel',9,p,'Confirm panel covers gross alpha, uranium, combined radium and listed radium components; do not double-order components.')
        else:
            for group in ['Gross alpha','Uranium','Combined radium']:
                add(f,group,6 if f=='P08' and group=='Combined radium' else 9,p)
    add('P04','Simazine',3,'14','Reconcile with SOC panel before ordering.')
    add('P04','Di(2-ethylhexyl) phthalate',3,'14','Reconcile with SOC panel before ordering.')
    add('P07','Atrazine',3,'14','Reconcile with SOC panel before ordering.')
    return rows

def propose(requirements, today, monthly_budget=None):
    """Greedy monthly cost balancing, never outside a reviewed collection window.

    Preference: Mon-Fri, at least two weeks ahead, 90 days before final deadline
    when feasible. Proposals are not approvals or completion records.
    """
    eligible=[r for r in requirements if r['reviewed'] and r['stage'] != 'Complete' and not r.get('planned')]
    if any(r.get('cost') is None for r in eligible):
        raise ValueError('Enter an estimated cost for every reviewed, unplanned requirement first (zero is allowed).')
    loads={}
    for r in requirements:
        if r.get('planned') and r.get('cost') is not None:
            key=r['planned'][:7]; loads[key]=loads.get(key,0)+r['cost']
    proposals=[]
    for r in sorted(eligible,key=lambda r:(r['window_end'],-r['cost'])):
        earliest=max(today+timedelta(days=14),parse_date(r['window_start']))
        latest=parse_date(r['window_end'])
        if earliest>latest:
            proposals.append({'id':r['id'],'conflict':'Too little lead time or window expired. Review manually; deadline was not moved.'}); continue
        preferred=max(earliest,latest-timedelta(days=90))
        candidates=[]
        d=earliest
        while d<=preferred:
            if d.weekday()==1: candidates.append(d) # Tuesdays, bottles must be confirmed received
            d+=timedelta(days=1)
        if not candidates:
            d=earliest
            while d<=latest:
                if d.weekday()<5: candidates.append(d)
                d+=timedelta(days=1)
        if not candidates:
            proposals.append({'id':r['id'],'conflict':'No weekday available in window.'}); continue
        d=min(candidates,key=lambda d:(loads.get(d.isoformat()[:7],0),d))
        key=d.isoformat()[:7]
        amount=loads.get(key,0)+r['cost']
        if monthly_budget is not None and amount>monthly_budget:
            proposals.append({'id':r['id'],'conflict':'Monthly budget cannot accommodate this proposal; deadline was not moved.'}); continue
        loads[key]=amount
        proposals.append({'id':r['id'],'planned':d.isoformat(),'order':bottle_order(d).isoformat(),'cost':r['cost'],'revision':r.get('revision',0)})
    return proposals
