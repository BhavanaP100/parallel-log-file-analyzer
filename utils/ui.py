"""
ui.py
------------------------------------------------------
Visual building blocks for the dashboard: inline SVG icons, the hero
banner, metric cards, and the two charts (pie + bar).

Nothing in here does any log analysis - it only turns numbers into
HTML / chart specs. The styling for every class used below lives in
assets/style.css.

Charts use Streamlit's built-in Vega-Lite support, so no extra
libraries (plotly, matplotlib, ...) are needed.
------------------------------------------------------
"""

import pandas as pd
import streamlit as st

from utils.log_utils import percent_of

# Colours shared by the charts and the legend (match style.css)
LEVEL_COLORS = {
    "INFO": "#22A06B",
    "WARNING": "#F5A00F",
    "ERROR": "#EF4444",
    "OTHER": "#94A3B8",
}
BLUE = "#1F6FE5"
GREEN = "#2E9E5B"


# ----------------------------------------------------------------------
# Icons & illustrations
#
# Streamlit's HTML sanitizer strips inline <svg>, so every icon is a plain
# <span class="ico ico-NAME"> whose shape comes from a CSS mask (defined in
# icon_css() below, injected once from app.py). Because it is a mask, the
# icon takes whatever text colour its parent has - exactly like an SVG
# using currentColor. Full-colour artwork uses CSS background images.
# ----------------------------------------------------------------------

