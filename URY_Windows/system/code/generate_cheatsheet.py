#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시험 직전 3분 A4 1페이지 초고밀도 치트시트(Cheat Sheet) 자동 추출 및 조판 모듈
- 🔑 초핵심 공식 & 절대 암기 정의 (Core Formulas & Definitions)
- ⚠️ 교수님 강조 함정 & 빈출 오답 포인트 (Traps & Pitfalls)
- 📊 핵심 키워드 3열 매트릭스 (Comparison Matrix)
- 🎯 단답형/약술형 예상 1순위 키워드 TOP 5
"""

import os
import sys
import glob
import shutil
import subprocess
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config_manager
import generate_mock_exams

WORKSPACE_DIR = config_manager.WORKSPACE_DIR
CHROME = generate_mock_exams.get_chrome_path()
PANDOC = generate_mock_exams.PANDOC

CHEATSHEET_PROMPT_TEMPLATE = """당신은 전공 과목 수석 졸업생이자 URY Engine의 시험 대비 최고 핵심 요약 AI입니다.
대상 과목: [{cname}]
시험 유형: {exam_type} | 목표 학점: {target_grade}
출제 범위: {scope}

제공된 강의노트, 슬라이드, 학습자료의 방대한 지식에서 **시험 당일 고사장 입실 직전 3분 동안 볼 수 있는 A4 딱 1페이지 초고밀도 요약본(Cheat Sheet)**을 작성해 주십시오.

[🚨 초고밀도 1페이지 작성 원칙]
1. [군더더기 100% 제거]: 사설, 인사말, 불필요한 서론/결론은 일절 작성하지 마십시오.
2. [시험 직결 지식 압축]: 오직 시험 문제로 출제될 확률이 90% 이상인 핵심 공식, 필수 정의, 단골 함정, 빈출 키워드만 압축 수록하십시오.
3. [가독성 극대화]: 간결한 불렛포인트, 3열 비교 표(Markdown Table), 수식($...$)을 적극 활용하십시오.

[반드시 포함해야 할 4대 핵심 섹션]
# ⚡ [{cname}] {exam_type} 대비 3분 완성 핵심 치트시트 (A4 1-Page)
> **과목**: {cname} | **시험**: {exam_type} | **범위**: {scope} | **목표**: {target_grade}

---

## 🔑 1. 초핵심 공식 & 절대 암기 정의 (Core Formulas & Rules)
- 시험에 반드시 쓰이는 핵심 수식(LaTeX $...$) 및 물리적/수학적/비즈니스적 의미를 1줄로 명시.
- 절대 잊지 말아야 할 전공 필수 법칙/정의를 빠짐없이 3~5개로 압축 서술.

## ⚠️ 2. 교수님 강조 함정 & 단골 오답 포인트 (Traps & Pitfalls)
- 학생들이 시험에서 가장 많이 헷갈려하거나 오답 선지로 출제되는 대립 개념 쌍 비교.
- 교수님이 수업 중 육성으로 "이거 틀리지 마라", "이거 헷갈리기 쉽다"고 강조한 실전 주의사항 3~4개.

## 📊 3. 필수 핵심 키워드 3열 매트릭스 (Comparison Matrix)
| 핵심 개념 (Key Concept) | 영문 표기 | 1줄 핵심 정의 및 시험 출제 포인트 |
(시험에 출제될 필수 용어 6~8개를 엄선하여 1줄로 일목요연하게 표로 정리)

