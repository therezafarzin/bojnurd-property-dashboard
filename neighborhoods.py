import re

ARABIC_MAP = str.maketrans({'ي':'ی','ك':'ک','ۀ':'ه','ة':'ه'})
DIRECTION_SUFFIXES = ('شمالی', 'جنوبی', 'شرقی', 'غربی')

# A small conservative alias layer. We do not guess unknown locations.
ALIASES = {
    'فردوسی جنوبی': 'فردوسی',
    'فردوسی شمالی': 'فردوسی',
    'استقلال شمالی': 'استقلال',
    'استقلال جنوبی': 'استقلال',
    'شریعتی شمالی': 'شریعتی',
    'شریعتی جنوبی': 'شریعتی',
    'امام خمینی شرقی': 'امام خمینی',
    'امام خمینی غربی': 'امام خمینی',
}


def clean_text(value):
    s = (value or '').translate(ARABIC_MAP)
    s = re.sub(r'[\u200c\u200f\u202a-\u202e]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip(' -،,')
    return s


def canonical_district(raw):
    s = clean_text(raw)
    if not s:
        return 'نامشخص'
    if s in ALIASES:
        return ALIASES[s]
    # Only remove a direction when it is the final word. This groups large areas
    # without collapsing unrelated names.
    parts = s.split()
    if len(parts) >= 2 and parts[-1] in DIRECTION_SUFFIXES:
        s = ' '.join(parts[:-1]).strip()
    return s or 'نامشخص'
