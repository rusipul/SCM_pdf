# 스캔 PDF OCR 폴백 Implementation Plan

> **⚠ 보류 (사용 안 함) — 2026-08-27**
> 최종적으로 OCR 기능은 도입하지 않기로 결정함 (사유는 `docs/superpowers/specs/2026-07-30-ocr-fallback-design.md` 상단 참고 — 건별 합계 라벨 OCR 인식 불안정). **이 계획은 실행되지 않았다.** 아래 태스크들은 하나도 구현되지 않은 상태이며, 참고용으로만 남겨둔다. 이 계획을 실행하라는 지시를 받더라도 먼저 사용자에게 위 결정이 여전히 유효한지 확인할 것.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 텍스트 레이어가 없는 스캔 PDF(예: `fedex운송비.pdf`)를 자동으로 OCR(Tesseract)로 재시도해서 처리할 수 있게 한다.

**Architecture:** `process_pdf`가 1차 텍스트 추출로 0건이면 `ocr_pdf_text`(pdfplumber로 페이지를 이미지화 → Tesseract OCR)를 자동 호출하고, OCR 전용 느슨한 정규식(`parse_shipments_lenient`)으로 다시 파싱한다. 기존 엄격한 경로(`parse_shipments`, 기존 정규식)는 전혀 건드리지 않는다 — 상태 기계 로직만 내부 헬퍼로 공유한다. GUI는 OCR이 오래 걸릴 수 있으므로(페이지당 약 6~7초) 간단한 진행 창을 띄운다. Tesseract는 exe에 통째로 번들링해 최종 사용자 PC에 별도 설치가 필요 없게 한다.

**Tech Stack:** pytesseract 0.3.13 (Tesseract 5.5.3 래퍼, 로컬에 이미 설치됨), pdfplumber의 페이지 이미지 렌더링(`page.to_image()`, 내부적으로 pypdfium2 사용, 이미 설치됨)

---

## 파일 구조

- `extract.py` (기존 파일 수정) — 리팩터링(상태 기계 공유), 느슨한 정규식 + `parse_shipments_lenient`, `_tesseract_cmd_path`, `ocr_pdf_text`, `process_pdf`에 OCR 폴백 추가
- `gui.py` (기존 파일 수정) — `process_pdfs_for_gui`에 `on_ocr_page` 콜백 전달 + OCR 처리 표시, `run_gui`에 진행 창 추가
- `requirements.txt` (기존 파일 수정) — `pytesseract` 추가 (런타임 의존성)
- `build.bat` (기존 파일 수정) — Tesseract-OCR 폴더 번들링 + `requirements.txt` 설치 단계 추가
- `tests/test_extract.py`, `tests/test_gui.py` (기존 파일 수정) — 새 함수 테스트 + 기존 테스트 중 영향받는 것 갱신

---

### Task 1: `parse_shipments`를 공유 헬퍼로 리팩터링 (동작 변경 없음)

이후 태스크에서 만들 `parse_shipments_lenient`가 같은 상태 기계 로직(날짜+AWB를 먼저 찾고 Total을 만나면 한 건 완성)을 재사용할 수 있도록, 정규식만 파라미터로 받는 내부 헬퍼로 분리한다. **정규식 상수도 동작도 전혀 바뀌지 않는다** — 순수 리팩터링이므로 새 테스트 없이 기존 테스트로만 검증한다.

**Files:**
- Modify: `extract.py:17-44`

- [ ] **Step 1: 리팩터링 전 기존 테스트 기준선 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (29 passed — 리팩터링 전이므로 기존 테스트 그대로. 만약 다른 숫자가 나오면 잘못된 브랜치 상태이니 먼저 확인할 것.)

- [ ] **Step 2: `extract.py:17-44`를 아래로 교체**

기존:
```python
SHIP_DATE_RE = re.compile(r'Ship Date (\d{2}/\d{2}/\d{4})')
AWB_RE = re.compile(r'Air Waybill Number (\d+)')
TOTAL_RE = re.compile(r'합계Total ([\d,]+\.\d{2})')


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
        total_match = TOTAL_RE.search(line)
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

새 코드:
```python
SHIP_DATE_RE = re.compile(r'Ship Date (\d{2}/\d{2}/\d{4})')
AWB_RE = re.compile(r'Air Waybill Number (\d+)')
TOTAL_RE = re.compile(r'합계Total ([\d,]+\.\d{2})')


