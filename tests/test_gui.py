import gui
from gui import process_pdfs_for_gui, format_summary_message


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

    assert summary["failed"] == ["a.pdf: broken"]


def test_process_pdfs_for_gui_uses_filename_not_full_path(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gui, "process_pdf",
        lambda path, output_dir=None: _fake_result(),
    )

    summary = process_pdfs_for_gui([str(tmp_path / "청구서.pdf")], tmp_path)

    assert summary["success"] == ["청구서.pdf"]


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
