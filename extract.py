import re
from pathlib import Path
import pdfplumber
from openpyxl import Workbook

GRAND_TOTAL_RE = re.compile(r'Grand Total\S*\s*KRW\s*([\d,]+\.\d{2})')


def parse_grand_total(text):
    match = GRAND_TOTAL_RE.search(text)
    if match:
        return float(match.group(1).replace(',', ''))
    return None


SHIP_DATE_RE = re.compile(r'Ship Date (\d{2}/\d{2}/\d{4})')
AWB_RE = re.compile(r'Air Waybill Number (\d+)')
TOTAL_RE = re.compile(r'^합계Total ([\d,]+\.\d{2})$')


def parse_shipments(text):
    shipments = []
    current_date = None
    current_awb = None
    for line in text.splitlines():
        date_match = SHIP_DATE_RE.search(line)
        if date_match:
            current_date = date_match.group(1)
            continue
        awb_match = AWB_RE.search(line)
        if awb_match:
            current_awb = awb_match.group(1)
            continue
        total_match = TOTAL_RE.match(line.strip())
        if total_match and current_date and current_awb:
            shipments.append({
                "ship_date": current_date,
                "awb_number": current_awb,
                "total": float(total_match.group(1).replace(',', '')),
            })
            current_date = None
            current_awb = None
    return shipments


def build_workbook(shipments, grand_total):
    wb = Workbook()
    ws = wb.active
    ws.title = "FedEx 청구 내역"
    ws.append(["선적일자", "AWB번호", "Total 금액"])
    for shipment in shipments:
        ws.append([shipment["ship_date"], shipment["awb_number"], shipment["total"]])
    extracted_sum = sum(shipment["total"] for shipment in shipments)
    ws.append(["합계", "", extracted_sum])
    if grand_total is not None and abs(extracted_sum - grand_total) > 0.01:
        ws.append([
            f"⚠ 합계 불일치 (추출 합계: {extracted_sum:,.2f} / "
            f"PDF Grand Total: {grand_total:,.2f})"
        ])
    return wb, extracted_sum


def extract_pdf_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def process_pdf(pdf_path):
    """Returns matched=True if grand_total agrees with the extracted sum,
    False if it disagrees, or None if no comparison could be made (no
    grand_total present, or no shipments found)."""
    pdf_path = Path(pdf_path)
    text = extract_pdf_text(pdf_path)
    shipments = parse_shipments(text)
    grand_total = parse_grand_total(text)

    if not shipments:
        return {
            "output_path": None,
            "shipment_count": 0,
            "extracted_sum": 0.0,
            "grand_total": grand_total,
            "matched": None,
        }

    wb, extracted_sum = build_workbook(shipments, grand_total)
    output_path = pdf_path.with_suffix(".xlsx")
    wb.save(output_path)
    matched = (
        None if grand_total is None
        else abs(extracted_sum - grand_total) <= 0.01
    )

    return {
        "output_path": output_path,
        "shipment_count": len(shipments),
        "extracted_sum": extracted_sum,
        "grand_total": grand_total,
        "matched": matched,
    }
