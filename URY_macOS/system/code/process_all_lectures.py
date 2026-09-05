#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
모든 과목의 음성 녹음을 감지하여 Gemini AI로 주차별 학습노트 및 전체 통합본을 .markdown_cache에 자동 적재하는 스크립트 v4.0
- .m4a 및 .mp3 (.wav, .aac) 파일 완전 지원
- 주차별 개별 마크다운([과목]_[N]주차_강의노트.md) + 전체 누적 통합본([과목]_통합강의노트.md) 동시 생성
- 마크다운 파일은 .markdown_cache/ 격리 보관소에 저장하여 사용자 폴더에는 오직 PDF만 노출
- 출처 태그([🎙️ 음성], [📖 교재], [💡 통합]) 자동 분류
- 핵심 키워드 정리 & 단원 종합 요약 자동 생성
"""

import os
import sys
import json
import threading
import urllib.request
import urllib.error
import time
import subprocess
import glob
import re
import unicodedata
from datetime import datetime
from typing import List, Dict, Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import config_manager
try:
    import doc_parser
except ImportError:
    doc_parser = None

WORKSPACE_DIR = config_manager.WORKSPACE_DIR
CACHE_DIR = os.path.join(WORKSPACE_DIR, ".markdown_cache")


def load_course_material_context(course_dir: str, week_num: int = None) -> str:
    """
    강의자료 폴더 내의 멀티포맷 문서(.pdf, .pptx, .hwpx, .ipynb 등)를 doc_parser로 파싱하여
    Gemini AI에게 제공할 교재/슬라이드 본문 및 발표자 노트 텍스트 컨텍스트 생성
    """
    if not doc_parser:
        return ""

    mat_dir = os.path.join(course_dir, "강의자료")
    if not os.path.exists(mat_dir):
        return ""

    supported_exts = [
        "*.pdf", "*.pptx", "*.ppt", "*.hwpx", "*.hwp",
        "*.ipynb", "*.docx", "*.doc", "*.py", "*.sql", "*.txt", "*.md"
    ]

    found_files = []
    for ext in supported_exts:
        found_files.extend(glob.glob(os.path.join(mat_dir, ext)))
        found_files.extend(glob.glob(os.path.join(mat_dir, "**", ext), recursive=True))

    found_files = sorted(list(set(found_files)))
    if not found_files:
        return ""

    materials_text = []
    for fpath in found_files:
        fname = os.path.basename(fpath)
        # 특정 주차 파일 필터링 시도 (파일명에 '1주차', 'week1', 'w1' 등 있는 경우)
        if week_num is not None:
            w_patterns = [f"{week_num}주차", f"week{week_num}", f"w{week_num}", f"ch{week_num}", f"chapter{week_num}"]
            fname_lower = fname.lower()
            # 주차 매칭 조건이 있더라도, 주차 표기가 아예 없으면 기본 참고용으로 포함
            has_any_week_mark = any(re.search(r"(\d+주차|week\d+|w\d+)", fname_lower) for _ in [1])
            if has_any_week_mark and not any(pat in fname_lower for pat in w_patterns):
                continue

        parsed = doc_parser.parse_document(fpath)
        p_text = parsed.get("full_text", "").strip()
        if p_text:
            notes_info = f"\n[🎙️ 발표자 노트 요약]:\n{parsed['notes_text']}" if parsed.get("notes_text") else ""
            materials_text.append(f"📄 [참고 강의자료: {fname}]\n{p_text[:12000]}{notes_info}")

    if not materials_text:
        return ""

    return "\n\n=== 📚 해당 과목 공식 강의자료 및 슬라이드 노트 컨텍스트 ===\n" + "\n\n".join(materials_text) + "\n=========================================\n"


def load_blackboard_images(course_dir: str) -> List[str]:
    """
    과목 폴더 내의 '칠판사진' 또는 '판서' 폴더에서 이미지 파일 목록 탐색 (.jpg, .jpeg, .png)
    """
    img_dirs = [
        os.path.join(course_dir, "칠판사진"),
        os.path.join(course_dir, "판서사진"),
        os.path.join(course_dir, "필기사진")
    ]

    image_paths = []
    for d in img_dirs:
        if os.path.exists(d):
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG"):
                image_paths.extend(glob.glob(os.path.join(d, ext)))
                image_paths.extend(glob.glob(os.path.join(d, "**", ext), recursive=True))

    return sorted(list(set(image_paths)))



def load_dotenv(ws_dir):
    env_path = os.path.join(ws_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))

load_dotenv(WORKSPACE_DIR)

SEMESTER_START = datetime(2026, 9, 1).date()

# API 키 및 모델
API_KEY = os.environ.get("GEMINI_API_KEY", config_manager.get_api_key())
MODEL = "gemini-flash-latest-high-res-exp"

def get_active_course_configs():
    """settings.json에서 등록된 과목 목록을 동적으로 로드"""
    settings = config_manager.load_settings()
    courses = settings.get("courses", [])
    if not courses:
        return COURSE_CONFIGS

    configs = {}
    for idx, c in enumerate(courses):
        cname = c.get("course_name", f"과목_{idx}")
        folder = c.get("folder_name", cname)
        prof = c.get("professor", "담당")
        key = f"c_{idx}"
        configs[key] = {
            "folder_name": folder,
            "name": cname,
            "en_name": cname,
            "cname_prefix": cname.replace(" ", ""),
            "en_prefix": cname.replace(" ", ""),
            "prof": f"{prof} 교수님" if prof and not prof.endswith("교수님") else prof,
            "lang": c.get("language_mode", "both"),
            "context": f"과목: {cname} ({prof}). 주교재 및 슬라이드 파싱 기반 URY AI 학습노트."
        }
    return configs

WEEKDAY_KR = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
WEEKDAY_EN = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}

def resolve_course_dir(folder_name):
    cdir = config_manager.get_course_dir(folder_name)
    for sub in ("음성녹음", "강의자료", "강의노트", "예상문제", "과제"):
        os.makedirs(os.path.join(cdir, sub), exist_ok=True)
    return cdir

def is_date_already_in_file(file_path, date_str):
    if not os.path.exists(file_path):
        return False
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return date_str in content

def get_audio_mime_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".mp3":
        return "audio/mp3"
    elif ext == ".wav":
        return "audio/wav"
    elif ext == ".aac":
        return "audio/aac"
    return "audio/mp4"

def upload_file_to_gemini(file_path, mime_type=None, log_fn=None):
    api_key = config_manager.get_api_key() or os.environ.get("GEMINI_API_KEY", "")
    if not api_key or len(api_key) < 10:
        raise Exception("Gemini API Key가 설정되지 않았습니다. '설정관리자'에서 [Google Gemini API Key]를 등록해 주세요.")

    if not mime_type:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            mime_type = "application/pdf"
        elif ext in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
        elif ext == ".png":
            mime_type = "image/png"
        else:
            mime_type = get_audio_mime_type(file_path)

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    msg_up = f"[{file_name}] 구글 Gemini File API로 업로드 중 ({round(file_size/1024/1024, 1)}MB, {mime_type})..."
    print(msg_up)
    if log_fn:
        log_fn(f"  📤 {msg_up}")

    start_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"
    cmd1 = [
        "curl", "-s", "-D", "-", "-X", "POST", start_url,
        "-H", "X-Goog-Upload-Protocol: resumable",
        "-H", "X-Goog-Upload-Command: start",
        "-H", f"X-Goog-Upload-Header-Content-Length: {file_size}",
        "-H", f"X-Goog-Upload-Header-Content-Type: {mime_type}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"file": {"display_name": file_name}})
    ]
    out1 = subprocess.check_output(cmd1).decode("utf-8", errors="ignore")
    upload_url = None
    for line in out1.splitlines():
        if line.lower().startswith("x-goog-upload-url:"):
            upload_url = line.split(":", 1)[1].strip()
            break
    if not upload_url:
        raise Exception("Upload URL 획득 실패: " + out1)

    cmd2 = [
        "curl", "-s", "-X", "POST", upload_url,
        "-H", "X-Goog-Upload-Command: upload, finalize",
        "-H", f"X-Goog-Upload-Offset: 0",
        "-H", f"Content-Type: {mime_type}",
        "--data-binary", f"@{file_path}"
    ]
    out2 = subprocess.check_output(cmd2).decode("utf-8", errors="ignore")
    res2 = json.loads(out2)
    file_uri = res2["file"]["uri"]
    file_state = res2["file"]["state"]

    if log_fn:
        log_fn(f"  ⏳ [{file_name}] 파일 전송 완료! Google AI 클라우드 인덱싱 대기 중...")
    print(f"[{file_name}] 업로드 완료! 상태 확인 중...")
    poll_count = 0
    while file_state == "PROCESSING":
        time.sleep(4)
        poll_count += 1
        if log_fn and poll_count % 2 == 0:
            log_fn(f"  ⏳ [{file_name}] 오디오 음향 신호 처리 및 텍스트 인덱싱 진행 중... ({poll_count * 4}초 대기)")
        check_url = f"https://generativelanguage.googleapis.com/v1beta/files/{res2['file']['name']}?key={api_key}"
        req = urllib.request.Request(check_url)
        with urllib.request.urlopen(req) as resp:
            state_data = json.loads(resp.read().decode("utf-8"))
            file_state = state_data.get("state")
            if file_state == "ACTIVE":
                break
            elif file_state == "FAILED":
                raise Exception(f"파일 처리 실패! ({file_name})")

    print(f"[{file_name}] Gemini 준비 완료: {file_uri}")
    if log_fn:
        log_fn(f"  ✅ [{file_name}] 클라우드 인덱싱 완료! AI 분석 준비 완료")
    return file_uri, mime_type

def upload_audio_to_gemini(file_path):
    return upload_file_to_gemini(file_path)

def generate_lecture_note(course_info, file_uri, target_date, week_num, is_english=False, mime_type="audio/mp4"):
    date_str = target_date.strftime("%Y-%m-%d")
    weekday_kr = WEEKDAY_KR[target_date.weekday()]
    weekday_en = WEEKDAY_EN[target_date.weekday()]

    lang_name = "English" if is_english else "Korean"
    print(f"[{course_info['name']} - {date_str}] Gemini 강의노트 생성 중 ({lang_name} 버전)...")

    prompts_dir = os.path.join(WORKSPACE_DIR, "system", "prompts")
    if not os.path.exists(prompts_dir):
        prompts_dir = os.path.join(WORKSPACE_DIR, "prompts")
    custom_prompt_file = os.path.join(prompts_dir, "강의노트_영어_프롬프트.txt" if is_english else "강의노트_한국어_프롬프트.txt")
    custom_prompt_loaded = False

    # 멀티포맷 강의자료 문서 및 발표자 노트 컨텍스트 추가
    course_dir = resolve_course_dir(course_info.get('folder_name', course_info.get('name', '')))
    mat_context = load_course_material_context(course_dir, week_num)
    combined_context = (course_info.get('context', '') or "") + mat_context

    if os.path.exists(custom_prompt_file):
        try:
            with open(custom_prompt_file, "r", encoding="utf-8") as pf:
                template = pf.read()
            prompt = template.format(
                course_name=course_info['name'],
                en_name=course_info['en_name'],
                date_str=date_str,
                weekday_kr=weekday_kr,
                weekday_en=weekday_en,
                context=combined_context,
                week_num=week_num
            )
            custom_prompt_loaded = True
        except Exception as e:

            print(f"[Warn] 커스텀 프롬프트 포맷팅 실패, 기본 프롬프트 사용: {e}")

    if not custom_prompt_loaded:
        if not is_english:
            prompt = f"""
