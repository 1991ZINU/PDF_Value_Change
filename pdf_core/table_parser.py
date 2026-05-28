"""
table_parser.py
표 내 셀 검색, 찾아바꾸기, 수정 내역 관리 모듈

EditRecord 구조:
  - old_text / new_text : 셀 전체 텍스트 (UI 표시, 수정 내역용)
  - diffs               : 실제 변경된 부분만 담은 목록 (pdf_writer 처리용)
                          [{"old": "변경 전", "new": "변경 후"}, ...]
  → pdf_writer는 diffs를 기반으로 span 단위 부분 교체를 수행
    셀 전체 텍스트가 아닌 변경된 값만 span에서 찾으므로 긴 셀도 처리 가능
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from pdf_core.pdf_reader import CellInfo, TableInfo


@dataclass
class EditRecord:
    """단일 셀 수정 내역"""

    table_index: int
    page_number: int
    row: int
    col: int
    old_text: str  # 셀 전체 이전 텍스트 (UI 표시용)
    new_text: str  # 셀 전체 이후 텍스트 (UI 표시용)
    cell_bbox: Tuple[float, float, float, float]
    # 실제 변경된 부분 목록 — pdf_writer가 이걸 기반으로 span 교체
    # [{"old": "16,500", "new": "22,000"}, {"old": "5,500", "new": "0"}, ...]
    diffs: List[dict] = field(default_factory=list)


@dataclass
class SearchResult:
    """찾아바꾸기 검색 결과 단일 항목"""

    table_index: int
    page_number: int
    row: int
    col: int
    text: str
    cell_bbox: Tuple[float, float, float, float]

    def label(self) -> str:
        return (
            f"표 {self.table_index + 1} | "
            f"페이지 {self.page_number + 1} | "
            f"{self.row + 1}행 {self.col + 1}열 | "
            f'"{self.text}"'
        )


class TableParser:
    """
    표 데이터 검색 및 수정 내역 관리
    - 직접 선택 수정 (팝업에서 텍스트 직접 편집)
    - 찾아바꾸기 (전체 / 선택)
    """

    def __init__(self, tables: List[TableInfo]):
        self.tables = tables
        self.edit_records: List[EditRecord] = []

    # ──────────────────────────────────────────
    # 직접 선택 수정
    # ──────────────────────────────────────────

    def edit_cell(
        self,
        table_index: int,
        row: int,
        col: int,
        new_text: str,
    ) -> Optional[EditRecord]:
        """
        팝업에서 편집된 셀 전체 텍스트를 받아 EditRecord 생성.

        diffs 계산:
          old_text와 new_text를 줄 단위로 비교하여
          실제 변경된 줄(값)만 diffs에 담음.
          → pdf_writer는 diffs의 각 항목을 span에서 찾아 부분 교체
        """
        table = self._get_table(table_index)
        if table is None:
            return None

        cell = table.get_cell(row, col)
        if cell is None:
            return None

        old_text = cell.text

        # old_text와 new_text가 동일하면 수정 없음
        if old_text == new_text:
            return None

        # 변경된 부분(diff) 계산
        diffs = self._compute_diffs(old_text, new_text)

        record = EditRecord(
            table_index=table_index,
            page_number=table.page_number,
            row=row,
            col=col,
            old_text=old_text,
            new_text=new_text,
            cell_bbox=cell.bbox,
            diffs=diffs,
        )

        # 내부 상태 업데이트
        cell.text = new_text
        self.edit_records.append(record)
        return record

    # ──────────────────────────────────────────
    # 찾아바꾸기
    # ──────────────────────────────────────────

    def search(
        self,
        keyword: str,
        case_sensitive: bool = False,
        exact_match: bool = False,
    ) -> List[SearchResult]:
        """전체 표에서 keyword를 포함하는 셀 목록 반환"""
        results: List[SearchResult] = []

        for table in self.tables:
            for row in table.cells:
                for cell in row:
                    if self._is_match(cell.text, keyword, case_sensitive, exact_match):
                        results.append(
                            SearchResult(
                                table_index=table.table_index,
                                page_number=table.page_number,
                                row=cell.row,
                                col=cell.col,
                                text=cell.text,
                                cell_bbox=cell.bbox,
                            )
                        )
        return results

    def replace_all(
        self,
        keyword: str,
        new_text: str,
        case_sensitive: bool = False,
        exact_match: bool = False,
    ) -> List[EditRecord]:
        """전체 일치 항목을 일괄 교체"""
        results = self.search(keyword, case_sensitive, exact_match)
        records: List[EditRecord] = []

        for result in results:
            table = self._get_table(result.table_index)
            if table is None:
                continue
            cell = table.get_cell(result.row, result.col)
            if cell is None:
                continue

            old_full = cell.text
            replaced = self._apply_replace(
                old_full, keyword, new_text, case_sensitive, exact_match
            )

            record = EditRecord(
                table_index=result.table_index,
                page_number=result.page_number,
                row=result.row,
                col=result.col,
                old_text=old_full,
                new_text=replaced,
                cell_bbox=result.cell_bbox,
                # 찾아바꾸기는 keyword→new_text 단순 교체
                diffs=[{"old": keyword, "new": new_text}],
            )
            cell.text = replaced
            self.edit_records.append(record)
            records.append(record)

        return records

    def replace_selected(
        self,
        selected: List[SearchResult],
        new_text: str,
        keyword: str,
        case_sensitive: bool = False,
        exact_match: bool = False,
    ) -> List[EditRecord]:
        """사용자가 선택한 항목만 교체"""
        records: List[EditRecord] = []

        for result in selected:
            table = self._get_table(result.table_index)
            if table is None:
                continue
            cell = table.get_cell(result.row, result.col)
            if cell is None:
                continue

            old_full = cell.text
            replaced = self._apply_replace(
                old_full, keyword, new_text, case_sensitive, exact_match
            )

            record = EditRecord(
                table_index=result.table_index,
                page_number=result.page_number,
                row=result.row,
                col=result.col,
                old_text=old_full,
                new_text=replaced,
                cell_bbox=result.cell_bbox,
                diffs=[{"old": keyword, "new": new_text}],
            )
            cell.text = replaced
            self.edit_records.append(record)
            records.append(record)

        return records

    # ──────────────────────────────────────────
    # 수정 내역 관리
    # ──────────────────────────────────────────

    def get_edit_summary(self) -> List[str]:
        summary = []
        for i, r in enumerate(self.edit_records, 1):
            summary.append(
                f"{i}. 표 {r.table_index + 1} | "
                f"페이지 {r.page_number + 1} | "
                f"{r.row + 1}행 {r.col + 1}열 | "
                f'"{r.old_text}" → "{r.new_text}"'
            )
        return summary

    def clear_records(self):
        self.edit_records.clear()

    # ──────────────────────────────────────────
    # 내부 유틸
    # ──────────────────────────────────────────

    def _compute_diffs(self, old_text: str, new_text: str) -> List[dict]:
        """
        old_text → new_text 변경 시 실제 달라진 토큰 목록 반환.

        방법: 공백/줄바꿈으로 분리한 토큰 단위로 비교.
        예)
          old: "할인액 -16,500원, 납부액 5,500원"
          new: "할인액 -22,000원, 납부액 0원"
          → [{"old": "-16,500원,", "new": "-22,000원,"},
             {"old": "5,500원",   "new": "0원"}]

        pdf_writer는 이 목록을 순서대로 span에서 찾아 교체함.
        """
        old_tokens = old_text.split()
        new_tokens = new_text.split()

        diffs: List[dict] = []

        # 길이가 같으면 위치 기반 비교
        if len(old_tokens) == len(new_tokens):
            for o, n in zip(old_tokens, new_tokens):
                if o != n:
                    diffs.append({"old": o, "new": n})
            return diffs

        # 길이가 다르면 줄 단위로 비교
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        max_len = max(len(old_lines), len(new_lines))
        for i in range(max_len):
            o_line = old_lines[i] if i < len(old_lines) else ""
            n_line = new_lines[i] if i < len(new_lines) else ""
            if o_line != n_line:
                # 줄 안에서 토큰 단위 비교
                o_toks = o_line.split()
                n_toks = n_line.split()
                if len(o_toks) == len(n_toks):
                    for o, n in zip(o_toks, n_toks):
                        if o != n:
                            diffs.append({"old": o, "new": n})
                else:
                    # 줄 전체를 교체 대상으로
                    if o_line:
                        diffs.append({"old": o_line, "new": n_line})

        return diffs

    def _apply_replace(
        self,
        text: str,
        keyword: str,
        new_val: str,
        case_sensitive: bool,
        exact_match: bool,
    ) -> str:
        if exact_match:
            return new_val
        if case_sensitive:
            return text.replace(keyword, new_val)
        return re.sub(re.escape(keyword), new_val, text, flags=re.IGNORECASE)

    def _get_table(self, table_index: int) -> Optional[TableInfo]:
        for t in self.tables:
            if t.table_index == table_index:
                return t
        return None

    def _is_match(
        self,
        text: str,
        keyword: str,
        case_sensitive: bool,
        exact_match: bool,
    ) -> bool:
        if not keyword:
            return False
        t = text if case_sensitive else text.lower()
        k = keyword if case_sensitive else keyword.lower()
        return t == k if exact_match else k in t
