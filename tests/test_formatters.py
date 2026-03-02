"""Tests for message formatters."""

import pytest

from src.bot.formatters import markdown_to_telegram_html, truncate_message


class TestMarkdownToTelegramHtml:
    def test_bold(self):
        result = markdown_to_telegram_html("**bold text**")
        assert result == "<b>bold text</b>"
    
    def test_italic(self):
        result = markdown_to_telegram_html("*italic text*")
        assert result == "<i>italic text</i>"
    
    def test_strikethrough(self):
        result = markdown_to_telegram_html("~~strike~~")
        assert result == "<s>strike</s>"
    
    def test_inline_code(self):
        result = markdown_to_telegram_html("use `code` here")
        assert result == "use <code>code</code> here"
    
    def test_code_block(self):
        result = markdown_to_telegram_html("```python\nprint('hello')\n```")
        assert '<pre><code class="language-python">' in result
        assert "print(&#x27;hello&#x27;)" in result
    
    def test_html_escape(self):
        result = markdown_to_telegram_html("test <script>alert('xss')</script>")
        assert "&lt;script&gt;" in result
        assert "<script>" not in result
    
    def test_mixed_formatting(self):
        result = markdown_to_telegram_html("**bold** and *italic* and `code`")
        assert "<b>bold</b>" in result
        assert "<i>italic</i>" in result
        assert "<code>code</code>" in result


class TestTruncateMessage:
    def test_short_message(self):
        result = truncate_message("short", 40)
        assert result == "short"
    
    def test_exact_length(self):
        result = truncate_message("a" * 40, 40)
        assert result == "a" * 40
    
    def test_long_message(self):
        result = truncate_message("a" * 50, 40)
        assert result == "a" * 40 + "..."
        assert len(result) == 43
