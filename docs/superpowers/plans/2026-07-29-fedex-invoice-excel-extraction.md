# FedEx 청구서 PDF → Excel 추출 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FedEx 청구서 PDF를 드래그&드롭하면 건별(선적일자, AWB번호, Total 금액)이 담긴 Excel 파일을 자동 생성하는 도구를 만든다.

**Architecture:** `extract.py`에 순수 파싱 함수(`parse_shipments`, `parse_grand_total`)와 엑셀 생성 함수(`build_workbook`)를 분리하고, 이를 조합하는 `process_pdf`/`main`을 둔다. 파싱·엑셀 생성 로직은 합성(가짜) 텍스트로, 파일 오케스트레이션은 `monkeypatch`로 PDF 읽기를 대체하여 테스트한다 — 실제 청구서 PDF(민감정보 포함, `.gitignore` 처리됨)는 자동화 테스트에 쓰지 않고 마지막 수동 통합 테스트에만 사용한다. `변환.bat`은 드래그&드롭된 파일 경로를 `extract.py`로 전달하는 얇은 래퍼다.

**Tech Stack:** Python 3.14, pdfplumber (PDF 텍스트 추출), openpyxl (xlsx 생성), pytest (monkeypatch/tmp_path/capsys)

---

## 파일 구조

- `requirements.txt` — 런타임/테스트 의존성
- `conftest.py` — 루트 디렉토리를 `sys.path`에 추가해 `tests/`에서 `extract` 모듈을 임포트 가능하게 함
- `extract.py` — 파싱 함수, 엑셀 생성 함수, PDF 처리 오케스트레이션, CLI 진입점 (`main`)
- `tests/test_extract.py` — `extract.py`의 전체 단위 테스트
- `변환.bat` — 드래그&드롭 진입점

---

### Task 1: 프로젝트 설정

**Files:**
- Create: `requirements.txt`
- Create: `conftest.py`
- Create: `tests/test_extract.py` (빈 파일로 시작)

- [x] **Step 1: `requirements.txt` 작성**

```
pdfplumber==0.11.10
openpyxl==3.1.5
pytest==9.1.1
```

- [x] **Step 2: 의존성 설치 확인**

Run: `pip install -r requirements.txt`
Expected: 이미 설치되어 있으므로 `Requirement already satisfied` 메시지들과 함께 오류 없이 종료

- [x] **Step 3: `conftest.py` 작성**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
```

- [x] **Step 4: 빈 테스트 파일 생성**

`tests/test_extract.py`:

```python
def test_placeholder():
    assert True
```

- [x] **Step 5: pytest 동작 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (`test_placeholder PASSED`)

- [x] **Step 6: 커밋**

```bash
git add requirements.txt conftest.py tests/test_extract.py
git commit -m "chore: set up project dependencies and test scaffolding"
```

---

### Task 2: Grand Total 파싱 (`parse_grand_total`)

PDF 1페이지에는 `Grand Total총액 KRW 7,834,180.00` 형식의 줄이 있다. 이 값을 검증 기준으로 사용한다.

**Files:**
- Modify: `extract.py` (신규 생성)
- Test: `tests/test_extract.py`

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_extract.py`의 `test_placeholder` 아래에 추가:

```python
from extract import parse_grand_total


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
```

- [x] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'extract'` (아직 `extract.py`가 없음)

- [x] **Step 3: 최소 구현 작성**

`extract.py` 신규 생성:

```python
import re

GRAND_TOTAL_RE = re.compile(r'Grand Total\S*\s*KRW\s*([\d,]+\.\d{2})')


def parse_grand_total(text):
    match = GRAND_TOTAL_RE.search(text)
    if match:
        return float(match.group(1).replace(',', ''))
    return None
```

- [x] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (3 passed — placeholder 포함)

- [x] **Step 5: 커밋**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: parse grand total from invoice summary page"
```

---

### Task 3: 건별 데이터 파싱 (`parse_shipments`)

PDF 상세 페이지에는 건마다 아래 세 줄이 이 순서로 나온다 (사이에 다른 줄들이 섞여 있음):
- `선적일자 Ship Date 05/27/2026 발송인Sender 수취인Recipient`
- `AWB 번호 Air Waybill Number 872265794268 SHIN JONG SUN ALBERT SHEN`
- `합계Total 585,440.00`

날짜와 AWB번호를 먼저 발견한 상태에서 `합계Total` 줄을 만나야 한 건이 완성된다. 셋 중 하나라도 없으면 해당 건은 건너뛴다.