## 🎯 4. 단답형·약술형 예상 1순위 키워드 TOP 5 (High-Yield Topics)
1. **[키워드 1]** : 출제 예상 질문 및 핵심 키포인트 모범 답안 어구
2. **[키워드 2]** : 출제 예상 질문 및 핵심 키포인트 모범 답안 어구
3. **[키워드 3]** : 출제 예상 질문 및 핵심 키포인트 모범 답안 어구
4. **[키워드 4]** : 출제 예상 질문 및 핵심 키포인트 모범 답안 어구
5. **[키워드 5]** : 출제 예상 질문 및 핵심 키포인트 모범 답안 어구
"""

def extract_text_from_file(file_path):
    """주어진 파일(마크다운, 텍스트, PDF)에서 텍스트 추출"""
    if not os.path.exists(file_path):
        return ""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".md", ".txt"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return ""
    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            pages_txt = []
            for p in reader.pages[:30]:
                t = p.extract_text()
                if t:
                    pages_txt.append(t)
            return "\n".join(pages_txt)
        except Exception:
            return ""
    return ""

def compile_cheatsheet_pdf(md_path, pdf_path, title):
    """A4 1페이지 초고밀도 전용 CSS를 적용하여 조판 PDF 렌더링"""
    folder_dir = os.path.dirname(md_path)
    html_path = md_path.replace(".md", ".tmp.html")

    # 기존 동일 치트시트 PDF 정리
    base_stem = os.path.splitext(os.path.basename(pdf_path))[0]
    for old_pdf in glob.glob(os.path.join(folder_dir, f"{base_stem}*.pdf")):
        if old_pdf != pdf_path:
            try:
                os.remove(old_pdf)
            except Exception:
                pass

    pandoc_done = False
    if PANDOC and os.path.exists(PANDOC):
        try:
            cmd_pandoc = [
                PANDOC, "-s", "--mathjax", os.path.basename(md_path), "-o", os.path.basename(html_path),
                "--metadata", f"title={title}"
            ]
            subprocess.check_call(cmd_pandoc, cwd=folder_dir)
            pandoc_done = True
        except Exception:
            pandoc_done = False

    if not pandoc_done:
        import generate_pdfs
        generate_pdfs.fallback_md_to_html(md_path, html_path, title)

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 초고밀도 A4 1페이지 중앙정렬 전용 CSS
    css = """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    @page {
        size: A4 portrait;
        margin: 8mm 10mm 8mm 10mm;
    }
    body {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 9.0pt;
        line-height: 1.35;
        color: #0f172a;
        margin: 0 auto;
        padding: 0;
        background: #ffffff;
        text-align: center;
    }
    h1, h2, h3, h4, p, div, blockquote {
        text-align: center !important;
    }
    h1 {
        font-size: 14.0pt;
        font-weight: 800;
        color: #1e3a8a;
        margin: 0 auto 4px auto;
        padding-bottom: 3px;
        border-bottom: 2px solid #2563eb;
    }
    blockquote {
        font-size: 8.0pt;
        color: #475569;
        margin: 2px auto 6px auto;
        padding: 2px 6px;
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        display: inline-block;
    }
    hr {
        border: 0;
        border-top: 1px solid #e2e8f0;
        margin: 4px auto;
    }
    h2 {
        font-size: 10.0pt;
        font-weight: 700;
        color: #1e40af;
        margin: 6px auto 2px auto;
        padding: 2px 8px;
        background: #eff6ff;
        border-left: 3px solid #2563eb;
        border-right: 3px solid #2563eb;
        border-radius: 2px;
        display: inline-block;
    }
    ul, ol {
        margin: 2px auto 4px auto;
        padding-left: 0;
        list-style-position: inside;
        text-align: center;
    }
    li {
        margin-bottom: 1.5px;
        line-height: 1.3;
        text-align: center;
    }
    strong {
        color: #0f172a;
        font-weight: 700;
    }
    table {
        width: 98%;
        margin: 4px auto 6px auto;
        border-collapse: collapse;
        font-size: 8.0pt;
    }
    th, td {
        border: 1px solid #cbd5e1;
        padding: 2.5px 5px;
        text-align: center !important;
    }
    th {
        background: #f8fafc;
        color: #1e293b;
        font-weight: 700;
    }
    code {
        font-size: 8.5pt;
        background: #f1f5f9;
        padding: 1px 3px;
        border-radius: 2px;
        color: #0369a1;
    }
    </style>
    """

    if "</head>" in html:
        html = html.replace("</head>", f"{css}</head>")
    else:
        html = f"{css}\n{html}"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    if CHROME and os.path.exists(CHROME):
        cmd = [
            CHROME,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={pdf_path}",
            html_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception as e:
            print(f"Chrome PDF 변환 경고: {e}")
    else:
        # Fallback to wkhtmltopdf
        wk = shutil.which("wkhtmltopdf")
        if wk:
            subprocess.run([wk, "--margin-top", "8mm", "--margin-bottom", "8mm", "--margin-left", "10mm", "--margin-right", "10mm", html_path, pdf_path], timeout=60)

    # 임시 html 정리
    if os.path.exists(html_path):
        try:
            os.remove(html_path)
        except Exception:
            pass

    return pdf_path

def generate_custom_cheatsheet(cname, scope="전범위", exam_type="중간고사", target_grade="A+", selected_files=None, log_func=print):
    """선택된 과목 및 자료를 바탕으로 1페이지 치트시트 PDF 생성 (MD는 자동 삭제)"""
    log_func(f"⚡ [{cname}] {exam_type} 3분 치트시트(1-Page) 분석 및 생성 시작...")

    folder_name = cname
    for c in config_manager.load_settings().get("courses", []):
        if c.get("course_name") == cname:
            folder_name = c.get("folder_name", cname)
            break

    course_dir = config_manager.get_course_dir(folder_name)
    exam_dir = os.path.join(course_dir, "예상문제")
    os.makedirs(exam_dir, exist_ok=True)

    # 1. 학습 자료 텍스트 수집
    collected_text = ""
    materials_used = []

    if selected_files:
        for fp in selected_files:
            if os.path.exists(fp):
                txt = extract_text_from_file(fp)
                if txt:
                    collected_text += f"\n\n--- [자료: {os.path.basename(fp)}] ---\n" + txt
                    materials_used.append(os.path.basename(fp))

    if not collected_text:
        # 자동 스캔 (.markdown_cache 또는 강의노트/)
        cache_dir = os.path.join(WORKSPACE_DIR, ".markdown_cache", folder_name)
        if not os.path.exists(cache_dir):
            cache_dir = os.path.join(WORKSPACE_DIR, ".markdown_cache", cname)
        if os.path.exists(cache_dir):
            for mdf in sorted(glob.glob(os.path.join(cache_dir, "*.md"))):
                txt = extract_text_from_file(mdf)
                if txt:
                    collected_text += f"\n\n--- [학습노트: {os.path.basename(mdf)}] ---\n" + txt
                    materials_used.append(os.path.basename(mdf))

    # 본문 길이 제한 (30,000자)
    if len(collected_text) > 30000:
        collected_text = collected_text[:30000] + "\n...(후략)..."

    # 프롬프트 조립
    prompt = CHEATSHEET_PROMPT_TEMPLATE.format(
        cname=cname,
        exam_type=exam_type,
        target_grade=target_grade,
        scope=scope
    )

    if collected_text:
        prompt += f"""