def _parse_shipments_with_patterns(text, date_re, awb_re, total_re):
    shipments = []
    current_date = None
    current_awb = None
    for line in text.splitlines():
        date_match = date_re.search(line)
        if date_match:
            current_date = date_match.group(1)
            continue
        awb_match = awb_re.search(line)
        if awb_match:
            current_awb = awb_match.group(1)
            continue
        total_match = total_re.search(line)
        if total_match and current_date and current_awb:
            shipments.append({
                "ship_date": current_date,
                "awb_number": current_awb,
                "total": float(total_match.group(1).replace(',', '')),
            })
            current_date = None
            current_awb = None
    return shipments


def parse_shipments(text):
    return _parse_shipments_with_patterns(text, SHIP_DATE_RE, AWB_RE, TOTAL_RE)
```

- [ ] **Step 3: 리팩터링 후 기존 테스트가 그대로 통과하는지 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (29 passed — Step 1과 정확히 같은 숫자. 하나라도 실패하면 리팩터링이 동작을 바꾼 것이므로 되돌아가서 확인할 것.)

- [ ] **Step 4: 커밋**

```bash
git add extract.py
git commit -m "refactor: extract shared state machine for shipment parsing"
```

---

### Task 2: OCR용 느슨한 파싱 (`parse_shipments_lenient`)

**Files:**
- Modify: `extract.py` (Task 1에서 만든 `_parse_shipments_with_patterns` 아래에 추가)
- Test: `tests/test_extract.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract.py`에 추가 (파일 안 아무 곳이나, 예를 들어 `SAMPLE_TWO_SHIPMENTS` 정의 아래):

```python
from extract import parse_shipments_lenient


def test_parse_shipments_lenient_extracts_when_awb_number_has_no_space_and_ship_date_has_extra_spaces():
    # 실제 OCR 결과 재현: "Air Waybill Number"가 "Air WaybillNumber"로,
    # "Ship Date"와 값 사이에 원본 PDF 열 정렬로 인한 다중 공백이 그대로 남음
    text = (
        "선적일자 Ship Date                  07/21/2026                    발송인 Sender\n"
        "AWB 번호 Air WaybillNumber 874651036480               SHIN JONG SUN\n"
        "& AI Total                                                                                                    206,960.00\n"
    )
    result = parse_shipments_lenient(text)
    assert result == [
        {"ship_date": "07/21/2026", "awb_number": "874651036480", "total": 206960.00},
    ]


def test_parse_shipments_lenient_matches_total_merged_with_ocr_noise():
    # 실제 OCR에서 "합계Total"이 "= AlTotal"로 깨졌지만 "Total"이라는 글자는 남아있던 사례
    text = (
        "선적일자 Ship Date 07/24/2026 발송인 Sender\n"
        "AWB 번호 Air WaybillNumber 874821355682 SHIN JONG SUN\n"
        "= AlTotal                                                                                                    206,960.00\n"
    )
    result = parse_shipments_lenient(text)
    assert result == [
        {"ship_date": "07/24/2026", "awb_number": "874821355682", "total": 206960.00},
    ]


def test_parse_shipments_lenient_cannot_recover_total_when_ocr_drops_english_word_entirely():
    # 알려진 한계: 실제 OCR에서 "합계Total"이 "합 계7아리"처럼 영문 "Total"조차
    # 남지 않을 정도로 깨진 경우, 느슨한 정규식으로도 복구 불가능하다.
    # 이런 건은 Grand Total 대조 검증(matched=False)이 안전장치 역할을 한다.
    text = (
        "선적일자 Ship Date 07/23/2026 발송인 Sender\n"
        "AWB 번호 Air Waybill Number 874762219119 CHLOE HAN\n"
        "합 계7아리                                                                                                      96,930.00\n"
    )
    assert parse_shipments_lenient(text) == []


