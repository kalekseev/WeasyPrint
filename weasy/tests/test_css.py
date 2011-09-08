# coding: utf8

#  WeasyPrint converts web documents (HTML, CSS, ...) to PDF.
#  Copyright (C) 2011  Simon Sapin
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Test the base mechanisms of CSS.

"""

import os.path
from cssutils.helper import path2url

from attest import Tests, raises, assert_hook  # pylint: disable=W0611
import cssutils

from . import resource_filename
from .test_boxes import monkeypatch_validation
from .. import css
from ..document import Document


SUITE = Tests()


def parse_html(filename, **kwargs):
    """Parse an HTML file from the test resources and resolve relative URL."""
    # Make a file:// URL
    url = path2url(resource_filename(filename))
    return Document.from_file(url, **kwargs)


@SUITE.test
def test_style_dict():
    """Test a style in a ``dict``."""
    style = css.computed_values.StyleDict({
        'margin-left': cssutils.css.PropertyValue('12px'),
        'display': cssutils.css.PropertyValue('block')})
    assert style.display[0].value == 'block'
    assert style.margin_left[0].value == 12
    with raises(AttributeError):
        style.position  # pylint: disable=W0104


@SUITE.test
def test_find_stylesheets():
    """Test if the stylesheets are found in a HTML document."""
    document = parse_html('doc1.html')

    sheets = list(css.find_stylesheets(document))
    assert len(sheets) == 3
    # Also test that stylesheets are in tree order
    assert [s.href.rsplit('/', 1)[-1].rsplit(',', 1)[-1] for s in sheets] \
        == ['sheet1.css', 'a%7Bcolor%3AcurrentColor%7D',
            'doc1.html']

    rules = list(rule for sheet in sheets
                      for rule in css.effective_rules(sheet, 'print'))
    assert len(rules) == 9
    # Also test appearance order
    assert [rule.selectorText for rule in rules] \
        == ['a', 'li', 'p', 'ul', 'li', 'a:after', ':first', 'ul',
            'body > h1:first-child']


@SUITE.test
def test_expand_shorthands():
    """Test the expand shorthands."""
    sheet = cssutils.parseFile(resource_filename('sheet2.css'))
    assert sheet.cssRules[0].selectorText == 'li'

    style = sheet.cssRules[0].style
    assert style['margin'] == '2em 0'
    assert style['margin-bottom'] == '3em'
    assert style['margin-left'] == '4em'
    assert not style['margin-top']

    style = dict(
        (name, css.values.as_css(values))
        for name, values, _priority in css.effective_declarations(style))

    assert 'margin' not in style
    assert style['margin-top'] == '2em'
    assert style['margin-right'] == '0'
    assert style['margin-bottom'] == '2em', \
        '3em was before the shorthand, should be masked'
    assert style['margin-left'] == '4em', \
        '4em was after the shorthand, should not be masked'


def parse_css(filename):
    """Parse and return the CSS at ``filename``."""
    return cssutils.parseFile(resource_filename(filename))


def validate_content(real_non_shorthand, name, values, required=False):
    """Fake validator for the ``content`` property."""
    if name == 'content':
        return [(name, values)]
    return real_non_shorthand(name, values, required)


@SUITE.test
def test_annotate_document():
    """Test a document with inline style."""
    # Short names for variables are OK here
    # pylint: disable=C0103

    # TODO: remove this patching when the `content` property is supported.
    with monkeypatch_validation(validate_content):
        document = parse_html(
            'doc1.html',
            user_stylesheets=[parse_css('user.css')],
            user_agent_stylesheets=[parse_css('mini_ua.css')],
        )

        # Element objects behave a lists of their children
        _head, body = document.dom
        h1, p, ul = body
        li_0, _li_1 = ul
        a, = li_0

        h1 = document.style_for(h1)
        p = document.style_for(p)
        ul = document.style_for(ul)
        li_0 = document.style_for(li_0)
        after = document.style_for(a, 'after')
        a = document.style_for(a)

    assert h1['background-image'][0].absoluteUri == 'file://' \
        + os.path.abspath(resource_filename('logo_small.png'))

    assert h1.font_weight[0].value == 700

    # 32px = 1em * font-size: 2em * initial 16px
    assert p.margin_top[0].value == 32
    assert p.margin_right[0].value == 0
    assert p.margin_bottom[0].value == 32
    assert p.margin_left[0].value == 0

    # 32px = 2em * initial 16px
    assert ul.margin_top[0].value == 32
    assert ul.margin_right[0].value == 32
    assert ul.margin_bottom[0].value == 32
    assert ul.margin_left[0].value == 32

    # thick = 5px, 0.25 inches = 96*.25 = 24px
    assert ul.border_top_width[0].value == 0
    assert ul.border_right_width[0].value == 5
    assert ul.border_bottom_width[0].value == 0
    assert ul.border_left_width[0].value == 24

    # 32px = 2em * initial 16px
    # 64px = 4em * initial 16px
    assert li_0.margin_top[0].value == 32
    assert li_0.margin_right[0].value == 0
    assert li_0.margin_bottom[0].value == 32
    assert li_0.margin_left[0].value == 64

    assert a.text_decoration[0].value == 'underline'

    assert a.padding_top[0].value == 1
    assert a.padding_right[0].value == 2
    assert a.padding_bottom[0].value == 3
    assert a.padding_left[0].value == 4

    color = a['color'][0]
    assert (color.red, color.green, color.blue, color.alpha) == (255, 0, 0, 1)
    # Test the initial border-color: currentColor
    color = a['border-top-color'][0]
    assert (color.red, color.green, color.blue, color.alpha) == (255, 0, 0, 1)

    # The href attr should be as in the source, not made absolute.
    assert ''.join(v.value for v in after['content']) == ' [home.html]'

    # TODO much more tests here: test that origin and selector precedence
    # and inheritance are correct, ...

    # pylint: enable=C0103


@SUITE.test
def test_default_stylesheet():
    """Test if the user-agent stylesheet is used and applied."""
    # TODO: remove this patching when the `content` property is supported.
    with monkeypatch_validation(validate_content):
        document = parse_html('doc1.html')
        head_style = document.style_for(document.dom.head)
    assert head_style.display[0].value == 'none', \
        'The HTML4 user-agent stylesheet was not applied'


@SUITE.test
def test_page():
    """Test the ``@page`` properties."""
    # TODO: remove this patching when the `content` property is supported.
    with monkeypatch_validation(validate_content):
        document = parse_html('doc1.html', user_stylesheets=[
            cssutils.parseString('''
                @page {
                    margin: 10px;
                }
                @page :right {
                    margin-bottom: 12pt;
                }
            ''')
        ])

        style = document.style_for('@page', 'first_left')

    assert style.margin_top[0].value == 5
    assert style.margin_left[0].value == 10
    assert style.margin_bottom[0].value == 10

    style = document.style_for('@page', 'first_right')
    assert style.margin_top[0].value == 5
    assert style.margin_left[0].value == 10
    assert style.margin_bottom[0].value == 16

    style = document.style_for('@page', 'left')
    assert style.margin_top[0].value == 10
    assert style.margin_left[0].value == 10
    assert style.margin_bottom[0].value == 10

    style = document.style_for('@page', 'right')
    assert style.margin_top[0].value == 10
    assert style.margin_left[0].value == 10
    assert style.margin_bottom[0].value == 16
