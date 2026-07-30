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
