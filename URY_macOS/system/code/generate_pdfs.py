#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
강의노트 Markdown을 고품질 출판용 PDF로 일괄 변환하는 스크립트 v5.2
- .markdown_cache/ 격리 보관소의 마크다운을 읽어와 사용자 폴더(강의노트/)에 PDF만 출력
- 각 주차별 개별 학습노트 PDF + 전체 누적 통합본 PDF를 동시 발행
- 마크다운 볼드체(**텍스트**), 이탤릭(*텍스트*), 인라인 코드(`코드`), 링크 파싱 지원으로 PDF 가독성 대폭 향상
- 이미지 경로 절대 URL(file://) 변환으로 PDF 내 그림 엑박 100% 방지
- MathJax 수식 완벽 렌더링 & 문장/표 잘림 방지 (page-break-inside: avoid)
"""

import os
import sys
import re
import subprocess
import time
import glob
import shutil
import argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR
CACHE_DIR = os.path.join(WORKSPACE_DIR, ".markdown_cache")

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

def get_pandoc_path():
    p = shutil.which("pandoc")
    if p and os.path.exists(p):
        return p
    candidates = [
        "/opt/homebrew/bin/pandoc",
        "/usr/local/bin/pandoc",
        "/opt/anaconda3/bin/pandoc",
        os.path.expanduser("~/anaconda3/bin/pandoc"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

PANDOC = get_pandoc_path()
CHROME = get_chrome_path()

CSS_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=JetBrains+Mono:wght@400;600&display=swap');

@page {
    size: A4;
    margin: 20mm 18mm 20mm 18mm;
    @bottom-center {
        content: counter(page);
        font-size: 8.5pt;
        font-family: 'Noto Sans KR', 'Pretendard', sans-serif;
        color: #64748b;
    }
}

body {
    font-family: 'Noto Sans KR', 'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif;
    font-size: 10pt;
    line-height: 1.75;
    color: #1e293b;
    word-break: keep-all;
    overflow-wrap: break-word;
    margin: 0 auto;
    padding: 0;
    max-width: 100%;
}

strong, b {
    font-weight: 700;
    color: #0f172a;
    background-color: transparent;
    padding: 0;
}

mark, .highlight {
    background-color: #fef9c3;
    color: #854d0e;
    padding: 1px 4px;
    border-radius: 3px;
    font-weight: 600;
}

em, i {
    font-style: italic;
    color: #334155;
}

h1 {
    font-size: 19pt;
    font-weight: 700;
    color: #0f172a;
    text-align: center;
    border-bottom: 2.5px solid #4f46e5;
    padding-bottom: 10px;
    margin-top: 0;
    margin-bottom: 16px;
    page-break-after: avoid;
    break-after: avoid-page;
    page-break-inside: avoid;
    break-inside: avoid;
}

blockquote:first-of-type {
    text-align: center;
    margin: 12px auto 20px auto;
    padding: 10px 16px;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #4f46e5;
    border-radius: 6px;
    color: #334155;
    font-size: 9pt;
    page-break-inside: avoid;
    break-inside: avoid;
}

h2 {
    font-size: 13.5pt;
    font-weight: 700;
    color: #1e1b4b;
    border-bottom: 1.5px solid #cbd5e1;
    padding-bottom: 4px;
    margin-top: 24px;
    margin-bottom: 10px;
    page-break-after: avoid;
    break-after: avoid-page;
    page-break-inside: avoid;
    break-inside: avoid;
}

h3 {
    font-size: 11pt;
    font-weight: 700;
    color: #4338ca;
    margin-top: 18px;
    margin-bottom: 8px;
    page-break-after: avoid;
    break-after: avoid-page;
    page-break-inside: avoid;
    break-inside: avoid;
}

h4 {
    font-size: 10pt;
    font-weight: 700;
    color: #0369a1;
    margin-top: 14px;
    margin-bottom: 6px;
    page-break-after: avoid;
    break-after: avoid-page;
    page-break-inside: avoid;
    break-inside: avoid;
}

/* 제목 바로 뒤의 본문/목록이 다음 페이지로 홀로 넘어가는 Orphan 현상 방지 */
h1 + *, h2 + *, h3 + *, h4 + * {
    page-break-before: avoid;
    break-before: avoid-page;
}

p {
    margin-top: 4px;
    margin-bottom: 8px;
    orphans: 3;
    widows: 3;
}

ul, ol {
    margin-top: 4px;
    margin-bottom: 10px;
    padding-left: 22px;
}

li {
    margin-bottom: 4px;
    page-break-inside: avoid;
    break-inside: avoid-page;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 18px auto;
    font-size: 9pt;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

thead {
    display: table-header-group;
}

tfoot {
    display: table-footer-group;
}

tr {
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

th, td {
    border: 1px solid #cbd5e1;
    padding: 7px 12px;
    vertical-align: top;
}

th {
    background-color: #374151;
    color: #ffffff;
    font-weight: 600;
    text-align: center;
}

tr:nth-child(even) {
    background-color: #f8fafc;
}

hr {
    border: 0;
    border-top: 1.5px solid #e2e8f0;
    margin: 22px auto;
    width: 90%;
}

blockquote {
    margin: 12px 0;
    padding: 10px 16px;
    background-color: #f8fafc;
    border-left: 4px solid #4f46e5;
    color: #334155;
    font-size: 9.5pt;
    border-radius: 0 6px 6px 0;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

pre {
    background-color: #0f172a;
    color: #f8fafc;
    padding: 12px 16px;
    border-radius: 6px;
    font-size: 9pt;
    line-height: 1.5;
    overflow-x: auto;
    font-family: 'JetBrains Mono', Consolas, monospace;
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

code {
    background-color: #f1f5f9;
    color: #dc2626;
    padding: 2px 5px;
    border-radius: 4px;
    font-size: 9pt;
    font-family: 'JetBrains Mono', Consolas, monospace;
}

pre code {
    background-color: transparent;
    color: inherit;
    padding: 0;
}

img {
    max-width: 90%;
    max-height: 200mm;
    height: auto;
    display: block;
    margin: 16px auto;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

figure, .image-container {
    page-break-inside: avoid !important;
    break-inside: avoid !important;
    text-align: center;
    margin: 16px auto;
}

.badge-voice {
    display: inline-block;
    background-color: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    border-radius: 12px;
    padding: 2px 8px;
    font-size: 8.5pt;
    font-weight: bold;
    margin-right: 4px;
    vertical-align: middle;
}

.badge-book {
    display: inline-block;
    background-color: #f0fdf4;
    color: #15803d;
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 2px 8px;
    font-size: 8.5pt;
    font-weight: bold;
    margin-right: 4px;
    vertical-align: middle;
}

.badge-hybrid {
    display: inline-block;
    background-color: #faf5ff;
    color: #7e22ce;
    border: 1px solid #e9d5ff;
    border-radius: 12px;
    padding: 2px 8px;
    font-size: 8.5pt;
    font-weight: bold;
    margin-right: 4px;
    vertical-align: middle;
}
</style>
"""

MATHJAX_SCRIPT = """
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
  },
  svg: { fontCache: 'global' }
};
</script>
<script type="text/javascript" id="MathJax-script" async
  src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js">
</script>
"""

MERMAID_SCRIPT = """
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
document.addEventListener("DOMContentLoaded", function() {
    mermaid.initialize({
        startOnLoad: true,
        theme: 'neutral',
        securityLevel: 'loose',
        flowchart: { useMaxWidth: true, htmlLabels: true }
    });
});
</script>
"""


def parse_inline_markdown(text):
    """마크다운 인라인 서식(**볼드**, *이탤릭*, `코드`, [링크])을 HTML 태그로 치환"""
    # 1. 인라인 코드 `code`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # 2. 볼드체 **bold** 또는 __bold__
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', text)
    # 3. 이탤릭체 *italic* 또는 _italic_
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    # 4. 취소선 ~~strike~~
    text = re.sub(r'~~([^~]+)~~', r'<del>\1</del>', text)
    # 5. 링크 [title](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text

def fallback_md_to_html(md_path, html_path, title="Lecture Note"):
    """Pandoc 미설치 환경 대비 인라인 서식 파싱 지원 마크다운 -> HTML 변환기"""
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    body_html = []
    in_table = False
    table_rows = []

    for line in lines:
        raw = line.rstrip("\n")
        l = raw.strip()

        if "|" in l and l.startswith("|") and l.endswith("|"):
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(l)
            continue
        elif in_table:
            in_table = False
            body_html.append("<table>")
            has_tbody = False
            for idx, r in enumerate(table_rows):
                cols = [c.strip() for c in r.strip("|").split("|")]
                if idx == 0:
                    body_html.append("<thead><tr>" + "".join([f"<th>{parse_inline_markdown(c)}</th>" for c in cols]) + "</tr></thead>")
                elif idx == 1 and all(set(c).issubset({'-', ':', ' '}) for c in cols):
                    continue
                else:
                    if not has_tbody:
                        body_html.append("<tbody>")
                        has_tbody = True
                    body_html.append("<tr>" + "".join([f"<td>{parse_inline_markdown(c)}</td>" for c in cols]) + "</tr>")
            if has_tbody:
                body_html.append("</tbody>")
            body_html.append("</table>")

        if l.startswith("# "):
            body_html.append(f"<h1>{parse_inline_markdown(l[2:])}</h1>")
        elif l.startswith("## "):
            body_html.append(f"<h2>{parse_inline_markdown(l[3:])}</h2>")
        elif l.startswith("### "):
            body_html.append(f"<h3>{parse_inline_markdown(l[4:])}</h3>")
        elif l.startswith("#### "):
            body_html.append(f"<h4>{parse_inline_markdown(l[5:])}</h4>")
        elif l.startswith("> "):
            body_html.append(f"<blockquote>{parse_inline_markdown(l[2:])}</blockquote>")
        elif l.startswith("- ") or l.startswith("* "):
            body_html.append(f"<li>{parse_inline_markdown(l[2:])}</li>")
        elif l.startswith("1. ") or l.startswith("2. ") or l.startswith("3. "):
            content = re.sub(r'^\d+\.\s*', '', l)
            body_html.append(f"<li>{parse_inline_markdown(content)}</li>")
        elif l == "---":
            body_html.append("<hr/>")
        elif l:
            body_html.append(f"<p>{parse_inline_markdown(l)}</p>")

    if in_table:
        body_html.append("<table>")
        has_tbody = False
        for idx, r in enumerate(table_rows):
            cols = [c.strip() for c in r.strip("|").split("|")]
            if idx == 0:
                body_html.append("<thead><tr>" + "".join([f"<th>{parse_inline_markdown(c)}</th>" for c in cols]) + "</tr></thead>")
            elif idx == 1 and all(set(c).issubset({'-', ':', ' '}) for c in cols):
                continue
            else:
                if not has_tbody:
                    body_html.append("<tbody>")
                    has_tbody = True
                body_html.append("<tr>" + "".join([f"<td>{parse_inline_markdown(c)}</td>" for c in cols]) + "</tr>")
        if has_tbody:
            body_html.append("</tbody>")
        body_html.append("</table>")

    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title></head><body>" + "".join(body_html) + "</body></html>"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(full_html)

def get_latest_date_from_md(md_path):
    if not os.path.exists(md_path):
        return datetime.now().strftime("%Y-%m-%d")
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    dates = re.findall(r"(\d{4}-\d{2}-\d{2})", content)
    if dates:
        return sorted(dates)[-1]
    return datetime.now().strftime("%Y-%m-%d")

def convert_single_md_to_pdf(md_path, pdf_output_path, display_name, folder_dir):
    """단일 마크다운 문서를 지정된 PDF 경로로 컴파일 (마크다운 볼드체/서식 100% 치환)"""
    cache_folder = os.path.dirname(md_path)
    html_path = md_path + ".tmp.html"
    latest_date = get_latest_date_from_md(md_path)

    print(f"[{display_name}] HTML 변환 중...")

    # 1. pandoc 또는 순수 파이썬 마크다운 변환기로 HTML 생성
    pandoc_bin = get_pandoc_path()
    if pandoc_bin and os.path.exists(pandoc_bin):
        try:
            cmd_pandoc = [
                pandoc_bin, "-s", "--mathjax", os.path.basename(md_path), "-o", os.path.basename(html_path),
                "--metadata", f"title={display_name}"
            ]
            subprocess.check_call(cmd_pandoc, cwd=cache_folder)
        except Exception:
            fallback_md_to_html(md_path, html_path, title=display_name)
    else:
        fallback_md_to_html(md_path, html_path, title=display_name)

    # 2. HTML 내용 읽기
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 남아있는 파싱되지 않은 **볼드체**를 HTML <strong> 태그로 최종 구출 치환
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', html)

    # 이미지 경로 절대 URL 변환
    def replace_img_src(match):
        img_src = match.group(1)
        if img_src.startswith("http://") or img_src.startswith("https://") or img_src.startswith("file://"):
            return f'src="{img_src}"'

        abs_candidate1 = os.path.abspath(os.path.join(cache_folder, img_src))
        abs_candidate2 = os.path.abspath(os.path.join(cache_folder, "..", "images", os.path.basename(img_src)))
        abs_candidate3 = os.path.abspath(os.path.join(folder_dir, "images", os.path.basename(img_src)))
        abs_candidate4 = os.path.abspath(os.path.join(folder_dir, "..", "images", os.path.basename(img_src)))

        found_path = None
        for cand in [abs_candidate1, abs_candidate2, abs_candidate3, abs_candidate4]:
            if os.path.exists(cand):
                found_path = cand
                break

        if found_path:
            return f'src="file://{found_path}"'
        else:
            return f'src="file://{abs_candidate1}"'

    html = re.sub(r'src="([^"]+)"', replace_img_src, html)

    # 출처 배지 치환
    html = re.sub(r'\[🎙️\s*음성\s*\(([^)]+)\)\]', r'<span class="badge-voice">🎙️ 음성 (\1)</span>', html)
    html = re.sub(r'\[🎙️\s*음성\]', '<span class="badge-voice">🎙️ 음성</span>', html)
    html = re.sub(r'\[📖\s*교재\]', '<span class="badge-book">📖 교재</span>', html)
    html = re.sub(r'\[📖\s*강의계획서\s*/\s*🎙️\s*음성\]', '<span class="badge-book">📖 강의계획서</span> <span class="badge-voice">🎙️ 음성</span>', html)
    html = re.sub(r'\[📖\s*교재\s*/\s*🎙️\s*음성\]', '<span class="badge-book">📖 교재</span> <span class="badge-voice">🎙️ 음성</span>', html)
    html = re.sub(r'\[📖\s*슬라이드\s*/\s*🎙️\s*음성\]', '<span class="badge-book">📖 슬라이드</span> <span class="badge-voice">🎙️ 음성</span>', html)
    html = re.sub(r'\[📖\s*교재·슬라이드\]', '<span class="badge-book">📖 교재·자료</span>', html)
    html = re.sub(r'\[💡\s*통합\s*\(([^)]+)\)\]', r'<span class="badge-hybrid">💡 통합 (\1)</span>', html)
    html = re.sub(r'\[💡\s*통합\]', '<span class="badge-hybrid">💡 통합</span>', html)
    html = re.sub(r'\[🎙️\s*Spoken\s*\(([^)]+)\)\]', r'<span class="badge-voice">🎙️ Spoken (\1)</span>', html)
    html = re.sub(r'\[🎙️\s*Spoken\]', '<span class="badge-voice">🎙️ Spoken</span>', html)
    html = re.sub(r'\[📖\s*Textbook\]', '<span class="badge-book">📖 Textbook</span>', html)
    html = re.sub(r'\[💡\s*Integrated\s*\(([^)]+)\)\]', r'<span class="badge-hybrid">💡 Integrated (\1)</span>', html)
    html = re.sub(r'\[💡\s*Integrated\]', '<span class="badge-hybrid">💡 Integrated</span>', html)

    # Mermaid 다이어그램 태그 정제 (Pandoc/Fallback 공통)
    html = re.sub(r'<pre\s+class="code">\s*<code\s+class="(?:language-)?mermaid">(.*?)</code>\s*</pre>', r'<pre class="mermaid">\1</pre>', html, flags=re.DOTALL)
    html = re.sub(r'<pre>\s*<code\s+class="(?:language-)?mermaid">(.*?)</code>\s*</pre>', r'<pre class="mermaid">\1</pre>', html, flags=re.DOTALL)
    html = re.sub(r'<code\s+class="(?:language-)?mermaid">(.*?)</code>', r'<pre class="mermaid">\1</pre>', html, flags=re.DOTALL)

    html = html.replace("</head>", f"{CSS_STYLE}\n{MATHJAX_SCRIPT}\n{MERMAID_SCRIPT}\n</head>")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 3. Google Chrome Headless로 PDF 렌더링
    print(f"[{display_name}] Chrome Headless PDF 렌더링 중...")
    cmd_chrome = [
        CHROME,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--allow-file-access-from-files",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_output_path}",
        html_path
    ]
    try:
        subprocess.check_call(cmd_chrome, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[Warn] Chrome 렌더링 명령 실패: {e}")

    if os.path.exists(html_path):
        os.remove(html_path)

    if os.path.exists(pdf_output_path):
        pdf_size = os.path.getsize(pdf_output_path)
        print(f"[{display_name}] PDF 생성 완료! ({round(pdf_size/1024/1024, 2)}MB) -> {os.path.basename(pdf_output_path)}")
        return pdf_output_path
    return None

def process_course_pdfs(course_folder, cname, en_prefix):
    """과목별로 주차별 개별 학습노트 및 전체 통합본 PDF를 일괄 컴파일"""
    cache_dir = os.path.join(CACHE_DIR, course_folder)
    course_dir = config_manager.get_course_dir(course_folder)
    notes_dir = os.path.join(course_dir, "강의노트")
    os.makedirs(notes_dir, exist_ok=True)

    if not os.path.exists(cache_dir):
        return

    md_files = glob.glob(os.path.join(cache_dir, "*.md"))
    md_files.sort()

    for md_p in md_files:
        fname = os.path.basename(md_p)
        latest_date = get_latest_date_from_md(md_p)

        # 1. 전체 통합본인 경우 (강의노트/통합/ 에 저장)
        if "통합강의노트" in fname or "Combined" in fname:
            comb_dir = os.path.join(notes_dir, "통합")
            os.makedirs(comb_dir, exist_ok=True)

            if "통합강의노트" in fname:
                base_name = f"{cname}_전체통합_강의노트"
                dated_name = f"{base_name}_최종({latest_date}).pdf"
                display_name = f"{cname} (전체 통합본)"
            else:
                base_name = f"{en_prefix}_Combined_Lecture_Notes"
                dated_name = f"{base_name}_Latest({latest_date}).pdf"
                display_name = f"{en_prefix} (Combined)"

            pdf_p = os.path.join(comb_dir, dated_name)

            for old_f in glob.glob(os.path.join(comb_dir, f"{base_name}*.pdf")):
                if os.path.basename(old_f) != dated_name:
                    try:
                        os.remove(old_f)
                    except Exception:
                        pass

            convert_single_md_to_pdf(md_p, pdf_p, display_name, comb_dir)

        # 2. 주차별 개별 학습노트인 경우 (강의노트/N주차/ 에 저장)
        else:
            week_match = re.search(r"(\d+)주차", fname) or re.search(r"Week(\d+)", fname, re.IGNORECASE)
            week_sub = f"{week_match.group(1)}주차" if week_match else "1주차"
            w_dir = os.path.join(notes_dir, week_sub)
            os.makedirs(w_dir, exist_ok=True)

            pdf_fname = fname.replace(".md", ".pdf")
            pdf_p = os.path.join(w_dir, pdf_fname)
            display_name = fname.replace(".md", "")
            convert_single_md_to_pdf(md_p, pdf_p, display_name, w_dir)

def generate_all_pdfs(target_courses=None):
    print("======================================================")
    print("🚀 [강의노트 PDF 출판 엔진 v5.2 시작]")
    print("   - 주차별 개별 학습노트 + 전체 통합본 동시 발행")
    print("   - 볼드체(**텍스트**) 치환 및 이미지 절대 경로 변환")
    print("======================================================")

    settings = config_manager.load_settings()
    courses = settings.get("courses", [])

    if not courses:
        courses = [
            {"folder_name": "마케팅원론", "course_name": "마케팅원론"},
            {"folder_name": "DB 기초 및 응용", "course_name": "DB 기초 및 응용"},
            {"folder_name": "빅데이터수학", "course_name": "빅데이터수학"}
        ]

    for c in courses:
        cname = c.get("course_name") or c.get("folder_name")
        folder = c.get("folder_name") or cname
        if target_courses and cname not in target_courses and folder not in target_courses:
            continue

        en_prefix = folder.replace(" ", "_")
        try:
            process_course_pdfs(folder, cname, en_prefix)
        except Exception as e:
            print(f"[Error] {folder} PDF 생성 실패: {e}")

    print("\n======================================================")
    print("🎉 모든 과목의 주차별 및 전체 통합본 PDF 출판 완료!")
    print("======================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF Generator")
    parser.add_argument("--courses", nargs="*", help="Target courses")
    args, _ = parser.parse_known_args()
    generate_all_pdfs(target_courses=args.courses)
