"""
cli_app.py
터미널 기반 PDF 표 편집기 인터페이스
"""

import os
import sys

# 프로젝트 루트를 sys.path에 추가 (VSCode 등 외부 실행 환경 대응)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pdf_core import PDFReader, TableParser, PDFWriter


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def hr():
    print("─" * 60)


def print_table(table, highlight_row=None, highlight_col=None):
    """표를 터미널에 보기 좋게 출력"""
    data = table.to_display()
    if not data:
        print("  (빈 표)")
        return

    # 열 너비 계산
    col_widths = []
    for c in range(table.cols):
        w = max(len(str(row[c])) if c < len(row) else 0 for row in data)
        col_widths.append(max(w, 4))

    # 헤더 행 번호 출력
    header = "     " + " | ".join(f"[{c+1}열]".ljust(col_widths[c]) for c in range(table.cols))
    print(header)
    hr()

    for r_idx, row in enumerate(data):
        prefix = f"[{r_idx+1}행] "
        cells = []
        for c_idx, cell in enumerate(row):
            text = str(cell).ljust(col_widths[c_idx])
            if r_idx == highlight_row and c_idx == highlight_col:
                text = f"*{text.strip()}*".ljust(col_widths[c_idx])
            cells.append(text)
        print(prefix + " | ".join(cells))


def run_cli():
    print("=" * 60)
    print("   PDF 표 편집기 (CLI 모드)")
    print("=" * 60)

    # ── PDF 파일 입력 ───────────────────────────────
    while True:
        pdf_path = input("\nPDF 파일 경로를 입력하세요: ").strip().strip('"')
        if os.path.isfile(pdf_path):
            break
        print(f"  [오류] 파일을 찾을 수 없습니다: {pdf_path}")

    reader = PDFReader(pdf_path)
    try:
        reader.open()
    except IOError as e:
        print(f"[오류] {e}")
        return

    print("\n표를 감지하는 중...")
    tables = reader.extract_tables()

    if not tables:
        print("[안내] 이 PDF에서 표를 찾지 못했습니다.")
        reader.close()
        return

    print(f"  총 {len(tables)}개의 표를 찾았습니다.\n")
    parser = TableParser(tables)

    # ── 메인 루프 ───────────────────────────────────
    while True:
        print("\n[메뉴]")
        print("  1. 표 직접 선택 후 셀 편집")
        print("  2. 찾아바꾸기")
        print("  3. 수정 내역 확인")
        print("  4. 저장 후 종료")
        print("  0. 저장 없이 종료")
        choice = input("선택: ").strip()

        if choice == "1":
            _direct_edit(parser, tables)

        elif choice == "2":
            _find_replace(parser)

        elif choice == "3":
            _show_records(parser)

        elif choice == "4":
            _save(reader, parser, pdf_path)
            break

        elif choice == "0":
            print("저장하지 않고 종료합니다.")
            break
        else:
            print("  올바른 번호를 입력하세요.")

    reader.close()


def _direct_edit(parser: TableParser, tables):
    """직접 선택 편집 서브메뉴"""
    print("\n── 표 목록 ──────────────────────────")
    for t in tables:
        print(f"  [{t.table_index + 1}] "
              f"페이지 {t.page_number + 1} | "
              f"{t.rows}행 × {t.cols}열")
    hr()

    try:
        t_no = int(input("편집할 표 번호: ")) - 1
        table = next((t for t in tables if t.table_index == t_no), None)
        if table is None:
            print("  [오류] 없는 표 번호입니다.")
            return
    except ValueError:
        print("  [오류] 숫자를 입력하세요.")
        return

    print(f"\n── 표 {t_no + 1} 내용 ──────────────────────")
    print_table(table)

    try:
        row = int(input("\n수정할 행 번호: ")) - 1
        col = int(input("수정할 열 번호: ")) - 1
    except ValueError:
        print("  [오류] 숫자를 입력하세요.")
        return

    cell = table.get_cell(row, col)
    if cell is None:
        print("  [오류] 해당 셀이 없습니다.")
        return

    print(f"\n  현재 값: \"{cell.text}\"")
    new_val = input("  새 값 입력: ").strip()

    record = parser.edit_cell(t_no, row, col, new_val)
    if record:
        print(f"  ✓ 수정 완료: \"{record.old_text}\" → \"{record.new_text}\"")
    else:
        print("  [오류] 수정에 실패했습니다.")


def _find_replace(parser: TableParser):
    """찾아바꾸기 서브메뉴"""
    print("\n── 찾아바꾸기 ──────────────────────────")
    keyword = input("찾을 값: ").strip()
    if not keyword:
        print("  [안내] 검색어를 입력해야 합니다.")
        return

    case_sensitive = input("대소문자 구분? (y/N): ").strip().lower() == "y"
    exact_match = input("정확히 일치하는 셀만? (y/N): ").strip().lower() == "y"

    results = parser.search(keyword, case_sensitive, exact_match)

    if not results:
        print(f"  \"{keyword}\"을(를) 찾지 못했습니다.")
        return

    print(f"\n  총 {len(results)}개 항목 발견:\n")
    for i, r in enumerate(results):
        print(f"    [{i + 1}] {r.label()}")

    print("\n  a. 전체 교체")
    print("  s. 항목 선택 후 교체")
    print("  0. 취소")
    action = input("선택: ").strip().lower()

    if action == "0":
        return

    new_text = input("바꿀 값: ").strip()

    if action == "a":
        records = parser.replace_all(keyword, new_text, case_sensitive, exact_match)
        print(f"  ✓ {len(records)}개 항목을 교체했습니다.")

    elif action == "s":
        raw = input("교체할 번호 입력 (예: 1,3,5): ").strip()
        try:
            indices = [int(x.strip()) - 1 for x in raw.split(",")]
            selected = [results[i] for i in indices if 0 <= i < len(results)]
        except (ValueError, IndexError):
            print("  [오류] 올바른 번호를 입력하세요.")
            return
        records = parser.replace_selected(
            selected, new_text, keyword, case_sensitive, exact_match
        )
        print(f"  ✓ {len(records)}개 항목을 교체했습니다.")
    else:
        print("  취소했습니다.")


def _show_records(parser: TableParser):
    """수정 내역 출력"""
    summary = parser.get_edit_summary()
    if not summary:
        print("\n  아직 수정된 내용이 없습니다.")
        return
    print(f"\n── 수정 내역 ({len(summary)}건) ─────────────────")
    for line in summary:
        print(f"  {line}")


def _save(reader: PDFReader, parser: TableParser, source_path: str):
    """저장 처리"""
    if not parser.edit_records:
        print("\n  수정된 내용이 없습니다.")
        return

    # 기본 출력 파일명 제안
    base, ext = os.path.splitext(source_path)
    default_out = base + "_수정본" + ext
    out = input(f"\n저장할 파일 경로 (Enter = {default_out}): ").strip().strip('"')
    if not out:
        out = default_out

    writer = PDFWriter(reader.get_fitz_doc(), source_path)
    count = writer.apply_edits(parser.edit_records)
    writer.save(out)
    print(f"\n  ✓ {count}개 셀이 교체된 PDF를 저장했습니다.")
    print(f"  저장 경로: {out}")


if __name__ == "__main__":
    run_cli()
