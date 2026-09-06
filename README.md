# 🎓 URY Engine v0.6.5 — Academic Note & Exam Studio

> **Ultimate Result for You Engine** — 대학 강의 녹음 음성과 강의 슬라이드(PDF, PPTX)를 AI(Google Gemini)로 결합하여 출판물급 **학술 강의노트, 실전 모의고사, A4 치트시트, 목표 학점 학습 로드맵**을 자동 제작해 주는 듀얼 플랫폼(macOS & Windows) 전공 학업 솔루션입니다.

---

## ✨ 핵심 기능 (Key Features)

- 🎙️ **강의 녹음 & 슬라이드 자동 통합**: 강의 녹음 음성(`m4a`, `mp3`)과 교수님 배포 슬라이드(`PDF`, `PPTX`)를 인공지능이 1:1 대조·합성하여 고밀도 강의노트 작성
- 📸 **슬라이드 핵심 도표 자동 추출 & 임베드**: 슬라이드 내 핵심 시각 자료(180 DPI PNG) 자동 추출 및 마크다운/PDF 임베드
- 📝 **실전 모의고사 & 정밀 채점기**: 주차별 4지선다 객관식 모의고사 자동 출제 및 학생 제출 답안 AI 1:1 대조 정밀 채점
- 🗺️ **목표 학점 맞춤형 학습 로드맵**: 주차별 세부 소주제, 핵심 사료 분석 및 검증 체크포인트 제공
- 📑 **출판용 고품질 PDF 컴파일**: A4 규격, 여백 최적화(`12mm 14mm`), Pretendard 글꼴 기반 인쇄용 PDF 렌더링
- 🛡️ **독립형 무설치 구동**: 파이프라인 엔진 및 파이프라인 동구동 환경 독립 내장 (파이프라인/파이썬 재설치 불필요)

---

## ⚡ 빠른 시작 (Quick Start)

### 🍏 macOS (맥북 / 맥 스튜디오)
1. **다운로드**: `URY_Engine_v0.6.5.dmg` (또는 `macOS.zip`) 열기 ➔ `URY Engine.app`을 `Applications`(응용 프로그램) 폴더로 드래그
2. **원클릭 실행**: Finder에서 **`01_macOS_실행하기.command`** 더블클릭 *(macOS 보안 격리 자동 해제 후 즉시 구동)*

### 🪟 Windows (윈도우 PC)
1. **압축 해제**: `URY_Engine_v0.6.5_Windows.zip` 압축 해제
2. **원클릭 실행**: `01_실행하기.bat` (또는 `설정관리자.bat`) 더블클릭

---

## 🔑 필수 준비물 (Google Gemini API Key 1분 무료 발급)

1. [Google AI Studio (aistudio.google.com)](https://aistudio.google.com/) 접속 ➔ Google 계정 로그인
2. **`Get API Key`** ➔ **`Create API Key`** 클릭 ➔ 생성된 Key 복사
3. URY Engine 실행 ➔ **[⚙️ 설정]** 탭 ➔ `Gemini Key` 입력란에 붙여넣기 ➔ **[저장 및 적용]**

---

## 📁 디렉터리 구조 및 파일 저장 위치

```
URY_Engine/
├── 과목명/
│   ├── 강의노트/        # 출판용 PDF 강의노트 (주차별 & 전체 통합본)
│   ├── 모의고사/        # 실전 예상문제 PDF 및 정답/해설
│   ├── 학습로드맵/      # 목표 학점 맞춤형 16주 로드맵 PDF
│   ├── 음성녹음/        # 수신된 강의 오디오 파일 (m4a, mp3, wav)
│   └── 강의자료/        # 교수님 발표 슬라이드 (PDF, PPTX)
└── 배포/                # 릴리즈 설치 파일 (.dmg, .zip)
```

---

## 📄 가이드 및 유틸리티

- 📘 [원스톱 초스피드 사용설명서 (USER_GUIDE.md)](./USER_GUIDE.md)
- 📄 [사용설명서 PDF (USER_GUIDE.pdf)](./USER_GUIDE.pdf)
- 🔒 [저작권법 제30조 준수 및 학업 윤리 방침](./공지사항_윤리및법적고지.txt)

---

> 💡 **License & Support**: URY Engine Academic Studio v0.6.5