**Files:**
- Modify: `extract.py`
- Test: `tests/test_extract.py`

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_extract.py`에 추가:

```python
from extract import parse_shipments

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
```

- [x] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_shipments' from 'extract'`

- [x] **Step 3: 최소 구현 작성**

`extract.py`에 추가:

```python
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
```

- [x] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (6 passed)

- [x] **Step 5: 커밋**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: parse per-shipment ship date, AWB number, and total"
```

---

### Task 4: 엑셀 생성 (`build_workbook`)

**Files:**
- Modify: `extract.py`
- Test: `tests/test_extract.py`

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_extract.py`에 추가:

```python
from extract import build_workbook

SHIPMENTS_FIXTURE = [
    {"ship_date": "05/27/2026", "awb_number": "872265794268", "total": 585440.00},
    {"ship_date": "05/28/2026", "awb_number": "872319321541", "total": 53880.00},
]


def test_build_workbook_writes_header_and_rows():
    wb, extracted_sum = build_workbook(SHIPMENTS_FIXTURE, grand_total=639320.00)
    ws = wb.active
    rows = [[cell.value for cell in row] for row in ws.iter_rows()]
    assert rows[0] == ["선적일자", "AWB번호", "Total 금액"]
    assert rows[1] == ["05/27/2026", "872265794268", 585440.00]
    assert rows[2] == ["05/28/2026", "872319321541", 53880.00]
    assert rows[3] == ["합계", "", 639320.00]
    assert extracted_sum == 639320.00


def test_build_workbook_flags_mismatch():
    wb, extracted_sum = build_workbook(SHIPMENTS_FIXTURE, grand_total=999999.00)
    ws = wb.active
    last_row = [cell.value for cell in list(ws.iter_rows())[-1]]
    assert "불일치" in last_row[0]


def test_build_workbook_no_warning_when_grand_total_missing():
    wb, extracted_sum = build_workbook(SHIPMENTS_FIXTURE, grand_total=None)
    ws = wb.active
    rows = [[cell.value for cell in row] for row in ws.iter_rows()]
    assert len(rows) == 4  # header + 2 shipments + sum row, no warning row
```

- [x] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_workbook' from 'extract'`

- [x] **Step 3: 최소 구현 작성**

`extract.py`에 추가:

```python
from openpyxl import Workbook


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
```

- [x] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (9 passed)

- [x] **Step 5: 커밋**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: build excel workbook with sum and mismatch warning row"
```

---

### Task 5: PDF 텍스트 추출 (`extract_pdf_text`)

pdfplumber를 감싸는 얇은 래퍼. 실제 PDF 파일 없이 단위 테스트하기 어려우므로 자동화 테스트는 생략하고, Task 7에서 실제 샘플 PDF로 수동 검증한다.

**Files:**
- Modify: `extract.py`

- [x] **Step 1: 구현 작성**

`extract.py`에 추가:

```python
import pdfplumber


def extract_pdf_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)
```

- [x] **Step 2: 기존 테스트가 깨지지 않았는지 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (9 passed)

- [x] **Step 3: 커밋**

```bash
git add extract.py
git commit -m "feat: add pdfplumber wrapper to extract full document text"
```

---

### Task 6: PDF 처리 오케스트레이션 (`process_pdf`)

`extract_pdf_text`를 `monkeypatch`로 대체해 실제 PDF 파일 없이 파일 저장 로직을 검증한다.

**Files:**
- Modify: `extract.py`
- Test: `tests/test_extract.py`

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_extract.py`에 추가:

