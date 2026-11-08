"""Incomplete metadata or downloads must not produce a partial PDF."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from astrbot_plugin_parser.core.exception import ParseException
from astrbot_plugin_parser.core.parsers.pixiv import PixivHelper, PixivParser


def test_page_order_is_preserved():
    pages = [
        {"urls": {"original": f"https://images.example.invalid/{n}.jpg"}}
        for n in range(3)
    ]
    assert PixivParser._page_image_urls(pages, 3) == [
        f"https://images.example.invalid/{n}.jpg" for n in range(3)
    ]


@pytest.mark.parametrize("pages,count", [
    ([], 0), ([], 1),
    ([{"urls": {"original": "https://images.example.invalid/1.jpg"}}], 2),
    ([{"urls": {}}], 1), ([{"urls": {"original": None}}], 1),
    ([None], 1), ({"error": "synthetic"}, 1),
])
def test_incomplete_page_metadata_is_rejected(pages, count):
    with pytest.raises(ParseException):
        PixivParser._page_image_urls(pages, count)


def test_failed_page_preserves_previous_pdf(tmp_path):
    existing = tmp_path / "pixiv_123.pdf"
    existing.write_bytes(b"previous complete document")
    parser = PixivParser.__new__(PixivParser)
    parser.cfg = SimpleNamespace(cache_dir=tmp_path)

    async def run():
        async def downloaded():
            return [tmp_path / "page1.jpg", tmp_path / "page3.jpg"]
        with pytest.raises(ParseException):
            await parser._build_pdf(asyncio.create_task(downloaded()), "123", 3)

    with patch.object(PixivHelper, "imgs_to_pdf") as convert:
        asyncio.run(run())
    convert.assert_not_called()
    assert existing.read_bytes() == b"previous complete document"


def test_complete_pages_are_forwarded_in_order(tmp_path):
    paths = [tmp_path / "page1.jpg", tmp_path / "page2.jpg"]
    parser = PixivParser.__new__(PixivParser)
    parser.cfg = SimpleNamespace(cache_dir=tmp_path)

    async def run():
        async def downloaded():
            return paths
        return await parser._build_pdf(asyncio.create_task(downloaded()), "123", 2)

    with patch.object(PixivHelper, "imgs_to_pdf") as convert:
        output = asyncio.run(run())
    assert output == tmp_path / "pixiv_123.pdf"
    convert.assert_called_once_with(paths, output)
