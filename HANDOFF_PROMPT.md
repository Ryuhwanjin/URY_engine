# 🎓 URY Engine v0.1 — 마스터 개발 인수인계서 (Handoff & Mac Mini Setup Guide)

> **안내**: 집의 Mac Mini (또는 Windows PC)에서 새로운 AI 보조원(Antigravity / Gemini / Claude 등)에게 이 문서 전체를 복사하여 전달하면, 프로젝트 구조와 현재 상태, 그리고 확정된 차기 로드맵을 100% 파악하고 바로 개발 및 디버깅을 이어갈 수 있습니다.

---

## 📌 1. 프로젝트 개요 및 핵심 아키텍처

- **프로젝트명**: URY Engine v0.1 (Ultimate Result for You — 전공 학업 관리 & 시험 대비 올인원 AI 자동화 엔진)
- **버전 체계**:
  - **v0.1**: 현재 메인 개발 및 배포 안정 버전 (Tab 2 실시간 ETA, macOS Sonoma/Sequoia Cocoa 크래시 방지 등 안정화 완료)
  - **v0.0**: 레거시 원본 백업본 (`백업/URY_macOS_v0.0_Release.zip`)
- **개발 환경**: Python 3.10+, Tkinter (GUI), Google Chrome / Microsoft Edge Headless (A4 출판용 PDF 조판), Google Gemini API
- **타깃 플랫폼**: 
  - **macOS**: Apple Silicon (M1/M2/M3/M4 Mac Mini / MacBook) 및 Intel Mac (`.command` 런처 및 독립형 `URY Engine.app`)
  - **Windows**: Windows 10/11 (64-bit 권장, 32-bit Python 환경 호환, `.bat` / `.vbs` 런처)
- **주요 기능 구성**:
  1. 🎙️ **학습노트 생성 스튜디오 (Tab 1)**: 음성 파일(`.m4a`, `.mp3`) + 슬라이드(`.pdf`) 분석 ➔ 출판용 양방향(한/영) PDF 강의노트 생성
  2. 📝 **실전 모의시험 & 맞춤 로드맵 (Tab 2)**: 객관식/서술형 시험지 및 해설 PDF 출제, D-Day 학습 로드맵, A4 1-Page 3분 치트시트 생성 (실시간 진행률 프로그레스 바 + ETA 카운트다운 탑재)
  3. ✍️ **실전 모의시험 AI 정밀 채점기**: 학생 답안 1:1 정밀 채점 (키워드 60% + 논리 40%), 등급(A+) 및 취약점 분석 리포트
  4. 💬 **교수님 말씀 Q&A AI 강의 튜터 (Tab 3)**: 강의자료 + 음성 발언 타임스탬프(`[🎙️ 음성 (MM:SS)]`) 기반 1:1 과외 챗봇
  5. 📊 **주차별 진도 대시보 (Tab 4)**: 1~16주차 전 차시 학습노트, 슬라이드, 예상문제 진행률 매트릭스 시각화
  6. ⚙️ **설정 및 실라버스 관리 (Tab 5~6)**: 과목별 강의계획서(Syllabus) 등록, Gemini API 키, 프롬프트 커스텀

---

## 🛠️ 2. 현재 상태 (v0.1 완료 내역)

1. **Tab 2 실시간 ETA 로그 및 프로그레스 바 완성**:
   - 비동기 스레드(`threading.Thread`) 적용으로 UI 프리징 0%.
   - 진행률 게이지(`ttk.Progressbar`) + 실시간 ETA 타이머(`⏱️ 경과 MM:SS | 남은 시간: 약 XX초`) + 다크 터미널 콘솔(`Menlo` 9pt) 연동 완료.
2. **macOS Sonoma/Sequoia Cocoa Tkinter SIGABRT 크래시 원천 차단**:
   - `setAllowedFileTypes:` C-레벨 메모리 버그를 방지하기 위해 AppleScript 기반 네이티브 다이얼로그 몽키패치 적용.