[참고 학습 자료 (주차별 강의노트 및 슬라이드 발췌)]
{collected_text}
"""
    else:
        prompt += f"""
(현재 주차별 강의노트가 아직 없으므로, [{cname}] 과목의 통상적인 핵심 전공 커리큘럼 기준 가장 중요한 핵심 이론으로 치트시트를 구성하십시오.)
"""

    log_func("  🤖 AI 엔진(Gemini)에 초압축 1페이지 요약 요청 중...")
    content = generate_mock_exams.call_gemini(prompt)

    # 임시 마크다운 생성
    today_str = datetime.now().strftime("%m%d")
    md_file = os.path.join(exam_dir, f"{cname}_{exam_type}_3분치트시트_{today_str}.md")
    pdf_file = os.path.join(exam_dir, f"{cname}_{exam_type}_3분치트시트_{today_str}.pdf")

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(content)

    log_func("  🖨️ A4 1페이지 초고밀도 조판 PDF 렌더링 중...")
    compile_cheatsheet_pdf(md_file, pdf_file, f"{cname} {exam_type} 3분 치트시트")

    # 사용자의 명시적 요청: 마크다운 파일 자동 삭제 (PDF 성공 생성 시에만 삭제)
    if os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 0:
        if os.path.exists(md_file):
            try:
                os.remove(md_file)
            except Exception:
                pass
        log_func(f"  ✅ [{cname}] 3분 치트시트 PDF 완성 (MD 삭제됨): {os.path.basename(pdf_file)}")
        return pdf_file, content
    else:
        log_func(f"  ℹ️ [{cname}] 3분 치트시트 마크다운 완성 (PDF 대기): {os.path.basename(md_file)}")
        return md_file, content

if __name__ == "__main__":
    c = "DB 기초 및 응용"
    pdf, txt = generate_custom_cheatsheet(c)
    print(f"Generated: {pdf} (Size: {os.path.getsize(pdf)} bytes)")
