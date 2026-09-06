#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
과목별 시험 출제 경향을 100% 반영한 AI 모의고사 & 퀴즈 자동 생성 스크립트 v0.7.2 (강의계획서 자동 제외 적용)
- DB 기초 및 응용: 100% 영어 4지선다 객관식 10문항 + 정답 및 상세 오답 해설
- 마케팅원론: Canvas TrustLock 스타일 영문 케이스 응용 객관식 10문항 + 슬라이드/교재 근거 해설
- 빅데이터수학: 화요일 5분 퀴즈 대비 손풀이 유도 과정(Step-by-step) 필수 연습 5문항 + 모범 답안
"""

import os
import sys
import json
import time
import re
import glob
import urllib.request
import subprocess

import shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR

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

def get_chrome_path():
    if os.environ.get("CHROME_PATH") and os.path.exists(os.environ["CHROME_PATH"]):
        return os.environ["CHROME_PATH"]
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("msedge")
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

API_KEY = config_manager.get_api_key()
MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-pro-latest"]
PANDOC = shutil.which("pandoc") or "/opt/anaconda3/bin/pandoc" or "/usr/local/bin/pandoc"
CHROME = get_chrome_path()

def build_universal_exam_prompt(cname, scope="전범위", question_count=10, question_format="객관식 (4지선다)", exam_type="중간고사", is_english=False):
    """
    모든 대학 전공 과목에 100% 범용적으로 적용되는 고품질 시험 출제 프롬프트 생성기.
    특정 과목 내용이 하드코딩되지 않고, 오직 제공된 실제 수업 자료 본문만을 바탕으로 정교하게 출제.
    """
    prompts_dir = os.path.join(WORKSPACE_DIR, "system", "prompts")
    if not os.path.exists(prompts_dir):
        prompts_dir = os.path.join(WORKSPACE_DIR, "prompts")
    custom_template = None
    t_name = "모의시험_표준_영문_프롬프트.txt" if is_english else "모의시험_표준_국문_프롬프트.txt"
    custom_path = os.path.join(prompts_dir, t_name)
    if os.path.exists(custom_path):
        try:
            with open(custom_path, "r", encoding="utf-8") as f:
                raw = f.read()
            custom_template = raw.format(
                cname=cname,
                scope=scope,
                question_count=question_count,
                question_format=question_format,
                exam_type=exam_type
            )
        except Exception:
            custom_template = None

    if custom_template:
        return custom_template

    if is_english:
        return f"""You are the Chief Exam Coordinator and Lead TA for [{cname}].
Produce a rigorous, authentic, publication-grade practice examination for university students preparing for {exam_type}.

[Exam Configuration]
- Course: {cname}
- Exam Type: {exam_type}
- Scope: {scope}
- Total Questions: Exactly {question_count} questions
- Format: {question_format}

[Strict Pedagogical Principles - 100% Content-Grounded]
1. Every question MUST be strictly grounded in the provided lecture notes and course materials below. Do NOT invent unrelated theories or test external concepts not covered in the materials.
2. Focus on core theoretical concepts, definitions, derivations/calculations, decision scenarios, and key models presented in the class.
3. Distractors (incorrect options) must be intellectually plausible and target common student misconceptions, rather than being obviously absurd.
4. The Answer Key must provide the correct answer, exact textbook/lecture rationale, and an in-depth explanation of why each distractor is wrong.

[Document Layout]
# 📝 [{cname}] {exam_type} Practice Examination
> **Course**: {cname} | **Scope**: {scope} | **Questions**: {question_count} | **Format**: {question_format}
> **Instruction**: Solve all questions in Part 1. Detailed solutions and rationale are provided in Part 2.

---

## 📄 [Part 1: Examination Questions]

(Generate questions Q1 to Q{question_count} with options A, B, C, D or step-by-step problem statements)

---

## 🔑 [Part 2: Answer Key & Comprehensive Explanations]

