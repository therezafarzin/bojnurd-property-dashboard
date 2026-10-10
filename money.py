import re

DIGIT_MAP = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def normalize_digits(text):
    return (text or '').translate(DIGIT_MAP)


def parse_money(text):
    """Parse a Divar Persian money label into toman.
    Handles full integer labels as well as forms like 3.5 billion / 850 million.
    Returns None for negotiable/unknown labels.
    """
    if not text:
        return None
    s = normalize_digits(str(text)).replace('٬', ',').replace('،', ',').strip()
    if any(k in s for k in ('توافقی', 'مجانی', 'رایگان')):
        return None

    # Persian colloquial slash is often used as a decimal separator: 5/400 میلیارد.
    s_decimal = re.sub(r'(?<=\d)/(?=\d)', '.', s)
    unit_mult = 1
    if 'میلیارد' in s_decimal:
        unit_mult = 1_000_000_000
    elif 'میلیون' in s_decimal:
        unit_mult = 1_000_000
    elif 'هزار' in s_decimal:
        unit_mult = 1_000

    if unit_mult != 1:
        m = re.search(r'(\d+(?:[.,]\d+)?)', s_decimal.replace(',', '.'))
        if m:
            try:
                return int(round(float(m.group(1)) * unit_mult))
            except ValueError:
                pass

    # Full formatted integer, e.g. 5,400,000,000 تومان.
    groups = re.findall(r'\d+', s)
    if not groups:
        return None
    joined = ''.join(groups)
    try:
        value = int(joined)
    except ValueError:
        return None
    if 'ریال' in s and 'تومان' not in s:
        value //= 10
    return value if value > 0 else None


def extract_sell_prices(*texts):
    total = None
    ppm = None
    for text in texts:
        if not text:
            continue
        value = parse_money(text)
        if value is None:
            continue
        t = normalize_digits(text)
        if 'متری' in t or 'هر متر' in t or 'متر مربع' in t:
            ppm = ppm or value
        elif 'تومان' in t or 'میلیارد' in t or 'میلیون' in t or 'ریال' in t:
            total = total or value
    return total, ppm


def parse_number(value):
    if value is None:
        return None
    s = normalize_digits(str(value)).replace(',', '').replace('٬', '')
    m = re.search(r'-?\d+(?:\.\d+)?', s)
    if not m:
        return None
    try:
        n = float(m.group(0))
        return int(n) if n.is_integer() else n
    except ValueError:
        return None