당신은 해당 과목의 수석 조교이자 최고의 학습 도우미입니다.
제공된 오디오는 [{course_info['name']}]의 {date_str}({weekday_kr}요일) 실제 전체 수업 녹음입니다.
배경 정보: {course_info['context']}

이 강의 녹음을 처음부터 끝까지 정밀하게 청취하고, 학생이 복습 및 시험 대비에 완벽히 활용할 수 있도록 **매우 상세하고 충실한 강의노트**를 작성해 주세요.

[작성 가이드라인 - 출처 구분 및 음성 타임스탬프 네비게이터 필수]
* 각 대주제 및 소주제, 주요 항목마다 반드시 아래의 [출처 태그]를 명시할 것:
  - `[🎙️ 음성 (MM:SS)]` : 교수님이 수업 중 실제 육성으로 언급한 내용 (공지사항, 출석번호, 시험/과제 팁, 질문과 답변, 칠판 판서, 일상 비유 등). 반드시 해당 발언이 시작되는 음성 녹음 구간의 타임스탬프를 분:초(MM:SS) 형태로 함께 표기할 것! (예: `[🎙️ 음성 (14:25)] 출석체크 번호 7421 안내`, `[🎙️ 음성 (45:10)] 중간고사 단답형 출제 힌트`)
  - `[📖 교재·슬라이드]` : 주교재 본문, 공식 강의 슬라이드(Slide 번호 표기 가능 시 표기), 실라버스 정의
  - `[💡 통합 (MM:SS)]` : 교재 이론을 바탕으로 교수님의 육성 해설과 실전 사례가 결합된 핵심 내용 (음성 발언 시간 병기)

1. 형식:
## {week_num}주차 ({date_str} {weekday_kr}) : [수업의 구체적인 핵심 주제/챕터명]

### 📌 1. 수업 공지사항 및 운영 규칙 [🎙️ 음성 (MM:SS)]
- 출석 번호, 퀴즈 관련 언급, 과제 마감일, 실습 및 교재 안내 등 교수님이 수업 중 언급한 모든 공지사항을 타임스탬프와 함께 빠짐없이 정리.

### 💡 2. 핵심 이론 및 상세 개념 분석 [출처 태그 명시]
- 잡소리(교수님의 사적인 잡담, 농담, 신변잡기, 수업 흐름과 무관한 딴소리)는 철저하게 100% 배제할 것.
- 오직 정규 학업과 시험에 직결되는 순수 강의 내용, 학문적 이론, 개념 정의, 논리적 전개, 실전 예시만을 추출하여 '최대한 상세하고 깊이 있게' 설명할 것.
- 슬라이드와 강의의 모든 챕터, 불렛포인트, 예시, 수식을 빠짐없이 체계적인 번호와 소제목으로 상세히 서술.
- 중요한 전문 용어는 반드시 `한국어 (English)`를 병기할 것.
- 표(Markdown Table), 비교 다이어그램, 수식(LaTeX/KaTeX)을 적극 활용할 것.

### 🎯 3. 핵심 키워드 정리 & 단원 종합 요약
#### 3.1 🔑 필수 핵심 키워드 사전
| 핵심 키워드 (Key Term) | 영문 표기 | 핵심 정의 및 시험 출제 포인트 |

#### 3.2 📋 단원 종합 핵심 요약 (Exam Key Takeaways)
- 오늘 다룬 강의 전체의 핵심 맥락과 주요 이론을 3~5개의 핵심 포인트로 일목요연하게 압축 정리 (시험 직전 3분 복습용).

### 📝 4. 금주 체크리스트 & 과제
- 학생들이 오늘 수업 후 수행해야 할 구체적인 실천 과제(체크박스 `- [ ]`).

* 어조: 전문적이고 깔끔한 강의노트 서술체 (-임, -함 또는 명사형 종결).
"""
        else:
            prompt = f"""
You are the head teaching assistant for [{course_info['en_name']}].
The provided audio is the full official class recording on {date_str} ({weekday_en}).
Course Context: {course_info['context']}

Listen carefully to the entire lecture audio and produce a comprehensive, academic-grade lecture note in English for exam preparation.

[Guidelines - Source Badging & Fluff-Free Academic Rigor]
* Strictly cover 100% of all theoretical topics, definitions, sub-bullets, mathematical derivations, business case studies, and instructor tips without any omission.
* Filter out all casual jokes, personal anecdotes, and off-topic digressions ("잡소리") to focus strictly on pure academic learning with maximum depth and detail.
* Tag sections and key points with:
  - `[🎙️ Spoken (MM:SS)]` : In-class verbal explanations, attendance codes, instructor's exam tips, Q&A. You MUST embed the exact audio playback timestamp (MM:SS or HH:MM:SS) where the remark begins (e.g. `[🎙️ Spoken (14:25)] Attendance code announced`, `[🎙️ Spoken (45:10)] Midterm exam hint`).
  - `[📖 Textbook/Slides]` : Official textbook definitions, syllabus rules, slide references.
  - `[💡 Integrated (MM:SS)]` : Theoretical concepts synthesized with practical business cases (with timestamp if referencing spoken explanation).