def test_parse_shipments_lenient_skips_total_without_preceding_awb():
    text = "Total 1,000.00\n"
    assert parse_shipments_lenient(text) == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_shipments_lenient' from 'extract'`

- [ ] **Step 3: 최소 구현 작성**

`extract.py`의 `parse_shipments` 함수 아래에 추가:

```python
SHIP_DATE_LENIENT_RE = re.compile(r'Ship Date\s+(\d{2}/\d{2}/\d{4})')
AWB_LENIENT_RE = re.compile(r'Air Waybill\s*Number\s+(\d+)')
TOTAL_LENIENT_RE = re.compile(r'Total\s+([\d,]+\.\d{2})')


def parse_shipments_lenient(text):
    return _parse_shipments_with_patterns(
        text, SHIP_DATE_LENIENT_RE, AWB_LENIENT_RE, TOTAL_LENIENT_RE
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (33 passed — 기존 29개 + 새 테스트 4개)

- [ ] **Step 5: 커밋**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: add lenient shipment parsing for OCR text"
```

---

### Task 3: Tesseract 경로 탐색 (`_tesseract_cmd_path`)

**Files:**
- Modify: `requirements.txt`
- Modify: `extract.py`
- Test: `tests/test_extract.py`

- [ ] **Step 1: 설치된 pytesseract 버전 확인**

Run: `pip show pytesseract`
Expected: `Name: pytesseract`, `Version: 0.3.13` (이미 설치되어 있음)

- [ ] **Step 2: `requirements.txt`에 추가**

`requirements.txt`를 아래로 교체:

```
pdfplumber==0.11.10
openpyxl==3.1.5
pytest==9.1.1
pytesseract==0.3.13
```

- [ ] **Step 3: 실패하는 테스트 작성**

`tests/test_extract.py`에 추가:

```python
def test_tesseract_cmd_path_uses_bundled_path_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    result = extract._tesseract_cmd_path()

    assert result == str(tmp_path / "Tesseract-OCR" / "tesseract.exe")


def test_tesseract_cmd_path_uses_local_install_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    result = extract._tesseract_cmd_path()

    assert result == r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `AttributeError: module 'extract' has no attribute '_tesseract_cmd_path'`

- [ ] **Step 5: 최소 구현 작성**

`extract.py` 맨 위 import 블록을 아래로 교체 (`import pytesseract` 한 줄 추가):

```python
import re
import sys
from pathlib import Path
import pdfplumber
import pytesseract
from openpyxl import Workbook
```

`extract.py`의 `parse_shipments_lenient` 함수 아래에 추가:

```python
def _tesseract_cmd_path():
    if getattr(sys, "frozen", False):
        return str(Path(sys._MEIPASS) / "Tesseract-OCR" / "tesseract.exe")
    return r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (35 passed — 기존 33개 + 새 테스트 2개)

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt extract.py tests/test_extract.py
git commit -m "feat: add tesseract binary path resolution for dev and frozen builds"
```

---

### Task 4: OCR 텍스트 추출 (`ocr_pdf_text`)

pdfplumber로 페이지를 이미지로 렌더링한 뒤 Tesseract로 OCR한다. 실제 PDF 렌더링과 실제 Tesseract 실행이 필요해 자동 테스트가 사실상 불가능하다 (기존 `extract_pdf_text`도 같은 이유로 자동 테스트가 없다) — Task 9에서 실제 스캔 PDF로 수동 검증한다.

**Files:**
- Modify: `extract.py`

- [ ] **Step 1: 구현 작성**

`extract.py`의 `_tesseract_cmd_path` 함수 아래에 추가:

```python
def ocr_pdf_text(pdf_path, on_page=None):
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd_path()
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages, start=1):
            if on_page:
                on_page(i, total_pages)
            image = page.to_image(resolution=300).original
            texts.append(pytesseract.image_to_string(image, lang="kor+eng"))
    return "\n".join(texts)
