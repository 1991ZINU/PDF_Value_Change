# debug_bbox.py
import fitz
import pdfplumber

doc = fitz.open("원본.pdf")
page = doc[0]
fitz_tables = page.find_tables()

# fitz 표 셀 bbox 확인
print("=== fitz find_tables() 셀 bbox ===")
for t_idx, table in enumerate(fitz_tables.tables):
    for cell in table.cells:
        # cell = (col, row, x0, y0, x1, y1)
        print(cell)
        x0, y0, x1, y1 = cell[0], cell[1], cell[2], cell[3]
        # 품명 근처 y좌표 (fitz y: 464~474)
        if 460 <= y0 <= 480:
            print(
                f"  표{t_idx+1} [{cell[1]}행{cell[0]}열] "
                f"bbox=({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f})"
            )

# span bbox 확인
print("\n=== span bbox (품명 근처) ===")
for b in page.get_text("dict")["blocks"]:
    for line in b.get("lines", []):
        for span in line.get("spans", []):
            if 460 <= span["bbox"][1] <= 480 and span["text"].strip():
                print(
                    f"  '{span['text']}'  "
                    f"bbox=({span['bbox'][0]:.1f},{span['bbox'][1]:.1f},"
                    f"{span['bbox'][2]:.1f},{span['bbox'][3]:.1f})"
                )