Format:
## Week {week_num} ({date_str} {weekday_en}) : [Specific Core Topic / Chapter Title]

### 📌 1. Class Announcements & Operational Guidelines `[🎙️ Spoken (MM:SS)]`
- Attendance verification code, quiz announcements, homework deadlines with exact timestamps.

### 💡 2. In-Depth Theoretical & Conceptual Analysis `[Tagged]`
- Zero filler or off-topic chitchat: Exhaustive, granular, and publication-grade academic analysis of all course concepts, theories, models, and slide bullet points.
- Provide fully articulated theoretical explanations, derivations, mathematical formulations (LaTeX/KaTeX), architecture diagrams, and comparison tables.
- Specific business scenarios, numerical examples, and professor's academic emphasis explained in maximum depth.

### 🎯 3. Core Keywords & Comprehensive Lecture Summary
#### 3.1 🔑 Key Terminology & Concepts
| Key Concept / Term | Korean Meaning | Rigorous Academic Definition & Exam Key Point |

#### 3.2 📋 Comprehensive Lecture Summary (Quick Review)
- High-yield executive summary condensing today's core themes into 3-5 high-impact takeaways for rapid pre-exam review.

### 📝 4. Action Checklist
- Concrete post-class study tasks with checkboxes `- [ ]`.
"""

    # 동일 주차 이전 차시 강의노트 감지 (중복 배제 및 진도 연속성)
    cache_c = os.path.join(CACHE_DIR, course_info["folder_name"])
    if not is_english:
        w_path = os.path.join(cache_c, f"{course_info['cname_prefix']}_{week_num}주차_강의노트.md")
    else:
        w_path = os.path.join(cache_c, f"{course_info['en_prefix']}_Week{week_num}_Lecture_Notes.md")

    prev_note_content = ""
    if os.path.exists(w_path):
        try:
            with open(w_path, "r", encoding="utf-8", errors="ignore") as f:
                c_raw = f.read().strip()
                if len(c_raw) > 200 and date_str not in c_raw:
                    prev_note_content = c_raw[:9000]
        except Exception:
            pass

    if prev_note_content:
        if not is_english:
            prompt += f"""

[🚨 이전 차시({week_num}주차 앞선 수업) 기작성 강의노트 발췌 - 중복 배제 필수 지침]
아래 내용은 이번 주차 앞선 수업에서 이미 작성되어 학생들에게 제공된 강의노트 본문입니다.
---
{prev_note_content}
---

[🚨 중복 배제 및 진도 연속성 엄격 원칙 (Zero-Duplication & Continuity)]
1. [기존 내용 단순 반복 엄금]:
   - 위 이전 차시 강의노트에 이미 수록된 학술 정의, 기본 개념, 동일한 실전 예시(도표, 주문 로그 표, 비유 등)는 이번 차시에서 똑같이 다시 작성하지 마십시오.
2. [지난 시간 복습 내용 압축]:
   - 교수님이 수업 초반에 지난 차시 내용을 복습(Review)하더라도 지면을 낭비하지 말고 "지난 차시에서는 ~을 다루었습니다." 수준으로 1~2줄로만 간략히 요약하고 즉시 오늘 수업의 새로운 진도로 넘어가십시오.
3. [오늘의 신규 진도에 90% 이상 집중]:
   - 오늘 수업에서 새롭게 등장한 심화 이론, 추가적인 분석 프레임워크, 수식 유도, 새로운 실전 사례, 오늘자 출석 번호 및 과제 공지에 집중하여 깊이 있게 서술하십시오.
4. [주차별 지식 통합]:
   - 키워드 사전과 단원 종합 요약은 이전 차시 내용을 그대로 베끼지 말고, 오늘 새롭게 배운 핵심 용어와 1주차 전체를 아우르는 최종 점검으로 구성하십시오.
"""
        else:
            prompt += f"""

[🚨 Prior Session Lecture Note Excerpt - Strict Deduplication Reference]
The following content was ALREADY synthesized in the earlier session of Week {week_num}:
---
{prev_note_content}
---

