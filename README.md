# PDF 표 편집기

PDF 문서의 표(테이블) 셀 값을 편집하는 Python 프로그램입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
# GUI 모드 (기본)
python main.py

# CLI 모드
python main.py --cli
```

## 주요 기능

- PDF 내 표(테이블) 자동 감지
- 셀 직접 선택 후 값 편집
- 찾아바꾸기 (전체 교체 / 선택 교체)
- 교체된 셀에 맑은 고딕 폰트 적용
- 레이아웃·이미지·폰트 원본 보존
- 원본 파일은 덮어쓰지 않고 새 파일로 저장

## 폴더 구조

```
pdf_table_editor/
├── main.py              # 진입점
├── requirements.txt
├── core/
│   ├── pdf_reader.py    # PDF 로드 & 표 추출
│   ├── table_parser.py  # 검색·수정 내역 관리
│   └── pdf_writer.py    # 값 교체 & PDF 저장
└── ui/
    ├── cli_app.py       # CLI 인터페이스
    └── gui_app.py       # tkinter GUI
```

## 환경

- Windows 전용 (맑은 고딕 폰트 자동 참조)
- Python 3.10 이상 권장
