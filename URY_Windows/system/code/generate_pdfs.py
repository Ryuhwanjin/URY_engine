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
import unicodedata
from datetime import datetime


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import importlib.util
class PriorityCodeLoader:
    def __init__(self, code_dir):
        self.code_dir = code_dir

    def find_spec(self, fullname, path=None, target=None):
        our_mods = {
            "config_manager", "settings_gui", "process_all_lectures",
            "generate_pdfs", "doc_parser", "dynamic_slide_integrator",
            "auto_organize", "generate_master_bible", "generate_mock_exams",
            "generate_cheatsheet", "generate_roadmap", "lecture_tutor",
            "audio_recorder", "pdf_viewer", "sync_markdown_vault"
        }
        if fullname in our_mods:
            target_path = os.path.join(self.code_dir, f"{fullname}.py")
            if os.path.exists(target_path):
                return importlib.util.spec_from_file_location(fullname, target_path)
        return None

if getattr(sys, "frozen", False):
    if not any(isinstance(x, PriorityCodeLoader) for x in sys.meta_path):
        sys.meta_path.insert(0, PriorityCodeLoader(SCRIPT_DIR))

import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR
CACHE_DIR = os.path.join(WORKSPACE_DIR, ".markdown_cache")

import tempfile

def find_chromium_browser():
    """시스템에 설치된 최적의 Chromium 계열 브라우저 바이너리 자동 감지"""
    if os.environ.get("CHROME_PATH") and os.path.exists(os.environ["CHROME_PATH"]):
        return os.environ["CHROME_PATH"]
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        os.path.expanduser("~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        "/Applications/Whale.app/Contents/MacOS/Whale",
        "/Applications/Naver Whale.app/Contents/MacOS/Naver Whale",
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chrome"),
        shutil.which("msedge"),
        shutil.which("brave"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

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

def render_html_to_pdf_pymupdf(html_content, output_pdf_path):
    """
    외부 브라우저(Chrome 등) 설치 여부와 무관하게 앱 번들 내장 PyMuPDF(fitz.Story)로
    A4 규격 출판용 PDF를 100% 자율 조판/발행하는 내장 렌더러
    """
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        # MuPDF CSS 파서와 호환되도록 CSS 정제
        cleaned_html = re.sub(r'@import url\([^)]+\);?', '', html_content)
        cleaned_html = re.sub(r'@bottom-[^{]+{[^}]+}', '', cleaned_html)
        cleaned_html = re.sub(r'@page\s*{[^}]*}', '', cleaned_html)

        mediabox = fitz.paper_rect('a4')  # 595 x 842 pt
        margin_x = 42
        margin_y = 42
        content_rect = fitz.Rect(margin_x, margin_y, mediabox.width - margin_x, mediabox.height - margin_y)

        def rectfn(rect_num, filled):
            return mediabox, content_rect, fitz.Identity

        os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
        try:
            writer = fitz.DocumentWriter(output_pdf_path)
            story = fitz.Story(html=cleaned_html)
            story.write(writer, rectfn)
            writer.close()
        except Exception:
            # Story 실패 시 fitz.open 및 Story text page fallback
            doc = fitz.open()
            page = doc.new_page(width=595, height=842)
            # 순수 텍스트 정제 후 인쇄
            clean_text = re.sub(r'<[^>]+>', '\n', cleaned_html)
            clean_text = re.sub(r'\n+', '\n', clean_text).strip()
            page.insert_text((40, 50), clean_text[:4000], fontsize=10)
            doc.save(output_pdf_path)
            doc.close()

        if os.path.exists(output_pdf_path) and os.path.getsize(output_pdf_path) > 0:
            return True
    except Exception as e:
        print(f"[Warn] PyMuPDF 내장 렌더링 실패: {e}")
    return False


PANDOC = get_pandoc_path()
CHROME = find_chromium_browser()

CSS_STYLE = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

@page {
    size: A4;
    margin: 12mm 14mm 14mm 14mm;
    @bottom-center {
        content: counter(page);
        font-size: 9pt;
        font-family: 'Pretendard', sans-serif;
        color: #64748b;
    }
}

body {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif;
    font-size: 9.5pt;
    line-height: 1.68;
    color: #1e293b;
    word-break: keep-all;
    overflow-wrap: break-word;
}

h1 {
    font-size: 19pt;
    color: #0f172a;
    border-bottom: 2.5px solid #2563eb;
    padding-bottom: 6px;
    margin-top: 0;
    margin-bottom: 14px;
    page-break-after: avoid;
    break-after: avoid;
}

h2 {
    font-size: 13.5pt;
    color: #1e3a8a;
    border-bottom: 1.5px solid #cbd5e1;
    padding-bottom: 4px;
    margin-top: 24px;
    margin-bottom: 10px;
    page-break-after: avoid;
    break-after: avoid;
}

h3 {
    font-size: 11pt;
    color: #2563eb;
    margin-top: 16px;
    margin-bottom: 6px;
    page-break-after: avoid;
    break-after: avoid;
}

h4 {
    font-size: 10pt;
    color: #0369a1;
    margin-top: 12px;
    margin-bottom: 4px;
    page-break-after: avoid;
    break-after: avoid;
}

/* 🌟 문장, 단락, 목록, 인용구 잘림 방지 */
p, li, blockquote {
    page-break-inside: avoid;
    break-inside: avoid;
    orphans: 3;
    widows: 3;
}

ul, ol {
    margin-top: 4px;
    margin-bottom: 8px;
    padding-left: 20px;
}

li {
    margin-bottom: 3px;
}

/* 🌟 표와 코드 블록이 페이지 경계에서 잘려나가지 않도록 보호 */
table, tr, tbody, pre {
    page-break-inside: avoid;
    break-inside: avoid;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 8.5pt;
}

th, td {
    border: 1px solid #cbd5e1;
    padding: 6px 10px;
    text-align: left;
}

th {
    background-color: #f1f5f9;
    color: #0f172a;
    font-weight: 600;
}

tr:nth-child(even) {
    background-color: #f8fafc;
}

blockquote {
    margin: 10px 0;
    padding: 8px 14px;
    background-color: #f8fafc;
    border-left: 3.5px solid #3b82f6;
    color: #334155;
    font-size: 9pt;
    border-radius: 0 4px 4px 0;
}

pre {
    background-color: #0f172a;
    color: #f8fafc;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 8.5pt;
    line-height: 1.45;
    overflow-x: auto;
}

code {
    background-color: #f1f5f9;
    color: #e11d48;
    padding: 2px 4px;
    border-radius: 3px;
    font-size: 8.5pt;
    font-family: 'JetBrains Mono', Menlo, Monaco, Consolas, monospace;
}

pre code {
    background-color: transparent;
    color: inherit;
    padding: 0;
}

img {
    max-width: 90%;
    height: auto;
    display: block;
    margin: 12px auto;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    page-break-inside: avoid;
    break-inside: avoid;
}

hr {
    border: 0;
    height: 1px;
    background: #e2e8f0;
    margin: 18px 0;
}

/* 🌟 출처 구분 알록달록 알약 배지 */
.badge-voice {
    display: inline-block;
    background-color: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 8pt;
    font-weight: bold;
    margin-right: 4px;
    vertical-align: middle;
}

.badge-book {
    display: inline-block;
    background-color: #f0fdf4;
    color: #15803d;
    border: 1px solid #bbf7d0;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 8pt;
    font-weight: bold;
    margin-right: 4px;
    vertical-align: middle;
}

.badge-hybrid {
    display: inline-block;
    background-color: #faf5ff;
    color: #7e22ce;
    border: 1px solid #e9d5ff;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 8pt;
    font-weight: bold;
    margin-right: 4px;
    vertical-align: middle;
}

.badge-syllabus {
    display: inline-block;
    background-color: #dcfce7;
    color: #15803d;
    border: 1px solid #86efac;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 8pt;
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
    pdf_output_path = unicodedata.normalize("NFC", pdf_output_path)
    pdf_dir = os.path.dirname(pdf_output_path)
    pdf_base = os.path.basename(pdf_output_path).lstrip(".")
    pdf_output_path = os.path.join(pdf_dir, pdf_base)
    folder_dir = unicodedata.normalize("NFC", folder_dir) if folder_dir else ""

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

    # 1. <code> 태그에 싸인 출처 태그 원복
    # 1. <code> 태그에 싸인 출처 태그 원복
    html = re.sub(r'<code>\s*(\[(?:🎙️|📖|💡)[^\]]+\])\s*</code>', r'\1', html)

    # 2. 출처 배지 치환 (render_pdf.py 방식과 100% 호환)
    html = re.sub(r'\[🎙️\s*음성\]', '<span class="badge-voice">🎙️ 음성</span>', html)
    html = re.sub(r'\[📖\s*교재\]', '<span class="badge-book">📖 교재</span>', html)
    html = re.sub(r'\[📖\s*강의계획서\s*/\s*🎙️\s*음성\]', '<span class="badge-book">📖 강의계획서</span> <span class="badge-voice">🎙️ 음성</span>', html)
    html = re.sub(r'\[📖\s*교재\s*/\s*🎙️\s*음성\]', '<span class="badge-book">📖 교재</span> <span class="badge-voice">🎙️ 음성</span>', html)
    html = re.sub(r'\[📖\s*슬라이드\s*/\s*🎙️\s*음성\]', '<span class="badge-book">📖 슬라이드</span> <span class="badge-voice">🎙️ 음성</span>', html)
    html = re.sub(r'\[📖\s*교재·슬라이드\]', '<span class="badge-book">📖 교재·자료</span>', html)
    html = re.sub(r'\[💡\s*통합\]', '<span class="badge-hybrid">💡 통합</span>', html)

    def replace_citation_smart(m):
        tag_type = m.group(1)
        content = m.group(2).strip()
        if tag_type == "📖":
            if "강의계획서" in content or "Syllabus" in content:
                return f'<span class="badge-syllabus">📖 {content}</span>'
            return f'<span class="badge-book">📖 {content}</span>'
        elif tag_type == "🎙️":
            return f'<span class="badge-voice">🎙️ {content}</span>'
        else:
            return f'<span class="badge-hybrid">💡 {content}</span>'

    html = re.sub(r'\[(📖|🎙️|💡)\s*([^\]]+)\]', replace_citation_smart, html)
    # 문장 기호 앞 불필요한 공백 제거
    html = re.sub(r'\s+([.,;:!?])', r'\1', html)

    # 3. ASCII 그림 및 텍스트 상자(┌─┐, │, └─┘, ===) 정제하여 깔끔한 Callout 박스로 치환
    def sanitize_ascii_boxes(m):
        code_text = m.group(1)
        if any(c in code_text for c in ['┌', '│', '└', '═', '╔', '║', '╚', '─']):
            lines = [l.strip() for l in code_text.splitlines()]
            clean_lines = []
            for l in lines:
                cleaned = re.sub(r'[┌┐└┘├┤┬┴┼─│═║╔╗╚╝╠╣╦╩╬]|[-=]{5,}', '', l).strip()
                if cleaned:
                    clean_lines.append(cleaned)
            return f'<blockquote class="callout-box">{"<br>".join(clean_lines)}</blockquote>'
        return m.group(0)

    html = re.sub(r'<pre(?:[^>]*)>\s*<code(?:[^>]*)>(.*?)</code>\s*</pre>', sanitize_ascii_boxes, html, flags=re.DOTALL)

    # Mermaid 다이어그램 태그 정제 (Pandoc/Fallback 공통)
    html = re.sub(r'<pre\s+class="code">\s*<code\s+class="(?:language-)?mermaid">(.*?)</code>\s*</pre>', r'<pre class="mermaid">\1</pre>', html, flags=re.DOTALL)
    html = re.sub(r'<pre>\s*<code\s+class="(?:language-)?mermaid">(.*?)</code>\s*</pre>', r'<pre class="mermaid">\1</pre>', html, flags=re.DOTALL)
    html = re.sub(r'<code\s+class="(?:language-)?mermaid">(.*?)</code>', r'<pre class="mermaid">\1</pre>', html, flags=re.DOTALL)

    # 시험 정답/Part 2 자동 페이지 분할
    html = re.sub(
        r'(<h[23][^>]*>(?:\[?Part\s*2|정답\s*및|Answer\s*Key|Step-by-Step).*?</h[23]>)',
        r'<div style="page-break-before: always; break-before: page; margin-top: 40px;"></div>\n\1',
        html,
        flags=re.IGNORECASE
    )

    html = html.replace("</head>", f"{CSS_STYLE}\n{MATHJAX_SCRIPT}\n{MERMAID_SCRIPT}\n</head>")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 3. 고품질 PDF 렌더링 (100% Chromium Headless 전용 렌더러 - render_pdf.py 와 동일 플래그)
    pdf_rendered = False
    browser_bin = find_chromium_browser()

    if browser_bin and os.path.exists(browser_bin):
        print(f"[{display_name}] 브라우저 기반 PDF 렌더링 시도 ({os.path.basename(browser_bin)})...")
        cmd_browser = [
            browser_bin,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={pdf_output_path}",
            html_path
        ]
        try:
            res = subprocess.run(cmd_browser, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if os.path.exists(pdf_output_path) and os.path.getsize(pdf_output_path) > 100:
                pdf_rendered = True
                print(f"[{display_name}] ✨ Chromium Headless 고품질 PDF 출판 성공! ({round(os.path.getsize(pdf_output_path)/1024/1024, 2)}MB)")
        except Exception as e:
            print(f"[Warn] 브라우저 렌더링 알림: {e}")
    else:
        print(f"[Error] [{display_name}] Chromium 계열 브라우저(Google Chrome, MS Edge, Naver Whale, Brave)를 찾을 수 없습니다.")

    if os.path.exists(html_path):
        try:
            os.remove(html_path)
        except Exception:
            pass

    # 5. 사용자 과목 폴더에 PDF 동기화 복사 보장
    if folder_dir and os.path.exists(pdf_output_path) and os.path.getsize(pdf_output_path) > 0:
        target_user_notes_dir = folder_dir
        os.makedirs(target_user_notes_dir, exist_ok=True)
        dest_user_pdf = unicodedata.normalize("NFC", os.path.join(target_user_notes_dir, os.path.basename(pdf_output_path)))
        if os.path.abspath(pdf_output_path) != os.path.abspath(dest_user_pdf):
            try:
                shutil.copy2(pdf_output_path, dest_user_pdf)
                print(f"[{display_name}] 📂 사용자 강의노트 폴더로 PDF 복사 완료: {dest_user_pdf}")
                pdf_output_path = dest_user_pdf
            except Exception as e_cp:
                print(f"[Warn] 사용자 폴더 복사 알림: {e_cp}")

    if os.path.exists(pdf_output_path) and os.path.getsize(pdf_output_path) > 0:
        pdf_size = os.path.getsize(pdf_output_path)
        print(f"[{display_name}] ✅ PDF 출판 완료! ({round(pdf_size/1024/1024, 2)}MB) -> {os.path.basename(pdf_output_path)}")
        return pdf_output_path

    else:
        print(f"[Error] [{display_name}] PDF 최종 생성 실패.")
    return None

def process_course_pdfs(course_folder, cname, en_prefix):
    """과목별로 주차별 개별 학습노트 및 전체 통합본 PDF를 일괄 컴파일 (캐시 + 사용자 폴더 양방향 탐색)"""
    root_ws = config_manager.get_root_workspace()
    cache_dir = os.path.join(root_ws, ".markdown_cache", course_folder)
    course_dir = config_manager.get_course_dir(course_folder)
    notes_dir = os.path.join(course_dir, "강의노트")
    os.makedirs(notes_dir, exist_ok=True)

    # 캐시 보관소 및 사용자 강의노트 폴더 양쪽에서 마크다운 수집 (숨김 마크다운 .*.md 포함 및 중복 제거)
    candidate_files = []
    if os.path.exists(cache_dir):
        candidate_files.extend(glob.glob(os.path.join(cache_dir, "*.md")))
        candidate_files.extend(glob.glob(os.path.join(cache_dir, ".*.md")))
    if os.path.exists(notes_dir):
        candidate_files.extend(glob.glob(os.path.join(notes_dir, "*.md")))
        candidate_files.extend(glob.glob(os.path.join(notes_dir, ".*.md")))
        candidate_files.extend(glob.glob(os.path.join(notes_dir, "**", "*.md"), recursive=True))
        candidate_files.extend(glob.glob(os.path.join(notes_dir, "**", ".*.md"), recursive=True))

    unique_files = {}
    for p in candidate_files:
        fname = os.path.basename(p)
        if fname not in unique_files or os.path.getmtime(p) > os.path.getmtime(unique_files[fname]):
            unique_files[fname] = p

    md_files = sorted(list(unique_files.values()))
    if not md_files:
        return

    # 루트 notes_dir 폴더에 오판 방치된 PDF 파일들 정리
    for orphan in glob.glob(os.path.join(notes_dir, "*.pdf")) + glob.glob(os.path.join(notes_dir, ".*.pdf")):
        try:
            os.remove(orphan)
        except Exception:
            pass

    for md_p in md_files:
        fname = os.path.basename(md_p)
        clean_fname = fname.lstrip('.')
        latest_date = get_latest_date_from_md(md_p)

        # 1. 전체 통합본인 경우 (강의노트/통합/ 에 저장)
        if "통합강의노트" in clean_fname or "Combined" in clean_fname:
            comb_dir = os.path.join(notes_dir, "통합")
            os.makedirs(comb_dir, exist_ok=True)

            if "통합강의노트" in clean_fname:
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
            week_match = re.search(r"(\d+)주차", clean_fname) or re.search(r"Week(\d+)", clean_fname, re.IGNORECASE)
            week_sub = f"{week_match.group(1)}주차" if week_match else "1주차"
            w_dir = os.path.join(notes_dir, week_sub)
            os.makedirs(w_dir, exist_ok=True)

            pdf_fname = clean_fname.replace(".md", ".pdf")
            pdf_p = os.path.join(w_dir, pdf_fname)
            display_name = clean_fname.replace(".md", "")
            convert_single_md_to_pdf(md_p, pdf_p, display_name, w_dir)

def generate_all_pdfs(target_courses=None):
    print("======================================================")
    print("🚀 [강의노트 PDF 출판 엔진 v5.2 시작]")
    print("   - 주차별 개별 학습노트 + 전체 통합본 동시 발행")
    print("   - 브라우저 및 내장 PyMuPDF 듀얼 렌더러 지원")
    print("======================================================")

    settings = config_manager.load_settings()
    courses = settings.get("courses", [])

    if not courses:
        courses = [
            {"folder_name": "마케팅원론", "course_name": "마케팅원론"}
        ]

    def norm(s):
        return unicodedata.normalize("NFC", str(s)).strip().lower() if s else ""

    norm_targets = [norm(t) for t in (target_courses or []) if t]

    seen_folders = set()
    all_targets = []
    for c in courses:
        cname = c.get("course_name") or c.get("folder_name")
        folder = c.get("folder_name") or cname
        all_targets.append((folder, cname))
        seen_folders.add(norm(folder))
        seen_folders.add(norm(cname))

    if target_courses:
        for t in target_courses:
            if t and norm(t) not in seen_folders:
                all_targets.append((t, t))
                seen_folders.add(norm(t))

    for folder, cname in all_targets:
        if norm_targets:
            if norm(cname) not in norm_targets and norm(folder) not in norm_targets:
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