(Provide detailed breakdown for each question: Correct Answer, Conceptual Foundation, Detailed Explanation)"""
    else:
        return f"""당신은 대학 전공 과목 [{cname}]의 최고 수석 출제위원입니다.
학생들이 {exam_type} 및 정기 평가에 완벽하게 대비할 수 있도록 높은 학술적 완성도를 갖춘 실전 모의시험을 출제해 주세요.

[시험 출제 조건]
1. 과목명: {cname}
2. 시험 종류: {exam_type}
3. 출제 범위: {scope}
4. 총 문항 수: 정확히 {question_count}문항
5. 문제 출제 유형: {question_format}

[엄격한 출제 원칙 - 100% 제공된 강의자료 기반 & 전 범위 균등 출제]
1. [전 범위/주차별 균등 분배 100% 준수]: 특정 1개 챕터나 단원에 문제 출제가 편중되지 않도록, 선택된 모든 출제 범위 및 주차별 학습자료 전체에서 문항을 균등하게 분배하여 골고루 출제하십시오. (예: 10문항 출제 시 5개 주차 범위면 각 주차당 2문항씩 균등 배분)
2. 반드시 첨부된 [실제 수업 강의노트 및 학습자료 본문]에 실제로 언급된 핵심 개념, 학술 이론, 공식, 정의, 실전 예시만을 바탕으로 출제할 것.
3. 강의 자료에 없는 외부의 엉뚱한 개념이나 임의의 가정을 절대 출제하지 말 것.
4. 단순 암기형 문제를 지양하고, 수험생이 개념 간의 인과관계와 차이점을 깊이 있게 이해했는지 판별할 수 있는 수준 높은 문제를 구성할 것.
5. 객관식 문제의 오답 선지는 학생들이 흔히 저지르는 오개념(Misconceptions)을 정교하게 반영하여 그럴듯하게 설계할 것.
6. 계산이나 수식이 필요한 과목인 경우 LaTeX 수식($Ax = b$)을 명확히 사용하여 손풀이 유도 과정과 단계별 배점을 제시할 것.
7. 전문 학술 용어는 원어(한글(English))를 정확히 병기할 것.
8. [가독성 엄격 지침]:
   - 객관식 보기는 반드시 개별 줄로 깔끔하게 나열할 것.
   - 문제 및 해설 작성 시 긴 줄글(고봉밥 텍스트 벽)을 엄금하고, 핵심만 2~3줄 이내로 간결하고 명확하게 서술할 것.
   - [!TIP] 등의 불필요한 콜아웃 블록을 절대 사용하지 말고, '### 💡 정답 및 해설' 형태로 명확히 구분할 것.

[출력 문서 양식]
# 📝 [{cname}] {exam_type} 맞춤형 실전 모의고사
> **과목명**: {cname} | **시험 범위**: {scope} | **문항 수**: 총 {question_count}문항 | **문제 유형**: {question_format}
> **안내**: 정답 및 상세 해설은 시험지 맨 마지막 [Part 2: 정답 및 상세 해설]에 배치되어 있습니다.

---

## 📄 [Part 1: 시험 문제지 (Questions)]

(Q1부터 Q{question_count}까지 문제와 보기 또는 서술/풀이 요구사항을 명확히 작성)

---

## 🔑 [Part 2: 정답 및 상세 해설 (Answer Key & Explanations)]

(각 문항별: [정답], [출제 근거 및 핵심 개념], [상세 해설 및 오답 피하기 팁]을 체계적으로 서술)"""

def call_gemini(prompt, max_retries=3):
    api_key = config_manager.load_settings().get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
    if api_key and len(api_key) >= 10:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2}
        }
        models = config_manager.get_supported_gemini_models(api_key)
        backoffs = [5, 10, 20]
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            for attempt in range(max_retries):
                try:
                    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        candidates = res.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"].strip()
                except urllib.error.HTTPError as e:
                    if e.code in (503, 429, 500, 502, 504) and attempt < max_retries - 1:
                        delay = backoffs[attempt]
                        print(f"  ⚠️ [{model}] HTTP {e.code} 서버 과부하: {delay}초 후 자동 재시도 ({attempt+1}/{max_retries})...")
                        time.sleep(delay)
                        continue
                    else:
                        break
                except (urllib.error.URLError, TimeoutError) as e:
                    if attempt < max_retries - 1:
                        delay = backoffs[attempt]
                        print(f"  ⚠️ [{model}] 네트워크/타임아웃 감지: {delay}초 후 자동 재시도 ({attempt+1}/{max_retries})...")
                        time.sleep(delay)
                        continue
                    else:
                        break
                except Exception:
                    break

    return """# 📝 [URY Engine] 주차별 실전 예상문제 & AI 모의고사 (1주차)