```

- [ ] **Step 2: 기존 테스트가 깨지지 않았는지 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (35 passed — 변경 없음, import만 추가됐으므로 그대로 통과해야 함)

- [ ] **Step 3: 커밋**

```bash
git add extract.py
git commit -m "feat: add OCR text extraction via pdfplumber page rendering and tesseract"
```

---

### Task 5: `process_pdf`에 OCR 자동 폴백 추가

1차 텍스트 추출으로 0건이면 자동으로 `ocr_pdf_text`를 호출해 재시도한다. 결과에 `used_ocr` 필드를 추가한다.

**중요:** 기존 테스트 중 `extract_pdf_text`를 "관련 없는 텍스트"(0건이 나오는 텍스트)로 mock하는 테스트 2개는, 이 변경 후 `ocr_pdf_text`도 자동으로 호출되므로 `ocr_pdf_text`까지 함께 mock해주지 않으면 실제 PDF 렌더링을 시도하다 깨진다. 이 태스크에서 그 2개를 같이 고친다.

**Files:**
- Modify: `extract.py` (`process_pdf` 함수)
- Modify: `tests/test_extract.py` (`test_process_pdf_skips_file_when_no_shipments_found`, `test_main_warns_when_zero_shipments_found` — 기존 테스트 수정)
- Test: `tests/test_extract.py` (신규 테스트 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract.py`에 추가 (예: `test_process_pdf_saves_to_specified_output_dir` 근처):

```python
def test_process_pdf_falls_back_to_ocr_when_text_extraction_finds_nothing(tmp_path, monkeypatch):
    pdf_path = tmp_path / "스캔청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: "텍스트 레이어 없음")
    monkeypatch.setattr(extract, "ocr_pdf_text", lambda path, on_page=None: SAMPLE_TWO_SHIPMENTS)

    result = process_pdf(pdf_path)

    assert result["shipment_count"] == 2
    assert result["used_ocr"] is True


def test_process_pdf_does_not_call_ocr_when_text_extraction_succeeds(tmp_path, monkeypatch):
    pdf_path = tmp_path / "청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: SAMPLE_TWO_SHIPMENTS)

    def fail_if_called(path, on_page=None):
        raise AssertionError("텍스트 추출이 성공했으면 ocr_pdf_text는 호출되면 안 됨")

    monkeypatch.setattr(extract, "ocr_pdf_text", fail_if_called)

    result = process_pdf(pdf_path)

    assert result["shipment_count"] == 2
    assert result["used_ocr"] is False


def test_process_pdf_reports_zero_shipments_when_ocr_also_finds_nothing(tmp_path, monkeypatch):
    pdf_path = tmp_path / "빈청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: "관련 없는 텍스트")
    monkeypatch.setattr(extract, "ocr_pdf_text", lambda path, on_page=None: "그래도 관련 없는 텍스트")

    result = process_pdf(pdf_path)

    assert result["shipment_count"] == 0
    assert result["used_ocr"] is False


def test_process_pdf_passes_on_ocr_page_callback_through_to_ocr_pdf_text(tmp_path, monkeypatch):
    pdf_path = tmp_path / "스캔청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: "텍스트 레이어 없음")

    received = {}

    def fake_ocr(path, on_page=None):
        received["on_page"] = on_page
        return SAMPLE_TWO_SHIPMENTS

    monkeypatch.setattr(extract, "ocr_pdf_text", fake_ocr)

    def my_callback(current, total):
        pass

    process_pdf(pdf_path, on_ocr_page=my_callback)

    assert received["on_page"] is my_callback
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `TypeError: process_pdf() got an unexpected keyword argument 'on_ocr_page'` (그리고 `used_ocr` 관련 `KeyError`/`AssertionError`도 함께 발생)

- [ ] **Step 3: `process_pdf` 수정**

`extract.py`의 `process_pdf` 함수 전체를 아래로 교체:

```python
def process_pdf(pdf_path, output_dir=None, on_ocr_page=None):
    """Returns matched=True if grand_total agrees with the extracted sum,
    False if it disagrees, or None if no comparison could be made (no
    grand_total present, or no shipments found). Saves the xlsx next to
    pdf_path unless output_dir is given, in which case it saves there.
    If normal text extraction finds no shipments, automatically retries
    via OCR (used_ocr=True in the result if that's what produced the
    shipments actually used)."""
    pdf_path = Path(pdf_path)
    text = extract_pdf_text(pdf_path)
    shipments = parse_shipments(text)
    used_ocr = False

    if not shipments:
        ocr_text = ocr_pdf_text(pdf_path, on_page=on_ocr_page)
        ocr_shipments = parse_shipments_lenient(ocr_text)
        if ocr_shipments:
            text = ocr_text
            shipments = ocr_shipments
            used_ocr = True

    grand_total = parse_grand_total(text)

    if not shipments:
        return {
            "output_path": None,
            "shipment_count": 0,
            "extracted_sum": 0.0,
            "grand_total": grand_total,
            "matched": None,
            "used_ocr": used_ocr,
        }

    wb, extracted_sum = build_workbook(shipments, grand_total)
    target_dir = Path(output_dir) if output_dir is not None else pdf_path.parent
    output_path = target_dir / (pdf_path.stem + ".xlsx")
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
        "used_ocr": used_ocr,
    }
