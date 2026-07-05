import pytest
from fastapi import HTTPException

from app.url_safety import validate_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/image.jpg",
        "http://localhost/image.jpg",
        "file:///etc/passwd",
        "http://10.0.0.4/private.png",
    ],
)
def test_rejects_non_public_urls(url: str) -> None:
    with pytest.raises(HTTPException):
        validate_public_http_url(url)
