"""
engine/voynich/renderer.py

Converts a VoynichPage into HTML/SVG for display.
The renderer knows only about glyphs and positions — no simulation data.
"""

from .alphabet import VoynichAlphabet, Glyph
from .encoder import VoynichPage, GlyphSequence, Illustration
from typing import Dict


GLYPH_SIZE = 12
LINE_HEIGHT = 20
PAGE_WIDTH = 600
PAGE_HEIGHT = 800
MARGIN = 60


def render_glyph(glyph: Glyph, x: float, y: float, scale: float = 1.0) -> str:
    return (
        f'<g transform="translate({x:.1f},{y:.1f}) scale({scale})">'
        f'<path d="{glyph.svg_path}" fill="none" stroke="currentColor" stroke-width="0.8"/>'
        f'</g>\n'
    )


def render_page(page: VoynichPage, alphabet: VoynichAlphabet) -> str:
    """Render a VoynichPage as a complete HTML page with embedded SVG."""
    glyph_map: Dict[str, Glyph] = {g.id: g for g in alphabet.glyphs}

    register_colors = {
        "liberation": "#E8E4D9",
        "shadow": "#1A1A2E",
        "transition": "#1E2A3A",
        "light": "#F5F0E8",
    }
    text_colors = {
        "liberation": "#2C1810",
        "shadow": "#7A8FAA",
        "transition": "#8A9FAA",
        "light": "#2C1810",
    }

    bg = register_colors.get(page.dominant_register, "#F5F0E8")
    fg = text_colors.get(page.dominant_register, "#2C1810")

    svg_parts = []

    # Render text sequences
    y = MARGIN
    for seq in page.sequences:
        x = MARGIN + seq.indent_level * 20
        if seq.has_space_before:
            y += LINE_HEIGHT * 0.5

        for glyph_id in seq.glyphs:
            if glyph_id == "SPACE":
                x += GLYPH_SIZE * 0.6
                continue

            glyph = glyph_map.get(glyph_id)
            if not glyph:
                continue

            scale = GLYPH_SIZE / 12.0
            svg_parts.append(render_glyph(glyph, x, y, scale))
            x += glyph.width * scale + 2

            if x > PAGE_WIDTH - MARGIN:
                x = MARGIN + seq.indent_level * 20
                y += LINE_HEIGHT

        y += LINE_HEIGHT
        if y > PAGE_HEIGHT - MARGIN - 100:
            break

    # Render illustrations
    for illus in page.illustrations:
        if not illus.svg_pattern:
            continue

        size_px = {"small": 60, "medium": 90, "large": 130}.get(illus.size, 60)
        positions = {
            "margin_left": (10, PAGE_HEIGHT // 2 - size_px // 2),
            "margin_right": (PAGE_WIDTH - size_px - 10, PAGE_HEIGHT // 2 - size_px // 2),
            "footer": (PAGE_WIDTH // 2 - size_px // 2, PAGE_HEIGHT - MARGIN - size_px),
            "center": (PAGE_WIDTH // 2 - size_px // 2, PAGE_HEIGHT // 2 - size_px // 2),
        }
        ix, iy = positions.get(illus.position, (MARGIN, MARGIN))

        svg_parts.append(
            f'<g transform="translate({ix},{iy}) scale({size_px / 100})" '
            f'opacity="0.6" color="{fg}">'
            f'<svg viewBox="0 0 100 100" width="100" height="100">'
            f'{illus.svg_pattern}'
            f'</svg></g>\n'
        )

    page_mark = "\u00b7" * (page.page_number % 7 + 1)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; background: {bg}; }}
  .page {{ width: {PAGE_WIDTH}px; height: {PAGE_HEIGHT}px;
           position: relative; overflow: hidden; }}
  .page-mark {{ position: absolute; bottom: 20px;
                width: 100%; text-align: center;
                color: {fg}; opacity: 0.4;
                font-size: 10px; letter-spacing: 4px; }}
  svg {{ color: {fg}; }}
</style>
</head>
<body>
<div class="page">
  <svg width="{PAGE_WIDTH}" height="{PAGE_HEIGHT}" viewBox="0 0 {PAGE_WIDTH} {PAGE_HEIGHT}">
    {''.join(svg_parts)}
  </svg>
  <div class="page-mark">{page_mark}</div>
</div>
</body>
</html>"""


def render_reader_html() -> str:
    """Return the standalone Voynich reader interface HTML."""
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>The Digital Voynich</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #1A1510; color: #8A7A6A; font-family: serif;
    height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; overflow: hidden;
  }
  #book-container {
    display: none; flex-direction: column;
    align-items: center; gap: 24px;
  }
  #page-display {
    width: 620px; height: 820px;
    border: 1px solid #3A3020;
    box-shadow: 0 0 80px rgba(0,0,0,0.9);
  }
  #controls {
    display: flex; gap: 40px; align-items: center;
    opacity: 0.4; transition: opacity 0.3s;
  }
  #controls:hover { opacity: 1; }
  button {
    background: none; border: 1px solid #5A4A3A;
    color: #8A7A6A; padding: 8px 24px; font-family: serif;
    font-size: 12px; letter-spacing: 4px; cursor: pointer;
    text-transform: uppercase;
  }
  button:hover { border-color: #8A7A6A; color: #C4A882; }
  #open-screen { text-align: center; cursor: pointer; }
  #open-screen h1 {
    font-size: 14px; letter-spacing: 8px; text-transform: uppercase;
    font-weight: normal; color: #5A4A3A; margin-bottom: 40px;
  }
  #open-btn { font-size: 11px; letter-spacing: 6px; padding: 12px 40px; }
  .page-mark { font-size: 10px; letter-spacing: 4px; color: #3A3020; }
</style>
</head>
<body>

<div id="open-screen">
  <h1>The Digital Voynich</h1>
  <button id="open-btn" onclick="openBook()">OPEN</button>
</div>

<div id="book-container">
  <iframe id="page-display" src="" frameborder="0"></iframe>
  <div id="controls">
    <button onclick="previousPage()">\u25c2</button>
    <div class="page-mark" id="page-mark">\u00b7</div>
    <button onclick="closeBook()">CLOSE</button>
    <div class="page-mark">\u00b7</div>
    <button onclick="nextPage()">\u25b8</button>
  </div>
</div>

<script>
  let currentPage = 1;
  let maxPage = 1;
  let pollInterval = null;

  function openBook() {
    document.getElementById('open-screen').style.display = 'none';
    document.getElementById('book-container').style.display = 'flex';
    loadPage(currentPage);
    pollInterval = setInterval(checkForNewPages, 5000);
    fetch('/api/voynich/open', { method: 'POST' }).catch(() => {});
  }

  function closeBook() {
    clearInterval(pollInterval);
    document.getElementById('book-container').style.display = 'none';
    document.getElementById('open-screen').style.display = 'block';
    fetch('/api/voynich/close', { method: 'POST' }).catch(() => {});
  }

  function loadPage(n) {
    document.getElementById('page-display').src = '/api/voynich/page/' + n;
    document.getElementById('page-mark').textContent = '\\u00b7'.repeat((n % 7) + 1);
  }

  function nextPage() {
    if (currentPage < maxPage) { currentPage++; loadPage(currentPage); }
  }

  function previousPage() {
    if (currentPage > 1) { currentPage--; loadPage(currentPage); }
  }

  function checkForNewPages() {
    fetch('/api/voynich/status')
      .then(r => r.json())
      .then(data => {
        maxPage = data.page_count || 1;
        if (currentPage === maxPage - 1) { currentPage = maxPage; loadPage(currentPage); }
      })
      .catch(() => {});
  }
</script>
</body>
</html>"""
