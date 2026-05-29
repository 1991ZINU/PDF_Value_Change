"""
main.py
PDF 표 편집기 — 진입점
실행 방법:
  python main.py          → GUI 실행
  python main.py --cli    → CLI 실행
  python main.py --help   → 도움말
"""

import argparse
import sys
import os

# 프로젝트 루트를 Python 경로에 추가 (VSCode 등 외부 실행 환경 대응)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(
        prog="PDF 표 편집기",
        description="PDF 문서의 표(테이블) 셀 값을 편집하는 도구",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="GUI 대신 터미널(CLI) 모드로 실행",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="PDF 표 편집기 v1.0.1",
    )

    args = parser.parse_args()

    if args.cli:
        from ui.cli_app import run_cli
        run_cli()
    else:
        try:
            from ui.gui_app import run_gui
            run_gui()
        except Exception as e:
            print(f"[오류] GUI를 시작할 수 없습니다: {e}")
            print("CLI 모드로 대신 실행합니다.\n")
            from ui.cli_app import run_cli
            run_cli()


if __name__ == "__main__":
    main()
