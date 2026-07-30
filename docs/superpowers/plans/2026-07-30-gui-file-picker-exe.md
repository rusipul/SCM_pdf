# GUI 파일 선택 + 실행 파일(exe) 패키징 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 컴맹 사용자가 Python 설치 없이 더블클릭 한 번으로 실행할 수 있는 `.exe`를 만든다 — PDF 여러 개를 파일 선택창에서 고르고, 저장 폴더도 고른 뒤, 메시지박스로 결과를 확인하는 tkinter GUI.

**Architecture:** `extract.py`의 `process_pdf`에 `output_dir` 파라미터를 추가해 저장 위치를 바꿀 수 있게 하고, 새 `gui.py`에 tkinter 다이얼로그를 다루는 `run_gui()`와 tkinter에 의존하지 않는 순수 로직(`process_pdfs_for_gui`, `format_summary_message`)을 분리한다. 순수 로직만 자동 테스트하고, `run_gui()`와 최종 exe는 PyInstaller로 빌드한 뒤 수동으로 검증한다.

**Tech Stack:** Python 3.14 표준 라이브러리 tkinter (filedialog, messagebox), PyInstaller (빌드 전용, 최종 사용자에게는 불필요)

---

## 파일 구조

- `extract.py` (기존 파일 수정) — `process_pdf`에 `output_dir` 파라미터 추가
- `gui.py` (신규) — `process_pdfs_for_gui`(순수 로직), `format_summary_message`(순수 로직), `run_gui`(tkinter 다이얼로그)
- `tests/test_gui.py` (신규) — `gui.py`의 순수 로직 테스트
- `requirements-dev.txt` (신규) — PyInstaller (빌드 전용 의존성)
- `build.bat` (신규) — PyInstaller로 exe 빌드하는 스크립트
- `.gitignore` (기존 파일 수정) — 빌드 산출물(`build/`, `dist/`, `*.spec`) 추가
- `변환.bat` (기존 파일 삭제) — GUI로 대체되어 제거

---

### Task 1: `extract.py`의 `process_pdf`에 `output_dir` 파라미터 추가

**Files:**
- Modify: `extract.py:69-101`
- Test: `tests/test_extract.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_extract.py`의 다른 `test_process_pdf_*` 테스트들 근처에 추가:

```python
def test_process_pdf_saves_to_specified_output_dir(tmp_path, monkeypatch):
    pdf_path = tmp_path / "청구서.pdf"
    pdf_path.write_bytes(b"%PDF-fake")
    output_subdir = tmp_path / "결과"
    output_subdir.mkdir()
    monkeypatch.setattr(extract, "extract_pdf_text", lambda path: SAMPLE_TWO_SHIPMENTS)

    result = process_pdf(pdf_path, output_dir=output_subdir)

    expected_path = output_subdir / "청구서.xlsx"
    assert result["output_path"] == expected_path
    assert expected_path.exists()
    assert not (tmp_path / "청구서.xlsx").exists()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_extract.py::test_process_pdf_saves_to_specified_output_dir -v`
Expected: FAIL with `TypeError: process_pdf() got an unexpected keyword argument 'output_dir'`

- [ ] **Step 3: 최소 구현 작성**

`extract.py:69-101`의 `process_pdf` 함수를 아래로 교체 (docstring과 `output_path` 계산 부분만 변경, 나머지 로직은 동일):

```python
def process_pdf(pdf_path, output_dir=None):
    """Returns matched=True if grand_total agrees with the extracted sum,
    False if it disagrees, or None if no comparison could be made (no
    grand_total present, or no shipments found). Saves the xlsx next to
    pdf_path unless output_dir is given, in which case it saves there."""
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
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (29 passed — 기존 28개 + 새 테스트 1개. `output_dir` 기본값이 `None`이라 `pdf_path.parent / (pdf_path.stem + ".xlsx")`는 기존 `pdf_path.with_suffix(".xlsx")`와 동일한 경로를 만들어내므로 기존 28개 테스트는 코드 변경 없이 그대로 통과한다.)

- [ ] **Step 5: 커밋**

```bash
git add extract.py tests/test_extract.py
git commit -m "feat: add output_dir parameter to process_pdf"
```

---

### Task 2: `gui.py` — `process_pdfs_for_gui` (순수 로직)

PDF 여러 개를 처리하고 파일명을 성공/불일치/추출실패/오류 네 그룹으로 분류한다. tkinter에 의존하지 않으므로 `extract.process_pdf`를 `monkeypatch`로 대체해 테스트한다 (기존 `tests/test_extract.py`가 `extract.extract_pdf_text`를 patch하던 것과 같은 패턴).

**Files:**
- Create: `gui.py`
- Create: `tests/test_gui.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_gui.py` 신규 생성:

```python
import gui
from gui import process_pdfs_for_gui