```python
from openpyxl import load_workbook
import extract
from extract import process_pdf


def test_process_pdf_writes_xlsx_next_to_pdf(tmp_path, monkeypatch):
    pdf_path = tmp_path / "청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: SAMPLE_TWO_SHIPMENTS)

    result = process_pdf(pdf_path)

    output_path = tmp_path / "청구서.xlsx"
    assert result["output_path"] == output_path
    assert output_path.exists()
    assert result["shipment_count"] == 2
    assert result["extracted_sum"] == 639320.00

    wb = load_workbook(output_path)
    ws = wb.active
    rows = [[cell.value for cell in row] for row in ws.iter_rows()]
    assert rows[0] == ["선적일자", "AWB번호", "Total 금액"]


def test_process_pdf_matches_when_grand_total_agrees(tmp_path, monkeypatch):
    pdf_path = tmp_path / "청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    text_with_grand_total = SAMPLE_TWO_SHIPMENTS + "\nGrand Total총액 KRW 639,320.00\n"
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: text_with_grand_total)

    result = process_pdf(pdf_path)

    assert result["matched"] is True
    assert result["grand_total"] == 639320.00


def test_process_pdf_returns_none_matched_when_grand_total_missing(tmp_path, monkeypatch):
    pdf_path = tmp_path / "청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: SAMPLE_TWO_SHIPMENTS)

    result = process_pdf(pdf_path)

    assert result["grand_total"] is None
    assert result["matched"] is None


def test_process_pdf_skips_file_when_no_shipments_found(tmp_path, monkeypatch):
    pdf_path = tmp_path / "빈청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: "관련 없는 텍스트")

    result = process_pdf(pdf_path)

    assert result["shipment_count"] == 0
    assert result["output_path"] is None
    assert not (tmp_path / "빈청구서.xlsx").exists()
```

- [x] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `ImportError: cannot import name 'process_pdf' from 'extract'`

- [x] **Step 3: 최소 구현 작성**

`extract.py`에 추가:

```python
from pathlib import Path


def process_pdf(pdf_path):
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
            "matched": False,
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
```

**중요:** 테스트에서 `monkeypatch.setattr(extract, "extract_pdf_text", ...)`로 모듈 속성을 대체하므로, `process_pdf` 내부에서는 `extract_pdf_text(pdf_path)`를 (임포트한 이름이 아니라) 모듈 전역 이름 그대로 호출해야 patch가 적용된다. 위 구현처럼 같은 파일 안에 정의되어 있으면 자동으로 만족된다.

- [x] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (13 passed)

- [x] **Step 5: 커밋**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: orchestrate PDF-to-Excel processing with grand total validation"
```

**실행 중 발견된 후속 수정 (코드 품질 리뷰 반영):** 위 구현대로 커밋한 뒤 품질 리뷰에서 두 가지가 지적되어 같은 태스크 안에서 바로 고쳤다:
1. 건수 0건(shipments 없음) 분기의 `"matched": False`는 "grand_total을 못 찾음"(`None`)과 의미가 겹쳐 혼동을 줄 수 있음 → `"matched": None`으로 변경 (0건일 때 어차피 `main`이 `shipment_count == 0`을 먼저 확인하고 넘어가므로 동작에는 영향 없음).
2. `matched: False`(진짜 불일치) 경로를 검증하는 `process_pdf` 테스트가 없었음 → `test_process_pdf_returns_false_matched_when_grand_total_disagrees` 추가.
3. `process_pdf`에 tri-state(`True`/`False`/`None`) 계약을 설명하는 짧은 docstring 추가.

추가 커밋: `refactor: use None sentinel for matched when no comparison possible, add disagreement test coverage`
**최종 테스트 수: 14 passed** (아래 Task 7의 "13 passed" 관련 서술은 이 최종 수치인 14를 기준으로 읽을 것).

---

### Task 7: CLI 진입점 (`main`)

**Files:**
- Modify: `extract.py`
- Test: `tests/test_extract.py`

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_extract.py`에 추가:

```python
from extract import main


def test_main_skips_non_pdf_files(tmp_path, capsys):
    txt_path = tmp_path / "메모.txt"
    txt_path.write_text("이건 PDF가 아님")

    main([str(txt_path)])

    captured = capsys.readouterr()
    assert "PDF 파일이 아닙니다" in captured.out


def test_main_reports_missing_file(capsys):
    main(["존재하지않는파일.pdf"])

    captured = capsys.readouterr()
    assert "찾을 수 없습니다" in captured.out


def test_main_prints_success_summary(tmp_path, monkeypatch, capsys):
    pdf_path = tmp_path / "청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: SAMPLE_TWO_SHIPMENTS)

    main([str(pdf_path)])

    captured = capsys.readouterr()
    assert "청구서.xlsx" in captured.out
    assert "2건" in captured.out


def test_main_warns_when_zero_shipments_found(tmp_path, monkeypatch, capsys):
    pdf_path = tmp_path / "빈청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: "관련 없는 텍스트")

    main([str(pdf_path)])

    captured = capsys.readouterr()
    assert "추출된 건이 없습니다" in captured.out


def test_main_shows_skipped_validation_when_grand_total_missing(tmp_path, monkeypatch, capsys):
    pdf_path = tmp_path / "청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: SAMPLE_TWO_SHIPMENTS)

    main([str(pdf_path)])

    captured = capsys.readouterr()
    assert "검증 생략" in captured.out
```