3. **AI 강의 튜터 마크다운 & 수식 유니코드 가독성 고도화**:
   - LaTeX 수식 유니코드 정제 및 12pt 고가독성 폰트 조판 완료.
4. **동일 날짜 다중 음성 녹음 자동 정렬 및 순번 부여**:
   - QuickTime 메타데이터(`mvhd`) 기반으로 1교시/2교시 순서 자동 판별 및 넘버링.

---

## 🔮 3. 확정된 차기 개발 로드맵 (URY v0.2 우선순위)

Mac Mini에서 개발을 재개할 때 구현할 핵심 5대 기능입니다:

### ① 📁 멀티포맷 강의자료 인풋 확장
* **목적**: PDF뿐 아니라 대학 수업에서 쓰이는 모든 자료를 확장자 변환 없이 그대로 수용.
* **지원 포맷**:
  * 주피터 노트북 (`.ipynb`), 파이썬 코드 (`.py`), SQL (`.sql`)
  * 한글 문서 (`.hwpx`, `.hwp`) — 오피스 없이 순수 파이썬 파싱
  * 파워포인트 (`.pptx`, `.ppt`) — 슬라이드 본문 + **교수님 발표자 노트(Notes)** 추출
  * 워드 문서 (`.docx`, `.doc`)
* **구현 방식**: `doc_parser.py` 모듈을 신설하여 텍스트/구조를 정제 후 Gemini 컨텍스트로 전달.

### ② 📊 시각화 표준화 (Mermaid 다이어그램 + LaTeX 수식 + 비교표)
* **목적**: 딱딱한 줄글 대신 교재 수준의 시각화 도표 자동 생성.
* **Mermaid 다이어그램**: 알고리즘 순서도(`flowchart TD`), 네트워크/시스템 통신(`sequenceDiagram`), 프로세스 상태 전이.
* **비교 매트릭스**: 대학 시험 단골인 "A vs B 비교(뮤텍스 vs 세마포어 등)" 표 자동 생성.
* **PDF 연동**: `generate_pdfs.py`에 Mermaid.js CDN 스크립트 연동으로 A4 인쇄 시 선명한 벡터 그래픽으로 조판.

### ③ 📷 칠판/필기 판서 사진 결합 (Vision 멀티모달)
* **목적**: 스마트폰 갤러리에 묻혀있는 칠판 판서/필기 사진을 슬라이드 요약에 통합.
* **구현 방식**: Tab 1 스튜디오에 `[📷 칠판 사진 추가 (선택, 최대 5장)]` 버튼 배치 ➔ Gemini 2.0 Flash 멀티모달에 이미지 전달 ➔ 요약본에 `[📝 칠판 판서 보충: 슬라이드 Np 관련]` 해설 블록 자동 생성.

### ④ 📚 중간/기말 전범위 "통합 바이블(마스터 노트)" 생성
* **목적**: 시험 2주 전 1~7주차 흩어진 파일들을 하나로 통합.
* **구현 방식**: Tab 2에 `[📚 전범위 통합 바이블 생성]` 버튼 ➔ 누적 마크다운 체크박스 선택 ➔ 중복 개념 제거, 1~7주차 통합 개념 트리, 전 범위 마스터 용어 색인(Glossary)이 담긴 단일 마스터 PDF 발행.

### ⑤ 🤖 AI 튜터 & 과제 도우미 퀵 액션 개편
* **목적**: 빈 입력창 대신 대학생의 과제/시험 질문을 유도하는 직관적 UI.
* **웰컴 퀵 액션 카드 3종**:
  1. `[📋 과제 명세서 분석]`: 과제 파일(HWP/PDF) 투입 시 감점 방지 체크리스트 및 수업 주차 매핑.
  2. `[💻 코딩 과제 힌트]`: 수업 진도 범위 내 스켈레톤 코드 & 디버깅.
  3. `[✍️ 레포트 목차 설계]`: 표절 방지 논리 구조 및 필수 학술 논점 가이드.
* **하단 입력창**: `[📎 과제/자료 첨부]` 버튼 추가로 HWP/PDF/DOCX 즉시 첨부 지원.

