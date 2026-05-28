"""
gui_app.py
tkinter 기반 PDF 표 편집기 GUI
"""

import os
import sys

# 프로젝트 루트를 sys.path에 추가 (VSCode 등 외부 실행 환경 대응)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pdf_core import PDFReader, PDFWriter, SearchResult, TableParser


class PDFTableEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF 표 편집기")
        self.geometry("1000x700")
        self.minsize(800, 550)
        self.configure(bg="#f4f4f4")

        # 상태
        self.reader: PDFReader = None
        self.parser: TableParser = None
        self.tables = []
        self.current_table_index = None  # 현재 선택된 표 index
        self.source_path = ""

        self._build_ui()

    # ─────────────────────────────────────────────────
    # UI 구성
    # ─────────────────────────────────────────────────

    def _build_ui(self):
        # ── 상단: 파일 열기 바 ──────────────────────
        top_bar = tk.Frame(self, bg="#2c3e50", pady=6)
        top_bar.pack(fill=tk.X)

        tk.Label(
            top_bar,
            text="PDF 표 편집기",
            bg="#2c3e50",
            fg="white",
            font=("맑은 고딕", 13, "bold"),
        ).pack(side=tk.LEFT, padx=14)

        tk.Button(
            top_bar,
            text="📂  PDF 열기",
            command=self._open_pdf,
            bg="#3498db",
            fg="white",
            relief=tk.FLAT,
            padx=10,
            pady=3,
            font=("맑은 고딕", 10),
        ).pack(side=tk.LEFT, padx=6)

        self.file_label = tk.Label(
            top_bar,
            text="파일이 선택되지 않았습니다.",
            bg="#2c3e50",
            fg="#bdc3c7",
            font=("맑은 고딕", 9),
        )
        self.file_label.pack(side=tk.LEFT, padx=8)

        # ── 메인: 좌측 패널 + 우측 패널 ─────────────
        main = tk.Frame(self, bg="#f4f4f4")
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # 좌측: 표 목록 + 찾아바꾸기
        left = tk.Frame(main, bg="#f4f4f4", width=220)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        left.pack_propagate(False)
        self._build_left(left)

        # 우측: 표 내용 + 편집 영역
        right = tk.Frame(main, bg="#f4f4f4")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_right(right)

        # ── 하단: 상태바 ─────────────────────────────
        status_bar = tk.Frame(self, bg="#dfe6e9", pady=3)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="PDF 파일을 열어 시작하세요.")
        tk.Label(
            status_bar,
            textvariable=self.status_var,
            bg="#dfe6e9",
            font=("맑은 고딕", 9),
            anchor="w",
        ).pack(side=tk.LEFT, padx=10)

    def _build_left(self, parent):
        # 표 목록
        tk.Label(
            parent, text="감지된 표 목록", bg="#f4f4f4", font=("맑은 고딕", 10, "bold")
        ).pack(anchor="w", pady=(4, 2))

        list_frame = tk.Frame(parent, bg="#f4f4f4")
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.table_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("맑은 고딕", 9),
            selectmode=tk.SINGLE,
            activestyle="dotbox",
            relief=tk.FLAT,
            bg="white",
            bd=1,
        )
        self.table_listbox.pack(fill=tk.BOTH, expand=True)
        self.table_listbox.bind("<<ListboxSelect>>", self._on_table_select)
        scrollbar.config(command=self.table_listbox.yview)

        # 찾아바꾸기
        tk.Label(
            parent, text="찾아바꾸기", bg="#f4f4f4", font=("맑은 고딕", 10, "bold")
        ).pack(anchor="w", pady=(12, 2))

        fr_frame = tk.Frame(parent, bg="#f4f4f4")
        fr_frame.pack(fill=tk.X)

        tk.Label(fr_frame, text="찾을 값", bg="#f4f4f4", font=("맑은 고딕", 9)).grid(
            row=0, column=0, sticky="w"
        )
        self.search_var = tk.StringVar()
        tk.Entry(
            fr_frame, textvariable=self.search_var, width=20, font=("맑은 고딕", 9)
        ).grid(row=0, column=1, padx=4, pady=2)

        tk.Label(fr_frame, text="바꿀 값", bg="#f4f4f4", font=("맑은 고딕", 9)).grid(
            row=1, column=0, sticky="w"
        )
        self.replace_var = tk.StringVar()
        tk.Entry(
            fr_frame, textvariable=self.replace_var, width=20, font=("맑은 고딕", 9)
        ).grid(row=1, column=1, padx=4, pady=2)

        self.case_var = tk.BooleanVar()
        tk.Checkbutton(
            fr_frame,
            text="대소문자 구분",
            variable=self.case_var,
            bg="#f4f4f4",
            font=("맑은 고딕", 8),
        ).grid(row=2, column=0, columnspan=2, sticky="w")

        self.exact_var = tk.BooleanVar()
        tk.Checkbutton(
            fr_frame,
            text="정확히 일치",
            variable=self.exact_var,
            bg="#f4f4f4",
            font=("맑은 고딕", 8),
        ).grid(row=3, column=0, columnspan=2, sticky="w")

        btn_row = tk.Frame(parent, bg="#f4f4f4")
        btn_row.pack(fill=tk.X, pady=4)
        tk.Button(
            btn_row,
            text="검색",
            command=self._do_search,
            bg="#3498db",
            fg="white",
            relief=tk.FLAT,
            font=("맑은 고딕", 9),
            padx=6,
        ).pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="전체 교체",
            command=self._do_replace_all,
            bg="#e67e22",
            fg="white",
            relief=tk.FLAT,
            font=("맑은 고딕", 9),
            padx=6,
        ).pack(side=tk.LEFT, padx=4)

        # 검색 결과
        tk.Label(
            parent, text="검색 결과", bg="#f4f4f4", font=("맑은 고딕", 9, "bold")
        ).pack(anchor="w", pady=(8, 2))

        res_frame = tk.Frame(parent, bg="#f4f4f4")
        res_frame.pack(fill=tk.BOTH, expand=True)
        res_scroll = tk.Scrollbar(res_frame)
        res_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_listbox = tk.Listbox(
            res_frame,
            yscrollcommand=res_scroll.set,
            font=("맑은 고딕", 8),
            selectmode=tk.MULTIPLE,
            relief=tk.FLAT,
            bg="white",
            bd=1,
        )
        self.result_listbox.pack(fill=tk.BOTH, expand=True)
        res_scroll.config(command=self.result_listbox.yview)

        tk.Button(
            parent,
            text="선택 항목만 교체",
            command=self._do_replace_selected,
            bg="#8e44ad",
            fg="white",
            relief=tk.FLAT,
            font=("맑은 고딕", 9),
        ).pack(fill=tk.X, pady=2)

        self._search_results: list[SearchResult] = []

    def _build_right(self, parent):
        # 표 내용 Treeview
        tk.Label(
            parent,
            text="표 내용 (셀을 더블클릭하여 편집)",
            bg="#f4f4f4",
            font=("맑은 고딕", 10, "bold"),
        ).pack(anchor="w", pady=(4, 2))

        tree_frame = tk.Frame(parent, bg="white", relief=tk.SUNKEN, bd=1)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self._on_cell_double_click)

        # 편집 영역
        edit_frame = tk.Frame(parent, bg="#f4f4f4", pady=6)
        edit_frame.pack(fill=tk.X)

        tk.Label(edit_frame, text="현재 값:", bg="#f4f4f4", font=("맑은 고딕", 9)).grid(
            row=0, column=0, sticky="w", padx=4
        )
        self.old_val_label = tk.Label(
            edit_frame, text="—", bg="#f4f4f4", fg="#7f8c8d", font=("맑은 고딕", 9)
        )
        self.old_val_label.grid(row=0, column=1, sticky="w")

        tk.Label(edit_frame, text="새 값:", bg="#f4f4f4", font=("맑은 고딕", 9)).grid(
            row=1, column=0, sticky="w", padx=4
        )
        self.new_val_var = tk.StringVar()
        self.new_val_entry = tk.Entry(
            edit_frame,
            textvariable=self.new_val_var,
            width=40,
            font=("맑은 고딕", 10),
            state=tk.DISABLED,
        )
        self.new_val_entry.grid(row=1, column=1, padx=4, pady=2, sticky="w")

        self.apply_btn = tk.Button(
            edit_frame,
            text="✓ 셀 값 적용",
            command=self._apply_cell_edit,
            bg="#27ae60",
            fg="white",
            relief=tk.FLAT,
            font=("맑은 고딕", 9),
            padx=8,
            state=tk.DISABLED,
        )
        self.apply_btn.grid(row=1, column=2, padx=6)

        # 하단 버튼
        btn_frame = tk.Frame(parent, bg="#f4f4f4", pady=4)
        btn_frame.pack(fill=tk.X)

        tk.Button(
            btn_frame,
            text="📋 수정 내역 보기",
            command=self._show_records,
            bg="#95a5a6",
            fg="white",
            relief=tk.FLAT,
            font=("맑은 고딕", 9),
            padx=8,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame,
            text="💾 저장",
            command=self._save_pdf,
            bg="#2c3e50",
            fg="white",
            relief=tk.FLAT,
            font=("맑은 고딕", 10, "bold"),
            padx=14,
        ).pack(side=tk.RIGHT, padx=4)

        # 더블클릭 편집 상태
        self._selected_row = None
        self._selected_col = None
        self._selected_table_idx = None

    # ─────────────────────────────────────────────────
    # 이벤트 핸들러
    # ─────────────────────────────────────────────────

    def _open_pdf(self):
        path = filedialog.askopenfilename(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")],
        )
        if not path:
            return

        if self.reader:
            self.reader.close()

        self.source_path = path
        self.reader = PDFReader(path)
        try:
            self.reader.open()
        except IOError as e:
            messagebox.showerror("오류", str(e))
            return

        self._set_status("표 감지 중...")
        self.tables = self.reader.extract_tables()
        self.parser = TableParser(self.tables)

        self.table_listbox.delete(0, tk.END)
        if not self.tables:
            messagebox.showinfo("안내", "이 PDF에서 표를 찾지 못했습니다.")
            self._set_status("표를 찾지 못했습니다.")
            return

        for t in self.tables:
            self.table_listbox.insert(
                tk.END,
                f"표 {t.table_index+1}  |  p.{t.page_number+1}  |  {t.rows}×{t.cols}",
            )

        self.file_label.config(text=os.path.basename(path))
        self._set_status(f"총 {len(self.tables)}개 표 감지 완료. 표를 선택하세요.")

    def _on_table_select(self, event):
        sel = self.table_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.current_table_index = self.tables[idx].table_index
        self._load_table_to_tree(self.tables[idx])
        self._set_status(f"표 {self.current_table_index+1} 선택됨")

    def _load_table_to_tree(self, table):
        """Treeview에 표 내용 로드"""
        self.tree.delete(*self.tree.get_children())
        cols = [str(c + 1) + "열" for c in range(table.cols)]
        self.tree["columns"] = cols
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=120, anchor="w")

        for r_idx, row in enumerate(table.cells):
            values = [cell.text for cell in row]
            self.tree.insert("", tk.END, iid=str(r_idx), values=values)

    def _on_cell_double_click(self, event):
        """셀 더블클릭 → 편집 활성화"""
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item or not col:
            return

        row_idx = int(item)
        col_idx = int(col.replace("#", "")) - 1

        if self.current_table_index is None:
            return

        table = next(
            (t for t in self.tables if t.table_index == self.current_table_index), None
        )
        if table is None:
            return

        cell = table.get_cell(row_idx, col_idx)
        if cell is None:
            return

        self._selected_row = row_idx
        self._selected_col = col_idx
        self._selected_table_idx = self.current_table_index

        self.old_val_label.config(text=f'"{cell.text}"')
        self.new_val_var.set(cell.text)
        self.new_val_entry.config(state=tk.NORMAL)
        self.apply_btn.config(state=tk.NORMAL)
        self.new_val_entry.focus()

    def _apply_cell_edit(self):
        """셀 편집 적용"""
        if self._selected_row is None:
            return
        new_text = self.new_val_var.get()
        record = self.parser.edit_cell(
            self._selected_table_idx, self._selected_row, self._selected_col, new_text
        )
        if record:
            # Treeview 업데이트
            table = next(
                t for t in self.tables if t.table_index == self._selected_table_idx
            )
            self._load_table_to_tree(table)
            self._set_status(
                f'✓ 수정: "{record.old_text}" → "{record.new_text}"  '
                f"(표{record.table_index+1} {record.row+1}행 {record.col+1}열)"
            )
            self.new_val_entry.config(state=tk.DISABLED)
            self.apply_btn.config(state=tk.DISABLED)

    def _do_search(self):
        """찾아바꾸기 - 검색"""
        if not self.parser:
            messagebox.showinfo("안내", "PDF를 먼저 열어주세요.")
            return
        keyword = self.search_var.get().strip()
        if not keyword:
            messagebox.showinfo("안내", "찾을 값을 입력하세요.")
            return

        results = self.parser.search(keyword, self.case_var.get(), self.exact_var.get())
        self._search_results = results

        self.result_listbox.delete(0, tk.END)
        for r in results:
            self.result_listbox.insert(tk.END, r.label())

        self._set_status(f'"{keyword}" 검색 결과: {len(results)}건')

    def _do_replace_all(self):
        if not self.parser:
            return
        keyword = self.search_var.get().strip()
        new_text = self.replace_var.get()
        if not keyword:
            messagebox.showinfo("안내", "찾을 값을 입력하세요.")
            return
        records = self.parser.replace_all(
            keyword, new_text, self.case_var.get(), self.exact_var.get()
        )
        self._refresh_current_table()
        messagebox.showinfo("완료", f"{len(records)}개 항목을 교체했습니다.")
        self._set_status(f"전체 교체 완료: {len(records)}건")

    def _do_replace_selected(self):
        if not self.parser or not self._search_results:
            return
        sel = self.result_listbox.curselection()
        if not sel:
            messagebox.showinfo("안내", "교체할 항목을 선택하세요.")
            return
        keyword = self.search_var.get().strip()
        new_text = self.replace_var.get()
        selected = [self._search_results[i] for i in sel]
        records = self.parser.replace_selected(
            selected, new_text, keyword, self.case_var.get(), self.exact_var.get()
        )
        self._refresh_current_table()
        messagebox.showinfo("완료", f"{len(records)}개 항목을 교체했습니다.")
        self._set_status(f"선택 교체 완료: {len(records)}건")

    def _refresh_current_table(self):
        if self.current_table_index is None:
            return
        table = next(
            (t for t in self.tables if t.table_index == self.current_table_index), None
        )
        if table:
            self._load_table_to_tree(table)

    def _show_records(self):
        if not self.parser:
            return
        summary = self.parser.get_edit_summary()
        if not summary:
            messagebox.showinfo("수정 내역", "아직 수정된 내용이 없습니다.")
            return
        win = tk.Toplevel(self)
        win.title("수정 내역")
        win.geometry("600x400")
        text = tk.Text(win, font=("맑은 고딕", 9), wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for line in summary:
            text.insert(tk.END, line + "\n")
        text.config(state=tk.DISABLED)

    def _save_pdf(self):
        if not self.parser or not self.parser.edit_records:
            messagebox.showinfo("안내", "수정된 내용이 없습니다.")
            return

        base, ext = os.path.splitext(self.source_path)
        default_name = os.path.basename(base) + "_수정본" + ext
        out = filedialog.asksaveasfilename(
            title="저장할 파일 경로 선택",
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("PDF 파일", "*.pdf")],
        )
        if not out:
            return

        writer = PDFWriter(self.reader.get_fitz_doc(), self.source_path)
        count = writer.apply_edits(self.parser.edit_records)
        writer.save(out)
        messagebox.showinfo(
            "저장 완료", f"{count}개 셀이 교체된 PDF를 저장했습니다.\n\n{out}"
        )
        self._set_status(f"저장 완료: {out}")

    def _set_status(self, msg: str):
        self.status_var.set(msg)


def run_gui():
    app = PDFTableEditorApp()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
