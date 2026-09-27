import hashlib
import io
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from krasnoyarsk_ml.housing import collector
from krasnoyarsk_ml.housing.collector import collect_candidate, save_photo, write_parquet
from krasnoyarsk_ml.housing.export import prepare
from krasnoyarsk_ml.housing.http import DownloadError, RawClient
from krasnoyarsk_ml.housing.sibdom import DISTRICTS, parse_listing
from krasnoyarsk_ml.pipeline import atomic_bytes, write_json


def listing_html():
    # Synthetic HTML fixture matches verified selectors; it is not a product listing.
    fields = {
        "Адрес": "Красноярск, Советский р-н, Тестовая улица, 10",
        "Общая площадь": "50,5 м²",
        "Этаж / всего": "3 / 9",
        "Год постройки": "2001",
    }
    cards = "".join(
        f'<div class="card-info-line"><div class="card-info-name">{k}</div>'
        f'<div class="card-info-content">{v}</div></div>'
        for k, v in fields.items()
    )
    return (
        "<h1>Продается 2-комн. квартира 50.5 м²</h1>"
        '<span class="card-banner-price--full">7 000 000 ₽</span>'
        + cards
        + '<script>selection: "POINT(92.9 56.01)"</script>'
        '<div class="card-gallery-main"><li data-src="https://img0.sibdom.ru/images/photo_1600_1200/stickers/1/123/1.jpeg"></li>'
        '<li data-src="https://img1.sibdom.ru/images/photo_1600_1200/stickers/1/123/1.jpeg"></li>'
        '<li data-src="https://img0.sibdom.ru/images/photo_1600_1200/houses/other.jpeg"></li></div>'
    )


def parse(html):
    return parse_listing(
        html, "https://www.sibdom.ru/stickers/view/123/", datetime.now(UTC), "a" * 64
    )


@pytest.mark.parametrize("verb", ["Продается", "Продаётся", "Продам"])
def test_listing_facts_coordinates_and_own_gallery(verb):
    row = parse(listing_html().replace("Продается", verb))
    assert row.price == 7_000_000
    assert row.area == 50.5
    assert row.price_m2 == pytest.approx(7_000_000 / 50.5)
    assert (row.lat, row.lon) == (56.01, 92.9)
    assert row.district_name == "Советский"
    assert row.building_year == 2001
    assert len(row.image_urls) == 1
    assert row.source_updated_at is None
    assert not row.is_demo


@pytest.mark.parametrize(
    "old,new",
    [
        ("Красноярск,", "Сосновоборск,"),
        ("3 / 9", "3-8 / 9"),
        ("Продается", "Сдается"),
        ("3 / 9", "10 / 9"),
        ("92.9 56.01", "56.01 92.9"),
    ],
)
def test_invalid_and_aggregate_listings_rejected(old, new):
    with pytest.raises(ValueError):
        parse(listing_html().replace(old, new))


def test_downloader_rejects_untrusted_hosts(tmp_path: Path):
    with RawClient(tmp_path) as client, pytest.raises(DownloadError, match="allowlist"):
        client.read("http://127.0.0.1/private")


def test_offline_cache_miss_does_not_call_network(tmp_path: Path):
    with (
        RawClient(tmp_path, offline=True) as client,
        pytest.raises(DownloadError, match="Offline cache missing"),
    ):
        client.read("https://www.sibdom.ru/stickers/view/123/")


def test_redirect_is_cached_and_host_validated(tmp_path):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        if request.url.path == "/first":
            return httpx.Response(302, headers={"location": "/last"})
        return httpx.Response(200, content=b"photo")

    with RawClient(tmp_path, delay=0) as client:
        client.client.close()
        client.client = httpx.Client(transport=httpx.MockTransport(respond))
        client.robots["img0.sibdom.ru"] = []
        assert client.read("https://img0.sibdom.ru/first")[0] == b"photo"
        client.offline = True
        assert client.read("https://img0.sibdom.ru/first")[0] == b"photo"
        assert len(calls) == 2


def test_full_building_is_rejected_before_downloading_photos(tmp_path):
    calls = []

    def read(url):
        calls.append(url)
        return listing_html().encode(), {
            "collected_at": datetime.now(UTC).isoformat(),
            "sha256": "a" * 64,
        }

    row, photos, errors = collect_candidate(
        SimpleNamespace(read=read),
        tmp_path,
        "https://www.sibdom.ru/stickers/view/123/",
        "sovetskijj",
        5,
        {(56.01, 92.9): 3},
        set(),
        3,
    )
    assert row is None and not photos
    assert errors[0]["reason"] == "Per-building diversity cap"
    assert len(calls) == 1