[Strict Deduplication & Seamless Continuity Directives]
1. DO NOT duplicate identical theoretical definitions, models, or tables already articulated above.
2. Condense instructor's introductory review of the previous lecture into 1-2 transition sentences.
3. Dedicate 90%+ of this note to NEW theoretical progress, new analytical frameworks, derivations, and today's operational announcements.
4. Synthesize Week {week_num} takeaways and action items cohesively.
"""

    api_key = config_manager.get_api_key() or os.environ.get("GEMINI_API_KEY", "")
    models_to_try = config_manager.get_supported_gemini_models(api_key)
    backoff_delays = [5, 10, 20]
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"file_data": {"mime_type": mime_type, "file_uri": file_uri}},
                    {"text": prompt}
                ]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 16384
            }
        }

        for attempt in range(len(backoff_delays)):
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=300) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    candidates = res.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                    raise RuntimeError(f"모델 응답 형식 불일치 ({res.get('promptFeedback', '알 수 없는 응답')})")
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    raw_bytes = e.read().decode("utf-8", errors="ignore")
                    err_json = json.loads(raw_bytes)
                    err_body = err_json.get("error", {}).get("message", raw_bytes[:100])
                except Exception:
                    err_body = str(e)
                if e.code in (503, 429, 500, 502, 504) and attempt < len(backoff_delays) - 1:
                    delay = backoff_delays[attempt]
                    print(f"  ⚠️ [{model}] HTTP {e.code} 서버 과부하 감지: {delay}초 후 자동 재시도 ({attempt+1}/{len(backoff_delays)})... ({err_body})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"  ❌ [{model}] HTTP {e.code} 에러: {err_body}")
                    break
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < len(backoff_delays) - 1:
                    delay = backoff_delays[attempt]
                    print(f"  ⚠️ [{model}] 네트워크/타임아웃 오류: {delay}초 후 자동 재시도 ({attempt+1}/{len(backoff_delays)})...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"  ❌ [{model}] 네트워크 연결 오류: {e}")
                    break
            except Exception as e:
                print(f"  ⚠️ [{model}] 호출 실패 ({e}), 다음 모델 시도...")
                break

    raise RuntimeError("모든 Gemini 모델 요청에 실패했습니다.")

def append_to_single_note_file(note_path, new_note_content, date_str, week_num, is_english=False, is_combined=True, config=None, source_files=None):
    if not os.path.exists(note_path):
        # 파일이 없을 경우 초기 헤더 작성
        audio_ref = f" (`{source_files['audio']}`)" if (source_files and source_files.get('audio')) else ""
        slide_ref = f" (`{', '.join(source_files['slides'])}`)" if (source_files and source_files.get('slides')) else ""
        c_name = config.get("name", config.get("course_name", ""))
        c_en = config.get("en_name", config.get("folder_name", c_name))
        c_prof = config.get("prof", "담당 교수님")
        if not is_english:
            title_type = "통합 강의노트" if is_combined else f"{week_num}주차 강의노트"
            header = f"# 📘 [{c_name}] {title_type} (2026-2학기)\n\n"
            header += f"- **과목명**: {c_name} ({c_en})\n"
            header += f"- **담당 교수**: {c_prof}\n\n---\n\n"
            header += "> 🏷️ **출처 구분 범례 (Source Legend)**:\n"
            header += f"> - `[🎙️ 음성]` : 교수님 실제 강의 육성 (공지사항, 출석 번호, 퀴즈/시험 출제 팁, 질문과 답변, 칠판 판서, 현장 비유 등){audio_ref}\n"
            header += f"> - `[📖 교재·슬라이드]` : 주교재(Textbook), 강의계획서(Syllabus), 공식 배포 슬라이드에 수록된 이론·정의·수식{slide_ref}\n"
            header += "> - `[💡 통합]` : 교재의 공식 이론을 바탕으로 교수님의 육성 해설과 실전 사례가 결합된 핵심 내용\n\n---\n\n"
            if is_combined:
                header += "## 📑 목차 (Table of Contents)\n- *(새로운 수업 내용이 이곳 아래로 순차적으로 적재됩니다)*\n\n---\n\n"
        else:
            title_type = "Combined Lecture Notes" if is_combined else f"Week {week_num} Lecture Notes"
            header = f"# 📘 [{c_en}] {title_type}\n\n"
            header += f"- **Course**: {c_en}\n"
            header += f"- **Instructor**: {c_prof}\n\n---\n\n"
            header += "> 🏷️ **Source Legend**:\n"
            header += f"> - `[🎙️ Spoken]` : In-class verbal lecture notes, attendance codes, exam tips, Q&A.{audio_ref}\n"
            header += f"> - `[📖 Slides/Textbook]` : Official textbook definitions, syllabus, and slides.{slide_ref}\n"
            header += "> - `[💡 Integrated]` : Synthesized concepts connecting theory and business cases.\n\n---\n\n"
            if is_combined:
                header += "## 📑 Table of Contents\n- *(Subsequent weekly lecture notes will be appended chronologically below)*\n\n---\n\n"
        content = header
    else:
        with open(note_path, "r", encoding="utf-8") as f:
            content = f.read()

    # 이미 존재하는 날짜인지 방어 검사
    if date_str in content:
        return

    # 목차 갱신 (통합본인 경우)
    if is_combined:
        lines = new_note_content.splitlines()
        header_line = ""
        for line in lines:
            if line.startswith("## ") and date_str in line:
                header_line = line.replace("## ", "").strip()
                break

        toc_marker = "- *(새로운 수업 내용이 이곳 아래로 순차적으로 적재됩니다)*" if not is_english else "- *(Subsequent weekly lecture notes will be appended chronologically below)*"
        if header_line and toc_marker in content:
            link_anchor = header_line.lower().replace(" ", "-").replace("(", "").replace(")", "").replace(":", "").replace(".", "")
            toc_entry = f"- [{header_line}](#{link_anchor})\n{toc_marker}"
            content = content.replace(toc_marker, toc_entry)

    updated_content = content.rstrip() + "\n\n---\n\n" + new_note_content + "\n"
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(updated_content)
    print(f"[{os.path.basename(note_path)}] {date_str} 강의노트 저장 완료!")

def save_to_markdown_cache(config, new_note_content, date_str, week_num, is_english=False, source_files=None):
    """주차별 개별 마크다운과 전체 통합본 마크다운을 .markdown_cache/ 및 사용자 강의노트/ 폴더에 동시 저장"""
    cache_c = os.path.join(CACHE_DIR, config["folder_name"])
    os.makedirs(cache_c, exist_ok=True)

    course_dir = resolve_course_dir(config["folder_name"])
    user_notes_dir = os.path.join(course_dir, "강의노트")
    user_week_dir = os.path.join(user_notes_dir, f"{week_num}주차")
    user_comb_dir = os.path.join(user_notes_dir, "통합")
    os.makedirs(user_notes_dir, exist_ok=True)
    os.makedirs(user_week_dir, exist_ok=True)
    os.makedirs(user_comb_dir, exist_ok=True)

    images_src = os.path.join(user_notes_dir, "images")
    images_dst = os.path.join(cache_c, "images")
    if os.path.exists(images_src) and not os.path.exists(images_dst):
        try:
            os.symlink(images_src, images_dst)
        except Exception:
            pass

    if not is_english:
        c_name = f"{config['cname_prefix']}_통합강의노트.md"
        w_name = f"{config['cname_prefix']}_{week_num}주차_강의노트.md"
    else:
        c_name = f"{config['en_prefix']}_Combined_Lecture_Notes.md"
        w_name = f"{config['en_prefix']}_Week{week_num}_Lecture_Notes.md"

    saved_paths = []
    # 1. .markdown_cache/ 격리 저장소
    c_path_cache = os.path.join(cache_c, c_name)
    w_path_cache = os.path.join(cache_c, w_name)
    append_to_single_note_file(c_path_cache, new_note_content, date_str, week_num, is_english=is_english, is_combined=True, config=config, source_files=source_files)
    append_to_single_note_file(w_path_cache, new_note_content, date_str, week_num, is_english=is_english, is_combined=False, config=config, source_files=source_files)

    # 2. 사용자가 직접 탐색하는 강의노트/ 폴더 동시 저장 (사용자 파일 찾기 보장)
    user_w_path1 = os.path.join(user_notes_dir, w_name)
    user_w_path2 = os.path.join(user_week_dir, w_name)
    user_c_path1 = os.path.join(user_notes_dir, c_name)
    user_c_path2 = os.path.join(user_comb_dir, c_name)

    append_to_single_note_file(user_w_path1, new_note_content, date_str, week_num, is_english=is_english, is_combined=False, config=config, source_files=source_files)
    append_to_single_note_file(user_w_path2, new_note_content, date_str, week_num, is_english=is_english, is_combined=False, config=config, source_files=source_files)
    append_to_single_note_file(user_c_path1, new_note_content, date_str, week_num, is_english=is_english, is_combined=True, config=config, source_files=source_files)
    append_to_single_note_file(user_c_path2, new_note_content, date_str, week_num, is_english=is_english, is_combined=True, config=config, source_files=source_files)

    saved_paths.extend([user_w_path1, user_w_path2, user_c_path1])
    return saved_paths

def scan_and_process_all_lectures(target_courses=None, target_audio_files=None):
    """모든 과목 폴더의 음성녹음 디렉터리를 스캔하여 미처리된 강의를 완전 자동으로 동적 처리"""
    print("======================================================")
    print("🔍 [강의 녹음 동적 감지 & 주차별/통합본 학습노트 적재 시작]")
    print("======================================================")

    processed_any = False

    active_configs = get_active_course_configs()
    for course_key, config in active_configs.items():
        cname = config["name"]
        folder_name = config["folder_name"]
        if target_courses and cname not in target_courses and folder_name not in target_courses:
            continue

        course_dir = resolve_course_dir(config["folder_name"])
        rec_dir = os.path.join(course_dir, "음성녹음")
        cache_c = os.path.join(CACHE_DIR, config["folder_name"])
        os.makedirs(cache_c, exist_ok=True)

        note_ko_comb = os.path.join(cache_c, f"{config['cname_prefix']}_통합강의노트.md")
        note_en_comb = os.path.join(cache_c, f"{config['en_prefix']}_Combined_Lecture_Notes.md")

        if not os.path.exists(rec_dir):
            continue

        audio_files = []
        for ext in ("*.m4a", "*.mp3", "*.wav", "*.aac"):
            audio_files.extend(glob.glob(os.path.join(rec_dir, ext)))

        audio_files.sort()

        for audio_path in audio_files:
            filename = os.path.basename(audio_path)
            if target_audio_files and filename not in target_audio_files and audio_path not in target_audio_files:
                continue

            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
            if date_match:
                date_str = date_match.group(1)
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                mtime = os.path.getmtime(audio_path)
                target_date = datetime.fromtimestamp(mtime).date()
                date_str = target_date.strftime("%Y-%m-%d")

            days_diff = (target_date - SEMESTER_START).days
            week_num = max(1, (days_diff // 7) + 1)

            allow_ko = config_manager.should_generate_korean(config["name"])
            allow_en = config_manager.should_generate_english(config["name"])

            need_ko = allow_ko and not is_date_already_in_file(note_ko_comb, date_str)
            need_en = allow_en and not is_date_already_in_file(note_en_comb, date_str)

            if not need_ko and not need_en:
                continue

            print(f"\n✨ [{config['name']}] 새로운 미처리 강의 감지됨: {filename}")
            print(f"   - 일자: {date_str} (개강 {week_num}주차)")
            print(f"   - 경로: {audio_path}")

            # 1. 구글 Gemini File API 업로드 (MIME 타입 자동 감지)
            file_uri, mime_type = upload_audio_to_gemini(audio_path)

            # 2. 한국어 강의노트 생성 및 주차별/통합본 저장
            if need_ko:
                note_ko = generate_lecture_note(config, file_uri, target_date, week_num, is_english=False, mime_type=mime_type)
                save_to_markdown_cache(config, note_ko, date_str, week_num, is_english=False)

            # 3. 영문 강의노트 생성 및 주차별/통합본 저장
            if need_en:
                note_en = generate_lecture_note(config, file_uri, target_date, week_num, is_english=True, mime_type=mime_type)
                save_to_markdown_cache(config, note_en, date_str, week_num, is_english=True)

            processed_any = True
            time.sleep(2)

    if not processed_any:
        print("\n✅ 선택된 과목의 녹음 파일이 이미 강의노트에 완벽하게 정리되어 있습니다! (새로 처리할 파일 없음)", flush=True)
    else:
        print("\n🎉 새로운 강의노트 생성이 완료되었습니다. PDF를 자동 갱신합니다...", flush=True)
        try:
            if getattr(sys, "frozen", False):
                import generate_pdfs
                generate_pdfs.generate_all_pdfs(target_courses=target_courses)
            else:
                cmd = [sys.executable, os.path.join(SCRIPT_DIR, "generate_pdfs.py")]
                if target_courses:
                    cmd.extend(["--courses"] + target_courses)
                subprocess.check_call(cmd)
            print("✅ 주차별 및 전체 통합본 PDF 최신화까지 자동 완료되었습니다!", flush=True)
        except Exception as e:
            print(f"[Warn] PDF 생성 중 오류: {e}", flush=True)

def generate_custom_lecture_note(cname, audio_path=None, slide_paths=None, date_str=None, week_num=None, lang_mode=None, log_callback=None, cancel_check=None):
    """
    사용자가 직접 선택한 과목, 음성 파일(옵션), 슬라이드 PDF(옵션)를 기반으로
    1. Gemini AI로 고품질 강의노트(마크다운) 생성 (100% 완전성 & 한/영 1:1 대칭 보장)
    2. .markdown_cache에 적재
    3. dynamic_slide_integrator로 슬라이드 도표 자동 추출 및 임베드
    4. generate_pdfs로 출판용 PDF 렌더링
    5. 실시간 진행 로그 및 ETA 콜백 전달
    """
    def check_cancel():
        if cancel_check and cancel_check():
            raise RuntimeError("🛑 사용자에 의해 작업이 즉시 중단되었습니다.")

    def log(msg, step=None, eta=None):
        check_cancel()
        print(msg, flush=True)
        if log_callback:
            try:
                log_callback(msg, step, eta)
            except Exception:
                pass

    check_cancel()
    log("=" * 65)
    log(f"🎙️ [맞춤형 학습노트 생성 스튜디오] 과목: {cname}", step=1, eta=40)
    log("=" * 65)

    configs = get_active_course_configs()
    course_cfg = None
    for cfg in configs.values():
        if cfg["name"] == cname or cfg["folder_name"] == cname:
            course_cfg = cfg
            break

    if not course_cfg:
        course_cfg = {
            "folder_name": cname,
            "name": cname,
            "en_name": cname,
            "cname_prefix": cname.replace(" ", ""),
            "en_prefix": cname.replace(" ", ""),
            "prof": "담당 교수님",
            "lang": lang_mode or "both",
            "context": f"과목: {cname}. URY AI 맞춤형 학습노트."
        }

    # 일자 및 주차 결정
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            target_date = datetime.now().date()
    else:
        target_date = datetime.now().date()

    if not week_num:
        diff_days = (target_date - SEMESTER_START).days
        week_num = max(1, (diff_days // 7) + 1)
    else:
        try:
            week_num = int(week_num)
        except Exception:
            week_num = 1

    actual_date_str = target_date.strftime("%Y-%m-%d")
    weekday_kr = WEEKDAY_KR[target_date.weekday()]
    weekday_en = WEEKDAY_EN[target_date.weekday()]

    final_lang = lang_mode or course_cfg.get("lang", "both")
    need_ko = final_lang in ("ko", "both")
    need_en = final_lang in ("en", "both")

    has_audio = audio_path and os.path.exists(audio_path)
    valid_slides = [p for p in (slide_paths or []) if os.path.exists(p)]

    log(f"• 대상 날짜: {actual_date_str} ({weekday_kr}요일) | {week_num}주차")
    audio_disp = os.path.basename(audio_path) if has_audio else "음성 자료 없음 (슬라이드 집중 분석 모드)"
    slide_disp = [os.path.basename(p) for p in valid_slides] if valid_slides else "슬라이드 미지정"
    log(f"• 음성 녹음: {audio_disp}")
    log(f"• 슬라이드: {slide_disp}")

    api_key = config_manager.get_api_key() or os.environ.get("GEMINI_API_KEY", "")
    if not api_key or len(api_key) < 10:
        raise RuntimeError("Gemini API Key가 설정되지 않았습니다. [설정] 탭에서 API Key를 등록해 주세요.")

    check_cancel()
    # 1. 파일 업로드 (음성 및 슬라이드)
    uploaded_parts = []
    if has_audio:
        check_cancel()
        log(f"\n[Step 1/4] 📤 음성 녹음 파일 클라우드 전송 중 ({os.path.basename(audio_path)})...", step=1, eta=35)
        audio_uri, audio_mime = upload_file_to_gemini(audio_path, log_fn=log)
        uploaded_parts.append({"file_data": {"mime_type": audio_mime, "file_uri": audio_uri}})

    if valid_slides:
        check_cancel()
        log(f"\n[Step 1/4] 📤 슬라이드 PDF 자료 전송 중 ({len(valid_slides)}건)...", step=1, eta=30)
        for sp in valid_slides[:2]:
            check_cancel()
            s_uri, s_mime = upload_file_to_gemini(sp, "application/pdf", log_fn=log)
            uploaded_parts.append({"file_data": {"mime_type": s_mime, "file_uri": s_uri}})

    audio_fname = os.path.basename(audio_path) if has_audio else ""
    slide_fnames = [os.path.basename(p) for p in valid_slides]
    slide_list_str = ", ".join(slide_fnames) if slide_fnames else ""
    first_slide = slide_fnames[0] if slide_fnames else "교재·슬라이드"
    source_files_dict = {
        "audio": audio_fname,
        "slides": slide_fnames
    }

    # 2. Gemini API 호출 함수 (커스텀 프롬프트)
    def call_gemini_with_parts(parts, prompt_text):
        check_cancel()
        full_parts = list(parts) + [{"text": prompt_text}]
        payload = {
            "contents": [{"parts": full_parts}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 16384
            }
        }
        models_to_try = config_manager.get_supported_gemini_models(api_key)
        top_display = ", ".join(models_to_try[:3])
        log(f"  ℹ️ [구글 최신 모델 순서 자동 감지]: {top_display} 등 {len(models_to_try)}개 모델 준비 완료", step=2)
        backoff_delays = [5, 10, 20]
        for model in models_to_try:
            check_cancel()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            for attempt in range(len(backoff_delays)):
                check_cancel()
                try:
                    log(f"  🚀 [{model}] 연결 및 강의노트 생성 시작...", step=2)
                    req_resp = [None, None]

                    def do_call():
                        try:
                            with urllib.request.urlopen(req, timeout=120) as resp:
                                req_resp[0] = resp.read()
                        except Exception as ex:
                            req_resp[1] = ex

                    call_th = threading.Thread(target=do_call, daemon=True)
                    call_th.start()

                    elapsed_wait = 0
                    while call_th.is_alive():
                        check_cancel()
                        time.sleep(1)
                        elapsed_wait += 1
                        if elapsed_wait % 5 == 0:
                            dots = "." * ((elapsed_wait // 5) % 4 + 1)
                            log(f"  ⏳ [{model}] AI 강의 심층 분석 및 강의노트 실시간 조판 중{dots} ({elapsed_wait}초 경과)", step=2)

                    if req_resp[1] is not None:
                        raise req_resp[1]

                    res = json.loads(req_resp[0].decode("utf-8"))
                    candidates = res.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
                    raise RuntimeError(f"응답 데이터 형식 불일치 ({res.get('promptFeedback', '알 수 없는 응답')})")
                except urllib.error.HTTPError as e:
                    check_cancel()
                    err_body = ""
                    try:
                        raw_bytes = e.read().decode("utf-8", errors="ignore")
                        err_json = json.loads(raw_bytes)
                        err_body = err_json.get("error", {}).get("message", raw_bytes[:120])
                    except Exception:
                        err_body = str(e)
                    if e.code in (503, 429, 500, 502, 504) and attempt < len(backoff_delays) - 1:
                        delay = backoff_delays[attempt]
                        log(f"  ⚠️ [{model}] HTTP {e.code} 서버 과부하 감지: {delay}초 후 자동 재시도 ({attempt+1}/{len(backoff_delays)})... ({err_body})", step=2)
                        time.sleep(delay)
                        continue
                    else:
                        log(f"  ❌ [{model}] HTTP {e.code} 에러: {err_body}", step=2)
                        break
                except (urllib.error.URLError, TimeoutError) as e:
                    check_cancel()
                    if attempt < len(backoff_delays) - 1:
                        delay = backoff_delays[attempt]
                        log(f"  ⚠️ [{model}] 네트워크/타임아웃 감지: {delay}초 후 자동 재시도 ({attempt+1}/{len(backoff_delays)})...", step=2)
                        time.sleep(delay)
                        continue
                    else:
                        log(f"  ❌ [{model}] 네트워크 연결 오류: {e}", step=2)
                        break
                except Exception as e:
                    check_cancel()
                    log(f"  ⚠️ [{model}] 호출 예외 ({type(e).__name__}): {e} -> 다음 모델 전환...", step=2)
                    break
        raise RuntimeError("모든 Gemini 모델 요청에 실패했습니다.")

    # 동일 주차 이전 차시 강의노트 감지 (중복 배제 및 진도 연속성)
    cache_c = os.path.join(CACHE_DIR, course_cfg["folder_name"])
    os.makedirs(cache_c, exist_ok=True)
    prev_ko_path = os.path.join(cache_c, f"{course_cfg['cname_prefix']}_{week_num}주차_강의노트.md")
    prev_en_path = os.path.join(cache_c, f"{course_cfg['en_prefix']}_Week{week_num}_Lecture_Notes.md")

    prev_ko_content = ""
    prev_en_content = ""
    if os.path.exists(prev_ko_path):
        try:
            with open(prev_ko_path, "r", encoding="utf-8", errors="ignore") as f:
                c_raw = f.read().strip()
                if len(c_raw) > 200 and actual_date_str not in c_raw:
                    prev_ko_content = c_raw[:9000]
        except Exception:
            pass

    if os.path.exists(prev_en_path):
        try:
            with open(prev_en_path, "r", encoding="utf-8", errors="ignore") as f:
                c_raw = f.read().strip()
                if len(c_raw) > 200 and actual_date_str not in c_raw:
                    prev_en_content = c_raw[:9000]
        except Exception:
            pass

    if prev_ko_content:
        log(f"  ℹ️ [진도 연속성 감지]: {week_num}주차 이전 차시 강의노트 확인됨 -> 1차시 중복 내용 배제 및 금일 신규 진도 집중 모드 가동", step=2)

    # 프롬프트 구성 (100% 완전성 & 한/영 1:1 대칭 보장 & 출처 파일명 명시 & 토큰 절약 테이블화)
    def build_custom_prompt(is_english=False, master_note=None):
        if is_english:
            if has_audio:
                source_desc = f"The provided audio is the official class recording for [{cname}] ('{audio_fname}'), along with lecture slide/course material file(s) ({slide_list_str if slide_fnames else 'None'})."
            else:
                source_desc = f"This lecture note is thoroughly synthesized from official lecture slides and course materials for [{cname}] ({slide_list_str if slide_fnames else 'None'})."

            audio_rule_en = f"- `[🎙️ {audio_fname} (MM:SS)]` : In-class verbal explanations, attendance codes, instructor's exam tips with exact audio playback timestamps (e.g. `[🎙️ {audio_fname} (14:25)] Attendance code announced`)." if has_audio else "- `[🎙️ Spoken (MM:SS)]` : In-class verbal lecture notes."
            slide_rule_en = f"- `[📖 {first_slide} p.page]` : Official definitions, syllabus rules, slide bullet points. You MUST cite the exact source file name and page or slide number (Provided files: {slide_list_str}, e.g. `[📖 {first_slide} p.3]`, `[📖 {first_slide} Slide 12]`)." if slide_fnames else "- `[📖 Slides p.page]` : Course materials and textbook sources."
            hybrid_rule_en = f"- `[💡 Integrated: {audio_fname} (MM:SS) + {first_slide} p.page]` : Theoretical concepts synthesized with practical business cases and verbal explanations." if (has_audio and slide_fnames) else "- `[💡 Integrated]` : Synthesized concepts."

            base_p = f"""You are the Head TA for [{cname}] powered by URY Engine.
