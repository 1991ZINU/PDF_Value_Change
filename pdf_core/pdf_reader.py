"""
pdf_reader.py
PDF 파일을 로드하고 표(테이블)를 감지·추출하는 모듈

좌표 전략:
  - 표 감지      : pdfplumber (표 구조·텍스트 파악에 강함)
  - 셀 bbox      : pymupdf로 직접 추출 (좌표계 통일)
    pdfplumber.cells 좌표는 내부 상대좌표라 pymupdf와 불일치 발생
    → pymupdf page.find_tables()로 셀 bbox를 가져와 통일
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import fitz
import pdfplumber


@dataclass
class CellInfo:
    row: int
    col: int
    text: str
    bbox: Tuple[float, float, float, float]  # pymupdf 절대 좌표 (x0,y0,x1,y1)


@dataclass
class TableInfo:
    table_index: int
    page_number: int
    bbox: Tuple[float, float, float, float]
    rows: int
    cols: int
    cells: List[List[CellInfo]] = field(default_factory=list)

    def get_cell(self, row: int, col: int) -> Optional[CellInfo]:
        try:
            return self.cells[row][col]
        except IndexError:
            return None

    def to_display(self) -> List[List[str]]:
        return [[cell.text for cell in row] for row in self.cells]


class PDFReader:

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self._fitz_doc: Optional[fitz.Document] = None
        self._plumber_doc = None
        self.tables: List[TableInfo] = []

    def open(self):
        try:
            self._fitz_doc = fitz.open(self.pdf_path)
            self._plumber_doc = pdfplumber.open(self.pdf_path)
        except Exception as e:
            raise IOError(f"PDF 파일을 열 수 없습니다: {e}")

    def close(self):
        if self._fitz_doc:
            self._fitz_doc.close()
        if self._plumber_doc:
            self._plumber_doc.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def page_count(self) -> int:
        return len(self._fitz_doc) if self._fitz_doc else 0

    def extract_tables(self) -> List[TableInfo]:
        """
        표 감지는 pdfplumber, 셀 bbox는 pymupdf로 통일하여 추출
        """
        if not self._plumber_doc:
            raise RuntimeError("PDF가 열려있지 않습니다.")

        self.tables = []
        table_index = 0

        for page_num in range(len(self._fitz_doc)):
            fitz_page = self._fitz_doc[page_num]
            plumber_page = self._plumber_doc.pages[page_num]

            # pdfplumber로 텍스트 추출
            raw_tables = plumber_page.extract_tables()
            if not raw_tables:
                continue

            # pymupdf로 표 bbox 추출 (좌표계 통일)
            fitz_tables = fitz_page.find_tables()

            for t_idx, raw_table in enumerate(raw_tables):
                if not raw_table:
                    continue

                rows = len(raw_table)
                cols = max(len(r) for r in raw_table) if rows > 0 else 0

                # pymupdf 표 bbox
                if t_idx < len(fitz_tables.tables):
                    fitz_table = fitz_tables.tables[t_idx]
                    table_bbox = tuple(fitz_table.bbox)
                else:
                    table_bbox = (0, 0, fitz_page.rect.width, fitz_page.rect.height)

                # 셀별 bbox를 pymupdf에서 직접 추출
                cells_2d = self._build_cells(
                    fitz_page, fitz_tables, t_idx, raw_table, rows, cols
                )

                self.tables.append(
                    TableInfo(
                        table_index=table_index,
                        page_number=page_num,
                        bbox=table_bbox,
                        rows=rows,
                        cols=cols,
                        cells=cells_2d,
                    )
                )
                table_index += 1

        return self.tables

    # def _build_cells(
    #     self,
    #     fitz_page: fitz.Page,
    #     fitz_tables,
    #     t_idx: int,
    #     raw_table: List,
    #     rows: int,
    #     cols: int,
    # ) -> List[List[CellInfo]]:
    #     """
    #     pymupdf find_tables() 결과에서 셀 bbox를 추출하여 CellInfo 구성
    #     pymupdf 표가 없으면 텍스트 위치로 bbox를 역추적
    #     """
    #     # pymupdf 표의 셀 bbox 맵 구성 {(row, col): fitz.Rect}
    #     fitz_cell_map: dict[Tuple[int, int], fitz.Rect] = {}

    #     if t_idx < len(fitz_tables.tables):
    #         fitz_table = fitz_tables.tables[t_idx]
    #         try:
    #             for cell in fitz_table.cells:
    #                 # fitz cell: (col, row, x0, y0, x1, y1)
    #                 r, c = cell[1], cell[0]
    #                 fitz_cell_map[(r, c)] = fitz.Rect(
    #                     cell[2], cell[3], cell[4], cell[5]
    #                 )
    #         except (TypeError, IndexError, AttributeError):
    #             pass

    #     cells_2d: List[List[CellInfo]] = []

    #     for r_idx, row in enumerate(raw_table):
    #         cell_row: List[CellInfo] = []
    #         for c_idx in range(cols):
    #             text = row[c_idx] if c_idx < len(row) else ""
    #             text = text.strip() if text else ""

    #             # pymupdf 셀 bbox 우선 사용
    #             if (r_idx, c_idx) in fitz_cell_map:
    #                 bbox = tuple(fitz_cell_map[(r_idx, c_idx)])
    #             else:
    #                 # fallback: 텍스트로 span 위치 역추적
    #                 bbox = self._find_text_bbox(fitz_page, text)

    #             cell_row.append(
    #                 CellInfo(
    #                     row=r_idx,
    #                     col=c_idx,
    #                     text=text,
    #                     bbox=bbox,
    #                 )
    #             )
    #         cells_2d.append(cell_row)

    #     return cells_2d

    def _build_cells(self, fitz_page, fitz_tables, t_idx, raw_table, rows, cols):
        """
        [수정] pdfplumber의 행/열 구조 내에서
        물리적으로 분리된 Span들을 각각 독립된 CellInfo로 쪼갭니다.
        """
        cells_2d = []

        # 1. 해당 테이블 영역(bbox) 확인
        if t_idx < len(fitz_tables.tables):
            table_bbox = fitz_tables.tables[t_idx].bbox
        else:
            return []  # 표를 못 찾은 경우 빈 리스트

        # 2. 해당 영역 내의 모든 Span(조각)을 가져옴
        # "dict" 모드는 텍스트를 가장 잘게 쪼개진 상태(Span)로 반환합니다.
        page_dict = fitz_page.get_text("dict", clip=table_bbox)

        all_spans = []
        for block in page_dict["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip():
                        all_spans.append(
                            {"text": span["text"].strip(), "bbox": span["bbox"]}
                        )

        # 3. [핵심] pdfplumber의 행/열 그리드 대신
        # 추출된 '개별 조각(Span)'을 각각 하나의 셀로 매핑하거나
        # 혹은 새로운 행/열 구조로 재배치합니다.

        # 여기서는 사용자 요청에 따라 '모두 다른 셀'로 구분하기 위해
        # Span 하나당 하나의 CellInfo를 생성하여 리스트화합니다.

        # 만약 기존 Treeview 구조를 유지해야 한다면,
        # 한 행에 여러 Span이 있을 때 열을 계속 옆으로 늘리는 방식을 취합니다.

        # 예시: 단순히 모든 조각을 1열에 한 조각씩 나열하거나
        # 물리적 Y좌표가 비슷하면 같은 행, 다르면 다른 행으로 정렬

        sorted_spans = sorted(all_spans, key=lambda x: (x["bbox"][1], x["bbox"][0]))

        current_row = []
        last_y = -1
        row_idx = 0

        for s in sorted_spans:
            # Y좌표 차이가 적으면 같은 행, 크면 다음 행 (약 5px 기준)
            if last_y != -1 and abs(s["bbox"][1] - last_y) > 5:
                cells_2d.append(current_row)
                current_row = []
                row_idx += 1

            current_row.append(
                CellInfo(
                    row=row_idx,
                    col=len(current_row),
                    text=s["text"],
                    bbox=tuple(s["bbox"]),
                )
            )
            last_y = s["bbox"][1]

        if current_row:
            cells_2d.append(current_row)

        return cells_2d

    def _find_text_bbox(
        self, fitz_page: fitz.Page, text: str
    ) -> Tuple[float, float, float, float]:
        """텍스트로 span bbox를 역추적 (fallback용)"""
        if not text.strip():
            return (0, 0, 0, 0)
        blocks = fitz_page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" not in b:
                continue
            for line in b["lines"]:
                for span in line["spans"]:
                    if text in span.get("text", ""):
                        return tuple(span["bbox"])
        return (0, 0, 0, 0)

    def get_fitz_doc(self) -> fitz.Document:
        if not self._fitz_doc:
            raise RuntimeError("PDF가 열려있지 않습니다.")
        return self._fitz_doc
