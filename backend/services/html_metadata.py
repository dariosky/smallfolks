import re
from html import escape
from typing import TypedDict

from fastapi import Request

import settings

DEFAULT_IMAGE = "/web-app-manifest-512x512.png"


class PageMetadata(TypedDict):
    status: int
    title: str
    description: str
    image: str
    image_alt: str
    url: str
    type: str


def build_metadata(request: Request) -> PageMetadata:
    return default_metadata(request)


def default_metadata(request: Request, status: int = 200) -> PageMetadata:
    return PageMetadata(
        status=status,
        title=settings.SITE_NAME,
        description="A calm, inspectable city-life simulation.",
        image=absolute_url(DEFAULT_IMAGE),
        image_alt=settings.SITE_NAME,
        url=canonical_url(request),
        type="website",
    )


def build_meta_html(metadata: PageMetadata) -> str:
    title = _escape(metadata["title"])
    description = _escape(metadata["description"])
    image = _escape(metadata["image"])
    image_alt = _escape(metadata["image_alt"])
    url = _escape(metadata["url"])
    page_type = _escape(metadata["type"])
    site_name = _escape(settings.SITE_NAME)
    robots = "index,follow" if metadata["status"] == 200 else "noindex,follow"
    return "\n".join(
        [
            f"<title>{title}</title>",
            f'<meta name="description" content="{description}" />',
            f'<link rel="canonical" href="{url}" />',
            f'<meta name="robots" content="{robots}" />',
            f'<meta property="og:type" content="{page_type}" />',
            f'<meta property="og:url" content="{url}" />',
            f'<meta property="og:title" content="{title}" />',
            f'<meta property="og:description" content="{description}" />',
            f'<meta property="og:image" content="{image}" />',
            f'<meta property="og:image:alt" content="{image_alt}" />',
            f'<meta property="og:site_name" content="{site_name}" />',
            '<meta name="twitter:card" content="summary_large_image" />',
            f'<meta name="twitter:title" content="{title}" />',
            f'<meta name="twitter:description" content="{description}" />',
            f'<meta name="twitter:image" content="{image}" />',
            f'<meta name="twitter:image:alt" content="{image_alt}" />',
        ]
    )


def inject_meta_html(html: str, meta_html: str) -> str:
    # Replace the frontend fallback title with the server's page metadata.
    html = re.sub(r"<title\b[^>]*>.*?</title>", "", html, flags=re.IGNORECASE | re.DOTALL)
    if "<!--APP_META-->" in html:
        return html.replace("<!--APP_META-->", meta_html, 1)
    if "</head>" in html:
        return html.replace("</head>", f"{meta_html}\n  </head>", 1)
    return html


def canonical_url(request: Request) -> str:
    base_url = settings.BASE_URL.rstrip("/")
    path = request.url.path or "/"
    return f"{base_url}{path}"


def absolute_url(value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value
    return f"{settings.BASE_URL.rstrip('/')}/{value.lstrip('/')}"


def _escape(value: str) -> str:
    return escape(str(value), quote=True)
