"""Real Divar collector for Bojnurd apartment-sale listings.

Uses the public endpoints used by Divar's own web client. No API key and no login
are required. The request rate is intentionally conservative because this is a
personal localhost dashboard, not a bulk/public scraping service.
"""
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

from config import Config
from money import extract_sell_prices, parse_number, normalize_digits
from neighborhoods import canonical_district, clean_text

CITIES_URL = 'https://api.divar.ir/v8/places/cities'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://divar.ir',
    'Referer': 'https://divar.ir/',
}


def current_jalali_year():
    # Accurate enough for building-age buckets around Nowruz without extra deps.
    now = datetime.now()
    return now.year - (621 if (now.month, now.day) >= (3, 21) else 622)


class RateLimiter:
    def __init__(self, budget=Config.DETAIL_BUDGET, window=Config.DETAIL_WINDOW_SECONDS):
        self.budget = budget
        self.window = window
        self.hits = deque()
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.hits and now - self.hits[0] > self.window:
                    self.hits.popleft()
                if len(self.hits) < self.budget:
                    self.hits.append(now)
                    return
                sleep_for = self.window - (now - self.hits[0]) + 0.1
            time.sleep(max(sleep_for, 0.1))


class DivarCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.detail_limiter = RateLimiter()

    def _post(self, url, payload, attempts=3):
        last = None
        for i in range(attempts):
            try:
                r = self.session.post(url, json=payload, timeout=Config.HTTP_TIMEOUT)
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
                time.sleep(2 * (i + 1))
        if last:
            raise last
        raise RuntimeError('خطای نامشخص در ارتباط با دیوار')

    def _get(self, url, attempts=3):
        last = None
        for i in range(attempts):
            try:
                r = self.session.get(url, timeout=Config.HTTP_TIMEOUT)
                if r.status_code == 429:
                    time.sleep((10, 20, 35)[min(i, 2)])
                    continue
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
                time.sleep(2 * (i + 1))
        if last:
            raise last
        raise RuntimeError('دریافت جزئیات آگهی از دیوار ناموفق بود')

    def resolve_city_id(self):
        """Resolve Bojnurd dynamically from Divar's city catalogue; fall back to 39."""
        try:
            payload = self._get(CITIES_URL).json()
            target_name = clean_text(Config.CITY_NAME).lower()
            target_slug = Config.CITY_SLUG.lower()

            def walk(obj):
                if isinstance(obj, dict):
                    yield obj
                    for value in obj.values():
                        yield from walk(value)
                elif isinstance(obj, list):
                    for value in obj:
                        yield from walk(value)

            for item in walk(payload):
                name = clean_text(item.get('name') or item.get('persian_name') or item.get('title')).lower()
                slug = str(item.get('slug') or item.get('english_name') or '').lower()
                city_id = item.get('id') or item.get('city_id')
                if city_id is not None and (name == target_name or slug == target_slug):
                    return str(city_id)
        except Exception:
            pass
        return str(Config.CITY_ID)

    @staticmethod
    def _form_data():
        return {'category': {'str': {'value': Config.CATEGORY}}}

    @staticmethod
    def _parse_card(widget):
        data = widget.get('data') or {}
        action_payload = (data.get('action') or {}).get('payload') or {}
        web_info = action_payload.get('web_info') or {}
        token = action_payload.get('token') or data.get('token')
        top = data.get('top_description_text') or ''
        middle = data.get('middle_description_text') or ''
        bottom = data.get('bottom_description_text') or ''
        total, ppm = extract_sell_prices(top, middle, bottom)
        raw_district = web_info.get('district_persian') or data.get('district') or ''
        return {
            'token': token,
            'title': clean_text(data.get('title') or ''),
            'district_raw': clean_text(raw_district),
            'district': canonical_district(raw_district),
            'total_price': total,
            'card_price_per_m2': ppm,
            'agency_text': clean_text(bottom),
            'last_modified': None,
            'url': f'https://divar.ir/v/{token}' if token else '',
            'source': 'divar-live',
            'raw_card': data,
        }

    def fetch_cards(self, on_progress=None):
        """Fetch the complete current apartment-sale list using pagination.
        Returns (items, complete, pages). complete=False means the configured
        safety page cap was reached before Divar said there were no more pages.
        """
        city_id = self.resolve_city_id()
        pagination = {'@type': 'type.googleapis.com/post_list.PaginationData', 'page': 1}
        seen = {}
        complete = False
        pages_done = 0
        last_cursor_repr = None

        for page_no in range(1, Config.MAX_LIST_PAGES + 1):
            body = {
                'city_ids': [city_id],
                'search_data': {'form_data': {'data': self._form_data()}},
                'pagination_data': pagination,
            }
            payload = self._post(Config.SEARCH_URL, body).json()
            pages_done = page_no
            row_count = 0
            for widget in payload.get('list_widgets', []):
                if widget.get('widget_type') != 'POST_ROW':
                    continue
                item = self._parse_card(widget)
                if item.get('token'):
                    seen[item['token']] = item
                    row_count += 1

            if on_progress:
                on_progress(page_no, len(seen))

            pg = payload.get('pagination') or {}
            if not pg.get('has_next_page'):
                complete = True
                break
            next_cursor = pg.get('data')
            cursor_repr = repr(next_cursor)
            if not next_cursor or cursor_repr == last_cursor_repr or row_count == 0:
                # Avoid an accidental infinite loop if Divar changes pagination.
                complete = False
                break
            last_cursor_repr = cursor_repr
            pagination = next_cursor
            time.sleep(Config.LIST_DELAY_SECONDS)

        return list(seen.values()), complete, pages_done

    @staticmethod
    def _parse_detail_payload(payload):
        fields = {}
        features = {}
        description = ''
        images = []
        lat = lon = None

        for section in payload.get('sections', []):
            sec_name = section.get('section_name')
            for widget in section.get('widgets', []):
                kind = widget.get('widget_type')
                data = widget.get('data') or {}

                if kind == 'GROUP_INFO_ROW':
                    for item in data.get('items', []):
                        title = clean_text(item.get('title'))
                        if title:
                            fields[title] = item.get('value')
                elif kind == 'UNEXPANDABLE_ROW':
                    title = clean_text(data.get('title'))
                    if title:
                        fields[title] = data.get('value')
                elif kind == 'GROUP_FEATURE_ROW':
                    for item in data.get('items', []):
                        title = clean_text(item.get('title'))
                        if not title:
                            continue
                        available = item.get('available')
                        if available is None:
                            available = 'ندارد' not in title
                        features[title.replace(' ندارد', '').strip()] = bool(available)
                elif kind == 'DESCRIPTION_ROW':
                    text = data.get('text')
                    if text and len(text) > len(description):
                        description = text

                if sec_name == 'IMAGE':
                    for shot in data.get('items', []):
                        url = (shot.get('image') or {}).get('url')
                        if url and url not in images:
                            images.append(url)

                if sec_name == 'MAP' or kind == 'MAP_ROW':
                    loc = data.get('location') or {}
                    point = (loc.get('exact_data') or {}).get('point') or loc.get('point') or {}
                    lat = point.get('latitude') or point.get('lat') or lat
                    lon = point.get('longitude') or point.get('lon') or lon

        def first_field(*names):
            for name in names:
                if name in fields:
                    return fields[name]
            return None

        size = parse_number(first_field('متراژ', 'مساحت'))
        rooms = parse_number(first_field('اتاق', 'تعداد اتاق'))
        year = parse_number(first_field('ساخت', 'سال ساخت'))
        floor = first_field('طبقه')

        if year is not None:
            year = int(year)
            if year < 1000 or year > current_jalali_year() + 2:
                year = None
        age = max(0, current_jalali_year() - year) if year else None

        # Detail pages sometimes also expose exact sale price rows.
        detail_total, detail_ppm = extract_sell_prices(
            first_field('قیمت کل', 'قیمت'),
            first_field('قیمت هر متر', 'قیمت هر متر مربع'),
        )

        return {
            'size_m2': float(size) if size is not None else None,
            'rooms': int(rooms) if rooms is not None else None,
            'year_built': year,
            'building_age': age,
            'floor': clean_text(floor) if floor is not None else None,
            'has_elevator': features.get('آسانسور'),
            'has_parking': features.get('پارکینگ'),
            'has_storage': features.get('انباری'),
            'description': description or '',
            'image_url': images[0] if images else None,
            'images': images,
            'lat': lat,
            'lon': lon,
            'detail_total_price': detail_total,
            'detail_price_per_m2': detail_ppm,
            'detail_raw': payload,
        }

    def fetch_detail(self, token):
        self.detail_limiter.acquire()
        url = Config.DETAIL_URL.format(token=token)
        return self._parse_detail_payload(self._get(url).json())

    def fetch_details(self, tokens, on_progress=None):
        """Fetch detail records in a small worker pool behind a shared limiter.
        Errors are returned per token instead of aborting the entire update.
        """
        tokens = list(dict.fromkeys(t for t in tokens if t))
        results = {}
        errors = {}
        done = 0
        lock = threading.Lock()

        def work(token):
            try:
                return token, self.fetch_detail(token), None
            except Exception as exc:  # one bad/removed ad should not kill the run
                return token, None, str(exc)

        with ThreadPoolExecutor(max_workers=max(1, Config.DETAIL_WORKERS)) as pool:
            futures = [pool.submit(work, token) for token in tokens]
            for fut in as_completed(futures):
                token, detail, error = fut.result()
                with lock:
                    done += 1
                    if detail is not None:
                        results[token] = detail
                    if error:
                        errors[token] = error
                    if on_progress:
                        on_progress(done, len(tokens), len(errors))
        return results, errors
