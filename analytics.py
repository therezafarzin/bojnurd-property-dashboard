from statistics import median
from config import Config


def percentile(values, p):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    k = (len(vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(vals) - 1)
    if f == c:
        return vals[f]
    return vals[f] * (c - k) + vals[c] * (k - f)


def valid_basic(row):
    s = row.get('size_m2')
    p = row.get('price_per_m2')
    return (
        row.get('active') == 1 and not row.get('duplicate_of') and
        s is not None and p is not None and
        Config.MIN_VALID_SIZE <= s <= Config.MAX_VALID_SIZE and
        Config.MIN_VALID_PRICE_PER_M2 <= p <= Config.MAX_VALID_PRICE_PER_M2
    )


def mark_outliers(rows):
    by_district = {}
    for r in rows:
        if valid_basic(r):
            by_district.setdefault(r.get('district') or 'نامشخص', []).append(r)
    outlier_tokens = set()
    for _, items in by_district.items():
        vals = [r['price_per_m2'] for r in items]
        if len(vals) < 6:
            continue
        q1 = percentile(vals, .25)
        q3 = percentile(vals, .75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        for r in items:
            if r['price_per_m2'] < low or r['price_per_m2'] > high:
                outlier_tokens.add(r['token'])
    return outlier_tokens


def district_stats(rows):
    groups = {}
    for r in rows:
        if valid_basic(r) and not r.get('is_outlier'):
            groups.setdefault(r.get('district') or 'نامشخص', []).append(r)
    result = []
    for district, items in groups.items():
        vals = [r['price_per_m2'] for r in items]
        new_vals = [r['price_per_m2'] for r in items
                    if r.get('building_age') is not None and r['building_age'] <= Config.NEW_BUILD_MAX_AGE]
        result.append({
            'district': district,
            'count': len(items),
            'median_ppm': median(vals),
            'q1_ppm': percentile(vals, .25),
            'q3_ppm': percentile(vals, .75),
            'min_ppm': min(vals),
            'max_ppm': max(vals),
            'new_build_count': len(new_vals),
            'new_build_median_ppm': median(new_vals) if new_vals else None,
        })
    return sorted(result, key=lambda x: (x['median_ppm'] or 0), reverse=True)
