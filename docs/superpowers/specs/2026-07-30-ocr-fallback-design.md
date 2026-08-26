# 스캔 PDF OCR 폴백 설계

## 배경 및 목적

`fedex운송비.pdf`(2026년 8월분 청구서)를 처리했더니 "추출 실패"가 떴다. 진단 결과, 이 파일은 텍스트 레이어가 전혀 없는 스캔 이미지 PDF였다 (11페이지 전부 문자(char) 객체 0개, 페이지마다 이미지 객체 2개). 문서 자체는 지금까지 처리해온 것과 똑같은 FedEx 청구서 양식(건별 상세 포함)이므로, OCR로 텍스트를 읽어내면 처리할 수 있다.

## 실제 진단 결과 (구현 전 확인됨)

- Tesseract 5.5.3(x64)가 이미 이 PC에 설치되어 있음 (`C:\Program Files\Tesseract-OCR\`), `kor.traineddata`/`eng.traineddata` 포함.
- 300dpi로 렌더링 후 OCR 시 페이지당 약 6~7초 소요 (11페이지 PDF 기준 약 1분+).
- 1페이지(요약) OCR 품질: 청구서 종류, Grand Total, 건수 등 핵심 숫자는 상당히 정확하게 읽힘. 한글은 부분적으로 깨짐.
- 2페이지(건별 상세) OCR 테스트 결과, 기존 정규식 3개 모두 문제 발생:
  - `AWB 번호 Air Waybill Number` → OCR에서 `Air WaybillNumber`(공백 소실)로 나와 기존 정규식(`Air Waybill Number `, 공백 1칸 고정)이 매치 안 됨.
  - `선적일자 Ship Date` → 라벨과 날짜 사이에 원본 PDF 열 정렬로 인한 다중 공백이 그대로 OCR됨 → 공백 1칸 고정 정규식이 매치 안 됨.
  - **`합계Total`(건별 합계 라벨)** → 실제 테스트 3건 모두 다르게 깨짐: `& AI Total`, `합 계7아리`, `= AlTotal`. 한글 "합계" 인식이 매우 불안정해서 이 라벨에 의존하는 매칭은 신뢰할 수 없음.

이 결과를 바탕으로 사용자와 논의해 다음을 결정함:
- 건별 합계는 OCR 모드에서 한글 라벨을 버리고 **영문 "Total"만으로 느슨하게** 찾는다 (오탐 위험이 있지만, 기존 Grand Total 대조 검증이 안전장치 역할을 함).
- OCR은 텍스트 추출이 0건일 때만 자동으로 재시도한다.
- 1분 이상 걸릴 수 있으므로 GUI에 간단한 진행 상황 표시를 추가한다.

## 범위

- `process_pdf`가 1차(pdfplumber) 텍스트 추출으로 건수 0건이면 자동으로 OCR 재시도
- OCR 전용 느슨한 정규식(영문 라벨/다중 공백 허용, 건별 합계는 "Total"만으로 매칭)
- Tesseract를 exe에 번들링해 최종 사용자 PC에 별도 설치 불필요
- GUI에 OCR 처리 중임을 보여주는 간단한 진행 창 추가
- 결과 메시지에 OCR로 처리된 파일 표시(정확도 낮을 수 있음을 사용자가 인지하도록)
- 기존 텍스트 추출 경로(정규식, `parse_shipments`, CLI `main()`)의 동작은 전혀 변경하지 않음 — OCR은 실패했을 때만 개입하는 폴백

## 아키텍처

```
extract_pdf_text(pdf) → parse_shipments(text) → 0건?
   0건 아님 → 기존 결과 그대로 사용 (지금까지와 동일)
   0건    → ocr_pdf_text(pdf, on_page=...) → parse_shipments_lenient(text) → 이 결과 사용, used_ocr=True
```

`parse_shipments`(기존, 엄격한 정규식)와 `parse_shipments_lenient`(신규, OCR용 느슨한 정규식)는 같은 상태 기계(날짜+AWB를 먼저 찾고 Total을 만나면 한 건 완성) 로직을 공유하도록 내부 헬퍼로 리팩터링한다. 기존 정규식 상수(`SHIP_DATE_RE`, `AWB_RE`, `TOTAL_RE`)와 `parse_shipments`의 동작·기존 29개 테스트는 전혀 바뀌지 않는다.

## 구성 요소

### 1. `extract.py`

- **느슨한 정규식 상수 추가** (기존 상수는 그대로 유지):
  - `SHIP_DATE_LENIENT_RE = re.compile(r'Ship Date\s+(\d{2}/\d{2}/\d{4})')`
  - `AWB_LENIENT_RE = re.compile(r'Air Waybill\s*Number\s+(\d+)')`
  - `TOTAL_LENIENT_RE = re.compile(r'Total\s+([\d,]+\.\d{2})')` (한글 라벨 없이 영문 "Total"만)
- **`_parse_shipments_with_patterns(text, date_re, awb_re, total_re)`**: 기존 `parse_shipments`의 상태 기계 로직을 이 헬퍼로 옮기고, `parse_shipments`와 `parse_shipments_lenient` 둘 다 이 헬퍼를 정규식만 다르게 호출하도록 리팩터링.
- **`parse_shipments_lenient(text)`**: `_parse_shipments_with_patterns`를 `*_LENIENT_RE`로 호출.
- **`_tesseract_cmd_path()`**: 개발 환경(로컬 설치된 Tesseract)과 빌드된 exe(번들된 Tesseract) 양쪽에서 올바른 `tesseract.exe` 경로를 찾는 헬퍼. `sys.frozen`이면 `sys._MEIPASS` 기준 번들 경로, 아니면 로컬 설치 경로(`C:\Program Files\Tesseract-OCR\tesseract.exe`) 또는 PATH.
- **`ocr_pdf_text(pdf_path, on_page=None)`**: pdfplumber로 각 페이지를 300dpi 이미지로 렌더링 → `pytesseract.image_to_string(image, lang='kor+eng')`. 페이지 처리 전후로 `on_page(현재_페이지_번호, 전체_페이지_수)` 호출(전달됐을 때만). 전체 페이지 텍스트를 줄바꿈으로 합쳐 반환.
- **`process_pdf` 수정**: 1차 `parse_shipments(text)`가 빈 리스트면 `ocr_pdf_text`로 재시도하고 `parse_shipments_lenient`로 파싱. 결과 딕셔너리에 `"used_ocr": bool` 키 추가. `on_ocr_page` 콜백 파라미터를 받아 `ocr_pdf_text`에 그대로 전달.

### 2. Tesseract 번들링 (`build.bat`)

로컬에 설치된 `C:\Program Files\Tesseract-OCR\` 폴더 전체를 PyInstaller `--add-data`로 exe에 포함시킨다 (필요한 dll이 매우 많아 개별 지정 대신 폴더째 포함하는 것이 안전). 정확히 어떤 하위 파일까지 포함할지(용량 절감을 위한 불필요 파일 제외 등)는 구현 중 실제 빌드 테스트로 조정한다.

### 3. `gui.py`

- `process_pdfs_for_gui(pdf_paths, output_dir, on_ocr_page=None)`: 새 콜백 파라미터를 받아 `process_pdf`에 그대로 전달(여전히 tkinter 비의존, 테스트 가능).
- `run_gui`: OCR이 시작되면(진행 콜백이 처음 호출되면) 작은 `Toplevel` 진행 창을 띄워 "OCR로 처리 중: <파일명> (N/전체 페이지)"를 표시하고 페이지마다 갱신, 끝나면 닫는다. 별도 스레드 없이 콜백 안에서 `root.update()`를 호출해 창이 응답하도록 한다 (페이지당 갱신 주기가 수 초라 스레드 없이도 "멈춘 것처럼" 보이지 않음).
- `format_summary_message`: `success`/`mismatched` 파일명 중 `used_ocr=True`인 것은 뒤에 "(OCR)" 표시를 붙여, 정확도가 낮을 수 있음을 알 수 있게 한다.

## 데이터 흐름

```
사용자가 exe 실행 → PDF 선택 → 저장 폴더 선택
   → 각 PDF:
       extract_pdf_text → parse_shipments
       → 0건이면: 진행 창 표시 → ocr_pdf_text(콜백으로 진행창 갱신) → parse_shipments_lenient
       → build_workbook → output_dir에 저장
   → 결과 집계(OCR 처리 여부 포함) → 메시지박스 표시
```

## 에러 처리

- 기존 규칙(파일 하나 실패해도 계속 진행, 0건이면 추출 실패로 분류)은 그대로 유지 — OCR까지 시도했는데도 0건이면 최종적으로 "추출 실패".
- OCR 자체가 예외를 던지면(Tesseract 실행 실패 등) 기존 `process_pdfs_for_gui`의 파일 단위 예외 처리에 그대로 걸려 "오류"로 분류됨 (기존 동작 재사용, 추가 코드 불필요).
- 정확도 안전장치는 새로 만들지 않고 **기존 Grand Total 대조 검증을 그대로 재사용**한다 — OCR로 잘못 읽힌 금액이 있으면 합계가 안 맞아 `matched=False`(⚠ 불일치)로 표시되어 사용자가 알아챌 수 있다.

## 테스트 계획

- `parse_shipments_lenient`: 공백이 여러 개인 라벨, "Total"만 있는(한글 라벨 없는) 합계 줄 등 OCR 스타일 텍스트로 단위 테스트.
- 기존 `parse_shipments`와 그 25개 테스트는 리팩터링 후에도 변경 없이 통과해야 함 (헬퍼 추출은 순수 리팩터링).
- `ocr_pdf_text`, `process_pdf`의 OCR 폴백 분기: `pytesseract`/`pdfplumber`를 `monkeypatch`로 대체해 "1차 0건 → OCR 호출됨 → 그 결과 사용" 흐름을 자동 테스트 (실제 OCR은 호출하지 않음).
- `on_page`/`on_ocr_page` 콜백이 올바른 인자로 호출되는지 fake 콜백으로 검증.
- 실제 Tesseract 번들링·정확도는 Task 9 때처럼 실제 스캔 PDF(`fedex운송비.pdf`)로 빌드된 exe를 수동 검증한다 — 특히 실제로 몇 건이 추출되는지, Grand Total과 맞는지, 진행 창이 뜨는지, 콘솔 없이 동작하는지.

## 향후 확장 (지금은 범위 밖)

- OCR 정확도 개선(전처리, 다른 OCR 엔진, 좌표 기반 추출 등)
- 사용자가 수동으로 OCR 모드를 강제 지정하는 옵션
- exe 용량 최적화 (Tesseract 번들 크기 축소)