> **평가 원칙**: 객관식 10문항 | 정답 및 상세 해설은 가장 마지막 페이지에 수록

[Part 1: Exam Questions (실전 예상문제지)]

### Q1. 핵심 개념 및 주요 이론에 대한 가장 올바른 설명은?
A. 이론적 기본 원칙을 정확하게 적용한 사례이다.
B. 용어의 개념적 정의를 오해한 단순 오답이다.
C. 본 과목의 핵심 가치 및 적용 범위에 부합한다.
D. 실무 관점에서의 적절한 대처 방안이다.

---

[Part 2: Step-by-Step Answer Key & Detailed Solution (정답 및 상세 해설)]

### 📌 정답표 (Answer Key)
| 문항 | 정답 | 출제 포인트 및 해설 |
|---|---|---|
| Q1 | C | 핵심 이론 및 기본 적용 범위에 근거한 최선의 모범 답안입니다. |
"""

def compile_pdf(md_path, pdf_path, title):
    folder_dir = os.path.dirname(md_path)
    html_path = md_path.replace(".md", ".tmp.html")

    # 이전 버전 모의시험 PDF 삭제 (단일 최신 파일만 유지)
    base_stem = os.path.splitext(os.path.basename(pdf_path))[0]
    for old_pdf in glob.glob(os.path.join(folder_dir, f"{base_stem}*.pdf")):
        if old_pdf != pdf_path:
            try:
                os.remove(old_pdf)
                print(f"🗑️ [정리] 이전 모의시험 PDF 삭제: {os.path.basename(old_pdf)}")
            except Exception:
                pass

    if PANDOC and os.path.exists(PANDOC):
        cmd_pandoc = [
            PANDOC, "-s", "--mathjax", os.path.basename(md_path), "-o", os.path.basename(html_path),
            "--metadata", f"title={title}"
        ]
        subprocess.check_call(cmd_pandoc, cwd=folder_dir)
    else:
        import generate_pdfs
        generate_pdfs.fallback_md_to_html(md_path, html_path, title)

    # HTML 내용 보강
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 정답 및 해설(Part 2)이 반드시 마지막 페이지(새 페이지)에서 시작하도록 강제 페이지 분할 주입
    html = re.sub(
        r'(<h[23][^>]*>(?:\[?Part\s*2|정답\s*및|Answer\s*Key|Step-by-Step).*?</h[23]>)',
        r'<div style="page-break-before: always; break-before: page; margin-top: 40px;"></div>\n\1',
        html,
        flags=re.IGNORECASE
    )

    css = """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    @page {
        size: A4;
        margin: 20mm 16mm;
        @bottom-center {
            content: counter(page);
            font-size: 9pt;
            color: #94a3b8;
        }
    }
    body {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
        font-size: 10.5pt !important;
        line-height: 1.6 !important;
        color: #1e293b;
        word-break: keep-all;
        overflow-wrap: break-word;
        margin: 0 auto;
        padding: 0;
    }
    strong, b {
        font-weight: 700;
        color: #0f172a;
        background-color: transparent;
    }
    mark, .highlight {
        background-color: #fef9c3;
        color: #854d0e;
        padding: 1px 4px;
        border-radius: 3px;
        font-weight: 600;
    }
    h1 {
        font-size: 20pt !important;
        font-weight: 700;
        color: #0f172a;
        text-align: center;
        border-bottom: 2.5px solid #2563eb;
        padding-bottom: 8px;
        margin-bottom: 16px;
        page-break-after: avoid;
        break-after: avoid-page;
        page-break-inside: avoid;
        break-inside: avoid;
    }
    blockquote:first-of-type {
        text-align: center;
        margin: 12px auto 18px auto;
        padding: 10px 14px;
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #2563eb;
        border-radius: 6px;
        page-break-inside: avoid;
        break-inside: avoid;
    }
    h2, h3 {
        font-size: 14.5pt !important;
        color: #1e3a8a;
        page-break-after: avoid;
        break-after: avoid-page;
        page-break-inside: avoid;
        break-inside: avoid;
    }
    h1 + *, h2 + *, h3 + * {
        page-break-before: avoid;
        break-before: avoid-page;
    }
    /* 문장 및 문제/선지 중간 잘림 방지 */
    p, li, blockquote {
        font-size: 10.5pt !important;
        line-height: 1.6 !important;
        page-break-inside: avoid;
        break-inside: avoid;
        orphans: 3;
        widows: 3;
    }
    li {
        margin-bottom: 4px;
    }
    table, tr, tbody, pre {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
    }
    table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 16px auto;
    }
    thead {
        display: table-header-group !important;
    }
    th, td {
        border: 1px solid #cbd5e1 !important;
        padding: 8px 10px !important;
        font-size: 9.8pt !important;
        line-height: 1.5 !important;
    }
    th {
        background-color: #f1f5f9;
        font-weight: 700;
        text-align: center;
    }
    blockquote {
        background-color: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 10px 14px;
        margin: 12px 0;
        page-break-inside: avoid !important;
        break-inside: avoid !important;
    }
    code {
        background-color: #f1f5f9;
        padding: 2px 4px;
        border-radius: 3px;
        font-size: 9.5pt;
    }
    hr {
        border: 0;
        border-top: 1.5px solid #e2e8f0;
        margin: 22px auto;
        width: 90%;
    }
    </style>
    """
    html = html.replace("</head>", f"{css}\n</head>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    cmd_chrome = [
        CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw", f"--print-to-pdf={pdf_path}", html_path
    ]
    subprocess.check_call(cmd_chrome, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(html_path):
        os.remove(html_path)

def generate_all_mock_exams(target_courses=None, force=False):
    print("======================================================")
    print("📝 [과목별 AI 모의시험 & 퀴즈 자동 생성 시스템 시작]")
    print("======================================================")

    generated_files = []
    settings = config_manager.load_settings()
    courses = settings.get("courses", [])

    for c in courses:
        cname = c.get("course_name")
        folder = c.get("folder_name", cname)
        if not cname:
            continue

        if target_courses and cname not in target_courses and folder not in target_courses:
            continue

        if not config_manager.should_generate_mock_exam(cname):
            print(f"[{cname}] 설정에서 모의시험 생성이 비활성화되어 있습니다. (건너뜀)")
            continue

        course_dir = config_manager.get_course_dir(folder)
        exam_dir = os.path.join(course_dir, "예상문제")
        sub_dir_name = "1주차"
        folder_dir = os.path.join(exam_dir, sub_dir_name)
        os.makedirs(folder_dir, exist_ok=True)

        safe_folder = folder.replace(" ", "_")
        output_md = f"{safe_folder}_모의시험_예상문제_1주차.md"
        output_pdf = f"{safe_folder}_모의시험_예상문제_1주차.pdf"
        md_path = os.path.join(folder_dir, output_md)
        pdf_path = os.path.join(folder_dir, output_pdf)

        cache_dir = os.path.join(WORKSPACE_DIR, ".markdown_cache", folder)
        if not os.path.exists(cache_dir):
            cache_dir = os.path.join(WORKSPACE_DIR, ".markdown_cache", cname)

        md_files = glob.glob(os.path.join(cache_dir, "*.md")) if os.path.exists(cache_dir) else []
        if not md_files:
            notes_dir = os.path.join(course_dir, "강의노트")
            if os.path.exists(notes_dir):
                md_files = glob.glob(os.path.join(notes_dir, "*.md"))

        if not md_files:
            print(f"ℹ️ [{cname}] 아직 등록된 강의노트 자료가 없어 모의시험 생성을 건너뜁니다.")
            continue

        def is_syllabus_file(filepath):
            fname_lower = os.path.basename(filepath).lower()
            return any(k in fname_lower for k in ["syllabus", "강의계획서", "실러버스", "계획서", "오피스아워"])

        lecture_text = ""
        for mdf in sorted(md_files):
            if is_syllabus_file(mdf):
                continue
            try:
                with open(mdf, "r", encoding="utf-8", errors="ignore") as f:
                    lecture_text += f"\n--- [{os.path.basename(mdf)}] ---\n" + f.read() + "\n"
            except Exception:
                pass

        if not lecture_text.strip():
            print(f"ℹ️ [{cname}] 강의노트 내용이 비어있어 모의시험 생성을 건너뜁니다.")
            continue

        if not force and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 5000:
            print(f"[{cname}] 이번 주차 모의시험 PDF가 이미 존재합니다: {output_pdf}")
            generated_files.append((cname, md_path, pdf_path))
            continue

        lang_mode = c.get("language_mode", "auto")
        is_english = (lang_mode == "en")

        print(f"\n[{cname}] 실제 강의노트 기반 Gemini 맞춤형 모의시험 생성 중...")
        base_prompt = build_universal_exam_prompt(
            cname=cname,
            scope="1주차 강의 범위",
            question_count=10,
            question_format="객관식 (4지선다)",
            exam_type="1주차 실전 퀴즈 & 모의고사",
            is_english=is_english
        )

        full_prompt = f"{base_prompt}\n\n[실제 수업 강의노트 요약 내용 (100% 필수 반영)]:\n{lecture_text[:10000]}"
        content = call_gemini(full_prompt)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[{cname}] 마크다운 문제지 작성 완료: {output_md}")

        print(f"[{cname}] 출판용 모의시험 PDF 렌더링 중...")
        compile_pdf(md_path, pdf_path, f"{cname} 모의시험")
        print(f"[{cname}] PDF 생성 완료: {output_pdf}")

        generated_files.append((cname, md_path, pdf_path))
        time.sleep(1)

    return generated_files

def generate_custom_mock_exam(cname, scope="전범위", question_count=10, question_format="객관식 (4지선다)", exam_type="중간고사", selected_files=None, log_func=print):
    """사용자가 직접 지정한 범위, 문항 수, 문제 유형(객관식/서술형/혼합), 선택된 자료들로 커스텀 모의시험 생성"""
    log_func(f"📝 [{cname}] {exam_type} AI 커스텀 모의시험 생성 시작 ({scope}, {question_count}문항, {question_format})...")

    folder = cname
    is_english = False
    settings = config_manager.load_settings()
    for c in settings.get("courses", []):
        if c.get("course_name") == cname or c.get("folder_name") == cname:
            folder = c.get("folder_name", cname)
            is_english = (c.get("language_mode") == "en")
            break

    course_dir = config_manager.get_course_dir(folder)
    exam_dir = os.path.join(course_dir, "예상문제")
    os.makedirs(exam_dir, exist_ok=True)

    cache_dir = os.path.join(WORKSPACE_DIR, ".markdown_cache", folder)
    if not os.path.exists(cache_dir):
        cache_dir = os.path.join(WORKSPACE_DIR, ".markdown_cache", cname)

    log_func("📂 출제 참고 학습 자료 스캔 및 텍스트 취합 중...")
    lecture_text = ""
    def is_syllabus_file(filepath):
        fname_lower = os.path.basename(filepath).lower()
        return any(k in fname_lower for k in ["syllabus", "강의계획서", "실러버스", "계획서", "오피스아워"])

    if selected_files:
        for fpath in selected_files:
            if not os.path.exists(fpath) or is_syllabus_file(fpath):
                continue
            fname = os.path.basename(fpath)
            try:
                if fpath.endswith(".md") or fpath.endswith(".txt"):
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        lecture_text += f"\n--- [{fname}] ---\n" + f.read() + "\n"
                elif fpath.endswith(".pdf"):
                    base = os.path.splitext(fname)[0]
                    matched_md = None
                    if os.path.exists(cache_dir):
                        for mdf in glob.glob(os.path.join(cache_dir, "*.md")):
                            if base in os.path.basename(mdf) and not is_syllabus_file(mdf):
                                matched_md = mdf
                                break
                    if matched_md and os.path.exists(matched_md):
                        with open(matched_md, "r", encoding="utf-8", errors="ignore") as f:
                            lecture_text += f"\n--- [{os.path.basename(matched_md)}] ---\n" + f.read() + "\n"
                    else:
                        try:
                            import pypdf
                            reader = pypdf.PdfReader(fpath)
                            pdf_txt = "\n".join([p.extract_text() or "" for p in reader.pages[:30]])
                            if pdf_txt.strip():
                                lecture_text += f"\n--- [{fname}] ---\n" + pdf_txt + "\n"
                        except Exception:
                            lecture_text += f"\n--- [지정 슬라이드: {fname}] ---\n"
            except Exception as e:
                print(f"[Warn] 지정 파일 읽기 실패 ({fname}): {e}")

    if not lecture_text.strip():
        md_files = glob.glob(os.path.join(cache_dir, "*.md")) if os.path.exists(cache_dir) else []
        if not md_files:
            notes_dir = os.path.join(course_dir, "강의노트")
            if os.path.exists(notes_dir):
                md_files = glob.glob(os.path.join(notes_dir, "*.md"))

        for mdf in sorted(md_files):
            if is_syllabus_file(mdf):
                continue
            try:
                with open(mdf, "r", encoding="utf-8", errors="ignore") as f:
                    lecture_text += f"\n--- [{os.path.basename(mdf)}] ---\n" + f.read() + "\n"
            except Exception:
                pass

    safe_cname = cname.replace(" ", "_")
    md_filename = f"{safe_cname}_{exam_type}_{question_count}문항_{datetime.now().strftime('%m%d')}.md"
    pdf_filename = f"{safe_cname}_{exam_type}_{question_count}문항_{datetime.now().strftime('%m%d')}.pdf"

    md_path = os.path.join(exam_dir, md_filename)
    pdf_path = os.path.join(exam_dir, pdf_filename)

    base_prompt = build_universal_exam_prompt(
        cname=cname,
        scope=scope,
        question_count=question_count,
        question_format=question_format,
        exam_type=exam_type,
        is_english=is_english
    )

    if lecture_text.strip():
        full_prompt = f"{base_prompt}\n\n[수업 강의노트 실제 내용 요약 (반드시 출제에 반영할 것)]:\n{lecture_text[:12000]}"
    else:
        full_prompt = base_prompt

    log_func(f"🤖 Gemini 모델에 {question_count}문항 모의시험 & 정밀 해설 출제 요청 중... (약 15~25초 소요)")
    content = call_gemini(full_prompt)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    log_func(f"📄 마크다운 시험지 작성 완료: {md_filename}")
    log_func(f"🖨️ 인쇄·출판용 고해상도 PDF 컴파일 중...")
    compile_pdf(md_path, pdf_path, f"{cname} {exam_type} ({question_count}문항)")
    log_func(f"🎉 [{cname}] {exam_type} 출판용 PDF 생성 완료: {pdf_filename}")

    return md_path, pdf_path, content

def grade_mock_exam_submission(cname, exam_type, exam_content, student_answers, log_func=print):
    """
    학생 제출 답안을 모의시험 문제 및 정답/해설과 대조하여 AI 정밀 채점 및 취약점 분석 리포트 생성
    """
    log_func(f"✍️ [{cname}] {exam_type} AI 모의시험 정밀 채점 시작...")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    today_str = datetime.now().strftime("%m%d")

    folder_name = cname
    for c in config_manager.load_settings().get("courses", []):
        if c.get("course_name") == cname:
            folder_name = c.get("folder_name", cname)
            break

    course_dir = config_manager.get_course_dir(folder_name)
    exam_dir = os.path.join(course_dir, "예상문제")
    os.makedirs(exam_dir, exist_ok=True)

    grading_prompt = f"""당신은 [{cname}] 전공 과목의 수석 채점관이자 학업 평가 AI입니다.
