from extract import parse_grand_total


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
