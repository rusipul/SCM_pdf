from pathlib import Path

from extract import process_pdf


def process_pdfs_for_gui(pdf_paths, output_dir):
    summary = {"success": [], "mismatched": [], "empty": [], "failed": []}
    for pdf_path in pdf_paths:
        path = Path(pdf_path)
        try:
            result = process_pdf(path, output_dir=output_dir)
        except Exception as exc:
            summary["failed"].append(f"{path.name}: {exc}")
            continue
        if result["shipment_count"] == 0:
            summary["empty"].append(path.name)
        elif result["matched"] is False:
            summary["mismatched"].append(path.name)
        else:
            summary["success"].append(path.name)
    return summary
