import csv
import io
import json
import threading
from datetime import datetime, timedelta, timezone
from statistics import median

from analytics import district_stats, mark_outliers, valid_basic
from collector import DivarCollector
from config import Config
from db import connect, now_iso
from dedupe import assign_duplicates
from neighborhoods import canonical_district

_UPDATE_LOCK = threading.Lock()


def _dict(row):
    return dict(row) if row is not None else None


def _set_run(run_id, **values):
    if not values:
        return
    keys = list(values)
    sql = 'UPDATE update_runs SET ' + ','.join(f'{k}=?' for k in keys) + ' WHERE id=?'
    with connect() as conn:
        conn.execute(sql, [values[k] for k in keys] + [run_id])


def _recent_enough(iso_text):
    if not iso_text:
        return False
    try:
        dt = datetime.fromisoformat(iso_text.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt <= timedelta(days=Config.DETAIL_CACHE_DAYS)
    except Exception:
        return False


def _merge_item(card, detail, old):
    old = old or {}
    detail = detail or {}
    size = detail.get('size_m2') if detail.get('size_m2') is not None else old.get('size_m2')
    year = detail.get('year_built') if detail.get('year_built') is not None else old.get('year_built')
    age = detail.get('building_age') if detail.get('building_age') is not None else old.get('building_age')
    rooms = detail.get('rooms') if detail.get('rooms') is not None else old.get('rooms')

    total = detail.get('detail_total_price') or card.get('total_price') or old.get('total_price')
    card_ppm = detail.get('detail_price_per_m2') or card.get('card_price_per_m2')
    if total is not None and total <= 0:
        total = None
    ppm = None
    if total and size:
        ppm = total / float(size)
    elif card_ppm:
        ppm = card_ppm
        if size:
            total = int(round(card_ppm * float(size)))
    elif old.get('price_per_m2'):
        ppm = old.get('price_per_m2')

    district_raw = card.get('district_raw') or old.get('district_raw') or old.get('district') or 'نامشخص'
    return {
        'token': card['token'],
        'title': card.get('title') or old.get('title') or '',
        'district_raw': district_raw,
        'district': canonical_district(district_raw),
        'size_m2': size,
        'total_price': total,
        'price_per_m2': ppm,
        'year_built': year,
        'building_age': age,
        'rooms': rooms,
        'floor': detail.get('floor') if detail.get('floor') is not None else old.get('floor'),
        'has_elevator': detail.get('has_elevator') if detail.get('has_elevator') is not None else old.get('has_elevator'),
        'has_parking': detail.get('has_parking') if detail.get('has_parking') is not None else old.get('has_parking'),
        'has_storage': detail.get('has_storage') if detail.get('has_storage') is not None else old.get('has_storage'),
        'image_url': detail.get('image_url') or old.get('image_url'),
        'description': detail.get('description') or old.get('description') or '',
        'url': card.get('url') or old.get('url') or f"https://divar.ir/v/{card['token']}",
        'source': 'divar-live',
        'last_modified': card.get('last_modified'),
        'raw_json': {'card': card.get('raw_card'), 'detail': detail.get('detail_raw') if detail else None},
    }


def start_update():
    with _UPDATE_LOCK:
        with connect() as conn:
            running = conn.execute("SELECT * FROM update_runs WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
            if running:
                try:
                    started = datetime.fromisoformat(running['started_at'].replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) - started < timedelta(hours=1):
                        return {'ok': True, 'already_running': True, 'run_id': running['id']}
                except Exception:
                    pass
                conn.execute("UPDATE update_runs SET status='error',finished_at=?,message=? WHERE id=?",
                             (now_iso(), 'اجرای قبلی نیمه‌کاره مانده بود.', running['id']))
            cur = conn.execute('''INSERT INTO update_runs(started_at,source,status,progress,stage,message)
                                  VALUES(?,?,?,?,?,?)''',
                               (now_iso(), 'divar-live', 'running', 1, 'شروع', 'در حال آماده‌سازی…'))
            run_id = cur.lastrowid
        thread = threading.Thread(target=_run_update, args=(run_id,), daemon=True)
        thread.start()
        return {'ok': True, 'already_running': False, 'run_id': run_id}


def _run_update(run_id):
    started = now_iso()
    try:
        collector = DivarCollector()

        def list_progress(page, count):
            pct = min(30, 4 + page * 2)
            _set_run(run_id, pages_done=page, fetched_count=count, progress=pct,
                     stage='دریافت آگهی‌ها', message=f'{count} آگهی از دیوار دریافت شد…')

        cards, complete, pages = collector.fetch_cards(on_progress=list_progress)
        _set_run(run_id, fetched_count=len(cards), pages_done=pages, complete_coverage=int(complete),
                 progress=32, stage='بررسی مشخصات', message='در حال بررسی جزئیات متراژ و سن بنا…')

        with connect() as conn:
            existing_rows = [dict(r) for r in conn.execute('SELECT * FROM listings')]
        existing = {r['token']: r for r in existing_rows}

        need_detail = []
        for card in cards:
            old = existing.get(card['token'])
            if not old or old.get('size_m2') is None or old.get('year_built') is None or not _recent_enough(old.get('detail_fetched_at')):
                need_detail.append(card['token'])
        _set_run(run_id, detail_total=len(need_detail))

        def detail_progress(done, total, errors):
            pct = 35 if total == 0 else 35 + int(43 * done / total)
            _set_run(run_id, detail_done=done, detail_errors=errors, progress=min(pct, 78),
                     stage='تکمیل مشخصات', message=f'جزئیات {done} از {total} آگهی تکمیل شد…')

        details, detail_errors = collector.fetch_details(need_detail, on_progress=detail_progress) if need_detail else ({}, {})
        observed = now_iso()
        inserted = updated = 0
        seen_tokens = {c['token'] for c in cards}

        _set_run(run_id, progress=80, stage='ذخیره و تحلیل', message='در حال ذخیره تاریخچه و تحلیل قیمت‌ها…')
        with connect() as conn:
            for card in cards:
                token = card['token']
                old = existing.get(token)
                detail = details.get(token)
                item = _merge_item(card, detail, old)
                detail_at = observed if detail else (old.get('detail_fetched_at') if old else None)
                raw_json = json.dumps(item['raw_json'], ensure_ascii=False) if item.get('raw_json') else None

                if old:
                    conn.execute('''UPDATE listings SET
                        title=?,district=?,district_raw=?,size_m2=?,total_price=?,price_per_m2=?,year_built=?,building_age=?,rooms=?,floor=?,
                        has_elevator=?,has_parking=?,has_storage=?,image_url=?,description=?,url=?,source=?,last_seen=?,last_modified=?,active=1,
                        detail_fetched_at=?,raw_json=? WHERE token=?''',
                        (item['title'], item['district'], item['district_raw'], item['size_m2'], item['total_price'], item['price_per_m2'],
                         item['year_built'], item['building_age'], item['rooms'], item['floor'],
                         _bool_int(item['has_elevator']), _bool_int(item['has_parking']), _bool_int(item['has_storage']),
                         item['image_url'], item['description'], item['url'], item['source'], observed, item['last_modified'], detail_at, raw_json, token))
                    updated += 1
                else:
                    conn.execute('''INSERT INTO listings(
                        token,title,district,district_raw,size_m2,total_price,price_per_m2,year_built,building_age,rooms,floor,
                        has_elevator,has_parking,has_storage,image_url,description,url,source,first_seen,last_seen,last_modified,active,detail_fetched_at,raw_json)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)''',
                        (token,item['title'],item['district'],item['district_raw'],item['size_m2'],item['total_price'],item['price_per_m2'],
                         item['year_built'],item['building_age'],item['rooms'],item['floor'],_bool_int(item['has_elevator']),
                         _bool_int(item['has_parking']),_bool_int(item['has_storage']),item['image_url'],item['description'],item['url'],
                         item['source'],observed,observed,item['last_modified'],detail_at,raw_json))
                    inserted += 1

                if item['total_price'] and item['price_per_m2']:
                    conn.execute('''INSERT OR IGNORE INTO price_history(token,observed_at,total_price,price_per_m2)
                                    VALUES(?,?,?,?)''',
                                 (token, observed[:16], int(item['total_price']), float(item['price_per_m2'])))

            # We only deactivate unseen listings when pagination reached a natural end.
            if complete:
                if seen_tokens:
                    placeholders = ','.join('?' for _ in seen_tokens)
                    conn.execute(f"UPDATE listings SET active=0 WHERE source='divar-live' AND token NOT IN ({placeholders})", tuple(seen_tokens))
                else:
                    # Empty result should not wipe history on a possibly bad upstream response.
                    complete = False

        # Recompute strong duplicates on the complete active set.
        with connect() as conn:
            active_rows = [dict(r) for r in conn.execute('SELECT * FROM listings WHERE active=1 ORDER BY first_seen')]
            conn.execute('UPDATE listings SET duplicate_of=NULL WHERE active=1')
            mapping = assign_duplicates(active_rows)
            for dup, original in mapping.items():
                conn.execute('UPDATE listings SET duplicate_of=? WHERE token=?', (original, dup))

        # Outlier detection after duplicates are assigned.
        with connect() as conn:
            active_rows = [dict(r) for r in conn.execute('SELECT * FROM listings WHERE active=1')]
            outliers = mark_outliers(active_rows)
            conn.execute('UPDATE listings SET is_outlier=0 WHERE active=1')
            for token in outliers:
                conn.execute('UPDATE listings SET is_outlier=1 WHERE token=?', (token,))

            final_rows = [dict(r) for r in conn.execute('SELECT * FROM listings WHERE active=1')]
            stats = district_stats(final_rows)
            for s in stats:
                conn.execute('''INSERT INTO market_snapshots(observed_at,district,valid_count,median_ppm,q1_ppm,q3_ppm,new_build_median_ppm,new_build_count)
                                VALUES(?,?,?,?,?,?,?,?)''',
                             (observed, s['district'], s['count'], s['median_ppm'], s['q1_ppm'], s['q3_ppm'],
                              s['new_build_median_ppm'], s['new_build_count']))

        message = f'{len(cards)} آگهی واقعی پردازش شد.'
        if detail_errors:
            message += f' جزئیات {len(detail_errors)} آگهی موقتاً قابل دریافت نبود.'
        if not complete:
            message += ' پوشش لیست کامل تأیید نشد؛ آگهی‌های قدیمی غیرفعال نشدند.'
        _set_run(run_id, finished_at=now_iso(), inserted_count=inserted, updated_count=updated,
                 duplicate_count=len(mapping), outlier_count=len(outliers), detail_done=len(need_detail),
                 detail_errors=len(detail_errors), complete_coverage=int(complete), progress=100,
                 stage='تمام شد', status='ok', message=message)
    except Exception as exc:
        _set_run(run_id, finished_at=now_iso(), status='error', progress=100, stage='خطا', message=str(exc))


def _bool_int(value):
    if value is None:
        return None
    return 1 if bool(value) else 0


def get_update_status(run_id=None):
    with connect() as conn:
        if run_id:
            row = conn.execute('SELECT * FROM update_runs WHERE id=?', (run_id,)).fetchone()
        else:
            row = conn.execute('SELECT * FROM update_runs ORDER BY id DESC LIMIT 1').fetchone()
    return _dict(row)


def _median(values):
    vals = [v for v in values if v is not None]
    return median(vals) if vals else None


def dashboard_data():
    with connect() as conn:
        rows = [dict(r) for r in conn.execute('SELECT * FROM listings WHERE active=1')]
        stats = district_stats(rows)
        valid = [r for r in rows if valid_basic(r) and not r.get('is_outlier')]
        new = [r for r in valid if r.get('building_age') is not None and r['building_age'] <= Config.NEW_BUILD_MAX_AGE]
        history = [dict(r) for r in conn.execute('''
            SELECT substr(observed_at,1,10) day, district, AVG(median_ppm) median_ppm
            FROM market_snapshots GROUP BY day,district ORDER BY day ASC
        ''')]
        last_run = conn.execute('SELECT * FROM update_runs ORDER BY id DESC LIMIT 1').fetchone()

        first_prices = {r['token']: r['first_price'] for r in conn.execute('''
            SELECT p.token, p.total_price AS first_price FROM price_history p
            JOIN (SELECT token, MIN(observed_at) t FROM price_history GROUP BY token) x
              ON p.token=x.token AND p.observed_at=x.t
        ''')}

    dist_medians = {d['district']: d['median_ppm'] for d in stats}
    latest_started = last_run['started_at'] if last_run else None
    for r in rows:
        dmed = dist_medians.get(r.get('district'))
        r['market_diff_pct'] = ((r['price_per_m2'] / dmed - 1) * 100) if r.get('price_per_m2') and dmed else None
        first = first_prices.get(r['token'])
        r['price_change_pct'] = ((r['total_price'] / first - 1) * 100) if first and r.get('total_price') else None
        r['is_new'] = bool(latest_started and r.get('first_seen') and r['first_seen'] >= latest_started)

    rows.sort(key=lambda r: (r.get('market_diff_pct') is None, r.get('market_diff_pct') or 9999))
    valid_detail = sum(1 for r in rows if r.get('size_m2') is not None and r.get('building_age') is not None)
    return {
        'summary': {
            'median_ppm': _median([r['price_per_m2'] for r in valid]),
            'new_build_median_ppm': _median([r['price_per_m2'] for r in new]),
            'valid_count': len(valid),
            'new_build_count': len(new),
            'district_count': len(stats),
            'active_count': len(rows),
            'duplicate_count': sum(1 for r in rows if r.get('duplicate_of')),
            'outlier_count': sum(1 for r in rows if r.get('is_outlier')),
            'detail_complete_count': valid_detail,
        },
        'districts': stats,
        'listings': rows,
        'history': history,
        'last_run': dict(last_run) if last_run else None,
        'source': 'divar-live',
        'source_label': 'دیوار — داده زنده',
        'new_build_max_age': Config.NEW_BUILD_MAX_AGE,
        'public_search_url': Config.PUBLIC_SEARCH_URL,
        'city': Config.CITY_NAME,
    }


def export_csv_text():
    data = dashboard_data()['listings']
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['token','عنوان','محله اصلی','محله دیوار','متراژ','سال ساخت','سن بنا','اتاق','قیمت کل','قیمت هر متر','درصد نسبت به میانه محله','تکراری','پرت','لینک'])
    for r in data:
        writer.writerow([
            r.get('token'), r.get('title'), r.get('district'), r.get('district_raw'), r.get('size_m2'),
            r.get('year_built'), r.get('building_age'), r.get('rooms'), r.get('total_price'), r.get('price_per_m2'),
            r.get('market_diff_pct'), bool(r.get('duplicate_of')), bool(r.get('is_outlier')), r.get('url')
        ])
    return '\ufeff' + output.getvalue()