Course: {cname} | Date: {actual_date_str} ({weekday_en}) | Week {week_num}
Context: {source_desc}

Produce a rigorous, publication-grade academic lecture note in English for exam preparation.

[Guidelines - 100% Comprehensive Coverage & Fluff-Free Academic Rigor]
* Strictly cover 100% of all theoretical topics, definitions, sub-bullets, mathematical derivations, business case studies, and instructor tips without any omission or excessive summarization.
* Filter out all casual jokes, personal anecdotes, and off-topic digressions ("잡소리") to keep the content purely academic and maximally thorough.
* Tag sections and key points with:
   {audio_rule_en}
   {slide_rule_en}
   {hybrid_rule_en}
* Format grading policies, evaluation criteria, and assessment weights strictly as a concise Markdown Table (`| Assessment Component | Weight (%) | Operational Details & Policies [Tagged] |`). Do NOT write repetitive paragraphs for every single grade letter.
* You MUST fully write all 4 sections to the very end without cutting off early: Section 1, Section 2 (deep theory & diagrams), Section 3 (keywords table & takeaways), and Section 4 (Action checklist).

Format:
# {cname} Week {week_num} Lecture Notes ({actual_date_str})
> 📌 **Course**: {cname} | **Week**: Week {week_num} | **Date**: {actual_date_str} ({weekday_en})
> 🏷️ **Source Reference Files**:
> - 🎙️ **Lecture Audio**: {audio_fname if has_audio else 'No audio recording'}
> - 📖 **Lecture Slides**: {slide_list_str if slide_fnames else 'No slide files specified'}

