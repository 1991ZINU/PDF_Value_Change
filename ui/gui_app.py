"""
gui_app.py - UI 개선 버전

개선 사항:
  - 표 헤더 고정 + 열 너비 자동 조정
  - 셀 클릭 시 전체 내용을 팝업 편집창으로 표시
  - 팝업 내 현재값/새값 모두 스크롤 가능한 텍스트박스
  - 수정 내역 탭: 전용 Treeview
  - 찾아바꾸기 탭: 결과 Treeview
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pdf_core import PDFReader, PDFWriter, SearchResult, TableParser

BG = "#f5f6fa"
BAR = "#2c3e50"
FONT = "맑은 고딕"
FGW = "white"


class PDFTableEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF 표 편집기")
        self.geometry("1280x800")
        self.minsize(960, 640)
        self.configure(bg=BG)

        self.reader: PDFReader = None
        self.parser: TableParser = None
        self.tables = []
        self.source_path = ""
        self.current_table_index = None
        self._search_results: list[SearchResult] = []

        self._build_ui()

    # ─────────────────────────────────────────────────
    # UI 구성
    # ─────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        self._build_main()
        self._build_statusbar()

    def _build_topbar(self):
        bar = tk.Frame(self, bg=BAR, pady=7)
        bar.pack(fill=tk.X)

        tk.Label(
            bar, text="PDF 표 편집기", bg=BAR, fg=FGW, font=(FONT, 13, "bold")
        ).pack(side=tk.LEFT, padx=14)

        tk.Button(
            bar,
            text="📂  PDF 열기",
            command=self._open_pdf,
            bg="#3498db",
            fg=FGW,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            font=(FONT, 10),
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            bar,
            text="💾  저장",
            command=self._save_pdf,
            bg="#27ae60",
            fg=FGW,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            font=(FONT, 10),
        ).pack(side=tk.LEFT, padx=4)

        self.file_label = tk.Label(
            bar,
            text="파일이 선택되지 않았습니다.",
            bg=BAR,
            fg="#bdc3c7",
            font=(FONT, 9),
        )
        self.file_label.pack(side=tk.LEFT, padx=10)

    def _build_main(self):
        pane = tk.PanedWindow(
            self, orient=tk.HORIZONTAL, bg=BG, sashwidth=5, sashrelief=tk.FLAT
        )
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # 좌측: 표 목록
        left = tk.Frame(pane, bg=BG)
        pane.add(left, minsize=160, width=190)
        self._build_table_list(left)

        # 우측: 탭 패널
        right = tk.Frame(pane, bg=BG)
        pane.add(right, minsize=600)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        tab_edit = tk.Frame(self.notebook, bg=BG)
        tab_search = tk.Frame(self.notebook, bg=BG)
        tab_log = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(tab_edit, text="  표 편집  ")
        self.notebook.add(tab_search, text="  찾아바꾸기  ")
        self.notebook.add(tab_log, text="  수정 내역  ")

        self._build_tab_edit(tab_edit)
        self._build_tab_search(tab_search)
        self._build_tab_log(tab_log)

    def _build_table_list(self, parent):
        tk.Label(parent, text="표 목록", bg=BG, font=(FONT, 10, "bold")).pack(
            anchor="w", pady=(4, 4), padx=4
        )

        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=4)

        sb = tk.Scrollbar(frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.table_listbox = tk.Listbox(
            frame,
            yscrollcommand=sb.set,
            font=(FONT, 9),
            selectmode=tk.SINGLE,
            activestyle="dotbox",
            relief=tk.FLAT,
            bg="white",
            bd=1,
            highlightthickness=0,
        )
        self.table_listbox.pack(fill=tk.BOTH, expand=True)
        self.table_listbox.bind("<<ListboxSelect>>", self._on_table_select)
        sb.config(command=self.table_listbox.yview)

    def _build_tab_edit(self, parent):
        """
        표 편집 탭
        - 상단: 열 헤더 + 행 번호 고정 Treeview
        - 셀 클릭 → 팝업 편집창 오픈
        """
        # 안내 레이블
        guide = tk.Frame(parent, bg="#eaf3fb", pady=4)
        guide.pack(fill=tk.X, padx=6, pady=(6, 0))
        tk.Label(
            guide,
            text="셀을 클릭하면 편집 팝업이 열립니다.",
            bg="#eaf3fb",
            fg="#1a5276",
            font=(FONT, 9),
        ).pack(side=tk.LEFT, padx=8)

        # Treeview + 스크롤
        tree_frame = tk.Frame(parent, bg="white", relief=tk.FLAT, bd=1)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree = ttk.Treeview(
            tree_frame,
            show="headings",
            selectmode="browse",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
        )
        self.tree.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        # 홀/짝 행 색상 구분
        self.tree.tag_configure("odd", background="#f7f9fc")
        self.tree.tag_configure("even", background="white")
        self.tree.tag_configure("modified", background="#fef9e7", foreground="#b7950b")

        self.tree.bind("<ButtonRelease-1>", self._on_cell_click)

    def _build_tab_search(self, parent):
        """찾아바꾸기 탭"""
        inp = tk.Frame(parent, bg=BG)
        inp.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(inp, text="찾을 값", bg=BG, font=(FONT, 9), width=7, anchor="e").grid(
            row=0, column=0, padx=(0, 4), pady=3
        )
        self.search_var = tk.StringVar()
        tk.Entry(
            inp,
            textvariable=self.search_var,
            font=(FONT, 10),
            width=40,
            relief=tk.SOLID,
            bd=1,
        ).grid(row=0, column=1, sticky="w")

        tk.Label(inp, text="바꿀 값", bg=BG, font=(FONT, 9), width=7, anchor="e").grid(
            row=1, column=0, padx=(0, 4), pady=3
        )
        self.replace_var = tk.StringVar()
        tk.Entry(
            inp,
            textvariable=self.replace_var,
            font=(FONT, 10),
            width=40,
            relief=tk.SOLID,
            bd=1,
        ).grid(row=1, column=1, sticky="w")

        opt = tk.Frame(inp, bg=BG)
        opt.grid(row=2, column=1, sticky="w", pady=2)
        self.case_var = tk.BooleanVar()
        self.exact_var = tk.BooleanVar()
        tk.Checkbutton(
            opt, text="대소문자 구분", variable=self.case_var, bg=BG, font=(FONT, 9)
        ).pack(side=tk.LEFT)
        tk.Checkbutton(
            opt, text="정확히 일치", variable=self.exact_var, bg=BG, font=(FONT, 9)
        ).pack(side=tk.LEFT, padx=10)

        btn = tk.Frame(inp, bg=BG)
        btn.grid(row=3, column=1, sticky="w", pady=4)
        tk.Button(
            btn,
            text="검색",
            command=self._do_search,
            bg="#3498db",
            fg=FGW,
            relief=tk.FLAT,
            font=(FONT, 9),
            padx=12,
        ).pack(side=tk.LEFT)
        tk.Button(
            btn,
            text="전체 교체",
            command=self._do_replace_all,
            bg="#e67e22",
            fg=FGW,
            relief=tk.FLAT,
            font=(FONT, 9),
            padx=12,
        ).pack(side=tk.LEFT, padx=6)
        tk.Button(
            btn,
            text="선택 교체",
            command=self._do_replace_selected,
            bg="#8e44ad",
            fg=FGW,
            relief=tk.FLAT,
            font=(FONT, 9),
            padx=12,
        ).pack(side=tk.LEFT)

        self.search_count_label = tk.Label(
            parent, text="", bg=BG, fg="#7f8c8d", font=(FONT, 9)
        )
        self.search_count_label.pack(anchor="w", padx=10)

        res_frame = tk.Frame(parent, bg="white", relief=tk.FLAT, bd=1)
        res_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 6))

        vsb2 = ttk.Scrollbar(res_frame, orient="vertical")
        hsb2 = ttk.Scrollbar(res_frame, orient="horizontal")
        vsb2.pack(side=tk.RIGHT, fill=tk.Y)
        hsb2.pack(side=tk.BOTTOM, fill=tk.X)

        cols = ("표", "페이지", "행", "열", "현재 값")
        self.result_tree = ttk.Treeview(
            res_frame,
            columns=cols,
            show="headings",
            selectmode="extended",
            yscrollcommand=vsb2.set,
            xscrollcommand=hsb2.set,
        )
        for c, w in zip(cols, [60, 70, 50, 50, 500]):
            self.result_tree.heading(c, text=c)
            self.result_tree.column(c, width=w, anchor="w")
        self.result_tree.pack(fill=tk.BOTH, expand=True)
        vsb2.config(command=self.result_tree.yview)
        hsb2.config(command=self.result_tree.xview)

    def _build_tab_log(self, parent):
        """수정 내역 탭"""
        header = tk.Frame(parent, bg=BG)
        header.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(header, text="수정 내역", bg=BG, font=(FONT, 10, "bold")).pack(
            side=tk.LEFT
        )
        tk.Button(
            header,
            text="내역 초기화",
            command=self._clear_log,
            bg="#e74c3c",
            fg=FGW,
            relief=tk.FLAT,
            font=(FONT, 9),
            padx=8,
        ).pack(side=tk.RIGHT)

        log_frame = tk.Frame(parent, bg="white", relief=tk.FLAT, bd=1)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        vsb = ttk.Scrollbar(log_frame, orient="vertical")
        hsb = ttk.Scrollbar(log_frame, orient="horizontal")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        cols = ("표", "페이지", "행", "열", "이전 값", "변경 값")
        self.log_tree = ttk.Treeview(
            log_frame,
            columns=cols,
            show="headings",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
        )
        for c, w in zip(cols, [60, 70, 50, 50, 300, 300]):
            self.log_tree.heading(c, text=c)
            self.log_tree.column(c, width=w, anchor="w")
        self.log_tree.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self.log_tree.yview)
        hsb.config(command=self.log_tree.xview)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg="#dfe6e9", pady=3)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="PDF 파일을 열어 시작하세요.")
        tk.Label(
            bar, textvariable=self.status_var, bg="#dfe6e9", font=(FONT, 9), anchor="w"
        ).pack(side=tk.LEFT, padx=10)

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
        self.update_idletasks()

        self.tables = self.reader.extract_tables()
        self.parser = TableParser(self.tables)

        self.table_listbox.delete(0, tk.END)
        self._clear_tree()

        if not self.tables:
            messagebox.showinfo("안내", "이 PDF에서 표를 찾지 못했습니다.")
            self._set_status("표를 찾지 못했습니다.")
            return

        for t in self.tables:
            self.table_listbox.insert(
                tk.END, f"표{t.table_index+1}  p.{t.page_number+1}  {t.rows}×{t.cols}"
            )

        self.file_label.config(text=os.path.basename(path))
        self._set_status(f"총 {len(self.tables)}개 표 감지 완료.")

    def _on_table_select(self, event):
        sel = self.table_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.current_table_index = self.tables[idx].table_index
        self._load_table_to_tree(self.tables[idx])
        self.notebook.select(0)
        t = self.tables[idx]
        self._set_status(
            f"표 {self.current_table_index+1} 선택됨  " f"({t.rows}행 × {t.cols}열)"
        )

    def _on_cell_click(self, event):
        """셀 클릭 → 팝업 편집창 오픈"""
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
        if not table:
            return

        cell = table.get_cell(row_idx, col_idx)
        if cell is None:
            return

        self._open_edit_popup(table, row_idx, col_idx, cell)

    # ─────────────────────────────────────────────────
    # 셀 편집 팝업
    # ─────────────────────────────────────────────────

    def _open_edit_popup(self, table, row_idx, col_idx, cell):
        """
        셀 편집 팝업
        - 위치 정보 표시
        - 현재 값: 읽기 전용 스크롤 텍스트박스 (전체 내용 표시)
        - 새 값   : 편집 가능 스크롤 텍스트박스
        """
        popup = tk.Toplevel(self)
        popup.title(
            f"셀 편집  —  표{self.current_table_index+1} | "
            f"{row_idx+1}행 {col_idx+1}열"
        )
        popup.geometry("640x420")
        popup.minsize(500, 360)
        popup.resizable(True, True)
        popup.grab_set()  # 모달 동작
        popup.configure(bg=BG)

        # ── 위치 정보 헤더 ───────────────────────────
        info_bar = tk.Frame(popup, bg="#eaf3fb", pady=5)
        info_bar.pack(fill=tk.X, padx=0)
        tk.Label(
            info_bar,
            text=(
                f"  표 {self.current_table_index+1}  |  "
                f"페이지 {table.page_number+1}  |  "
                f"{row_idx+1}행  {col_idx+1}열"
            ),
            bg="#eaf3fb",
            fg="#1a5276",
            font=(FONT, 10, "bold"),
        ).pack(side=tk.LEFT, padx=8)

        # ── 현재 값 (읽기 전용) ──────────────────────
        body = tk.Frame(popup, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(10, 4))

        # 현재 값 레이블 + 텍스트박스
        tk.Label(body, text="현재 값", bg=BG, font=(FONT, 9, "bold"), fg="#555").pack(
            anchor="w"
        )

        cur_frame = tk.Frame(body, bg="white", relief=tk.SOLID, bd=1)
        cur_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 8))

        cur_vsb = tk.Scrollbar(cur_frame)
        cur_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        cur_hsb = tk.Scrollbar(cur_frame, orient=tk.HORIZONTAL)
        cur_hsb.pack(side=tk.BOTTOM, fill=tk.X)

        cur_text = tk.Text(
            cur_frame,
            font=(FONT, 10),
            wrap=tk.WORD,
            yscrollcommand=cur_vsb.set,
            xscrollcommand=cur_hsb.set,
            state=tk.NORMAL,
            bg="#f8f9fa",
            relief=tk.FLAT,
            height=5,
        )
        cur_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        cur_vsb.config(command=cur_text.yview)
        cur_hsb.config(command=cur_text.xview)

        # 현재 값 삽입 후 읽기 전용으로 변경
        cur_text.insert("1.0", cell.text)
        cur_text.config(state=tk.DISABLED)

        # ── 새 값 (편집 가능) ───────────────────────
        tk.Label(
            body,
            text="새 값  (Enter: 줄바꿈 가능)",
            bg=BG,
            font=(FONT, 9, "bold"),
            fg="#555",
        ).pack(anchor="w")

        new_frame = tk.Frame(body, bg="white", relief=tk.SOLID, bd=1)
        new_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        new_vsb = tk.Scrollbar(new_frame)
        new_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        new_text = tk.Text(
            new_frame,
            font=(FONT, 10),
            wrap=tk.WORD,
            yscrollcommand=new_vsb.set,
            relief=tk.FLAT,
            height=5,
        )
        new_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        new_vsb.config(command=new_text.yview)

        # 현재 값을 새 값 입력창에 미리 채워줌
        new_text.insert("1.0", cell.text)
        new_text.focus()
        new_text.mark_set("insert", "end")

        # ── 하단 버튼 ────────────────────────────────
        btn_bar = tk.Frame(popup, bg=BG, pady=8)
        btn_bar.pack(fill=tk.X, padx=12)

        def _apply():
            new_val = new_text.get("1.0", tk.END).rstrip("\n")
            record = self.parser.edit_cell(
                self.current_table_index, row_idx, col_idx, new_val
            )
            if record:
                self._load_table_to_tree(table)
                self._append_log(record)
                self._set_status(
                    f"✓ 수정 완료: "
                    f"표{record.table_index+1} {record.row+1}행 {record.col+1}열"
                )
            popup.destroy()

        def _cancel():
            popup.destroy()

        tk.Button(
            btn_bar,
            text="✓ 적용",
            command=_apply,
            bg="#27ae60",
            fg=FGW,
            relief=tk.FLAT,
            font=(FONT, 10, "bold"),
            padx=20,
            pady=4,
        ).pack(side=tk.RIGHT, padx=4)

        tk.Button(
            btn_bar,
            text="✕ 취소",
            command=_cancel,
            bg="#95a5a6",
            fg=FGW,
            relief=tk.FLAT,
            font=(FONT, 10),
            padx=20,
            pady=4,
        ).pack(side=tk.RIGHT)

        # Esc 키로 팝업 닫기
        popup.bind("<Escape>", lambda e: _cancel())

    # ─────────────────────────────────────────────────
    # 찾아바꾸기
    # ─────────────────────────────────────────────────

    def _do_search(self):
        if not self.parser:
            messagebox.showinfo("안내", "PDF를 먼저 열어주세요.")
            return
        keyword = self.search_var.get().strip()
        if not keyword:
            messagebox.showinfo("안내", "찾을 값을 입력하세요.")
            return

        results = self.parser.search(keyword, self.case_var.get(), self.exact_var.get())
        self._search_results = results

        self.result_tree.delete(*self.result_tree.get_children())
        for r in results:
            self.result_tree.insert(
                "",
                tk.END,
                values=(
                    f"표{r.table_index+1}",
                    f"p.{r.page_number+1}",
                    f"{r.row+1}행",
                    f"{r.col+1}열",
                    r.text,
                ),
            )

        self.search_count_label.config(text=f"검색 결과: {len(results)}건")
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
        for r in records:
            self._append_log(r)
        self._refresh_current_table()
        messagebox.showinfo("완료", f"{len(records)}개 항목을 교체했습니다.")
        self._set_status(f"전체 교체 완료: {len(records)}건")

    def _do_replace_selected(self):
        if not self.parser or not self._search_results:
            return
        sel = self.result_tree.selection()
        if not sel:
            messagebox.showinfo("안내", "교체할 항목을 선택하세요.")
            return
        all_items = self.result_tree.get_children()
        indices = [all_items.index(s) for s in sel]
        selected = [self._search_results[i] for i in indices]

        keyword = self.search_var.get().strip()
        new_text = self.replace_var.get()
        records = self.parser.replace_selected(
            selected, new_text, keyword, self.case_var.get(), self.exact_var.get()
        )
        for r in records:
            self._append_log(r)
        self._refresh_current_table()
        messagebox.showinfo("완료", f"{len(records)}개 항목을 교체했습니다.")
        self._set_status(f"선택 교체 완료: {len(records)}건")

    # ─────────────────────────────────────────────────
    # 수정 내역
    # ─────────────────────────────────────────────────

    def _append_log(self, record):
        self.log_tree.insert(
            "",
            tk.END,
            values=(
                f"표{record.table_index+1}",
                f"p.{record.page_number+1}",
                f"{record.row+1}행",
                f"{record.col+1}열",
                record.old_text,
                record.new_text,
            ),
        )

    def _clear_log(self):
        if messagebox.askyesno("확인", "수정 내역을 초기화하시겠습니까?"):
            self.parser.clear_records()
            self.log_tree.delete(*self.log_tree.get_children())
            self._set_status("수정 내역이 초기화되었습니다.")

    # ─────────────────────────────────────────────────
    # 저장
    # ─────────────────────────────────────────────────

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

    # ─────────────────────────────────────────────────
    # 헬퍼
    # ─────────────────────────────────────────────────

    # def _load_table_to_tree(self, table):
    #     """
    #     Treeview에 표 로드
    #     - 열 너비를 셀 내용 길이에 맞게 자동 조정
    #     - 긴 텍스트는 Treeview에서 말줄임(...) 처리
    #       (전체 내용은 팝업에서 확인)
    #     """
    #     self._clear_tree()
    #     cols = [f"{c+1}열" for c in range(table.cols)]
    #     self.tree["columns"] = cols

    #     for c in cols:
    #         self.tree.heading(c, text=c)
    #         self.tree.column(c, width=90, minwidth=50, anchor="w")

    #     for r_idx, row in enumerate(table.cells):
    #         tag = "odd" if r_idx % 2 else "even"
    #         # Treeview 표시용: 줄바꿈을 공백으로, 60자 초과 시 말줄임
    #         values = []
    #         for cell in row:
    #             txt = cell.text.replace("\n", " ")
    #             values.append(txt[:60] + "…" if len(txt) > 60 else txt)
    #         self.tree.insert("", tk.END, iid=str(r_idx), values=values, tags=(tag,))

    #     # 열 너비 자동 조정 (헤더 + 최대 20행 샘플 기준)
    #     sample_rows = list(table.cells)[:20]
    #     for c_idx, col_name in enumerate(cols):
    #         max_len = len(col_name)
    #         for row in sample_rows:
    #             if c_idx < len(row):
    #                 txt = row[c_idx].text.replace("\n", " ")
    #                 max_len = max(max_len, min(len(txt), 60))
    #         # 글자당 약 8px, 최소 70 최대 250
    #         width = max(70, min(max_len * 8, 250))
    #         self.tree.column(col_name, width=width)

    def _load_table_to_tree(self, table):
        """
        물리적으로 쪼개진 모든 Span을 독립된 칸에 표시
        """
        self._clear_tree()

        # 1. 최대 열 개수 계산 (행마다 쪼개진 조각의 수가 다를 수 있음)
        max_cols = 0
        for row in table.cells:
            max_cols = max(max_cols, len(row))

        cols = [f"{c+1}조각" for c in range(max_cols)]
        self.tree["columns"] = cols

        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=150, anchor="w")

        # 2. 데이터 삽입
        for r_idx, row in enumerate(table.cells):
            tag = "odd" if r_idx % 2 else "even"

            # 각 조각(Span)의 텍스트를 각 컬럼에 배치
            values = [cell.text for cell in row]

            # 모자라는 열은 빈 문자열로 채움
            while len(values) < max_cols:
                values.append("")

            self.tree.insert("", tk.END, iid=str(r_idx), values=values, tags=(tag,))

        # 3. 자동 너비 조정
        for c_idx, col_name in enumerate(cols):
            self.tree.column(col_name, width=180)  # 조각 단위이므로 넉넉하게 배정

    def _clear_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = []

    def _refresh_current_table(self):
        if self.current_table_index is None:
            return
        table = next(
            (t for t in self.tables if t.table_index == self.current_table_index), None
        )
        if table:
            self._load_table_to_tree(table)

    def _set_status(self, msg: str):
        self.status_var.set(msg)


def run_gui():
    app = PDFTableEditorApp()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