def _fake_result(shipment_count=2, matched=True):
    return {
        "output_path": None,
        "shipment_count": shipment_count,
        "extracted_sum": 100.0,
        "grand_total": 100.0,
        "matched": matched,
    }


def test_process_pdfs_for_gui_classifies_success(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, output_dir=None: _fake_result(matched=True),
    )

    summary = process_pdfs_for_gui(["a.pdf", "b.pdf"], tmp_path)

    assert summary == {"success": ["a.pdf", "b.pdf"], "mismatched": [], "empty": [], "failed": []}


def test_process_pdfs_for_gui_classifies_mismatched(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, output_dir=None: _fake_result(matched=False),
    )

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["mismatched"] == ["a.pdf"]


def test_process_pdfs_for_gui_treats_none_matched_as_success(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, output_dir=None: _fake_result(matched=None),
    )

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["success"] == ["a.pdf"]


def test_process_pdfs_for_gui_classifies_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, output_dir=None: _fake_result(shipment_count=0, matched=None),
    )

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["empty"] == ["a.pdf"]


def test_process_pdfs_for_gui_classifies_failed(monkeypatch, tmp_path):
    def raise_error(path, output_dir=None):
        raise ValueError("broken")

    monkeypatch.setattr(gui, "process_pdf", raise_error)

    summary = process_pdfs_for_gui(["a.pdf"], tmp_path)

    assert summary["failed"] == ["a.pdf"]