```

- [ ] **Step 4: 실제 I/O를 시도하다 깨지는 기존 테스트 2개 수정**

`tests/test_extract.py`의 `test_process_pdf_skips_file_when_no_shipments_found`를 아래로 교체:

```python
def test_process_pdf_skips_file_when_no_shipments_found(tmp_path, monkeypatch):
    pdf_path = tmp_path / "빈청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: "관련 없는 텍스트")
    monkeypatch.setattr(extract, "ocr_pdf_text", lambda path, on_page=None: "관련 없는 텍스트")

    result = process_pdf(pdf_path)

    assert result["shipment_count"] == 0
    assert result["output_path"] is None
    assert not (tmp_path / "빈청구서.xlsx").exists()
```

`tests/test_extract.py`의 `test_main_warns_when_zero_shipments_found`를 아래로 교체:

```python
def test_main_warns_when_zero_shipments_found(tmp_path, monkeypatch, capsys):
    pdf_path = tmp_path / "빈청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: "관련 없는 텍스트")
    monkeypatch.setattr(extract, "ocr_pdf_text", lambda path, on_page=None: "관련 없는 텍스트")

    main([str(pdf_path)])

    captured = capsys.readouterr()
    assert "추출된 건이 없습니다" in captured.out
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (39 passed — 기존 35개 + 새 테스트 4개)

- [ ] **Step 6: 커밋**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: automatically retry with OCR when text extraction finds no shipments"
```

---

### Task 6: `gui.py` — OCR 폴백 연동 + 결과 표시에 OCR 여부 반영

`process_pdfs_for_gui`가 `on_ocr_page` 콜백을 받아 `process_pdf`로 그대로 전달하고, OCR로 처리된 파일은 이름 뒤에 "(OCR)"을 붙여 반환한다 (그러면 `format_summary_message`는 수정 없이 그대로 동작한다 — 이미 문자열을 join할 뿐이므로).

**중요:** `process_pdf`의 시그니처가 `on_ocr_page` 파라미터를 받게 되어, `gui.process_pdf`를 patch하는 기존 테스트 6개의 가짜 함수들이 이 키워드 인자를 받지 않으면 `TypeError`가 난다. 이 태스크에서 기존 가짜 함수들을 전부 `**kwargs`를 받도록 고친다 (매번 새 키워드가 생길 때마다 고치지 않아도 되게).

**Files:**
- Modify: `gui.py` (`process_pdfs_for_gui` 함수)
- Modify: `tests/test_gui.py` (기존 가짜 함수 시그니처 6곳 + 신규 테스트)

- [ ] **Step 1: 기존 가짜 함수 시그니처를 `**kwargs`로 통일**

`tests/test_gui.py`에서 아래 6곳을 각각 교체한다 (전부 `lambda path, output_dir=None:` 또는 `def raise_error(path, output_dir=None):` 형태 → `**kwargs`로):

`test_process_pdfs_for_gui_classifies_success`:
```python
def test_process_pdfs_for_gui_classifies_success(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, **kwargs: _fake_result(matched=True),
    )

    summary = process_pdfs_for_gui(["a.pdf", "b.pdf"], tmp_path)

    assert summary == {"success": ["a.pdf", "b.pdf"], "mismatched": [], "empty": [], "failed": []}