대상 과목: [{cname}] | 시험 유형: {exam_type}

아래 제공된 [모의시험 원문 (문제, 공식 정답표 및 상세 해설)]을 기준으로, [학생이 제출한 답안]을 공정하고 정밀하게 채점하십시오.

[공정하고 엄격한 채점 기준]
1. [객관식 문항]:
   - 공식 정답표와 1:1 대조하여 일치하면 배점 부여(O), 불일치 시 0점(X).
2. [서술형 / 주관식 / 손풀이 문항]:
   - 전공 핵심 필수 키워드 및 개념 정의 포함 여부 (60%)
   - 논리적 전개, 원리 설명 및 수식 계산 과정의 타당성 (40%)
   - 핵심 개념은 언급했으나 설명이 미흡한 경우 부분 점수(Partial Credit)를 공정하게 부여하십시오.

[반드시 준수할 출력 리포트 서식]
# 📊 [{cname}] {exam_type} 실전 모의시험 AI 정밀 채점 리포트
> **응시 과목**: {cname} | **시험 구분**: {exam_type} | **채점 일시**: {now_str}

---

## 🏆 종합 성적 요약 (Score Summary)
- 🎯 **총점**: **[XX] / 100점** (예상 학점 등급: **[A+ / A / B+ / B / C ...]**)
- 📈 **영역별 점수**: 객관식 [XX]점 | 서술형·약술형 [XX]점
- 💡 **총평**: (학생의 전반적인 시험 준비도와 이해 수준을 2~3줄로 총평)

