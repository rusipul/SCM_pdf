import re

GRAND_TOTAL_RE = re.compile(r'Grand Total\S*\s*KRW\s*([\d,]+\.\d{2})')


def parse_grand_total(text):
    match = GRAND_TOTAL_RE.search(text)
    if match:
        return float(match.group(1).replace(',', ''))
    return None