def test_process_pdfs_for_gui_uses_filename_not_full_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, output_dir=None: _fake_result(),
    )

    summary = process_pdfs_for_gui([str(tmp_path / "청구서.pdf")], tmp_path)

    assert summary["success"] == ["청구서.pdf"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_gui.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gui'` (아직 `gui.py`가 없음)

- [ ] **Step 3: 최소 구현 작성**

`gui.py` 신규 생성:

```python
from pathlib import Path

from extract import process_pdf


def process_pdfs_for_gui(pdf_paths, output_dir):
    summary = {"success": [], "mismatched": [], "empty": [], "failed": []}
    for pdf_path in pdf_paths:
        path = Path(pdf_path)
        try:
            result = process_pdf(path, output_dir=output_dir)
        except Exception:
            summary["failed"].append(path.name)
            continue
        if result["shipment_count"] == 0:
            summary["empty"].append(path.name)
        elif result["matched"] is False:
            summary["mismatched"].append(path.name)
        else:
            summary["success"].append(path.name)
    return summary
```

**중요:** 테스트에서 `monkeypatch.setattr(gui, "process_pdf", ...)`로 모듈 속성을 대체하므로, `process_pdfs_for_gui` 내부에서는 `process_pdf(path, output_dir=output_dir)`를 모듈 전역 이름 그대로 호출해야 patch가 적용된다. `from extract import process_pdf`로 가져온 이름이 `gui` 모듈의 전역 네임스페이스에 바인딩되므로, 위 구현처럼 작성하면 자동으로 만족된다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_gui.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add gui.py tests/test_gui.py
git commit -m "feat: add process_pdfs_for_gui to classify batch results"
```

**실행 중 발견된 후속 수정 (코드 품질 리뷰 반영):** 위 구현대로 커밋한 뒤, exe는 `--windowed`(콘솔 없음)로 빌드되므로 오류 발생 시 사용자가 원인을 전혀 알 수 없다는 지적이 있었다. `except Exception:` → `except Exception as exc:`로, `summary["failed"].append(path.name)` → `summary["failed"].append(f"{path.name}: {exc}")`로 변경 (기존 CLI `main()`의 `print(f"... {exc}")` 패턴과 동일하게 맞춤). `failed`는 여전히 `list[str]`이므로 이후 태스크(`format_summary_message`)의 처리 방식은 바뀌지 않는다.

`test_process_pdfs_for_gui_classifies_failed`의 마지막 단언도 `assert summary["failed"] == ["a.pdf: broken"]`로 갱신됨.

추가 커밋: `fix: include exception message in failed-file classification`
**최종 테스트 수: `tests/test_gui.py` 6개, `tests/test_extract.py` 29개 (합계 35개).**

---

### Task 3: `gui.py` — `format_summary_message` (순수 로직)

**Files:**
- Modify: `gui.py`
- Test: `tests/test_gui.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_gui.py`에 추가:

```python
from gui import format_summary_message


def test_format_summary_message_all_success():
    summary = {"success": ["a.pdf", "b.pdf"], "mismatched": [], "empty": [], "failed": []}

    message = format_summary_message(summary)

    assert "완료: 2건 / 전체 2건" in message


def test_format_summary_message_includes_mismatched_names():
    summary = {"success": [], "mismatched": ["a.pdf"], "empty": [], "failed": []}

    message = format_summary_message(summary)

    assert "불일치" in message
    assert "a.pdf" in message


def test_format_summary_message_includes_empty_names():
    summary = {"success": [], "mismatched": [], "empty": ["a.pdf"], "failed": []}

    message = format_summary_message(summary)

    assert "a.pdf" in message


def test_format_summary_message_includes_failed_names():
    summary = {"success": [], "mismatched": [], "empty": [], "failed": ["a.pdf"]}

    message = format_summary_message(summary)

    assert "오류" in message
    assert "a.pdf" in message


def test_format_summary_message_omits_empty_categories():
    summary = {"success": ["a.pdf"], "mismatched": [], "empty": [], "failed": []}

    message = format_summary_message(summary)

    assert "불일치" not in message
    assert "오류" not in message
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_gui.py -v`
Expected: FAIL with `ImportError: cannot import name 'format_summary_message' from 'gui'`

- [ ] **Step 3: 최소 구현 작성**

`gui.py`에 추가:

```python
def format_summary_message(summary):
    total = sum(len(names) for names in summary.values())
    completed = len(summary["success"]) + len(summary["mismatched"])
    lines = [f"완료: {completed}건 / 전체 {total}건"]
    if summary["mismatched"]:
        lines.append(f"⚠ 합계 불일치: {', '.join(summary['mismatched'])}")
    if summary["empty"]:
        lines.append(f"건너뜀(추출 실패): {', '.join(summary['empty'])}")
    if summary["failed"]:
        lines.append(f"오류: {', '.join(summary['failed'])}")
    return "\n".join(lines)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_gui.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: 커밋**

```bash
git add gui.py tests/test_gui.py
git commit -m "feat: add format_summary_message for GUI result display"
```

---

### Task 4: `gui.py` — `run_gui` (tkinter 다이얼로그)

tkinter 다이얼로그는 실제 화면과 사용자 입력에 의존하므로 자동화 테스트를 작성하지 않는다 (Task 2/3에서 이미 그 내부 로직은 테스트했다). Task 9에서 실제 빌드된 exe로 수동 검증한다.

**Files:**
- Modify: `gui.py`

- [ ] **Step 1: 구현 작성**

`gui.py`의 기존 `from pathlib import Path` 아래에 import 한 줄 추가:

```python
from tkinter import Tk, filedialog, messagebox
```

`gui.py` 맨 아래에 추가:

```python
def run_gui():
    root = Tk()
    root.withdraw()

    pdf_paths = filedialog.askopenfilenames(
        title="FedEx 청구서 PDF 선택",
        filetypes=[("PDF 파일", "*.pdf")],
    )
    if not pdf_paths:
        root.destroy()
        return

    output_dir = filedialog.askdirectory(title="결과 파일을 저장할 폴더 선택")
    if not output_dir:
        root.destroy()
        return

    summary = process_pdfs_for_gui(pdf_paths, output_dir)
    message = format_summary_message(summary)
    messagebox.showinfo("처리 결과", message)
    root.destroy()


if __name__ == "__main__":
    run_gui()
```

최종 `gui.py`는 이 순서로 구성된다: import들 → `process_pdfs_for_gui` → `format_summary_message` → `run_gui` → `if __name__ == "__main__":` 블록.

- [ ] **Step 2: 기존 테스트가 깨지지 않았는지 확인**

Run: `python -m pytest tests/test_gui.py tests/test_extract.py -v`
Expected: PASS (11 + 29 = 40 passed)

- [ ] **Step 3: 커밋**

```bash
git add gui.py
git commit -m "feat: add run_gui tkinter entry point"
```

---

### Task 5: `변환.bat` 삭제

GUI(`gui.py`, 이후 exe)로 대체되므로 기존 드래그&드롭 배치파일은 제거한다.

**Files:**
- Delete: `변환.bat`

- [ ] **Step 1: 파일 삭제 및 커밋**

```bash
git rm 변환.bat
git commit -m "chore: remove drag-and-drop batch file, replaced by GUI"
```

---

### Task 6: `requirements-dev.txt` — PyInstaller 설치

**Files:**
- Create: `requirements-dev.txt`

- [ ] **Step 1: PyInstaller 설치**

Run: `pip install pyinstaller`
Expected: 설치 성공 메시지와 함께 종료 (이미 설치돼 있다면 `Requirement already satisfied`)

- [ ] **Step 2: 설치된 정확한 버전 확인**

Run: `pip show pyinstaller`
Expected: `Name: pyinstaller` 와 `Version: X.Y.Z` 출력 — 이 버전 번호를 다음 단계에서 사용한다.

- [ ] **Step 3: `requirements-dev.txt` 작성**

Step 2에서 확인한 실제 버전 번호로 아래 형식에 맞춰 파일을 만든다 (예시이며, 실제 설치된 버전으로 `X.Y.Z`를 교체할 것):

```
pyinstaller==X.Y.Z
```

- [ ] **Step 4: 커밋**

```bash
git add requirements-dev.txt
git commit -m "chore: add PyInstaller as a build-only dependency"
```

---

### Task 7: `build.bat` — exe 빌드 스크립트

**Files:**
- Create: `build.bat`

- [ ] **Step 1: 배치파일 작성**

`build.bat`:

```bat
@echo off
setlocal
pip install -r requirements-dev.txt
pyinstaller --onefile --windowed --name "FedEx인보이스변환" gui.py
echo.
echo 빌드 완료: dist\FedEx인보이스변환.exe
pause
```

- [ ] **Step 2: 커밋**

```bash
git add build.bat
git commit -m "feat: add build.bat to package gui.py into a standalone exe"
```

---

### Task 8: `.gitignore`에 빌드 산출물 추가

PyInstaller는 `build/`(중간 산출물), `dist/`(최종 exe), `*.spec`(자동 생성 설정 파일)을 만든다. 모두 코드로부터 재생성 가능하고 용량이 크므로 커밋 대상이 아니다.

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: 현재 `.gitignore` 확인**

Run: `cat .gitignore`
Expected:
```
*.pdf
*.xlsx
__pycache__/
*.pyc
```

- [ ] **Step 2: 빌드 산출물 항목 추가**

`.gitignore`를 아래 내용으로 교체:

```
*.pdf
*.xlsx
__pycache__/
*.pyc
build/
dist/
*.spec
```

- [ ] **Step 3: 커밋**

```bash
git add .gitignore
git commit -m "chore: ignore PyInstaller build artifacts"
```

---

### Task 9: 실제 빌드 + 수동 통합 테스트

자동화 테스트는 순수 로직(`process_pdfs_for_gui`, `format_summary_message`)만 검증했다. `run_gui()`와 exe 패키징 자체는 실제로 빌드하고 실행해서 확인해야 한다 — 특히 PyInstaller가 pdfplumber의 바이너리 의존성(pypdfium2 등)을 제대로 포함했는지는 실행해보기 전에는 알 수 없다.

**Files:** 없음 (수동 검증만)

- [ ] **Step 1: 빌드 실행**

Run: `build.bat` (더블클릭 또는 `.\build.bat`)
Expected: 에러 없이 종료되고 `dist\FedEx인보이스변환.exe` 파일이 생성됨

Run: `dir dist\FedEx인보이스변환.exe`
Expected: 파일이 존재함 (수십 MB 크기가 정상)

- [ ] **Step 2: 실제 샘플 PDF로 exe 실행**

`FEDEX인보이스.pdf`(로컬에 있는 실제 샘플, git에는 없음)를 프로젝트 폴더가 아닌 다른 임시 폴더에 복사해둔 뒤:

`dist\FedEx인보이스변환.exe`를 더블클릭

Expected:
- 검은 콘솔 창 없이 파일 선택창만 뜸
- 복사해둔 PDF를 선택 → 저장 폴더 선택창이 뜸 → 임의의 폴더 선택
- 잠시 후 메시지박스로 `완료: 1건 / 전체 1건` 표시
- 지정한 폴더에 `FEDEX인보이스.xlsx`가 생성되어 있고, 열어보면 29개 행 + 헤더 + 합계 행이 정상적으로 들어있음 (이전 CLI 통합 테스트 때와 동일한 내용)

- [ ] **Step 3: 문제 발생 시 대응**

`ModuleNotFoundError`나 pdfplumber/pypdfium2 관련 오류가 exe 실행 중 발생하면, PyInstaller가 해당 패키지의 바이너리를 자동으로 못 찾은 것이다. `build.bat`의 pyinstaller 명령에 `--collect-all pypdfium2` 옵션을 추가해 다시 빌드:

```bat
pyinstaller --onefile --windowed --name "FedEx인보이스변환" --collect-all pypdfium2 gui.py
```

수정한 옵션이 실제로 문제를 해결하면 `build.bat`을 이 옵션이 포함된 버전으로 갱신하고 커밋한다.

- [ ] **Step 4: 취소 동작 확인**

exe를 다시 실행해서 파일 선택창에서 "취소"를 눌러봄
Expected: 아무 메시지박스도 뜨지 않고 조용히 종료됨 (프로세스가 남아있지 않아야 함)

- [ ] **Step 5: 결과 보고**

Step 1-4를 모두 통과했다면 완료. Step 3에서 `build.bat`을 수정했다면 그 변경사항이 커밋되어 있는지 `git status`로 확인.