- [x] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `ImportError: cannot import name 'main' from 'extract'`

- [x] **Step 3: 최소 구현 작성**

`extract.py`에 추가:

```python
import sys


def main(argv):
    if not argv:
        print("사용법: python extract.py <PDF파일...>")
        return

    for arg in argv:
        path = Path(arg)

        if path.suffix.lower() != ".pdf":
            print(f"[건너뜀] PDF 파일이 아닙니다: {path.name}")
            continue

        if not path.exists():
            print(f"[오류] 파일을 찾을 수 없습니다: {path}")
            continue

        try:
            result = process_pdf(path)
        except Exception as exc:
            print(f"[오류] {path.name} 처리 중 문제가 발생했습니다: {exc}")
            continue

        if result["shipment_count"] == 0:
            print(f"[경고] {path.name}: 추출된 건이 없습니다. PDF 양식을 확인하세요.")
            continue

        if result["grand_total"] is None:
            status = "검증 생략 (Grand Total 미발견)"
        elif result["matched"]:
            status = "일치"
        else:
            status = "⚠ 불일치"
        print(
            f"[완료] {path.name} → {result['output_path'].name} "
            f"({result['shipment_count']}건, 합계 검증: {status})"
        )


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [x] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (19 passed) — Task 6이 14개로 끝났으므로 14 + 5(Task 7에서 추가되는 테스트) = 19

- [x] **Step 5: 커밋**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: add CLI entry point with per-file error handling"
```

---

### Task 8: 드래그&드롭 배치파일

**Files:**
- Create: `변환.bat`

- [x] **Step 1: 배치파일 작성**

`변환.bat`:

```bat
@echo off
setlocal
python "%~dp0extract.py" %*
echo.
pause
```

`%~dp0`은 이 배치파일이 위치한 폴더 경로이므로, 어느 위치에서 드래그&드롭하든 같은 폴더의 `extract.py`를 정확히 찾는다. `%*`는 드롭된 모든 파일 경로를 그대로 전달한다(공백 포함 경로는 Windows 탐색기가 자동으로 따옴표 처리해서 넘겨준다).

- [x] **Step 2: 커밋**

```bash
git add 변환.bat
git commit -m "feat: add drag-and-drop batch entry point"
```

---

### Task 9: 실제 샘플 PDF로 수동 통합 테스트

자동화 테스트는 합성 데이터로만 이루어졌으므로, 실제 청구서 PDF 형식과 정말 맞는지 마지막으로 검증한다. `FEDEX인보이스.pdf`는 `.gitignore`에 포함되어 있어 저장소에는 없지만 로컬 `C:\Users\USER\DEV\SCM_pdf\`에 존재한다.

- [x] **Step 1: 커맨드라인으로 직접 실행**

Run: `python extract.py FEDEX인보이스.pdf`
Expected: `[완료] FEDEX인보이스.pdf → FEDEX인보이스.xlsx (29건, 합계 검증: 일치)`

- [x] **Step 2: 생성된 엑셀 육안 확인**

`FEDEX인보이스.xlsx`를 열어:
- 29개 데이터 행 + 헤더 + 합계 행 = 31행인지 확인
- 첫 번째 행이 `05/27/2026 / 872265794268 / 585440.00`인지 원본 PDF 2페이지와 대조
- 마지막 합계 행이 `7834180.00`인지 확인 (경고 행이 없어야 함)

- [x] **Step 3: 배치파일로 드래그&드롭 실행**

`FEDEX인보이스.pdf` 파일을 `변환.bat` 위로 드래그&드롭
Expected: 콘솔 창이 열리고 Step 1과 동일한 완료 메시지가 출력된 뒤 `계속하려면 아무 키나 누르십시오...`로 대기

- [x] **Step 4: 생성된 xlsx 정리**

`FEDEX인보이스.xlsx`는 `.gitignore`에 걸려 있어 커밋 대상이 아니다. 그대로 두거나 삭제해도 무방하며 git 상태에는 영향 없음을 `git status`로 확인.

Run: `git status`
Expected: `nothing to commit, working tree clean` (xlsx는 untracked로도 나타나지 않음)

---

## 향후 확장 (이번 계획 범위 밖)

- 고정 마감 양식에 값 채워넣기
- 누적 파일에 추가하는 방식
- Freight/Deductions/Other Charges 등 상세 항목 추출
