"""擷取器測試共用 fixtures。"""

import pytest
import respx
import httpx


@pytest.fixture
def mock_http():
    """提供 respx mock 實例，用於模擬 HTTP 請求。"""
    with respx.mock(assert_all_called=False) as router:
        yield router


def mock_response(html: str, status_code: int = 200) -> httpx.Response:
    """建立模擬的 HTTP 回應。"""
    return httpx.Response(status_code, text=html)
