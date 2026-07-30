from pathlib import Path
from tkinter import Tk, filedialog, messagebox

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


def format_summary_message(summary):
    total = sum(len(names) for names in summary.values())
    completed = len(summary["success"]) + len(summary["mismatched"])
    lines = [f"완료: {completed}건 / 전체 {total}건"]
    if summary["mismatched"]:
        lines.append(f"⚠ 합계 불일치: {', '.join(summary['mismatched'])}")
    if summary["empty"]:
        lines.append(f"건너뜀(추출 실패): {', '.join(summary['empty'])}")
    if summary["failed"]:
        lines.append("오류:\n  " + "\n  ".join(summary["failed"]))
    return "\n".join(lines)


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
