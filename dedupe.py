from difflib import SequenceMatcher
from urllib.parse import urlparse
from neighborhoods import clean_text


def _norm(s):
    return clean_text(s).lower()


def similarity(a, b):
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _image_key(url):
    if not url:
        return None
    path = urlparse(url).path
    # Divar CDN URLs may include size variants; filename is the useful identity.
    return path.rsplit('/', 1)[-1] or path


def is_strong_duplicate(candidate, original):
    if candidate.get('token') == original.get('token'):
        return False
    if _norm(candidate.get('district')) != _norm(original.get('district')):
        return False

    sa, sb = candidate.get('size_m2'), original.get('size_m2')
    pa, pb = candidate.get('total_price'), original.get('total_price')
    if not sa or not sb or not pa or not pb:
        return False
    if abs(sa - sb) / max(sa, sb) > 0.025:
        return False
    if abs(pa - pb) / max(pa, pb) > 0.035:
        return False

    ya, yb = candidate.get('year_built'), original.get('year_built')
    if ya and yb and abs(int(ya) - int(yb)) > 1:
        return False
    ra, rb = candidate.get('rooms'), original.get('rooms')
    if ra is not None and rb is not None and str(ra) != str(rb):
        return False

    ia, ib = _image_key(candidate.get('image_url')), _image_key(original.get('image_url'))
    if ia and ib and ia == ib:
        return True

    title_sim = similarity(candidate.get('title'), original.get('title'))
    desc_sim = similarity((candidate.get('description') or '')[:800], (original.get('description') or '')[:800])
    # Conservative: do not collapse two genuinely distinct units just because
    # an agency gave them similar metadata.
    return title_sim >= 0.88 and desc_sim >= 0.72


def assign_duplicates(rows):
    """Return {duplicate_token: original_token}. Oldest row wins."""
    ordered = sorted(rows, key=lambda r: ((r.get('first_seen') or ''), r.get('token') or ''))
    originals = []
    mapping = {}
    for row in ordered:
        found = None
        for original in reversed(originals[-250:]):
            if is_strong_duplicate(row, original):
                found = original.get('token')
                break
        if found:
            mapping[row.get('token')] = found
        else:
            originals.append(row)
    return mapping
