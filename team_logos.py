"""BestBets 6.1 — team graphics with reliable local fallback.

The package contains 30 locally rendered *identification badges*, not official
NBA team marks. Real marks are fetched only from public NBA/ESPN image CDNs,
validated as raster images, cached on the user's machine and then embedded as
local data URIs. When neither remote source responds, a badge is always shown.
Network downloads run in a background daemon; the UI never waits for them.
"""
from __future__ import annotations

from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import threading
import time

from PIL import Image, UnidentifiedImageError
import requests

from simulation_engine import TEAM_IDS

ROOT = Path(__file__).resolve().parent
BADGES = ROOT / 'assets' / 'team_badges'
OFFICIAL = ROOT / 'assets' / 'team_logos'
OFFICIAL.mkdir(parents=True, exist_ok=True)
TEAM_CODES = tuple(sorted(TEAM_IDS))
ESPN_ABBR = {'UTA': 'utah', 'NYK': 'ny', 'GSW': 'gs', 'NOP': 'no', 'SAS': 'sa', 'PHX': 'phx', 'LAC': 'lac', 'BKN': 'bkn'}
_REFRESH_SECONDS = 21 * 86400
_THREAD_LOCK = threading.Lock()
_LAST_TRY = 0.0
_THREAD = None


def logo_candidates(code: str):
    """ESPN first, NBA CDN second; no unofficial mirror or bypass of 403."""
    code = str(code).upper()
    if code not in TEAM_IDS:
        return []
    # ESPN supports the standard team abbreviation; some teams also use aliases.
    espn_names = [code.lower()]
    alias = ESPN_ABBR.get(code)
    if alias and alias not in espn_names:
        espn_names.append(alias)
    urls = [f'https://a.espncdn.com/i/teamlogos/nba/500/{name}.png' for name in espn_names]
    urls.append(f'https://cdn.nba.com/logos/nba/{TEAM_IDS[code]}/primary/L/logo.png')
    return urls


def _validate_raster(payload: bytes) -> bytes | None:
    """Only small valid raster images; never embed fetched HTML or remote SVG."""
    if not (100 <= len(payload) <= 2_000_000):
        return None
    try:
        with Image.open(BytesIO(payload)) as im:
            im.verify()
        with Image.open(BytesIO(payload)) as im:
            if im.format not in ('PNG', 'WEBP', 'JPEG'):
                return None
            if im.width < 32 or im.height < 32 or im.width * im.height > 8_000_000:
                return None
            im.thumbnail((240, 240))
            out = BytesIO()
            im.convert('RGBA').save(out, format='PNG', optimize=True)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        return None


def fetch_one_logo(code: str, *, http_get=None, now: float | None = None) -> bool:
    """Download and cache an official logo; never overwrite a good file with bad data."""
    code = str(code).upper()
    if code not in TEAM_IDS:
        return False
    path = OFFICIAL / f'{code}.png'
    now = time.time() if now is None else now
    if path.is_file() and path.stat().st_size > 100 and now - path.stat().st_mtime < _REFRESH_SECONDS:
        return True
    get = http_get or requests.get
    for url in logo_candidates(code):
        try:
            response = get(url, timeout=(2.2, 4.0), headers={
                'User-Agent': 'BestBets/6.1 (team-logo cache)', 'Accept': 'image/png,image/webp,image/jpeg'
            })
            if response.status_code != 200:
                continue
            body = _validate_raster(response.content)
            if body is None:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f'{code}.{threading.get_ident()}.tmp')
            tmp.write_bytes(body)
            tmp.replace(path)
            return True
        except (requests.RequestException, OSError, ValueError):
            continue
    return path.is_file() and path.stat().st_size > 100


def _download_batch(codes: tuple[str, ...]):
    # A bounded pool avoids 30 sequential network timeouts on slow connections.
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix='bb-logo') as pool:
        list(pool.map(fetch_one_logo, codes))


def refresh_logos_in_background(codes=None) -> bool:
    """Start a nonblocking, at-most-once-per-day background refresh.

    Returns True if a refresh was scheduled; any unresolved logo is rendered
    immediately using its bundled local badge.
    """
    global _LAST_TRY, _THREAD
    raw = TEAM_CODES if codes is None else codes
    codes = tuple(sorted(set(str(c).upper() for c in raw if str(c).upper() in TEAM_IDS)))
    if not codes:
        return False
    current = time.monotonic()
    with _THREAD_LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return False
        if current - _LAST_TRY < 20 * 3600:
            return False
        pending = tuple(c for c in codes if not (OFFICIAL / f'{c}.png').is_file() or
                        time.time() - (OFFICIAL / f'{c}.png').stat().st_mtime > _REFRESH_SECONDS)
        if not pending:
            _LAST_TRY = current
            return False
        _LAST_TRY = current
        _THREAD = threading.Thread(target=_download_batch, args=(pending,), daemon=True, name='bb-logo-refresh')
        _THREAD.start()
    return True


def logo_file(code: str) -> Path:
    """Always return a local path (official downloaded PNG or built-in badge PNG)."""
    code = str(code).upper()
    if code not in TEAM_IDS:
        return BADGES / 'NBA.png'
    official = OFFICIAL / f'{code}.png'
    if official.is_file() and official.stat().st_size > 100:
        return official
    return BADGES / f'{code}.png'


def logo_data_uri(code: str) -> str:
    """Use local, self-contained data URI so NBA CDN cannot break card images."""
    path = logo_file(code)
    if not path.is_file():
        return ''
    return 'data:image/png;base64,' + b64encode(path.read_bytes()).decode('ascii')


def cached_official_count() -> int:
    return sum(1 for c in TEAM_CODES if (OFFICIAL / f'{c}.png').is_file())
