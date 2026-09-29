from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring  # nosec B405

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

import settings
from services.html_metadata import build_meta_html, build_metadata, inject_meta_html

router = APIRouter(include_in_schema=False)
HTML_CACHE_CONTROL = "no-cache"
PUBLIC_ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
TEXT_CACHE_CONTROL = "public, max-age=3600"


def get_index_path() -> Path:
    index_path = settings.DIST_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="Frontend build is missing. Run `cd frontend && npm run build`.",
        )
    return index_path


def get_index_html() -> str:
    return get_index_path().read_text(encoding="utf-8")


def get_public_asset_path(full_path: str) -> Path | None:
    if not full_path or full_path == "index.html":
        return None
    dist_dir = settings.DIST_DIR.resolve()
    asset_path = (dist_dir / full_path).resolve()
    if dist_dir not in asset_path.parents or not asset_path.is_file():
        return None
    return asset_path


def html_response(request: Request, method: str = "GET") -> Response:
    metadata = build_metadata(request)
    headers = {"Cache-Control": HTML_CACHE_CONTROL}
    if metadata["status"] != 200:
        headers["X-Robots-Tag"] = "noindex"
    if method == "HEAD":
        return Response(
            status_code=metadata["status"],
            headers=headers,
            media_type="text/html",
        )
    html = inject_meta_html(get_index_html(), build_meta_html(metadata))
    return HTMLResponse(html, status_code=metadata["status"], headers=headers)


def _absolute_url(path: str) -> str:
    return f"{settings.BASE_URL.rstrip('/')}/{path.lstrip('/')}"


@router.get("/")
def index(request: Request) -> Response:
    return html_response(request)


@router.head("/")
def index_head(request: Request) -> Response:
    return html_response(request, method="HEAD")


@router.get("/robots.txt")
def robots_txt() -> Response:
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api",
            "Disallow: /app/",
            "Disallow: /app$",
            f"Sitemap: {_absolute_url('/sitemap.xml')}",
            "",
        ]
    )
    return Response(
        content,
        headers={"Cache-Control": TEXT_CACHE_CONTROL},
        media_type="text/plain; charset=utf-8",
    )


@router.get("/sitemap.xml")
def sitemap_xml() -> Response:
    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for url in [_absolute_url("/")]:
        url_element = SubElement(urlset, "url")
        loc = SubElement(url_element, "loc")
        loc.text = url
    xml = tostring(urlset, encoding="utf-8", xml_declaration=True)
    return Response(
        xml,
        headers={"Cache-Control": TEXT_CACHE_CONTROL},
        media_type="application/xml",
    )


@router.get("/{full_path:path}")
def spa_fallback(request: Request, full_path: str) -> Response:
    if full_path.startswith(settings.API_PREFIX.strip("/")):
        raise HTTPException(status_code=404, detail="Not found")
    asset_path = get_public_asset_path(full_path)
    if asset_path is not None:
        return FileResponse(
            asset_path,
            headers={"Cache-Control": PUBLIC_ASSET_CACHE_CONTROL},
        )
    return html_response(request)


@router.head("/{full_path:path}")
def spa_fallback_head(request: Request, full_path: str) -> Response:
    if full_path.startswith(settings.API_PREFIX.strip("/")):
        raise HTTPException(status_code=404, detail="Not found")
    if get_public_asset_path(full_path) is not None:
        return Response(
            status_code=200,
            headers={"Cache-Control": PUBLIC_ASSET_CACHE_CONTROL},
        )
    return html_response(request, method="HEAD")
