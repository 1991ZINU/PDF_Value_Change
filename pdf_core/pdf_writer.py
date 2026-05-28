"""
pdf_writer.py - cell_bbox(span bbox) 직접 치환 버전

pdf_reader._build_cells()가 span.bbox를 그대로 CellInfo.bbox로 저장하므로
record.cell_bbox = 실제 span bbox
→ 스트림에서 해당 좌표의 토큰을 바로 찾아 치환
→ span 탐색 불필요, fontfile 임베딩 없음, 용량 원본 유지
"""

import os
import re
from typing import Dict, List, Optional, Tuple

import fitz

from pdf_core.table_parser import EditRecord

DEFAULT_FONT_PATHS = [
    r"C:\Windows\Fonts\MALGUN.TTF",
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
]

COORD_TOLERANCE = 3.0


def _unescape(s: str) -> str:
    return (
        s.replace("\\\\", "\x00")
        .replace("\\(", "(")
        .replace("\\)", ")")
        .replace("\x00", "\\")
    )


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _to_raw(text: str) -> str:
    """유니코드 → PDF 스트림 latin-1
    ASCII: 그대로, 한글/기타: CP949 인코딩 후 latin-1 재해석"""
    result = ""
    for ch in text:
        if ord(ch) < 0x80:
            result += ch
        else:
            try:
                result += ch.encode("cp949").decode("latin-1")
            except Exception:
                result += ch
    return result


def _clean(content: str) -> str:
    """토큰 content의 \\X 패턴 제거 → 순수 문자만 반환"""
    return re.sub(r"\\(.)", r"\1", content)