## 📌 1. Class Announcements & Operational Guidelines `[Tagged]`
- Attendance verification codes, quiz announcements, homework deadlines, course policies with exact timestamps.
- Assessment Breakdown Table (`| Assessment Component | Weight (%) | Operational Details & Policies [Tagged] |`).

## 💡 2. In-Depth Theoretical & Conceptual Analysis `[Tagged]`
- Zero filler or off-topic chitchat: Exhaustive, granular, and publication-grade academic analysis of all course concepts, theories, models, and slide bullet points.
- Provide fully articulated theoretical explanations, derivations, mathematical formulations (LaTeX/KaTeX), architecture diagrams, and comparison tables.
- Specific business scenarios, numerical examples, and professor's academic emphasis explained in maximum depth.

## 🎯 3. Core Keywords & Comprehensive Lecture Summary
### 3.1 🔑 Essential Keywords & Terminology
| Key Concept / Term | Korean Meaning | Rigorous Academic Definition & Exam Key Point |

### 3.2 📋 Comprehensive Lecture Summary (Quick Review)
- High-yield executive summary condensing today's core themes into 3-5 high-impact takeaways for rapid pre-exam review.

## 📝 4. Action Checklist & Review Tasks
- Concrete post-class study tasks with checkboxes `- [ ]`.

Tone: Professional academic publication tone."""

            if prev_en_content:
                base_p += f"""

--------------------------------------------------------------------------------
[🚨 Prior Session Lecture Note Excerpt - Strict Deduplication Reference]
The following content was ALREADY synthesized in the earlier session of Week {week_num}:
{prev_en_content}