def _stroke(body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')


def _cutout(shape, holes):
    """Solid shape with see-through details (so the parent's colour shows around them)."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<defs><mask id="m"><rect width="24" height="24" fill="#fff"/>'
            f'<g stroke="#000" stroke-width="2.3" stroke-linecap="round" fill="none">{holes}</g></mask></defs>'
            f'<g mask="url(#m)" fill="#000">{shape}</g></svg>')


MASK_ICONS = {
    "bolt": _stroke('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" fill="#000"/>'),
    "database": _stroke(
        '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>'
        '<path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>'),
    "clock": _stroke('<circle cx="12" cy="12" r="9.5"/><polyline points="12 6.5 12 12 15.5 14"/>'),
    "upload": _stroke(
        '<path d="M20 17.6A4.5 4.5 0 0 0 18 9h-1.3A7 7 0 1 0 4 15.3"/>'
        '<polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/>'),
    "gear": _stroke(
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 '
        '1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83'
        'l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82'
        'l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51'
        '1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09'
        'a1.65 1.65 0 0 0-1.51 1z"/>'),
    "bars": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#000">'
             '<rect x="3" y="11" width="4.5" height="10" rx="1.2"/><rect x="9.75" y="4" width="4.5" height="17" rx="1.2"/>'
             '<rect x="16.5" y="8" width="4.5" height="13" rx="1.2"/></svg>'),
    "speed": _cutout('<path d="M13 1.5 4 14h6l-1 8.5L19 10h-6z"/>', ""),
    "file": _cutout('<path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/>',
                    '<path d="M8 13h8M8 17.2h5"/>'),
    "info": _cutout('<circle cx="12" cy="12" r="10"/>', '<path d="M12 11v5.5M12 7.5v.1"/>'),
    "warn": _cutout('<path d="M10.3 3.6 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0z"/>',
                    '<path d="M12 9.5v4.6M12 17.4v.1"/>'),
    "error": _cutout('<circle cx="12" cy="12" r="10"/>', '<path d="m8.5 8.5 7 7m0-7-7 7"/>'),
    "clock_solid": _cutout('<circle cx="12" cy="12" r="10"/>', '<path d="M12 6.8V12l3.4 2"/>'),
}

LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="76" height="76" viewBox="0 0 76 76" fill="none">'
    '<g stroke="#CFE0FF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M44 8H20a6 6 0 0 0-6 6v44a6 6 0 0 0 6 6h14"/><path d="M44 8l14 14v10"/><path d="M44 8v14h14"/>'
    '<path d="M23 31h14M23 41h9M23 51h7"/></g>'
    '<g transform="translate(51 51)"><circle r="14" fill="#2F7BF0"/>'
    '<g stroke="#2F7BF0" stroke-width="5" stroke-linecap="round">'
    '<path d="M0-17v6M0 11v6M-17 0h6M11 0h6M-12-12l4 4M8 8l4 4M12-12l-4 4M-8 8l-4 4"/></g>'
    '<circle r="5.2" fill="#0E2243"/></g></svg>'
)

HERO_ART = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 340 200">'
    '<ellipse cx="120" cy="120" rx="105" ry="68" fill="#CFE0FA" opacity=".65"/>'
    '<ellipse cx="272" cy="105" rx="52" ry="62" fill="#D9E7FB" opacity=".8"/>'
    '<rect x="76" y="22" width="150" height="150" rx="16" fill="#fff" stroke="#DCE7F8"/>'
    '<rect x="76" y="22" width="150" height="150" rx="16" fill="#EAF2FE" opacity=".5"/>'
    '<g stroke-linecap="round" stroke-width="5">'
    '<path d="M96 52h42" stroke="#1B2F57"/><path d="M148 52h50" stroke="#7FA6EC"/>'
    '<path d="M96 70h28" stroke="#1B2F57"/><path d="M134 70h64" stroke="#7FA6EC"/>'
    '<path d="M96 88h54" stroke="#7FA6EC"/><path d="M96 106h24" stroke="#1B2F57"/>'
    '<path d="M96 138h70" stroke="#1B2F57"/><path d="M96 154h104" stroke="#7FA6EC"/></g>'
    '<circle cx="206" cy="92" r="46" fill="#DCEBFF" fill-opacity=".72" stroke="#0F2F66" stroke-width="9"/>'
    '<path d="M178 66a34 34 0 0 1 22-10" stroke="#fff" stroke-opacity=".8" stroke-width="5" fill="none" stroke-linecap="round"/>'
    '<path d="m240 128 42 44" stroke="#0F2F66" stroke-width="13" stroke-linecap="round"/></svg>'
)

COLOR_IMAGES = {
    "logo": LOGO_SVG,
    "hero": HERO_ART,
    "python": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M11.9 2C8 2 8.2 3.7 8.2 3.7v1.8H12v.6H6.6S4 5.8 4 9.8s2.3 3.9 2.3 3.9h1.4v-1.9s-.1-2.3 2.2-2.3h3.8s2.1 0 2.1-2.1V4.2S16.1 2 11.9 2zM9.8 3.3a.7.7 0 1 1 0 1.4.7.7 0 0 1 0-1.4z" fill="#4B8BBE"/>'
        '<path d="M12.1 22c3.9 0 3.7-1.7 3.7-1.7v-1.8H12v-.6h5.4s2.6.3 2.6-3.7-2.3-3.9-2.3-3.9h-1.4v1.9s.1 2.3-2.2 2.3h-3.8s-2.1 0-2.1 2.1v3.2S7.9 22 12.1 22zm2.1-1.3a.7.7 0 1 1 0-1.4.7.7 0 0 1 0 1.4z" fill="#FFD43B"/></svg>'),
    "streamlit": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M12 4 2 8.6l10 4.6 10-4.6z" fill="#FF7B7B"/><path d="m2 8.6 10 4.6v7.2L2 15.8z" fill="#E53E4D"/>'
        '<path d="m22 8.6-10 4.6v7.2l10-4.6z" fill="#FF4B4B"/></svg>'),
    "pandas": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<rect x="4" y="3" width="3.4" height="18" rx="1" fill="#8B7CF6"/>'
        '<rect x="10.3" y="7" width="3.4" height="10" rx="1" fill="#FFCA28"/>'
        '<rect x="16.6" y="3" width="3.4" height="18" rx="1" fill="#8B7CF6"/></svg>'),
}

ICON_SIZES = (18, 20, 22, 24, 26, 28)


def _uri(svg):
    from urllib.parse import quote
    return 'url("data:image/svg+xml,' + quote(svg, safe="") + '")'


def icon_css():
    """CSS that defines every .ico-* / .img-* class. Injected once per page load."""
    rules = [
        ".ico{display:inline-block;flex:none;background-color:currentColor;"
        "-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;"
        "-webkit-mask-position:center;mask-position:center;-webkit-mask-size:contain;mask-size:contain}",
        ".img{display:inline-block;flex:none;background-repeat:no-repeat;background-position:center;background-size:contain}",
    ]
    rules += [f".ico-s{n}{{width:{n}px;height:{n}px}}" for n in ICON_SIZES]
    for name, svg in MASK_ICONS.items():
        u = _uri(svg)
        rules.append(f".ico-{name}{{-webkit-mask-image:{u};mask-image:{u}}}")
    for name, svg in COLOR_IMAGES.items():
        rules.append(f".img-{name}{{background-image:{_uri(svg)}}}")
    return "\n".join(rules)


def icon(name, size=22):
    """Return a small inline icon (as safe HTML) coloured by the parent's text colour."""
    return f'<span class="ico ico-{name} ico-s{size}"></span>'


# ----------------------------------------------------------------------
# Helper: render a block of HTML (st.html needs no markdown escaping)
# ----------------------------------------------------------------------

def html(markup):
    """Render raw HTML. Newlines/indentation are collapsed first."""
    st.html("".join(line.strip() for line in markup.splitlines()))


# ----------------------------------------------------------------------
# Sidebar pieces
# ----------------------------------------------------------------------

def sidebar_brand():
    html("""
    <div class="brand">
        <div class="brand-logo"><span class="img img-logo"></span></div>
        <div class="brand-name">Parallel Log<br>Analyzer</div>
        <div class="brand-sub">Sequential vs Multithreaded<br>Log Processing</div>
    </div>
    """)


def sidebar_built_with():
    items = [
        ('<span class="img img-python ico-s22"></span>', "Python"),
        ('<span class="img img-streamlit ico-s22"></span>', "Streamlit"),
        ('<span class="img img-pandas ico-s22"></span>', "Pandas"),
        ('<span class="bw-gear">' + icon("gear", 22) + "</span>", "Multithreading"),
    ]
    rows = "".join(f'<div class="bw-item">{svg}<span>{name}</span></div>' for svg, name in items)
    html(f'<div class="built-with"><div class="bw-title">Built with</div>{rows}</div>')


# ----------------------------------------------------------------------
# Hero banner
# ----------------------------------------------------------------------

def hero(eyebrow, title, subtitle, features=None, compact=False):
    feats = ""
    if features:
        cells = "".join(
            f'<div class="hero-feature"><div class="hf-icon">{icon_svg}</div>'
            f'<div><div class="hf-title">{t}</div><div class="hf-sub">{s}</div></div></div>'
            for icon_svg, t, s in features
        )
        feats = f'<div class="hero-features">{cells}</div>'
    html(f"""
    <div class="hero{' compact' if compact else ''}">
        <div class="hero-text">
            <div class="hero-eyebrow">{eyebrow}</div>
            <div class="hero-title" role="heading" aria-level="1">{title}</div>
            <div class="hero-sub">{subtitle}</div>
            {feats}
        </div>
        <div class="hero-art"><span class="img img-hero"></span></div>
    </div>
    """)


def dashboard_hero():
    hero(
        "COLLEGE PROJECT",
        "Parallel Log File Analyzer",
        "Analyze log files and compare sequential and multithreaded processing.",
        features=[
            (icon("bolt", 20), "Fast Analysis", "Process large logs efficiently"),
            (icon("database", 20), "Compare Performance", "Sequential vs Multithreaded"),
            (icon("bars", 20), "Detailed Insights", "Visualize log statistics"),
        ],
    )


# ----------------------------------------------------------------------
# Cards
# ----------------------------------------------------------------------

def card_title(icon_svg, title, subtitle=None, tone="blue"):
    sub = f'<div class="card-sub">{subtitle}</div>' if subtitle else ""
    html(f"""
    <div class="card-head">
        <div class="card-title"><span class="ct-icon tone-{tone}-ink">{icon_svg}</span>{title}</div>
        {sub}
    </div>
    """)


def stat_card(label, value, sub, tone, icon_svg):
    return f"""
    <div class="stat-card tone-{tone}">
        <div class="stat-icon">{icon_svg}</div>
        <div class="stat-body">
            <div class="stat-label">{label}</div>
            <div class="stat-value">{value}</div>
            <div class="stat-sub">{sub}</div>
        </div>
    </div>
    """


def stat_grid(cards):
    html(f'<div class="stat-grid cols-{len(cards)}">{"".join(cards)}</div>')


def level_cards(counts, total):
    """The 4 headline cards: Total / INFO / WARNING / ERROR."""
    if counts is None:
        dash, none_sub = "\u2014", "Run an analysis"
        stat_grid([
            stat_card("Total Log Entries", dash, "Lines processed", "blue", icon("file", 28)),
            stat_card("INFO Logs", dash, none_sub, "green", icon("info", 28)),
            stat_card("WARNING Logs", dash, none_sub, "amber", icon("warn", 28)),
            stat_card("ERROR Logs", dash, none_sub, "red", icon("error", 28)),
        ])
        return
    stat_grid([
        stat_card("Total Log Entries", f"{total:,}", "Lines processed", "blue", icon("file", 28)),
        stat_card("INFO Logs", f"{counts.get('INFO', 0):,}",
                  f"{percent_of(counts.get('INFO', 0), total)} of total", "green", icon("info", 28)),
        stat_card("WARNING Logs", f"{counts.get('WARNING', 0):,}",
                  f"{percent_of(counts.get('WARNING', 0), total)} of total", "amber", icon("warn", 28)),
        stat_card("ERROR Logs", f"{counts.get('ERROR', 0):,}",
                  f"{percent_of(counts.get('ERROR', 0), total)} of total", "red", icon("error", 28)),
    ])


def empty_note(title, body):
    html(f'<div class="empty-note"><div class="en-title">{title}</div><div>{body}</div></div>')


def section_heading(text):
    html(f'<div class="section-heading">{text}</div>')


def info_card(title, body_html):
    html(f'<div class="content-card"><h4>{title}</h4><div class="cc-body">{body_html}</div></div>')


# ----------------------------------------------------------------------
# Charts (Vega-Lite specs)
# ----------------------------------------------------------------------

_CHART_CONFIG = {
    "font": "Inter, Segoe UI, Arial, sans-serif",
    "background": None,
    "view": {"stroke": None},
    "axis": {"labelColor": "#5B6B86", "titleColor": "#5B6B86", "gridColor": "#E5ECF7",
             "domainColor": "#C9D6EA", "tickColor": "#C9D6EA", "labelFontSize": 12, "titleFontSize": 12,
             "titleFontWeight": "normal"},
}


def _level_frame(counts):
    total = sum(counts.values()) or 1
    rows = [(k, v) for k, v in counts.items() if v > 0 or k != "OTHER"]
    df = pd.DataFrame(rows, columns=["Log Level", "Count"])
    df["Share"] = df["Count"] / total
    # Hide the in-slice label on very thin slices so text never overlaps
    df["Label"] = df["Share"].apply(lambda s: f"{s * 100:.1f}%" if s >= 0.04 else "")
    return df


def level_pie(counts):
    df = _level_frame(counts)
    domain = list(df["Log Level"])
    spec = {
        "height": 250,
        "config": _CHART_CONFIG,
        "encoding": {
            "theta": {"field": "Count", "type": "quantitative", "stack": True},
            "color": {"field": "Log Level", "type": "nominal", "legend": None,
                      "scale": {"domain": domain, "range": [LEVEL_COLORS[d] for d in domain]}},
            "order": {"field": "Count", "type": "quantitative", "sort": "descending"},
        },
        "layer": [
            {"mark": {"type": "arc", "outerRadius": 108, "stroke": "#FFFFFF", "strokeWidth": 2},
             "encoding": {"tooltip": [{"field": "Log Level"}, {"field": "Count", "format": ","}]}},
            {"mark": {"type": "text", "radius": 72, "fontSize": 14, "fontWeight": 700, "color": "#FFFFFF"},
             "encoding": {"text": {"field": "Label", "type": "nominal"}, "color": {"value": "#FFFFFF"}}},
        ],
    }
    st.vega_lite_chart(df, spec, width="stretch")


def level_legend(counts, total):
    rows = ""
    for level, n in counts.items():
        if level == "OTHER" and n == 0:
            continue
        rows += (
            f'<div class="lg-row"><span class="lg-dot dot-{level.lower()}"></span>'
            f'<span class="lg-name">{level}</span><span class="lg-n">{n:,}</span>'
            f'<span class="lg-pct">{percent_of(n, total)}</span></div>'
        )
    html(f'<div class="legend">{rows}</div>')


def time_bar(seq_time, par_time):
    """Bar chart of measured execution times. Either value may be None."""
    from utils.log_utils import format_short_seconds

    rows = []
    if seq_time is not None:
        rows.append(("Sequential", seq_time))
    if par_time is not None:
        rows.append(("Multithreaded", par_time))
    df = pd.DataFrame(rows, columns=["Method", "Seconds"])
    df["Label"] = df["Seconds"].apply(format_short_seconds)
    spec = {
        "height": 250,
        "config": _CHART_CONFIG,
        "encoding": {
            "x": {"field": "Method", "type": "nominal", "sort": ["Sequential", "Multithreaded"],
                  "axis": {"labelAngle": 0, "title": None, "labelFontSize": 13, "domain": True, "ticks": False}},
            "y": {"field": "Seconds", "type": "quantitative",
                  "axis": {"title": "Time (seconds)", "tickCount": 5, "grid": True, "domain": False}},
        },
        "layer": [
            {"mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3, "size": 110},
             "encoding": {"color": {"field": "Method", "type": "nominal", "legend": None,
                                    "scale": {"domain": ["Sequential", "Multithreaded"], "range": [BLUE, GREEN]}},
                          "tooltip": [{"field": "Method"}, {"field": "Label", "title": "Time"}]}},
            {"mark": {"type": "text", "dy": -9, "fontSize": 13, "fontWeight": 700, "color": "#1F2A44"},
             "encoding": {"text": {"field": "Label", "type": "nominal"}}},
        ],
    }
    st.vega_lite_chart(df, spec, width="stretch")