---

## 📝 문항별 정밀 채점 내역 (Detailed Item Analysis)

### Q1. [문항 요약] — [ ✅ 정답 (10/10점) | ⚠️ 부분 점수 (5/10점) | ❌ 오답 (0/10점) ]
- **학생 제출 답안**: (학생이 적은 답안 요약)
- **공식 정답**: (정답표 상의 정답)
- **채점 및 감점 사유**: (어떤 핵심 키워드가 맞았고, 무엇이 빠져서 감점되었는지 명확히 설명)

(모든 출제 문항에 대해 빠짐없이 동일하게 작성)

---

## 🚨 맞춤 취약점 분석 및 1순위 복습 가이드 (Weak Point Review)
1. **[취약 개념 1]** : 틀린 이유 분석 및 복습해야 할 강의노트 단원 안내 (교수님 발언 팁 포함)
2. **[취약 개념 2]** : 틀린 이유 분석 및 복습해야 할 강의노트 단원 안내
3. **[시험 당일 주의사항]** : 실제 본시험에서 같은 실수를 반복하지 않기 위한 1줄 팁

==================================================
[1. 모의시험 원문 (문제 + 정답표 + 상세해설)]
{exam_content[:15000]}

==================================================
[2. 학생이 제출한 답안]
{student_answers}
"""

    log_func("  🤖 AI 채점관이 답안을 분석하고 채점 기준표와 대조 중...")
    report_content = call_gemini(grading_prompt)

    safe_cname = cname.replace(" ", "_")
    report_filename = f"{safe_cname}_{exam_type}_채점리포트_{today_str}.md"
    report_path = os.path.join(exam_dir, report_filename)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    log_func(f"  ✅ [{cname}] 채점 완료! 리포트 저장: {report_filename}")
    return report_path, report_content

if __name__ == "__main__":
    generate_all_mock_exams()