[Strict Deduplication & Seamless Continuity Directives]
1. DO NOT duplicate identical theoretical definitions, models, or tables already articulated above.
2. Condense instructor's introductory review of the previous lecture into 1-2 transition sentences.
3. Dedicate 90%+ of this note to NEW theoretical progress, new analytical frameworks, derivations, and today's operational announcements.
4. Synthesize Week {week_num} takeaways and action items cohesively.
--------------------------------------------------------------------------------
"""
            return base_p

        else:
            # 한국어 강의노트 프롬프트
            if master_note:
                # 영문 마스터 노트가 주어졌을 때 -> 100% 1:1 대칭 매핑 모드
                base_p = f"""당신은 해당 전공 과목의 최고 수석 조교이자 URY Engine AI입니다.
과목명: {cname} | 일자: {actual_date_str}({weekday_kr}) | {week_num}주차
참조 원본 파일:
- 강의 음성: {audio_fname if has_audio else '음성 녹음 없음'}
- 강의 슬라이드: {slide_list_str if slide_fnames else '지정된 슬라이드 없음'}

[🚨 영문 마스터 노트 기반 100% 1:1 완벽 대칭 조판 지침 (Master Blueprint Synchronization)]
아래에 제공된 [영문 마스터 강의노트]는 이번 강의의 구조적 기준 청사진(Master Blueprint)입니다.
학생이 한/영 버전을 완벽하게 상호 대조하며 공부할 수 있도록, 영문 마스터 노트의 모든 섹션, 표, 세부 개념, 다이어그램, 키워드 사전, 체크리스트를 빠짐없이 1:1 완벽 대응하여 한국어로 번역 및 학술 조판하십시오.

[핵심 작성 원칙]
1. [섹션 번호 및 구조 100% 일치]:
   - 1. 수업 개요 및 공지사항, 2. 핵심 이론 및 상세 개념 분석(2.1, 2.2, 2.3 등), 3. 핵심 키워드 정리 & 단원 종합 요약(3.1 표, 3.2 요약), 4. 금주 핵심 복습 체크리스트까지 4개 섹션 전체를 영문 마스터 노트와 정확히 1:1로 일치시킬 것.
   - 영문 노트에 있는 2번 이론 분석(마케팅 가치 패러다임, 아스키 다이어그램, 소비자 인식 및 브랜드 자산, 4Ps 테이블 등)이 한글 강의노트에서 절대로 누락되지 않도록 100% 대칭 수록할 것.
2. [표(Markdown Table) 구조 엄격 준수]:
   - 성적 평가 방식은 영문처럼 `| 평가 항목 | 비중 (%) | 세부 운영 규칙 및 정책 [출처 태그] |` 테이블로 깔끔하게 정리할 것 (A+, A0 등 개별 학점 구간을 줄글로 길게 늘여 쓰지 말 것).
   - 4Ps 분석표, 키워드 사전 표 역시 영문 마스터 노트의 컬럼과 행 구조를 1:1 그대로 유지하여 번역할 것.
3. [출처 태그 보존]:
   - 영문 마스터 노트에 표기된 모든 출처 태그(`[🎙️ {audio_fname} (MM:SS)]`, `[📖 {first_slide} p.X]`, `[💡 통합]`)를 한글 노트의 정확한 해당 위치에 동일하게 기재할 것.
4. [전문 용어 병기]:
   - 핵심 개념은 반드시 `한국어 번역 (English Official Term)` 형태로 병기할 것.
5. [절대 중단 금지]:
   - 토큰 제한이 16,384로 충분히 확보되어 있으므로, 절대로 1번 섹션에서 멈추지 말고 4번 체크리스트까지 완벽하게 끝까지 작성할 것.

[영문 마스터 강의노트 청사진]:
--------------------------------------------------------------------------------
{master_note}
--------------------------------------------------------------------------------

한국어 강의노트 형식:
# {cname} {week_num}주차 맞춤 강의노트 ({actual_date_str})
> 📌 **과목명**: {cname} | **주차**: {week_num}주차 | **수업 일자**: {actual_date_str} ({weekday_kr})
> 🏷️ **참조 원본 파일**:
> - 🎙️ **강의 음성**: {audio_fname if has_audio else '음성 녹음 없음'}
> - 📖 **강의 슬라이드**: {slide_list_str if slide_fnames else '지정된 슬라이드 없음'}

## 📌 1. 수업 개요 및 주요 공지사항 `[Tagged]`
- 평가 기준 테이블 (`| 평가 항목 | 비중 (%) | 세부 운영 규칙 및 정책 [출처 태그] |`) 및 출석/과제/시험 규정

## 💡 2. 핵심 이론 및 상세 개념 분석 `[Tagged]`
- 영문 마스터 노트의 2.1, 2.2, 2.3 등 모든 이론, 프레임워크, 도표, 다이어그램을 100% 대칭 해설

## 🎯 3. 핵심 키워드 정리 & 단원 종합 요약
### 3.1 🔑 필수 핵심 키워드 사전
| 핵심 키워드 (Key Term) | 영문 표기 | 핵심 정의 및 시험 출제 포인트 |

### 3.2 📋 단원 종합 핵심 요약 (Exam Key Takeaways)
- 3~5개 핵심 포인트

## 📝 4. 금주 핵심 복습 체크리스트
- `- [ ]` 체크리스트 항목

어조: 전문적이고 깔끔한 강의노트 서술체 (-임, -함 또는 명사형 종결)."""
                return base_p

            else:
                # 독립 한국어 생성 모드
                if has_audio:
                    source_desc = f"제공된 오디오는 [{cname}]의 실제 강의 녹음 ('{audio_fname}')이며, 슬라이드 자료 ({slide_list_str if slide_fnames else '없음'})가 함께 제공되었습니다."
                else:
                    source_desc = f"본 강의노트는 [{cname}]의 공식 강의 슬라이드 및 교재 자료 ({slide_list_str if slide_fnames else '없음'})를 바탕으로 작성되는 완벽한 시험 대비 독학용 집중 강의노트입니다."

                audio_rule_kr = f"- `[🎙️ {audio_fname} (MM:SS)]` : 교수님 실제 육성/설명/시험팁 (음성 발언 시작 시간 표기, 예: `[🎙️ {audio_fname} (14:25)]`)." if has_audio else "- `[🎙️ 음성 (MM:SS)]` : 교수님 실제 육성 강의노트."
                slide_rule_kr = f"- `[📖 {first_slide} p.페이지]` : 슬라이드 본문, 공식 정의, 수식, 표 (제공된 파일: {slide_list_str}, 예: `[📖 {first_slide} p.3]`, `[📖 {first_slide} Slide 12]`)." if slide_fnames else "- `[📖 교재·슬라이드 p.페이지]` : 교재 및 슬라이드 출처."
                hybrid_rule_kr = f"- `[💡 통합: {audio_fname} (MM:SS) + {first_slide} p.페이지]` : 이론과 교수님 육성 해설 결합." if (has_audio and slide_fnames) else "- `[💡 통합]` : 이론과 실전 사례 결합."

                base_p = f"""당신은 해당 전공 과목의 최고 수석 조교이자 URY Engine AI입니다.
과목명: {cname} | 일자: {actual_date_str}({weekday_kr}) | {week_num}주차
배경 정보: {source_desc}

학생이 복습 및 중간/기말고사에 완벽하게 대비할 수 있도록 매우 체계적이고 깊이 있는 강의노트를 작성해 주세요.

[🚨 내용 완전성 및 4개 섹션 완결 원칙]
- 슬라이드 및 교재에 포함된 모든 공식 정의, 세부 불렛포인트, 예시, 비즈니스/수학적 사례, 수식, 표의 내용을 단 하나도 요약하여 누락하지 말고 100% 완전하게 한국어로 번역 및 상세 해설할 것.
- 핵심 전문 용어는 반드시 `한글 번역 (English Official Term)` 형태로 병기할 것.
- 평가 규정 및 세부 배점은 `| 평가 항목 | 비중 (%) | 세부 운영 규칙 및 정책 [출처 태그] |` 마크다운 테이블로 집약하고, 불필요한 줄글로 페이지를 낭비하지 말 것.
- 반드시 1. 개요, 2. 핵심 이론 분석, 3. 키워드 사전, 4. 체크리스트까지 4개 섹션 전체를 끝까지 완벽히 작성할 것.

