"""Text has to be readable on the colour it sits on.

Measured, not judged by eye. Every pair below is a combination the product
actually renders, and the numbers are what a browser would compute.

Three were unreadable rather than merely tight:

* White on `bg-warning` — **1.63:1**. Bootstrap's amber is a light colour; white
  on it is nearly invisible. It carried the dashboard's "Đang thực hiện" count,
  on a screen meant to be read across a workshop.
* White on `bg-info` — **1.96:1**. Same shape.
* `text-warning` on white — **1.63:1**. This was the headline debt figure on the
  receivables report: the one number that screen exists to show.

All three fail even the 3:1 allowance for large text, so no amount of "it is a
big number" rescues them.

Two more were just under AA and are fixed with them: `.text-muted` on the body
background (4.30:1, needs 4.5) and the footer's version string on dark
(3.29:1) — the string a user is asked to read out when they ring for support.

The thresholds are WCAG 2.1 AA: 4.5:1 for normal text, 3:1 for large or for
non-text that carries meaning. The test computes the ratio rather than pinning
a hex value, so changing a colour is allowed and making it unreadable is not.
"""
import io
import pathlib
import re

import pytest

CSS = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'static' / 'css' / 'style.css'


def _channel(value):
    value = value / 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(colour):
    r, g, b = colour
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def contrast(foreground, background):
    high = max(_luminance(_rgb(foreground)), _luminance(_rgb(background)))
    low = min(_luminance(_rgb(foreground)), _luminance(_rgb(background)))
    return (high + 0.05) / (low + 0.05)


def _declared(selector, prop):
    """Read a colour the stylesheet sets, so the test follows the CSS.

    Handles a grouped selector — `a, b, c { ... }` — because the first version
    of this matched only a block whose selector list was exactly the one asked
    for, and reported the CSS as missing when it was simply shared.
    """
    text = io.open(CSS, encoding='utf-8').read()
    # Strip comments first: everything between two braces is captured as the
    # selector list, so a comment above a rule became part of its name and the
    # rule read as missing.
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    for selectors, body in re.findall(r'([^{}]+)\{([^}]*)\}', text):
        names = [part.strip() for part in selectors.split(',')]
        if selector not in names:
            continue
        found = re.search(prop + r'\s*:\s*(#[0-9a-fA-F]{6})', body)
        if found:
            return found.group(1)
    raise AssertionError(f'{selector} does not set {prop} in style.css')


def test_the_contrast_helper_agrees_with_known_values():
    """Guard the measurement itself before trusting what it says."""
    assert round(contrast('#000000', '#ffffff'), 2) == 21.0
    assert round(contrast('#ffffff', '#ffc107'), 2) == 1.63


@pytest.mark.parametrize('name, selector, background, minimum', [
    # The KPI cards on the dashboard: read across a room, so their own floor
    # is the large-text 3:1 — but white on amber does not even reach that.
    ('dashboard amber card', '.stats-card.bg-warning', '#ffc107', 4.5),
    ('dashboard cyan card', '.stats-card.bg-info', '#0dcaf0', 4.5),
])
def test_kpi_card_text_is_readable(name, selector, background, minimum):
    colour = _declared(selector, 'color')
    ratio = contrast(colour, background)
    assert ratio >= minimum, f'{name}: {ratio:.2f}:1 (needs {minimum}:1)'


def test_the_headline_debt_figure_is_readable():
    """The one number the receivables report exists to show."""
    colour = _declared('.sofa-amount-warning', 'color')
    ratio = contrast(colour, '#ffffff')
    assert ratio >= 4.5, f'{ratio:.2f}:1 on white'


def test_muted_text_is_readable_on_the_page_background():
    """`body` is #f5f5f5, not white, which is what took this under AA."""
    colour = _declared('.text-muted', 'color')
    ratio = contrast(colour, '#f5f5f5')
    assert ratio >= 4.5, f'{ratio:.2f}:1 on the page background'


def test_the_footer_version_is_readable():
    """What a user is asked to read out when they ring for support."""
    colour = _declared('footer .app-version', 'color')
    ratio = contrast(colour, '#212529')
    assert ratio >= 4.5, f'{ratio:.2f}:1 on the dark footer'