class PDFWriter:

    def __init__(self, fitz_doc: fitz.Document, source_path: str):
        self._doc = fitz_doc
        self._source_path = source_path

    # ── 공개 메서드 ────────────────────────────────────────────────────────

    def apply_edits(self, records: List[EditRecord]) -> int:
        if not records:
            return 0
        page_records: dict[int, List[EditRecord]] = {}
        for r in records:
            page_records.setdefault(r.page_number, []).append(r)
        count = 0
        for page_num, recs in page_records.items():
            page = self._doc[page_num]
            count += self._apply_to_page(page, recs)
        return count

    def save(self, output_path: str):
        self._doc.save(output_path, garbage=3, deflate=True, clean=False)

    # ── 페이지 처리 ────────────────────────────────────────────────────────

    def _apply_to_page(self, page: fitz.Page, records: List[EditRecord]) -> int:
        # 페이지의 모든 콘텐츠 스트림 로드
        xref_list = page.get_contents()
        streams: Dict[int, str] = {}
        for xref in xref_list:
            streams[xref] = self._doc.xref_stream(xref).decode("latin-1")

        page_height = page.rect.height
        change_count = 0

        for record in records:
            # diffs가 있으면 diff 단위로, 없으면 old_text 전체로
            diffs = (
                record.diffs
                if record.diffs
                else [{"old": record.old_text, "new": record.new_text}]
            )

            bx0, by0, bx1, by1 = record.cell_bbox
            if bx0 == 0 and by0 == 0 and bx1 == 0 and by1 == 0:
                print(f"  [경고] cell_bbox 없음: '{record.old_text}'")
                continue

            # fitz 좌표 → PDF 좌표 변환
            pdf_x0, pdf_x1 = bx0, bx1
            pdf_y0 = page_height - by1
            pdf_y1 = page_height - by0

            print(
                f"\n  표{record.table_index+1} "
                f"{record.row+1}행 {record.col+1}열  "
                f"cell_bbox=({bx0:.1f},{by0:.1f},{bx1:.1f},{by1:.1f})"
            )

            for diff in diffs:
                old_val = diff.get("old", "")
                new_val = diff.get("new", "")
                if not old_val or old_val == new_val:
                    continue

                print(f"  └ '{old_val}' → '{new_val}'")

                replaced = False
                for xref, stream in streams.items():
                    new_stream, ok = self._replace_in_stream(
                        stream,
                        pdf_x0,
                        pdf_y0,
                        pdf_x1,
                        pdf_y1,
                        old_val,
                        new_val,
                    )
                    if ok:
                        streams[xref] = new_stream
                        print(f"    ✅ xref={xref}")
                        replaced = True
                        change_count += 1
                        break

                if not replaced:
                    print(f"    ❌ 모든 스트림에서 실패")

        # 변경된 스트림만 업데이트
        for xref, stream in streams.items():
            orig = self._doc.xref_stream(xref).decode("latin-1")
            if stream != orig:
                self._doc.update_stream(xref, stream.encode("latin-1"))

        return change_count

    # ── 스트림 치환 ────────────────────────────────────────────────────────

    def _replace_in_stream(
        self,
        stream: str,
        pdf_x0: float,
        pdf_y0: float,
        pdf_x1: float,
        pdf_y1: float,
        old_val: str,
        new_val: str,
    ) -> Tuple[str, bool]:

        old_raw = _to_raw(old_val)
        new_raw = _to_raw(new_val)

        tokens = self._parse_tokens(stream)

        # cell_bbox 범위 내 토큰 수집
        cell_tokens = [
            t
            for t in tokens
            if (
                pdf_x0 - COORD_TOLERANCE <= t["x"] <= pdf_x1 + COORD_TOLERANCE
                and pdf_y0 - COORD_TOLERANCE <= t["y"] <= pdf_y1 + COORD_TOLERANCE
            )
        ]
        if not cell_tokens:
            return stream, False

        # 토큰 clean 합산 후 old_raw 매칭
        token_cleans = [(t, _clean(t["content"])) for t in cell_tokens]
        cell_clean = "".join(c for _, c in token_cleans)

        if old_raw not in cell_clean:
            return stream, False

        # old_raw 위치의 토큰 추출
        match_start = cell_clean.find(old_raw)
        match_end = match_start + len(old_raw)
        cumul = 0
        matched = []
        for t, c in token_cleans:
            ts, te = cumul, cumul + len(c)
            if te > match_start and ts < match_end:
                matched.append(t)
            cumul = te
            if cumul >= match_end:
                break

        if not matched:
            return stream, False

        # ── 글자수 동일: 토큰 1:1 교체 ──────────────────────────────────
        if len(old_raw) == len(new_raw):
            replacements = []
            new_pos = 0
            for t in matched:
                c = _clean(t["content"])
                part_len = len(c)
                new_part = list(new_raw[new_pos : new_pos + part_len])
                new_pos += part_len
                orig = t["content"]
                char_iter = iter(new_part)
                new_content = re.sub(
                    r"\\(.)",
                    lambda m: "\\" + next(char_iter, m.group(1)),
                    orig,
                )
                replacements.append((t["start"], t["end"], f"({new_content}) Tj"))

            for s, e, tj in sorted(replacements, key=lambda x: x[0], reverse=True):
                stream = stream[:s] + tj + stream[e:]
            return stream, True

        # ── 글자수 다름: 토큰 블록을 새 Tm+Tj 시퀀스로 통째 교체 ─────────
        first_t = matched[0]
        start_x = first_t["x"]
        start_y = first_t["y"]

        # 글자 간격: 기존 토큰들의 평균 x 간격
        if len(matched) > 1:
            xs = [t["x"] for t in matched]
            gaps = [xs[i + 1] - xs[i] for i in range(len(xs) - 1) if xs[i + 1] > xs[i]]
            spacing = sum(gaps) / len(gaps) if gaps else 4.5
        else:
            spacing = (pdf_x1 - pdf_x0) / max(len(old_raw), 1)

        # 직전 Tm 매트릭스 앞 4값 추출 (회전/스케일 유지)
        tm_re = re.compile(
            r"([-\d.]+)[ \t]+([-\d.]+)[ \t]+([-\d.]+)[ \t]+"
            r"([-\d.]+)[ \t]+([-\d.]+)[ \t]+([-\d.]+)[ \t]+Tm"
        )
        tm_prefix = "1.00000 0.00000 0.00000 1.00000"
        for m in tm_re.finditer(stream, 0, first_t["start"]):
            tm_prefix = f"{m.group(1)} {m.group(2)} " f"{m.group(3)} {m.group(4)}"

        # 새 Tm+Tj 시퀀스 생성 (글자마다 x좌표 이동)
        new_seq = ""
        cur_x = start_x
        for ch in new_raw:
            new_seq += (
                f"{tm_prefix} {cur_x:.5f} {start_y:.5f} Tm\n" f"({_escape(ch)}) Tj\n"
            )
            cur_x += spacing

        # 매칭 블록 전체를 새 시퀀스로 교체
        stream = stream[: matched[0]["start"]] + new_seq + stream[matched[-1]["end"] :]
        return stream, True

    # ── 토큰 파싱 ──────────────────────────────────────────────────────────

    def _parse_tokens(self, stream: str) -> List[dict]:
        """스트림에서 Tm 좌표 + Tj 내용 순차 파싱"""
        tokens = []
        cur_x, cur_y = 0.0, 0.0
        pos = 0
        n = len(stream)
        tm_re = re.compile(
            r"([-\d.]+)[ \t]+([-\d.]+)[ \t]+([-\d.]+)[ \t]+"
            r"([-\d.]+)[ \t]+([-\d.]+)[ \t]+([-\d.]+)[ \t]+Tm"
        )
        tj_re = re.compile(r"\(([^)\\]*(?:\\.[^)\\]*)*)\)[ \t]*Tj")
        while pos < n:
            tm_m = tm_re.search(stream, pos)
            tj_m = tj_re.search(stream, pos)
            if not tm_m and not tj_m:
                break
            tm_pos = tm_m.start() if tm_m else n
            tj_pos = tj_m.start() if tj_m else n
            if tm_pos <= tj_pos:
                cur_x = float(tm_m.group(5))
                cur_y = float(tm_m.group(6))
                pos = tm_m.end()
            else:
                content = _unescape(tj_m.group(1))
                tokens.append(
                    {
                        "start": tj_m.start(),
                        "end": tj_m.end(),
                        "content": content,
                        "x": cur_x,
                        "y": cur_y,
                    }
                )
                pos = tj_m.end()
        return tokens
