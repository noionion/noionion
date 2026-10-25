"""Public, aggregate-only Codex account usage schema and SVG panel."""
from datetime import date, datetime, timedelta
import math
from xml.etree import ElementTree as E

N = '{http://www.w3.org/2000/svg}'
SUMMARY_KEYS = ('lifetimeTokens', 'peakDailyTokens', 'currentStreakDays', 'longestStreakDays')


def nonnegative(value):
    return type(value) is int and value >= 0


def sanitize(response, fetched_at):
    """Allowlist counters only: never serialize account details or credentials."""
    summary = response.get('summary')
    if not isinstance(summary, dict):
        raise ValueError('Account usage summary is unavailable')
    clean = {}
    for key in SUMMARY_KEYS:
        value = summary.get(key)
        if value is not None and not nonnegative(value):
            raise ValueError(f'Invalid account counter: {key}')
        clean[key] = value
    if all(value is None for value in clean.values()):
        raise ValueError('Account usage counters are unavailable')
    buckets = response.get('dailyUsageBuckets')
    daily = {}
    if buckets is not None:
        if not isinstance(buckets, list):
            raise ValueError('Invalid daily buckets')
        for bucket in buckets:
            day, tokens = bucket['startDate'], bucket['tokens']
            if date.fromisoformat(day).isoformat() != day or day in daily or not nonnegative(tokens):
                raise ValueError('Invalid or duplicate account usage bucket')
            if day > datetime.fromisoformat(fetched_at).date().isoformat():
                raise ValueError('Future account usage bucket')
            daily[day] = tokens
    return {'version': 1, 'source': 'codex-account-usage', 'fetched_at': fetched_at,
            'summary': clean, 'daily': None if buckets is None else dict(sorted(daily.items()))}


def validate(data):
    if data.get('version') != 1 or data.get('source') != 'codex-account-usage':
        raise ValueError('Unsupported Codex account usage data')
    timestamp = datetime.fromisoformat(data['fetched_at'])
    if timestamp.utcoffset() is None:
        raise ValueError('Usage snapshot needs a timezone')
    daily = data['daily']
    if daily is not None and not isinstance(daily, dict):
        raise ValueError('Invalid daily usage')
    # Round-trip through the allowlist so unexpected fields cannot reach the profile.
    checked = sanitize({'summary': data['summary'], 'dailyUsageBuckets': None if daily is None else
                        [{'startDate': day, 'tokens': tokens} for day, tokens in daily.items()]},
                       data['fetched_at'])
    if checked != data:
        raise ValueError('Unexpected fields in public usage data')
    return data


def short(value):
    if value is None:
        return 'N/A'
    for scale, suffix in [(1e9, 'B'), (1e6, 'M'), (1e3, 'K')]:
        if value >= scale:
            return f'{value/scale:.2f}{suffix}'
    return str(value)


def panel(data, dark, y=700):
    validate(data)
    fetched = datetime.fromisoformat(data['fetched_at'])
    end = fetched.date()
    start = end - timedelta(days=364)
    daily = {date.fromisoformat(day): tokens for day, tokens in (data['daily'] or {}).items()}
    summary = data['summary']
    ink, muted, accent, missing, zero, colors = (
        ('#e6edf3', '#919ba7', '#69b5ff', '#161b22', '#303d4a',
         ['#164c68', '#147ca0', '#22acd1', '#84e0ef']) if dark else
        ('#202932', '#6b7785', '#0969da', '#ebedf0', '#c9d4df',
         ['#c4e9f3', '#79ccdf', '#299abb', '#096e95']))
    root = E.Element(N+'svg', {'id': 'codex-usage', 'x': '0', 'y': str(y), 'width': '900',
                              'height': '250', 'viewBox': '0 0 900 250',
                              'role': 'img', 'aria-labelledby': 'usage-title usage-desc'})
    E.SubElement(root, N+'title', id='usage-title').text = 'Codex account token activity'
    E.SubElement(root, N+'desc', id='usage-desc').text = (
        f'Official account usage snapshot {data["fetched_at"]}. '
        'Lifetime tokens, peak daily tokens, usage streak and reported daily buckets. '
        'Missing dates are unknown, not zero. This is token activity, not remaining quota.')

    def text(x, y, value, size=12, color=None, weight=400, mono=False, **attrs):
        attrs.update(x=str(x), y=str(y), fill=color or ink)
        attrs.update({'font-size': str(size), 'font-weight': str(weight),
                      'font-family': 'Consolas,Menlo,monospace' if mono else
                      "Arial,'Microsoft YaHei','Noto Sans CJK SC',sans-serif"})
        E.SubElement(root, N+'text', attrs).text = str(value)

    text(28, 24, '$ codex usage --account', 11, accent, mono=True)
    text(872, 24, 'CODEX TOKEN ACTIVITY', 10, muted, mono=True, **{'text-anchor': 'end'})
    last30 = (sum(tokens for day, tokens in daily.items() if end-timedelta(days=29) <= day <= end)
              if any(end-timedelta(days=29) <= day <= end for day in daily) else None)
    metrics = [(short(summary['lifetimeTokens']), 'Lifetime tokens'),
               (short(last30), 'Last 30 days / reported'),
               (short(summary['peakDailyTokens']), 'Peak daily tokens'),
               (short(summary['currentStreakDays']), 'Current streak / days')]
    for i, (value, caption) in enumerate(metrics):
        text(28+i*219, 68, value, 30, weight=700)
        text(28+i*219, 90, caption, 11, muted)
    positive = sorted(tokens for day, tokens in daily.items() if start <= day <= end and tokens > 0)
    thresholds = [positive[math.ceil(len(positive)*q)-1] for q in (.25, .5, .75)] if positive else [0]*3
    first = start-timedelta(days=(start.weekday()+1) % 7)
    for offset in range(365):
        day = start+timedelta(days=offset)
        col, row = divmod((day-first).days, 7)
        tokens = daily.get(day)
        fill = missing if tokens is None else zero if tokens == 0 else colors[sum(tokens > t for t in thresholds)]
        cell = E.SubElement(root, N+'rect', {'class': 'usage-day', 'x': str(28+col*16),
                                           'y': str(110+row*16), 'width': '12', 'height': '12',
                                           'rx': '2', 'fill': fill})
        E.SubElement(cell, N+'title').text = f'{day}: ' + ('no record' if tokens is None else f'{tokens:,} tokens')
    latest = max(daily).isoformat() if daily else 'N/A'
    text(28, 239, f'账号官方统计 · 最新日记录 {latest} · 灰格表示无记录', 11, muted)
    text(872, 239, f'同步 {fetched:%Y-%m-%d %H:%M} UTC{fetched:%z}', 10, muted,
         **{'text-anchor': 'end'})
    return root
