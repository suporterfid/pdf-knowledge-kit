from __future__ import annotations

from bs4 import BeautifulSoup

BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "td",
    "th",
    "ul",
}


def extract_html_text(html: str) -> str:
    """Convert HTML into readable text with minimal noise."""

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()

    lines = []
    for element in soup.stripped_strings:
        parent = getattr(element, "parent", None)
        if parent and parent.name and parent.name.lower() in BLOCK_TAGS:
            lines.append(element.strip())
        else:
            if lines:
                lines[-1] = f"{lines[-1]} {element.strip()}".strip()
            else:
                lines.append(element.strip())
    return "\n".join(lines)