def test_export_validates_all_photo_links_and_detects_corruption(tmp_path):
    buffer = io.BytesIO()
    Image.new("RGB", (200, 300), "blue").save(buffer, format="JPEG")
    content = buffer.getvalue()
    now = datetime.now(UTC)
    client = SimpleNamespace(
        lock=threading.Lock(),
        read=lambda url: (
            content,
            {
                "sha256": hashlib.sha256(content).hexdigest(),
                "collected_at": now.isoformat(),
            },
        ),
    )
    apartments, media = [], []
    for index, name in enumerate(DISTRICTS.values(), 100):
        url = f"https://www.sibdom.ru/stickers/view/{index}/"
        html = listing_html().replace("Советский", name).replace("/123/", f"/{index}/")
        sha = hashlib.sha256(html.encode()).hexdigest()
        raw = tmp_path / "raw/housing/sibdom" / (hashlib.sha256(url.encode()).hexdigest() + ".bin")
        atomic_bytes(raw, html.encode())
        write_json(raw.with_suffix(".json"), {"collected_at": now.isoformat()})
        row = parse_listing(html, url, now, sha).model_dump()
        photo = save_photo(client, tmp_path, row, row["image_urls"][0], 0)
        row.update(cover_storage_key=photo["storage_key"], photo_count=1)
        apartments.append(row)
        media.append(photo)
    processed = tmp_path / "processed/housing"
    write_parquet(processed / "apartments.parquet", apartments)
    write_parquet(processed / "media.parquet", media)
    write_json(processed / "collection_report.json", {"status": "complete"})
    result = prepare(tmp_path, tmp_path / "bundle.zip", expected=7)
    assert result["apartments"] == 7 and result["photos"] == 7
    assert len(result["district_counts"]) == 7
    (tmp_path / media[0]["local_path"]).write_bytes(b"broken")
    with pytest.raises(ValueError, match="checksum"):
        prepare(tmp_path, tmp_path / "bundle.zip", expected=7)


def test_resume_can_fill_district_shortage_without_duplicate_rows(tmp_path, monkeypatch):
    pages = {}
    districts = {}
    image = io.BytesIO()
    Image.new("RGB", (200, 200), "blue").save(image, format="JPEG")
    now = datetime.now(UTC).isoformat()
    for index, (slug, name) in enumerate(DISTRICTS.items()):
        url = f"https://www.sibdom.ru/kvartiry/{slug}/"
        districts[slug] = url
        links = []
        for offset in range(3 if index == 0 else 1 if index == 1 else 2):
            identifier = 1000 + index * 10 + offset
            listing = f"https://www.sibdom.ru/stickers/view/{identifier}/"
            links.append(f'<a href="{listing}">Apartment</a>')
            pages[listing] = (
                listing_html()
                .replace("Советский", name)
                .replace("/123/", f"/{identifier}/")
                .replace("92.9 56.01", f"92.9 {56 + identifier / 10000}")
            ).encode()
        pages[url] = "".join(links).encode()
    # A cross-district recommendation must not suppress the actual listing later.
    first = districts[next(iter(DISTRICTS))]
    pages[first] = b'<a href="https://www.sibdom.ru/stickers/view/1010/">Related</a>' + pages[first]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.lock = threading.Lock()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def check_robots(self, url):
            pass

        def read(self, url):
            body = image.getvalue() if "img0.sibdom.ru" in url else pages.get(url, b"")
            return body, {"sha256": hashlib.sha256(body).hexdigest(), "collected_at": now}

    monkeypatch.setattr(collector, "RawClient", FakeClient)
    monkeypatch.setattr(collector, "district_links", lambda html: districts)
    monkeypatch.setattr(collector, "secondary_url", lambda html: None)
    strict = collector.run(tmp_path, 14, 1, 1, True, 0, 3)
    assert strict["status"] == "partial" and strict["records_valid"] == 13
    filled = collector.run(tmp_path, 14, 1, 1, True, 0, 3, allow_uneven=True)
    assert filled["status"] == "complete"
    assert filled["records_valid"] == filled["photos_valid"] == 14
    assert len(filled["district_counts"]) == 7
    assert filled["district_counts"]["Октябрьский"] == 3
