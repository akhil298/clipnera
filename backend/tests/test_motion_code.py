"""Motion code: a graphic the model writes is cleaned to an allowlist before the renderer sees it."""

from __future__ import annotations

import pytest

from reel_engine.motion_code import Rejected, clean, free_area


def test_scripts_handlers_and_outside_urls_never_reach_the_renderer():
    for html in ('<div><script>alert(1)</script></div>', '<img src="x" onerror="alert(1)">', '<iframe src="https://x.io"></iframe>',
                 '<svg><animate attributeName="x"/></svg>'):
        with pytest.raises(Rejected):
            clean(html, "")
    for css in ('.a{background:url(https://x.io/a.png)}', '@import "x.css";', '.a{background:url("javascript:alert(1)")}'):
        with pytest.raises(Rejected):
            clean('<div class="a"></div>', css)


def test_allowed_markup_survives_and_unknown_attributes_are_dropped():
    html, css = clean('<div class="mg" onclick="x()" data-x="1"><svg viewBox="0 0 10 10"><path d="M0 0L10 10" pathLength="1"/>'
                      '<rect fill="url(#g)"/></svg><b>50&lt;x</b></div>', ".mg{fill:url(#g)}")
    assert "onclick" not in html and "data-x" not in html
    assert 'class="mg"' in html and 'd="M0 0L10 10"' in html and 'fill="url(#g)"' in html and "50&lt;x" in html
    assert css == ".mg{fill:url(#g)}"


def test_the_free_area_names_the_bands_around_the_face():
    assert "nobody" in free_area([])
    text = free_area([(300, 200, 800, 900)])
    assert "below the face: y 920-1860" in text and "never draw over it" in text and "above the face" not in text
