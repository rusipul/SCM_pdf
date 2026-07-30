# GUI 파일 선택 + 실행 파일(exe) 패키징 설계

## 배경 및 목적

기존 `변환.bat`(드래그&드롭)은 개발자에게는 편하지만, 실제 사용자는 컴맹이라 드래그&드롭이나 Python 설치를 요구하는 방식이 부담스럽다. 파일 탐색기 스타일의 "파일 선택" 대화상자로 PDF를 고르고, 결과를 저장할 폴더도 고를 수 있게 하며, 최종적으로는 Python 설치 여부와 상관없이 더블클릭 한 번으로 실행되는 단일 `.exe` 파일로 배포한다.

## 범위

- PDF 파일을 파일 선택 대화상자에서 여러 개 선택 가능
- 결과 xlsx를 저장할 폴더를 별도 대화상자에서 선택 가능 (기존에는 항상 PDF와 같은 폴더에 저장)
- 처리 후 결과(성공/불일치/추출실패/오류 건수)를 메시지박스 한 번으로 요약 표시
- 콘솔(터미널) 창 없이 GUI만 뜨도록 함
- Python이 설치되지 않은 PC에서도 실행 가능한 단일 `.exe`로 패키징
- 기존 `변환.bat`과 콘솔 기반 CLI(`extract.py`의 `main()`)는 삭제/변경하지 않고 그대로 유지 — GUI는 새로운 별도 진입점으로 추가되며, `변환.bat`만 삭제 대상

## 아키텍처

```
FedEx인보이스변환.exe (PyInstaller로 gui.py를 패키징한 결과물)
   더블클릭
      → PDF 파일 선택 대화상자 (여러 개 선택 가능, 취소 시 조용히 종료)
      → 저장 폴더 선택 대화상자 (취소 시 조용히 종료)
      → 선택된 PDF들을 순서대로 process_pdf(path, output_dir=...) 호출
      → 결과 집계 → 메시지박스 한 번으로 요약 표시
```

`gui.py`는 tkinter 기반이며, **다이얼로그를 직접 다루는 부분(`run_gui`)**과 **순수 로직(여러 파일 처리 결과 집계, 메시지 문구 생성)**을 분리한다. tkinter 다이얼로그는 자동화 테스트가 사실상 불가능하므로, 테스트는 순수 로직 함수들에 대해서만 작성한다.

## 구성 요소

### 1. `extract.py` (기존 파일 수정)

`process_pdf(pdf_path, output_dir=None)` — `output_dir` 파라미터 추가. `None`이면 기존과 동일하게 PDF와 같은 폴더에 저장 (기존 CLI 동작과 28개 기존 테스트에 영향 없음). 값이 주어지면 그 폴더에 `<PDF 이름>.xlsx`로 저장.

### 2. `gui.py` (신규)

- `process_pdfs_for_gui(pdf_paths, output_dir) -> dict`: 각 PDF에 대해 `process_pdf`를 호출하고, 파일명을 성공/불일치/추출실패(0건)/오류 네 그룹으로 분류해 딕셔너리로 반환. tkinter에 의존하지 않는 순수 함수 — 단위 테스트 대상.
- `format_summary_message(summary: dict) -> str`: 위 분류 결과를 사람이 읽을 메시지 문자열로 변환 (예: `"완료: 3건 / 전체 3건"`, 불일치·오류 파일명 나열). 역시 순수 함수 — 단위 테스트 대상.
- `run_gui()`: tkinter `Tk()` 루트 생성(숨김) → `filedialog.askopenfilenames`로 PDF 선택 → `filedialog.askdirectory`로 저장 폴더 선택 → `process_pdfs_for_gui` 호출 → `format_summary_message`로 문구 생성 → `messagebox.showinfo`로 표시. 자동 테스트 대상이 아님(수동 검증).

### 3. 빌드 관련 (신규)

- `requirements-dev.txt`: `pyinstaller` (빌드 시에만 필요, 최종 사용자에게는 불필요)
- `build.bat`: `pyinstaller --onefile --windowed --name "FedEx인보이스변환" gui.py`를 실행하는 한 줄짜리 빌드 스크립트
- `.gitignore`에 `build/`, `dist/`, `*.spec` 추가 (PyInstaller가 생성하는 산출물·중간 파일은 커밋 대상이 아님)

### 4. `변환.bat` 삭제

GUI로 대체되므로 제거한다.

## 데이터 흐름

```
사용자가 FedEx인보이스변환.exe 더블클릭
   → PDF 선택 (여러 개 가능) → 취소 시 종료
   → 저장 폴더 선택 → 취소 시 종료
   → 각 PDF: extract_pdf_text → parse_shipments/parse_grand_total → build_workbook
     → 지정된 output_dir에 저장
   → 결과 집계 → 메시지박스 1회 표시
```

## 에러 처리

기존 CLI(`main`)와 동일한 규칙을 따른다:
- 한 파일 처리 중 예외가 발생해도 나머지 파일은 계속 처리하고, 해당 파일은 "오류"로 분류
- 추출된 건수가 0건이면 "추출 실패"로 분류 (파일 자체는 건너뜀, xlsx 생성 안 함)
- 합계 불일치(`matched is False`)는 "불일치"로 별도 분류
- Grand Total을 못 찾아 검증을 못 한 경우(`matched is None`)는 "완료"로 집계하되 검증 여부는 별도로 언급하지 않음 (메시지박스가 너무 길어지지 않도록 단순화 — CLI의 "검증 생략" 문구는 GUI 요약에는 포함하지 않는다)

## 테스트 계획

- `process_pdfs_for_gui`, `format_summary_message`: 기존 `process_pdf`를 `monkeypatch`로 대체해 순수 로직을 자동 테스트 (성공/불일치/추출실패/오류 각 케이스)
- `run_gui()` 자체는 자동 테스트하지 않음 — 대신 실제로 `build.bat`을 실행해 exe를 만들고, 실제 샘플 PDF로 다음을 수동 검증:
  - exe가 Python 설치 여부와 무관하게(별도 venv 등에서) 실행되는지
  - 파일 선택 → 폴더 선택 → 처리 → 메시지박스까지 전체 흐름이 정상 동작하는지
  - pdfplumber/openpyxl 등 의존 라이브러리가 exe에 정상적으로 포함되어 PDF 처리가 실제로 되는지 (PyInstaller가 간혹 일부 패키지의 바이너리 의존성을 누락하는 경우가 있어 반드시 실물 확인 필요)
  - 콘솔 창이 뜨지 않는지

## 향후 확장 (지금은 범위 밖)

- exe에 아이콘 적용
- 설치 프로그램(인스톨러) 형태로 배포
- 처리 진행률을 보여주는 진행 표시줄