[작성 가이드라인 - 출처 구분 및 파일명 네비게이터 필수]
1. 출처 태그 명시:
   {audio_rule_kr}
   {slide_rule_kr}
   {hybrid_rule_kr}
2. 형식:
# {cname} {week_num}주차 맞춤 강의노트 ({actual_date_str})
> 📌 **과목명**: {cname} | **주차**: {week_num}주차 | **수업 일자**: {actual_date_str} ({weekday_kr})
> 🏷️ **참조 원본 파일**:
> - 🎙️ **강의 음성**: {audio_fname if has_audio else '음성 녹음 없음'}
> - 📖 **강의 슬라이드**: {slide_list_str if slide_fnames else '지정된 슬라이드 없음'}

## 📌 1. 수업 개요 및 주요 공지사항 `[Tagged]`
- 이번 주차 핵심 학습 목표 및 출석/과제/시험 관련 공지 사항을 타임스탬프와 함께 완벽 정리
- 성적 평가 기준 테이블 (`| 평가 항목 | 비중 (%) | 세부 운영 규칙 및 정책 [출처 태그] |`)

## 💡 2. 핵심 이론 및 상세 개념 분석 `[Tagged]`
- 잡소리(사담, 농담, 딴소리)는 일절 배제하고, 슬라이드와 강의의 모든 챕터, 불렛포인트, 세부 개념, 공식을 빠짐없이 체계적인 번호와 소제목으로 '최대한 상세하게' 해설
- 비교 표(Markdown Table), 수식(LaTeX/KaTeX), 구조 다이어그램 적극 활용

## 🎯 3. 핵심 키워드 정리 & 단원 종합 요약
### 3.1 🔑 필수 핵심 키워드 사전
| 핵심 키워드 (Key Term) | 영문 표기 | 핵심 정의 및 시험 출제 포인트 |

### 3.2 📋 단원 종합 핵심 요약 (Exam Key Takeaways)
- 3~5개의 핵심 포인트 압축 정리

## 📝 4. 금주 핵심 복습 체크리스트
- 학생이 오늘 반드시 점검해야 할 질문과 과제 (`- [ ]`)

어조: 전문적이고 깔끔한 강의노트 서술체 (-임, -함 또는 명사형 종결)."""

                if prev_ko_content:
                    base_p += f"""

--------------------------------------------------------------------------------
[🚨 이전 차시({week_num}주차 앞선 수업) 기작성 강의노트 발췌 - 중복 배제 필수 참고자료]
아래 내용은 이번 주차 앞선 수업에서 이미 작성되어 학생들에게 배포된 강의노트 본문입니다:
{prev_ko_content}

[🚨 중복 배제 및 진도 연속성 엄격 원칙 (Zero-Duplication & Continuity)]
1. [기존 내용 단순 반복 엄금]: 위 1차시 강의노트에 이미 수록된 학술 정의, 기본 개념, 동일한 실전 예시는 이번 2차시 강의노트에서 다시 작성하지 마십시오.
2. [지난 시간 복습 내용 압축]: 복습 내용은 1~2줄로만 간략히 요약하고 즉시 오늘 수업의 새로운 진도로 넘어가십시오.
3. [오늘의 신규 진도에 90% 이상 집중]: 오늘 새롭게 등장한 심화 이론, 분석 프레임워크, 수식 유도, 사례에 집중하십시오.
4. [1주차 주차별 지식 통합]: 키워드 사전과 복습 체크리스트는 1주차 전체를 아우르는 최종 점검 질문으로 구성하십시오.
--------------------------------------------------------------------------------
"""
                return base_p

    last_content = ""
    note_en = None
    note_ko = None
    all_saved_mds = []
    cdir = config_manager.get_course_dir(course_cfg["folder_name"])
    user_notes_dir = os.path.join(cdir, "강의노트")
    os.makedirs(user_notes_dir, exist_ok=True)

    # 3. 마크다운 생성 및 저장 (both 모드일 경우 영문 마스터 노트를 1차 생성하여 한국어 노트와 100% 1:1 대칭 보장)
    if need_en:
        check_cancel()
        en_eta = 45 if has_audio else 20
        log("\n[Step 2/4] 🧠 Gemini AI 영문 맞춤 강의노트 심층 작성 중 (마스터 청사진 수립)...", step=2, eta=en_eta)
        prompt_en = build_custom_prompt(is_english=True)
        note_en = call_gemini_with_parts(uploaded_parts, prompt_en)
        check_cancel()
        saved = save_to_markdown_cache(course_cfg, note_en, actual_date_str, week_num, is_english=True, source_files=source_files_dict)
        if saved:
            all_saved_mds.extend(saved)
        last_content = note_en
        log("  ✅ 영문 마스터 강의노트 적재 완료", step=2, eta=40 if (has_audio and need_ko) else 15)

    if need_ko:
        check_cancel()
        ko_eta = 80 if (has_audio and need_en) else (50 if has_audio else 35)
        log("\n[Step 2/4] 🧠 Gemini AI 한국어 맞춤 강의노트 심층 작성 중 (100% 1:1 대칭 & 완전성 보장)...", step=2, eta=ko_eta)
        prompt_ko = build_custom_prompt(is_english=False, master_note=note_en)
        note_ko = call_gemini_with_parts(uploaded_parts, prompt_ko)
        check_cancel()
        saved = save_to_markdown_cache(course_cfg, note_ko, actual_date_str, week_num, is_english=False, source_files=source_files_dict)
        if saved:
            all_saved_mds.extend(saved)
        last_content = note_ko
        log("  ✅ 한국어 강의노트 적재 완료 (한/영 1:1 완벽 대칭 & 내용 누락 방지 검증 통과)", step=2, eta=10)

    # 4. 슬라이드 도표 자동 추출 & 마크다운 임베드
    check_cancel()
    try:
        import dynamic_slide_integrator
        log("\n[Step 3/4] 📸 슬라이드 도표 자동 추출 및 마크다운 임베드 수행 중...", step=3, eta=8)
        dynamic_slide_integrator.process_course_slides_dynamic(course_cfg, slide_paths=valid_slides)
        log("  ✅ 슬라이드 고화질 도표(180 DPI) 추출 및 이미지 링크 결합 완료", step=3, eta=5)
    except Exception as e:
        log(f"  ⚠️ 슬라이드 도표 임베드 알림: {e}", step=3)

    # 5. 출판용 PDF 렌더링
    check_cancel()
    generated_pdfs = []
    try:
        import generate_pdfs
        log("\n[Step 4/4] 📑 출판용 고품질 PDF 컴파일 및 렌더링 중...", step=4, eta=3)
        target_keys = list(set([cname, course_cfg.get("name", ""), course_cfg.get("folder_name", "")]))
        target_keys = [k for k in target_keys if k]
        generate_pdfs.generate_all_pdfs(target_courses=target_keys)
        pdf_glob = os.path.join(cdir, "강의노트", "**", "*.pdf")
        for p in glob.glob(pdf_glob, recursive=True):
            if p not in generated_pdfs:
                generated_pdfs.append(p)
        log(f"  ✅ 출판용 PDF 렌더링 완료 ({len(generated_pdfs)}개 문서 감지됨)", step=4, eta=1)
    except Exception as e:
        log(f"  ⚠️ PDF 컴파일 중 알림: {e}", step=4)

    unique_mds = sorted(list(set(all_saved_mds)))
    log("\n🎉 [완료] 맞춤형 학습노트 저장이 성공적으로 완료되었습니다!", step=4, eta=0)
    log(f"📂 [최종 저장 폴더]: {user_notes_dir}")
    for md_file in unique_mds:
        log(f"  📄 마크다운 강의노트: {os.path.basename(md_file)}")
    for pdf_file in sorted(generated_pdfs):
        log(f"  📑 출판용 PDF: {os.path.basename(pdf_file)}")

    return {
        "course_name": cname,
        "date_str": actual_date_str,
        "week_num": week_num,
        "content": last_content,
        "pdf_files": sorted(generated_pdfs),
        "markdown_files": unique_mds,
        "notes_dir": user_notes_dir
    }

if __name__ == "__main__":
    scan_and_process_all_lectures()
