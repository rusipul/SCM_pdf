from extract import parse_grand_total, parse_shipments


def test_placeholder():
    assert True


def test_parse_grand_total_extracts_amount():
    text = (
        "Total Number of Shipments총 발송 건수 29\n"
        "Grand Total총액 KRW 7,834,180.00\n"
        "2026년 FedEx 요금 개정 및 기타 주요 변경 사항\n"
    )
    assert parse_grand_total(text) == 7834180.00


def test_parse_grand_total_returns_none_when_absent():
    text = "Summary by Payment Type 결제 유형별 요약\nTotal 합계 2,348,680.00\n"
    assert parse_grand_total(text) is None


SAMPLE_TWO_SHIPMENTS = """\
선적일자 Ship Date 05/27/2026 발송인Sender 수취인Recipient
AWB 번호 Air Waybill Number 872265794268 SHIN JONG SUN ALBERT SHEN
서비스 종류 Service Type 2P OKINS ELECTRONICS ,LTD GREATEK ELECTRONICS INC.
운임Freight Charges 1,539,900.00
차감Deductions 기본 할인 Base Discount (1,148,300.00)
기타비용Other Charges 유류할증 추가요금 Fuel Surcharge 193,840.00
합계Total 585,440.00
49.50%의 유류할증료가 부과되었습니다.
선적일자 Ship Date 05/28/2026 발송인Sender 수취인Recipient
AWB 번호 Air Waybill Number 872319321541 ARIA DONG KAORI ANEZAKI
합계Total 53,880.00
"""


def test_parse_shipments_extracts_all_fields():
    result = parse_shipments(SAMPLE_TWO_SHIPMENTS)
    assert result == [
        {"ship_date": "05/27/2026", "awb_number": "872265794268", "total": 585440.00},
        {"ship_date": "05/28/2026", "awb_number": "872319321541", "total": 53880.00},
    ]


def test_parse_shipments_returns_empty_list_when_no_matches():
    assert parse_shipments("아무 패턴도 없는 텍스트입니다.") == []


def test_parse_shipments_skips_total_without_preceding_awb():
    text = "합계Total 1,000.00\n"
    assert parse_shipments(text) == []
