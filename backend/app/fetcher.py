from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from .config import Settings, get_settings
from .url_safety import validate_public_http_url


@dataclass
class FetchedImage:
    image_bytes: bytes
    content_type: str
    context: dict


async def fetch_public_image(url: str, settings: Settings | None = None) -> FetchedImage:
    settings = settings or get_settings()
    validated_url = validate_public_http_url(url)
    page_response = await _guarded_get(validated_url, settings)
    content_type = _content_type(page_response)

    if content_type in settings.allowed_image_types:
        return FetchedImage(
            image_bytes=page_response.content,
            content_type=content_type,
            context=_base_context(url, str(page_response.url), content_type),
        )

    if "text/html" not in content_type:
        raise HTTPException(status_code=415, detail="Public URL must point to an image or an HTML page with a public image.")

    soup = BeautifulSoup(page_response.text, "html.parser")
    image_url = _extract_page_image_url(soup, str(page_response.url))
    if not image_url:
        raise HTTPException(status_code=422, detail="No public image metadata was found on that page.")

    image_response = await _guarded_get(image_url, settings)
    image_type = _content_type(image_response)
    if image_type not in settings.allowed_image_types:
        raise HTTPException(status_code=415, detail="The page image is not a supported image type.")

    context = _base_context(url, str(image_response.url), image_type)
    context.update(
        {
            "page_url": str(page_response.url),
            "page_title": _text_or_none(soup.title.string if soup.title else None),
            "site_name": _meta_content(soup, "property", "og:site_name"),
            "public_actor": _public_actor(soup),
            "fetched_image_url": str(image_response.url),
        }
    )
    return FetchedImage(image_bytes=image_response.content, content_type=image_type, context=context)


async def _guarded_get(url: str, settings: Settings, redirect_count: int = 0) -> httpx.Response:
    if redirect_count > 4:
        raise HTTPException(status_code=400, detail="Too many redirects while fetching the public URL.")

    validated_url = validate_public_http_url(url)
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        follow_redirects=False,
        headers={"User-Agent": "AI-Deepfake-Analyzer/0.1 (+privacy-preserving research tool)"},
    ) as client:
        response = await client.get(validated_url)

    if response.status_code in {301, 302, 303, 307, 308}:
        location = response.headers.get("location")
        if not location:
            raise HTTPException(status_code=400, detail="Redirect response did not include a location.")
        return await _guarded_get(urljoin(str(response.url), location), settings, redirect_count + 1)

    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Public URL returned HTTP {response.status_code}.")

    length_header = response.headers.get("content-length")
    if length_header and int(length_header) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Remote image is larger than the configured limit.")
    if len(response.content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Remote response is larger than the configured limit.")

    return response


def _content_type(response: httpx.Response) -> str:
    return response.headers.get("content-type", "").split(";")[0].strip().lower()


def _base_context(submitted_url: str, final_url: str, content_type: str) -> dict:
    parsed = urlparse(final_url)
    return {
        "submitted_url": submitted_url,
        "final_url": final_url,
        "domain": parsed.netloc,
        "content_type": content_type,
        "attribution_boundary": "Public page metadata only; no private identity inference or face search was performed.",
    }


def _extract_page_image_url(soup: BeautifulSoup, base_url: str) -> str | None:
    candidates = [
        _meta_content(soup, "property", "og:image"),
        _meta_content(soup, "name", "twitter:image"),
        _meta_content(soup, "property", "og:image:secure_url"),
    ]
    first_img = soup.find("img")
    if first_img and first_img.get("src"):
        candidates.append(first_img.get("src"))

    for candidate in candidates:
        if candidate:
            return urljoin(base_url, candidate)
    return None


def _meta_content(soup: BeautifulSoup, attr: str, value: str) -> str | None:
    tag = soup.find("meta", attrs={attr: value})
    if not tag:
        return None
    return _text_or_none(tag.get("content"))


def _public_actor(soup: BeautifulSoup) -> str | None:
    candidates = [
        _meta_content(soup, "name", "author"),
        _meta_content(soup, "property", "article:author"),
        _meta_content(soup, "name", "twitter:creator"),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _text_or_none(value: str | None) -> str | None:
    if not value:
        return None
    normalized = " ".join(value.split())
    return normalized[:300] if normalized else None
