"""Parser for observed public Sibdom HTML (not undocumented APIs)."""

import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

BASE = "https://www.sibdom.ru"
START = BASE + "/kvartiry/prodam_krasnoyarsk_svezhiye/"
PARSER_VERSION = 2
DISTRICTS = {
    "oktyabrskijj": "Октябрьский",
    "sovetskijj": "Советский",
    "sverdlovskijj": "Свердловский",
    "kirovskijj": "Кировский",
    "centralnyjj": "Центральный",
    "zheleznodorozhnyjj": "Железнодорожный",
    "leninskijj": "Ленинский",
}


class Apartment(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str
    external_id: str
    title: str
    price: int = Field(gt=0)
    price_m2: float = Field(gt=0)
    currency: str = "RUB"
    area: float = Field(gt=0, le=1000)
    rooms: int = Field(ge=0, le=20)
    floor: int = Field(ge=1)
    floors_total: int = Field(ge=1)
    building_year: int | None = None
    address: str
    lat: float = Field(ge=55.8, le=56.3)
    lon: float = Field(ge=92.4, le=93.4)
    coordinate_method: str = "listing_map_point"
    district_name: str
    district_source_id: str
    district_assignment_method: str = "listing_address_tag_not_spatial_join"
    complex_source_id: str | None = None
    complex_name: str | None = None
    complex_source_url: str | None = None
    market_type: str
    offer_type: str = "sale"
    source: str = "sibdom"
    source_id: str
    source_url: str
    source_updated_at: AwareDatetime | None = None
    collected_at: AwareDatetime
    raw_sha256: str
    is_demo: bool = False
    image_urls: list[str]

    @model_validator(mode="after")
    def check_floor_and_price(self):
        if self.floor > self.floors_total:
            raise ValueError("Floor exceeds building floors")
        if not 10_000 <= self.price_m2 <= 2_000_000:
            raise ValueError("Suspicious price/m2; requires review")
        return self


def clean(text: str) -> str:
    return re.sub(r"\s+([,.;])", r"\1", " ".join(text.split()))


def district_links(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for a in soup.select('a[data-mobile-group="district"][href]'):
        for slug in DISTRICTS:
            if f"_{slug}-r-n" in a["href"]:
                result[slug] = urljoin(BASE, a["href"])
    if set(result) != set(DISTRICTS):
        raise ValueError("District filters missing or source structure changed")
    return result


def secondary_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        if a.get_text(" ", strip=True).startswith("Вторичка") and "vtorichka" in a["href"]:
            return urljoin(BASE, a["href"])
    return None


def listing_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return list(
        dict.fromkeys(
            urljoin(BASE, a["href"])
            for a in soup.find_all("a", href=True)
            if re.fullmatch(r"(?:https://www\.sibdom\.ru)?/stickers/view/\d+/", a["href"])
        )
    )


def page_count(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    pagination = soup.select_one(".page-pagination[data-total_pages]")
    return max(1, int(pagination["data-total_pages"])) if pagination else 1


def parse_listing(html: str, url: str, collected_at: datetime, raw_sha256: str) -> Apartment:
    soup = BeautifulSoup(html, "html.parser")
    title = clean(soup.h1.get_text(" ")) if soup.h1 else ""
    if not title.lower().startswith(("продается", "продаётся", "продам")) or not any(
        word in title.lower() for word in ("квартира", "студия")
    ):
        raise ValueError("Not an individual apartment sale")
    identifier = re.fullmatch(r"/stickers/view/(\d+)/", urlsplit(url).path)
    if not identifier:
        raise ValueError("Unexpected listing URL")
    source_id = identifier[1]
    fields = {}
    for line in soup.select(".card-info-line"):
        key, value = line.select_one(".card-info-name"), line.select_one(".card-info-content")
        if key and value:
            fields[clean(key.get_text(" "))] = clean(value.get_text(" "))
    address = fields.get("Адрес", "")
    if not address.startswith("Красноярск,"):
        raise ValueError("Listing is outside Krasnoyarsk")
    district = next(((s, n) for s, n in DISTRICTS.items() if f"{n} р-н" in address), None)
    if not district:
        raise ValueError("District missing from actual listing address")
    rooms_match = re.search(r"(\d+)-комн", title)
    rooms = int(rooms_match[1]) if rooms_match else (0 if "студи" in title.lower() else None)
    if rooms is None:
        raise ValueError("Room count missing")
    floor_match = re.fullmatch(r"(\d+)\s*/\s*(\d+)", fields.get("Этаж / всего", ""))
    if not floor_match:
        raise ValueError("Missing floor or aggregate offer with a floor range")
    area_match = re.search(r"\d+(?:[.,]\d+)?", fields.get("Общая площадь", ""))
    price_element = soup.select_one(".card-banner-price--full")
    if not area_match or not price_element:
        raise ValueError("Area or full price missing")
    area = float(area_match[0].replace(",", "."))
    if area <= 0:
        raise ValueError("Area must be positive")
    price_text = price_element.get_text(" ", strip=True)
    if "млн" in price_text or "тыс" in price_text:
        raise ValueError("Expected full integer price, not abbreviated value")
    price = int(re.sub(r"\D", "", price_text))
    # Use WKT selection, not background-map parameters (their order differs on this source).
    coords = re.search(r"selection:\s*['\"]POINT\(([\d.]+)\s+([\d.]+)\)['\"]", html)
    if not coords:
        raise ValueError("No listing map coordinates")
    image_urls = []
    for node in soup.select(".card-gallery-main li[data-src]"):
        image_url = node["data-src"]
        parts = urlsplit(image_url)
        if (
            parts.scheme == "https"
            and re.fullmatch(r"img\d+\.sibdom\.ru", parts.hostname or "")
            and re.search(rf"/stickers/\d+/{source_id}/[^/]+$", parts.path)
            and parts.path not in {urlsplit(u).path for u in image_urls}
        ):
            # Exclude house/complex galleries, agents, and duplicates of the same source photo.
            image_urls.append(image_url)
    if not image_urls:
        raise ValueError("No photographs belonging to this listing gallery")
    complex_a = soup.select_one('h1 a[href*="/novostroyki/krasnoyarsk/"]')
    complex_url = urljoin(BASE, complex_a["href"]) if complex_a else None
    complex_id = re.search(r"/krasnoyarsk/(\d+)-", complex_url or "")
    year = re.search(r"\b(19\d{2}|20\d{2})\b", fields.get("Год постройки", ""))
    return Apartment(
        id=f"sibdom:{source_id}",
        external_id=source_id,
        title=title,
        price=price,
        price_m2=price / area,
        area=area,
        rooms=rooms,
        floor=int(floor_match[1]),
        floors_total=int(floor_match[2]),
        building_year=int(year[1]) if year else None,
        address=address,
        lat=float(coords[2]),
        lon=float(coords[1]),
        district_name=district[1],
        district_source_id=district[0],
        complex_source_id=complex_id[1] if complex_id else None,
        complex_name=clean(complex_a.get_text(" ")) if complex_a else None,
        complex_source_url=complex_url,
        # A completion date on a linked complex does not prove primary sale.
        market_type="unspecified",
        source_id=source_id,
        source_url=url,
        collected_at=collected_at,
        raw_sha256=raw_sha256,
        image_urls=image_urls,
    )