```

`test_process_pdfs_for_gui_classifies_mismatched`:
```python
def test_process_pdfs_for_gui_classifies_mismatched(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, **kwargs: _fake_result(matched=False),
    )

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["mismatched"] == ["a.pdf"]
```

`test_process_pdfs_for_gui_treats_none_matched_as_success`:
```python
def test_process_pdfs_for_gui_treats_none_matched_as_success(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, **kwargs: _fake_result(matched=None),
    )

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["success"] == ["a.pdf"]
```

`test_process_pdfs_for_gui_classifies_empty`:
```python
def test_process_pdfs_for_gui_classifies_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, **kwargs: _fake_result(shipment_count=0, matched=None),
    )

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["empty"] == ["a.pdf"]
```

`test_process_pdfs_for_gui_classifies_failed`:
```python
def test_process_pdfs_for_gui_classifies_failed(monkeypatch, tmp_path):
    def raise_error(path, **kwargs):
        raise ValueError("broken")

    monkeypatch.setattr(gui, "process_pdf", raise_error)

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["failed"] == ["a.pdf: broken"]
```

`test_process_pdfs_for_gui_uses_filename_not_full_path`:
```python
def test_process_pdfs_for_gui_uses_filename_not_full_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, **kwargs: _fake_result(),
    )

    summary = process_pdfs_for_gui([str(tmp_path / "청구서.pdf")], tmp_path)

    assert summary["success"] == ["청구서.pdf"]
```

또한 `_fake_result` 헬퍼가 `used_ocr` 키를 포함하도록 교체 (기본값 `False`):

```python
def _fake_result(shipment_count=2, matched=True, used_ocr=False):
    return {
        "output_path": None,
        "shipment_count": shipment_count,
        "extracted_sum": 100.0,
        "grand_total": 100.0,
        "matched": matched,
        "used_ocr": used_ocr,
    }
```

- [ ] **Step 2: 여기까지 기존 테스트가 통과하는지 확인 (아직 신규 기능 구현 전)**

Run: `python -m pytest tests/test_gui.py -v`
Expected: PASS (12 passed — 시그니처만 바꿨고 `gui.py` 자체는 아직 안 건드렸으므로 그대로 통과)

- [ ] **Step 3: OCR 표시 실패하는 테스트 작성**

`tests/test_gui.py`에 추가:

```python
def test_process_pdfs_for_gui_tags_ocr_success_with_marker(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, **kwargs: _fake_result(matched=True, used_ocr=True),
    )

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["success"] == ["a.pdf (OCR)"]


def test_process_pdfs_for_gui_no_marker_when_ocr_not_used(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, **kwargs: _fake_result(matched=True, used_ocr=False),
    )

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["success"] == ["a.pdf"]


def test_process_pdfs_for_gui_passes_on_ocr_page_through_to_process_pdf(monkeypatch, tmp_path):
    received = {}

    def fake_process_pdf(path, output_dir=None, on_ocr_page=None):
        received["on_ocr_page"] = on_ocr_page
        return _fake_result()

    monkeypatch.setattr(gui, "process_pdf", fake_process_pdf)

    def my_callback(current, total):
        pass

    process_pdfs_for_gui(["a.pdf"], tmp_path, on_ocr_page=my_callback)

    assert received["on_ocr_page"] is my_callback
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `python -m pytest tests/test_gui.py -v`
Expected: FAIL — `test_process_pdfs_for_gui_tags_ocr_success_with_marker`는 `assert summary["success"] == ["a.pdf (OCR)"]`에서 실패 (아직 태그 안 붙임), `test_process_pdfs_for_gui_passes_on_ocr_page_through_to_process_pdf`는 `TypeError: process_pdfs_for_gui() got an unexpected keyword argument 'on_ocr_page'`

- [ ] **Step 5: `process_pdfs_for_gui` 구현 수정**

`gui.py`의 `process_pdfs_for_gui` 함수 전체를 아래로 교체:

