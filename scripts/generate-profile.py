"""Generate self-contained profile SVGs. Use --offline for bundled public snapshots."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
from xml.etree import ElementTree as E
from codex_usage import panel, validate as validate_usage

ROOT = Path(__file__).resolve().parent
N = '{http://www.w3.org/2000/svg}'
E.register_namespace('', N[1:-1])
LANGUAGE_API = ('https://readme-stats.mufanc.xyz/api/top-langs/'
                '?username=noionion&layout=compact&langs_count=8&hide_title=true'
                '&hide_border=true&hide=css,stylus,html,javascript,pug')
EXCLUDED_LANGUAGES = {'css', 'stylus', 'html', 'javascript', 'pug'}


def fetch(path):
    headers = {'User-Agent': 'noionion-profile', 'Accept': 'application/vnd.github+json'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    for attempt in range(3):
        try:
            with urlopen(Request('https://api.github.com/' + path, headers=headers), timeout=30) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def repositories(offline):
    if offline:
        return json.loads((ROOT / 'inputs/repos.json').read_text(encoding='utf-8'))
    repos, page = [], 1
    while True:
        batch = fetch(f'users/noionion/repos?type=owner&per_page=100&page={page}')
        repos.extend(r for r in batch if not r['private'])
        if len(batch) < 100:
            return repos
        page += 1


def language_data(offline):
    if offline:
        data = (ROOT / 'inputs/languages.svg').read_bytes()
    else:
        for attempt in range(3):
            try:
                request = Request(LANGUAGE_API, headers={'User-Agent': 'noionion-profile'})
                with urlopen(request, timeout=30) as response:
                    data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise ValueError('Oversized language API response')
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
    svg = E.fromstring(data)
    if svg.tag != N+'svg':
        raise ValueError('Language API did not return SVG')
    languages = []
    for group in svg.iter(N+'g'):
        node = group.find(f"{N}text[@data-testid='lang-name']")
        circle = group.find(N+'circle')
        if node is not None and circle is not None:
            name, percentage = ''.join(node.itertext()).strip().rsplit(' ', 1)
            languages.append((name, float(percentage.rstrip('%')), circle.get('fill')))
    if not 1 <= len(languages) <= 8 or abs(sum(pct for _, pct, _ in languages)-100) > 0.1:
        raise ValueError('Incomplete language statistics; refusing to replace the profile')
    if any(name.lower() in EXCLUDED_LANGUAGES or not 0 <= pct <= 100
           for name, pct, _ in languages):
        raise ValueError('Invalid or excluded language in API response')
    return languages


def generate(repos, languages, snakes, output, dark, usage):
    theme = 'dark' if dark else 'light'
    ink, muted, accent, line, bg = (
        ('#e6edf3', '#919ba7', '#69b5ff', '#30363d', '#0d1117') if dark else
        ('#202932', '#6b7785', '#0969da', '#e1e6ec', '#ffffff'))
    r = E.Element(N+'svg', {'width': '900', 'height': '1000', 'viewBox': '0 0 900 1000',
                            'role': 'img', 'aria-labelledby': 'title desc'})
    E.SubElement(r, N+'title', id='title').text = 'noionion — CPU verification engineer'
    E.SubElement(r, N+'desc', id='desc').text = (
        'CPU 验证工程师，关注 RISC-V Privilege 和 AIA。公开仓库统计、主要语言、贡献动画与 Codex 账号 token 统计。博客：https://noionion.top')

    def el(tag, parent=None, **attrs):
        return E.SubElement(r if parent is None else parent, N+tag,
                            {k.replace('_', '-'): str(v) for k, v in attrs.items()})

    def text(x, y, value, size=13, color=None, weight=400, mono=False, **attrs):
        font = 'Consolas,Menlo,monospace' if mono else "Arial,'Microsoft YaHei','Noto Sans CJK SC',sans-serif"
        node = el('text', x=x, y=y, fill=color or ink, font_family=font,
                  font_size=size, font_weight=weight, **attrs)
        node.text = str(value)

    def label(x, y, value):
        text(x, y, value, 11, accent, 500, True)

    def rule(y):
        el('path', d=f'M28 {y}H872', stroke=line)

    el('rect', width=900, height=1000, rx=12, fill=bg)
    label(28, 30, 'noionion@github:~')
    text(26, 99, 'noionion', 56, weight=700, letter_spacing='-2')
    text(29, 130, 'CPU 验证工程师 / 喜欢折腾的普通人 qwq', 16, muted)
    label(590, 40, '$ ./focus')
    for y, name in [(72, 'RISC-V Privilege'), (100, 'AIA / Interrupts'), (128, 'CPU Verification')]:
        el('circle', cx=595, cy=y-4, r=3, fill=accent)
        text(608, y, name, 14, weight=600, mono=True)
    rule(157)
    label(28, 188, '$ whoami')
    text(28, 220, '学过嵌入式，捣鼓过网页，玩过 OS。现在，来玩 CPU 吧。', 15)
    text(28, 247, 'GitHub 大部分时间用来提 issue；偶尔写点小东西，也记录一路踩过的坑。', 14, muted)
    text(28, 274, 'noionion.top', 14, accent, 600, True)
    text(184, 274, '设计 / 教程 / 日记 · 工作繁忙，随缘更新', 13, muted)
    rule(298)
    own = [repo for repo in repos if not repo['fork']]
    label(28, 329, '$ gh stats --public')
    stats = [(len(repos), 'Public repos'), (len(own), 'Original repos'),
             (sum(repo['stargazers_count'] for repo in own), 'Stars earned'),
             (len(repos)-len(own), 'Forked repos')]
    for i, (value, name) in enumerate(stats):
        x = 28+i*119
        text(x, 375, value, 32, weight=700)
        text(x, 399, name, 11, muted)
    text(28, 429, '公开数据每日更新 · Stars 仅统计非 fork 仓库', 11, muted)
    label(548, 329, '$ gh languages')
    x = 548
    defs = el('defs')
    clip = el('clipPath', parent=defs, id='language-bar')
    el('rect', parent=clip, x=548, y=349, width=324, height=8, rx=4)
    for name, percentage, color in languages:
        width = 324*percentage/100
        el('rect', x=x, y=349, width=width, height=8,
           fill=color, clip_path='url(#language-bar)')
        x += width
    # Keep the legend bounded even if new primary languages are added.
    for i, (name, percentage, color) in enumerate(languages):
        x, y = 548+(i // 4)*170, 381+(i % 4)*24
        el('circle', cx=x+3, cy=y-4, r=3, fill=color)
        text(x+13, y, f'{name} {percentage:.2f}%', 11)
    text(548, 475, 'readme-stats.mufanc.xyz / 代码占比', 10, muted)
    rule(495)
    label(28, 527, '$ git log --graph')
    text(872, 527, 'CONTRIBUTION ACTIVITY', 10, muted, mono=True, text_anchor='end')
    filename = 'github-snake-dark.svg' if dark else 'github-snake.svg'
    snake = deepcopy(E.parse(snakes / filename).getroot())
    snake.attrib.update(id='contribution-snake', x='10', y='541', width='880', height='132',
                        viewBox='-16 -18 880 132')
    for style in snake.iter(N+'style'):
        css = style.text or ''
        variables = dict(re.findall(r'(--[\w-]+):([^;}]+)', css))
        # Literal colors work in static SVG renderers as well as GitHub's image view.
        css = re.sub(r'var\((--[\w-]+)\)', lambda m: variables[m[1]], css)
        style.text = re.sub(r':root\{[^}]*\}', '', css)
    r.append(snake)
    rule(686)
    r.append(panel(usage, dark))
    rule(953)
    text(28, 980, 'From embedded to OS, now exploring CPUs.', 11, muted, mono=True)
    text(872, 980, '欢迎来博客踩一踩！', 11, accent, text_anchor='end')
    target = output / f'profile-{theme}.svg'
    E.ElementTree(r).write(target, encoding='utf-8', xml_declaration=True)
    validate(target)
    print(f'Generated and validated {target}')


def validate(path):
    svg = E.parse(path).getroot()
    ids = [node.get('id') for node in svg.iter() if node.get('id')]
    assert len(ids) == len(set(ids)), 'Duplicate SVG IDs'
    assert not list(svg.iter(N+'image')), 'Unexpected external image dependency'
    snake = svg.find(f"{N}svg[@id='contribution-snake']")
    assert snake is not None, 'Missing contribution snake'
    animation = E.tostring(snake)
    assert b'@keyframes' in animation and b'infinite' in animation, 'Animation lost'
    usage = svg.find(f"{N}svg[@id='codex-usage']")
    assert usage is not None, 'Missing Codex usage panel'
    assert len([e for e in usage.iter(N+'rect') if e.get('class') == 'usage-day']) == 365


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--snakes', type=Path)
    parser.add_argument('--output', type=Path, default=Path('assets'))
    parser.add_argument('--usage', type=Path, default=ROOT.parent / 'data/codex-usage.json')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    repos = repositories(args.offline)
    languages = language_data(args.offline)
    usage = validate_usage(json.loads(args.usage.read_text(encoding='utf-8')))
    if not repos:
        raise ValueError('No repository data; refusing to publish an empty profile')
    for dark in (False, True):
        generate(repos, languages, args.snakes or ROOT / 'inputs', args.output, dark, usage)


if __name__ == '__main__':
    main()