### ⑥ 🎙️ 노트북 내장 실시간 녹음기 (Built-in Audio Recorder)
* **목적**: 에어드랍 메타데이터 꼬임(수신 시각으로 파일 시간 변경되는 현상) 원천 방지.
* **구현 방식**: Tab 1에서 과목 선택 후 `[🔴 녹음 시작]` ➔ `[⏹️ 종료]` 시 오늘 날짜 해당 과목 폴더에 자동 안착.

---

## 🚀 4. Mac Mini에서 실행 및 개발 시작 가이드

### 1) 환경 세팅
```bash
# 1. 압축 해제 후 디렉터리로 이동
cd URY_MacMini_Project_v0.1

# 2. 필수 파이썬 라이브러리 설치 (최초 1회)
pip3 install -r requirements.txt

# 3. 설정관리자 & 스튜디오 실행
python3 설정관리자.py
# 또는 마우스로 '설정관리자.command' 더블클릭
```

### 2) macOS 보안 경고 (Gatekeeper) 발생 시
* 터미널에서 아래 명령을 실행하거나, 폴더 내 `보안경고_자동해제.command`를 더블클릭하세요:
```bash
xattr -cr .
chmod +x *.command code/*.py
```

### 3) Mac Mini에서 새 AI(Antigravity 등)에게 전달할 프롬프트
> *"이 폴더는 대학생 올인원 학업 관리 AI 엔진인 URY Engine v0.1 프로젝트입니다. `HANDOFF_PROMPT.md`를 읽고 프로젝트 구조와 현재 상태를 파악한 뒤, 3번 항목의 로드맵 중 [원하는 기능]을 구현해 주세요."*

---

## 📂 5. 주요 소스코드 구조도

```text
URY_MacMini_Project_v0.1/
  ├─ URY Engine.app           # macOS 독립형 실행 번들 (파이썬 미설치 환경 즉시 구동)
  ├─ 설정관리자.py            # 진입점: GUI 대시보드 구동기
  ├─ 설정관리자.command         # macOS 원클릭 런처
  ├─ run_pipeline.py          # 전체 배치 파이프라인 수동 구동기
  ├─ requirements.txt         # 파이썬 의존성 목록
  ├─ USER_GUIDE.md / .pdf     # 사용자 공식 매뉴얼
  ├─ HANDOFF_PROMPT.md        # 개발자 인수인계 및 차기 로드맵 문서
  ├─ code/                    # 핵심 백엔드/GUI 소스코드
  │   ├─ settings_gui.py              # 통합 GUI (Tab 1~6 화면 및 이벤트 전체)
  │   ├─ process_all_lectures.py      # 맞춤형 학습노트 생성 엔진 & Gemini API
  │   ├─ lecture_tutor.py             # AI 튜터 & 과제 도우미 RAG 엔진
  │   ├─ generate_mock_exams.py       # 실전 모의시험 출제 & AI 자동 채점기
  │   ├─ generate_roadmap.py          # 목표 학점 D-Day 학습 로드맵 생성기
  │   ├─ generate_cheatsheet.py       # A4 1-Page 초고밀도 치트시트 조판기
  │   ├─ generate_pdfs.py             # Chrome/Edge Headless 출판용 PDF 렌더러
  │   ├─ dynamic_slide_integrator.py  # 슬라이드 도표 앵커링 추출기
  │   ├─ auto_organize.py             # 음성 녹음 자동 분류 및 1/2교시 순번 정렬기
  │   ├─ config_manager.py            # settings.json 및 경로/환경변수 관리자
  │   └─ ensure_requirements.py       # 패키지 자동 점검 및 설치기
  ├─ prompts/                 # Gemini 전용 고품질 학술 프롬프트 템플릿
  ├─ 00_녹음_수신함/           # 스마트폰 녹음 파일 투입 폴더
  └─ 2026년 2학기/            # 과목별 데이터 저장소 (강의노트, 음성녹음, 강의자료)
```