```python
def process_pdfs_for_gui(pdf_paths, output_dir, on_ocr_page=None):
    summary = {"success": [], "mismatched": [], "empty": [], "failed": []}
    for pdf_path in pdf_paths:
        path = Path(pdf_path)
        try:
            result = process_pdf(path, output_dir=output_dir, on_ocr_page=on_ocr_page)
        except Exception as exc:
            summary["failed"].append(f"{path.name}: {exc}")
            continue
        label = f"{path.name} (OCR)" if result.get("used_ocr") else path.name
        if result["shipment_count"] == 0:
            summary["empty"].append(path.name)
        elif result["matched"] is False:
            summary["mismatched"].append(label)
        else:
            summary["success"].append(label)
    return summary
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python -m pytest tests/test_gui.py -v`
Expected: PASS (15 passed — 기존 12개 + 새 테스트 3개)

- [ ] **Step 7: 전체 테스트 확인**

Run: `python -m pytest tests/ -v`
Expected: PASS (54 passed — `test_extract.py` 39개 + `test_gui.py` 15개)

- [ ] **Step 8: 커밋**

```bash
git add gui.py tests/test_gui.py
git commit -m "feat: pass OCR progress callback through GUI layer and tag OCR results"
```

---

### Task 7: `gui.py` — OCR 진행 창

OCR은 페이지당 6~7초씩 걸릴 수 있어 아무 표시 없이 그대로 두면 멈춘 것처럼 보인다. 별도 스레드 없이, 콜백 안에서 `root.update()`를 호출해 작은 진행 창이 갱신되도록 한다. tkinter 창이라 자동 테스트 대상이 아니다 (Task 4의 `ocr_pdf_text`와 같은 이유) — Task 9에서 수동 검증한다.

**Files:**
- Modify: `gui.py` (`run_gui` 함수, import 구문)

- [ ] **Step 1: import 구문 수정**

`gui.py`의 기존 import 줄:
```python
from tkinter import Tk, filedialog, messagebox
```
을 아래로 교체:
```python
from tkinter import Tk, Toplevel, Label, filedialog, messagebox
```

- [ ] **Step 2: `run_gui` 함수 전체를 아래로 교체**

```python
def run_gui():
    root = Tk()
    root.withdraw()
    progress = {"window": None, "label": None}

    def on_ocr_page(current, total):
        if progress["window"] is None:
            window = Toplevel(root)
            window.title("처리 중")
            label = Label(window, text="", padx=20, pady=20)
            label.pack()
            progress["window"] = window
            progress["label"] = label
        progress["label"].config(text=f"OCR로 처리 중... ({current}/{total} 페이지)")
        root.update()

    try:
        pdf_paths = filedialog.askopenfilenames(
            title="FedEx 청구서 PDF 선택",
            filetypes=[("PDF 파일", "*.pdf")],
        )
        if not pdf_paths:
            return

        output_dir = filedialog.askdirectory(title="결과 파일을 저장할 폴더 선택")
        if not output_dir:
            return

        summary = process_pdfs_for_gui(pdf_paths, output_dir, on_ocr_page=on_ocr_page)
        message = format_summary_message(summary)
        messagebox.showinfo("처리 결과", message)
    except Exception as exc:
        messagebox.showerror("오류", f"예상치 못한 오류가 발생했습니다:\n{exc}")
    finally:
        if progress["window"] is not None:
            progress["window"].destroy()
        root.destroy()
```

- [ ] **Step 3: 기존 테스트가 깨지지 않았는지 확인**

Run: `python -m pytest tests/ -v`
Expected: PASS (54 passed — `run_gui`는 애초에 테스트 대상이 아니었으므로 변경 없음)

- [ ] **Step 4: 커밋**

```bash
git add gui.py
git commit -m "feat: show progress window during OCR processing"
```

---

### Task 8: `build.bat` — Tesseract 번들링

**Files:**
- Modify: `build.bat`

- [ ] **Step 1: `build.bat` 전체를 아래로 교체**

