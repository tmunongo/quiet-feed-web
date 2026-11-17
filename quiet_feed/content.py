import html
import re
from html.parser import HTMLParser
from xml.etree.ElementTree import Element, SubElement, tostring

import nh3
from defusedxml.ElementTree import fromstring
from markupsafe import Markup

TAGS = set(
    "p br b i em strong a ul ol li blockquote h1 h2 h3 h4 img figure figcaption pre code hr table thead tbody tr th td".split()
)


def sanitize_html(value):
    if not value:
        return None
    return nh3.clean(
        value,
        tags=TAGS,
        attributes={
            "a": {"href", "title", "target"},
            "img": {"src", "alt", "title", "width", "height", "loading"},
        },
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
        set_tag_attribute_values={"a": {"target": "_blank"}},
    )


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value):
    parser = TextExtractor()
    parser.feed(sanitize_html(value or "") or "")
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def render_dispatch(value):
    """Render the original dispatch Markdown subset; only internal article links."""

    def inline(text):
        text = html.escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

        def link(match):
            title, href = match.groups()
            if re.fullmatch(r"/article/[a-zA-Z0-9_-]+", href):
                return f'<a href="{href}">{title}</a>'
            return title

        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)

    output, paragraph, list_type = [], [], None

    def flush():
        if paragraph:
            output.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_list():
        nonlocal list_type
        if list_type:
            output.append(f"</{list_type}>")
            list_type = None

    for line in (value or "").splitlines():
        line = line.strip()
        if not line:
            flush()
            close_list()
            continue
        heading = re.match(r"(?:\d+\.\s+)?(#{1,4})\s+(.+)", line)
        item = re.match(r"([-*]|\d+\.)\s+(.+)", line)
        if heading:
            flush()
            close_list()
            level = len(heading[1])
            output.append(f"<h{level}>{inline(heading[2])}</h{level}>")
        elif re.fullmatch(r"(?:-{3,}|\*{3,}|_{3,})", line):
            flush()
            close_list()
            output.append("<hr>")
        elif item:
            flush()
            kind = "ul" if item[1] in {"-", "*"} else "ol"
            if kind != list_type:
                close_list()
                output.append(f"<{kind}>")
                list_type = kind
            output.append(f"<li>{inline(item[2])}</li>")
        elif line.startswith(">"):
            flush()
            close_list()
            output.append(f"<blockquote>{inline(line[1:].strip())}</blockquote>")
        else:
            close_list()
            paragraph.append(line)
    flush()
    close_list()
    return Markup("\n".join(output))


def parse_opml(value):
    root = fromstring(value)
    body = root.find("body")
    if root.tag != "opml" or body is None:
        raise ValueError("Couldn't read that file as OPML.")
    result = []

    def walk(outline, category):
        if url := outline.get("xmlUrl"):
            result.append(
                {
                    "url": url,
                    "title": outline.get("title") or outline.get("text") or url,
                    "category": category,
                }
            )
        else:
            category = outline.get("title") or outline.get("text") or category
            for child in outline.findall("outline"):
                walk(child, category)

    for outline in body.findall("outline"):
        walk(outline, "General")
    return result


def build_opml(feeds):
    root = Element("opml", version="2.0")
    SubElement(SubElement(root, "head"), "title").text = "Quiet Feed subscriptions"
    body = SubElement(root, "body")
    groups = {}
    for feed in feeds:
        if feed.category not in groups:
            groups[feed.category] = SubElement(
                body, "outline", text=feed.category, title=feed.category
            )
        SubElement(
            groups[feed.category],
            "outline",
            type="rss",
            text=feed.title,
            title=feed.title,
            xmlUrl=feed.url,
        )
    return tostring(root, encoding="utf-8", xml_declaration=True)
