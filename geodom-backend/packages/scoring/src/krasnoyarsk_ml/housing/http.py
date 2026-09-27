"""Bounded, resumable public downloads with raw provenance and per-host pacing."""

import hashlib
import json
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from ..pipeline import atomic_bytes, write_json

AGENT = "KrasnoyarskHousingResearch/0.1"


class DownloadError(RuntimeError):
    pass


class RawClient:
    def __init__(self, root: Path, delay: float = 1.0, offline: bool = False):
        self.root, self.delay, self.offline = root, delay, offline
        self.client = httpx.Client(
            timeout=45, headers={"User-Agent": AGENT}, follow_redirects=False
        )
        self.lock = threading.Lock()
        self.next_request: dict[str, float] = {}
        self.robots: dict[str, list[str]] = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    def allowed_host(self, url: str) -> str:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or not (
            host == "www.sibdom.ru" or re.fullmatch(r"img\d+\.sibdom\.ru", host)
        ):
            raise DownloadError("Download URL outside the source allowlist")
        return host

    def paced(self, host: str) -> None:
        with self.lock:
            now = time.monotonic()
            scheduled = max(now, self.next_request.get(host, now))
            self.next_request[host] = scheduled + self.delay
        time.sleep(max(0, scheduled - now))

    def read(
        self, url: str, max_bytes: int = 10_000_000, check_robots: bool = True, redirects: int = 0
    ) -> tuple[bytes, dict]:
        if redirects > 4:
            raise DownloadError("Too many redirects")
        host = self.allowed_host(url)
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.root / f"{key}.bin"
        meta_path = self.root / f"{key}.json"
        if path.exists() and meta_path.exists():
            content = path.read_bytes()
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if hashlib.sha256(content).hexdigest() == meta["sha256"]:
                if meta["status"] in {301, 302, 303, 307, 308} and meta.get("location"):
                    return self.read(
                        urljoin(url, meta["location"]), max_bytes, check_robots, redirects + 1
                    )
                if meta["status"] == 200:
                    return content, meta
                if meta["status"] not in {301, 302, 303, 307, 308}:
                    raise DownloadError(f"Cached HTTP {meta['status']}: {url}")
        if self.offline:
            raise DownloadError(f"Offline cache missing: {url}")
        if check_robots:
            self.check_robots(url)
        for attempt in range(3):
            self.paced(host)
            try:
                with self.client.stream("GET", url) as response:
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise DownloadError(f"Response exceeds {max_bytes} bytes")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    status = response.status_code
                    meta = {
                        "url": url,
                        "status": status,
                        "collected_at": datetime.now(UTC).isoformat(),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "content_type": response.headers.get("content-type"),
                        "etag": response.headers.get("etag"),
                        "location": response.headers.get("location"),
                        "bytes": len(content),
                    }
                    if status in {429, 500, 502, 503, 504}:
                        # Preserve errors, but do not make them the permanent successful cache.
                        failure = self.root / "errors" / f"{key}-{time.time_ns()}"
                        atomic_bytes(failure.with_suffix(".bin"), content)
                        write_json(failure.with_suffix(".json"), meta)
                        if attempt < 2:
                            time.sleep(10 * (attempt + 1))
                            continue
                    atomic_bytes(path, content)
                    write_json(meta_path, meta)
                    if status in {301, 302, 303, 307, 308} and meta["location"]:
                        return self.read(
                            urljoin(url, meta["location"]), max_bytes, check_robots, redirects + 1
                        )
                    if status != 200:
                        raise DownloadError(f"HTTP {status}: {url}")
                    return content, meta
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise DownloadError(f"Network failed: {url}: {type(exc).__name__}") from exc
                time.sleep(3 * (attempt + 1))
        raise DownloadError(f"Retry exhausted: {url}")

    def check_robots(self, url: str) -> None:
        host = self.allowed_host(url)
        if host not in self.robots:
            robots_url = f"https://{host}/robots.txt"
            try:
                body, _ = self.read(robots_url, check_robots=False)
            except DownloadError as exc:
                if "HTTP 404" in str(exc):
                    self.robots[host] = []
                else:
                    raise
            else:
                rules, active = [], False
                for line in body.decode("utf-8", errors="replace").splitlines():
                    key, _, value = line.partition(":")
                    if key.lower().strip() == "user-agent":
                        active = value.strip() == "*"
                    elif active and key.lower().strip() == "disallow" and value.strip():
                        rules.append(value.strip())
                self.robots[host] = rules
        parsed = urlsplit(url)
        target = parsed.path + ("?" + parsed.query if parsed.query else "")
        for rule in self.robots[host]:
            pattern = re.escape(rule).replace(r"\*", ".*").replace(r"\$", "$")
            if re.match(pattern, target):
                raise DownloadError(f"robots.txt disallows {url}")