```bat
@echo off
setlocal
pip install -r requirements.txt
pip install -r requirements-dev.txt
rem charset-normalizer's mypyc-compiled extension (.pyd) is incompatible with
rem PyInstaller onefile builds (confirmed by an actual build test). Force a
rem reinstall of the pure-Python variant to work around it.
pip install --no-binary charset-normalizer --force-reinstall --no-deps charset-normalizer
pyinstaller --onefile --windowed --name FedExInvoiceConverter --add-data "C:\Program Files\Tesseract-OCR;Tesseract-OCR" gui.py
echo.
echo Build complete: dist\FedExInvoiceConverter.exe
pause
```

(`pip install -r requirements.txt` 줄을 추가한 이유: `pytesseract`가 이제 런타임 의존성인데, 기존 `build.bat`은 `requirements-dev.txt`만 설치했었다 — 이 환경엔 이미 다 설치되어 있어 지금까지는 문제가 없었지만, 다른 환경에서 빌드할 경우를 위해 명시적으로 설치하도록 함.)

- [ ] **Step 2: 커밋**

```bash
git add build.bat
git commit -m "feat: bundle Tesseract-OCR into the built exe"
```

---

### Task 9: 실제 스캔 PDF로 수동 검증

**Files:** 없음 (수동 검증만)

- [ ] **Step 1: 빌드 실행**

Run: `build.bat` (더블클릭 또는 `.\build.bat`)
Expected: 에러 없이 종료되고 `dist\FedExInvoiceConverter.exe` 생성됨. Tesseract 폴더 전체가 포함돼 있어 기존(103MB)보다 용량이 더 커질 것으로 예상됨 — 문제 없음.

- [ ] **Step 2: 커맨드라인으로 OCR 폴백 자체를 먼저 검증 (exe 빌드 전에 빠르게)**

Run:
```
python -c "import extract; r = extract.process_pdf('fedex운송비.pdf'); print(r['shipment_count'], r['used_ocr'], r['matched'])"
```
Expected: `used_ocr`가 `True`, `shipment_count`가 20건대(원본 28건 중 일부는 OCR 한계로 못 찾을 수 있음 — Task 2에서 확인한 "합 계7아리" 같은 완전히 깨진 라벨은 복구 불가), `matched`는 `True`/`False` 어느 쪽이든 나올 수 있음(합계가 안 맞으면 `False`가 정상 — OCR 특성상 자연스러운 결과). 생성된 `fedex운송비.xlsx`를 열어서 몇 건을 원본 PDF와 대조.

- [ ] **Step 3: exe로 전체 흐름 검증**

`fedex운송비.pdf`를 프로젝트 폴더 밖 임시 폴더에 복사한 뒤 `dist\FedExInvoiceConverter.exe` 더블클릭 → 그 PDF 선택 → 저장 폴더 선택

Expected:
- 콘솔 창 없이 파일 선택창만 뜸
- 처리 중 "OCR로 처리 중... (N/11 페이지)" 진행 창이 뜨고 갱신됨 (1분 정도 소요 예상)
- 완료 후 메시지박스에 "(OCR)" 표시가 붙은 결과가 보임
- 지정한 폴더에 `fedex운송비.xlsx` 생성 확인

- [ ] **Step 4: 문제 발생 시 대응**

Tesseract 관련 오류(`tesseract is not installed or it's not in your PATH` 등)가 exe 실행 중 발생하면, `--add-data`로 번들된 Tesseract 폴더 경로가 실제 압축 해제 위치와 다른 것이다. `extract._tesseract_cmd_path()`가 반환하는 경로와 `sys._MEIPASS` 하위 실제 폴더 구조를 비교해서 필요하면 `--add-data` 대상 경로명을 조정하고 재빌드.

- [ ] **Step 5: 기존 기능(텍스트 PDF) 회귀 확인**

Run: `python -c "import extract; r = extract.process_pdf('FEDEX인보이스.pdf'); print(r['shipment_count'], r['used_ocr'], r['matched'])"`
Expected: `29 False True` (기존처럼 OCR 없이 정상 처리 — OCR 폴백이 기존 경로에 영향 없음을 최종 확인)

- [ ] **Step 6: 결과 보고**

Step 1-5를 모두 통과했다면 완료. Step 4에서 코드를 수정했다면 커밋됐는지 `git status`로 확인.
