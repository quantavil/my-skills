#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown-it-py>=4,<5", "jinja2>=3.1.6,<4"]
# ///
"""Render one Markdown fact-check into a standalone HTML report; optional DOT maps."""
import argparse
import base64
from html import escape
from pathlib import Path
import shutil
import subprocess
import sys


VERDICTS = {'Supported': 'supported', 'Misleading': 'misleading', 'False': 'false',
            'Unverifiable': 'unverifiable', 'Opinion': 'opinion'}


def diagram(source):
    if not shutil.which('dot'):
        raise ValueError('This report contains a DOT map. Install Graphviz (the dot executable), or keep the argument as prose and remove the optional map.')
    try:
        result = subprocess.run(
            ['dot', '-Tsvg', '-Gbgcolor=transparent', '-Gpad=0.25', '-Granksep=0.4',
             '-Gnodesep=0.3', '-Nshape=box', '-Nstyle=rounded,filled', '-Nfillcolor=#edf3ff',
             '-Ncolor=#9baed0', '-Nfontname=DejaVu Sans', '-Nfontsize=12',
             '-Ecolor=#64748b', '-Efontname=DejaVu Sans', '-Efontsize=10'],
            input=source, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Argument map took too long to render; simplify it.') from exc
    if result.returncode:
        raise ValueError('Invalid argument map: ' + result.stderr[-1200:])
    encoded = base64.b64encode(result.stdout.encode('utf-8')).decode('ascii')
    # SVG displayed as an image is inert; never inject SVG source into the HTML DOM.
    return ('<figure class="argument-map"><img alt="Argument map; premises and conclusion are explained in the accompanying text" '
            f'src="data:image/svg+xml;base64,{encoded}">'
            '<figcaption>Argument map · follow the labeled connections; node colors do not indicate truth.</figcaption></figure>\n')


def render(markdown, title=None, language='en'):
    if not markdown.strip():
        raise ValueError('Report is empty')
    try:
        from markdown_it import MarkdownIt
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError as exc:
        raise RuntimeError('Missing report dependencies. Run with uv: uv run render_report.py report.md --output report.html') from exc
    md = MarkdownIt('commonmark', {'html': False})
    default_fence = md.renderer.rules['fence']

    def fence(tokens, index, options, env):
        token = tokens[index]
        if token.info.strip().split()[:1] == ['dot']:
            return diagram(token.content)
        return default_fence(tokens, index, options, env)

    def strong_open(tokens, index, options, env):
        next_text = tokens[index + 1].content if index + 1 < len(tokens) else ''
        style = VERDICTS.get(next_text)
        return f'<strong class="verdict verdict-{style}">' if style else '<strong>'

    md.renderer.rules['fence'] = fence
    md.renderer.rules['strong_open'] = strong_open
    md.renderer.rules['image'] = lambda tokens, index, options, env: escape(tokens[index].content)
    tokens = md.parse(markdown)
    contents = []
    for index, token in enumerate(tokens):
        if token.type != 'heading_open':
            continue
        inline = tokens[index + 1]
        label = ''.join(child.content for child in (inline.children or []) if child.type in ('text', 'code_inline'))
        if token.tag == 'h1' and title is None:
            title = label
        if token.tag in ('h2', 'h3'):
            anchor = f'section-{len(contents) + 1}'
            token.attrSet('id', anchor)
            contents.append({'id': anchor, 'label': label, 'level': token.tag})
    content = md.renderer.render(tokens, md.options, {})
    assets = Path(__file__).resolve().parents[1] / 'assets'
    template = Environment(loader=FileSystemLoader(assets),
                           autoescape=select_autoescape(default=True)).get_template('report.html.j2')
    return template.render(title=title or 'Fact-check report', language=language,
                           content=content, contents=contents)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path, help='Existing Markdown report; never rewritten')
    parser.add_argument('--output', type=Path, help='Defaults to the input path with .html extension')
    parser.add_argument('--title', help='Optional browser-tab title')
    parser.add_argument('--lang', default='en', help='Report language code, e.g. en or hi')
    args = parser.parse_args(argv)
    source = args.report.expanduser().resolve()
    output = args.output.expanduser().resolve() if args.output else source.with_suffix('.html')
    if source == output:
        raise ValueError('Output must differ from the Markdown input')
    page = render(source.read_text(encoding='utf-8-sig'), args.title, args.lang)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(page, encoding='utf-8')
    temporary.replace(output)
    print(output)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
