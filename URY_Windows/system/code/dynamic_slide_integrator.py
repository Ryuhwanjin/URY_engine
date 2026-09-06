#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공식 강의자료(PDF) 기반 완전 자동 동적 슬라이드 이미지 추출 및 마크다운 임베드 시스템
- 하드코딩 제거: settings.json 등록 과목을 동적으로 파싱
- 슬라이드 PDF에서 N페이지를 180 DPI 고화질 이미지로 자동 추출
- 추출된 이미지를 .markdown_cache/, 강의노트/images/ 에 자동 저장
"""

import os
import re
import glob
import sys
import shutil

try:
    import pymupdf as fitz
    FITZ_AVAILABLE = True
except ImportError:
    try:
        import fitz
        FITZ_AVAILABLE = True
    except ImportError:
        fitz = None
        FITZ_AVAILABLE = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR

def find_slide_pdfs(course_dir, explicit_slide_paths=None):
    if explicit_slide_paths:
        valid_explicit = [p for p in explicit_slide_paths if os.path.exists(p) and p.lower().endswith(".pdf")]
        if valid_explicit:
            return sorted(valid_explicit)

    slide_pdfs = []
    fallback_pdfs = []
    search_dirs = [
        os.path.join(course_dir, "강의자료"),
        course_dir
    ]
    for sdir in search_dirs:
        if os.path.exists(sdir):
            for pdf_p in glob.glob(os.path.join(sdir, "*.pdf")):
                lower_name = os.path.basename(pdf_p).lower()
                if "syllabus" in lower_name or "강의계획서" in lower_name:
                    if pdf_p not in fallback_pdfs:
                        fallback_pdfs.append(pdf_p)
                    continue
                if pdf_p not in slide_pdfs:
                    slide_pdfs.append(pdf_p)

    if not slide_pdfs and fallback_pdfs:
        return sorted(fallback_pdfs)

    return sorted(slide_pdfs)

def extract_slide_page(pdf_path, page_num, out_dirs, dpi=180):
    if isinstance(out_dirs, str):
        out_dirs = [out_dirs]

    primary_dir = out_dirs[0]
    os.makedirs(primary_dir, exist_ok=True)

    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    safe_stem = re.sub(r"[^a-zA-Z0-9가-힣_-]", "_", stem)[:30]
    out_filename = f"{safe_stem}_p{page_num:02d}.png"
    primary_path = os.path.join(primary_dir, out_filename)

    if not os.path.exists(primary_path):
        try:
            doc = fitz.open(pdf_path)
            if 1 <= page_num <= len(doc):
                page = doc[page_num - 1]
                pix = page.get_pixmap(dpi=dpi)
                pix.save(primary_path)
        except Exception as e:
            print(f"[Error] {pdf_path} P.{page_num} 이미지 추출 실패: {e}")
            return None

    for odir in out_dirs[1:]:
        if odir:
            os.makedirs(odir, exist_ok=True)
            target_path = os.path.join(odir, out_filename)
            if not os.path.exists(target_path) and os.path.exists(primary_path):
                try:
                    shutil.copy2(primary_path, target_path)
                except Exception:
                    pass

    return out_filename

def collect_all_markdown_notes(folder_name, course_dir):
    notes = []
    search_dirs = [
        os.path.join(WORKSPACE_DIR, ".markdown_cache", folder_name),
        os.path.join(course_dir, "강의노트")
    ]
    for sdir in search_dirs:
        if os.path.exists(sdir):
            for root, _, files in os.walk(sdir):
                for f in files:
                    if f.endswith(".md"):
                        fp = os.path.join(root, f)
                        if fp not in notes:
                            notes.append(fp)
    return notes

def parse_slide_pages_from_line(line):
    pages = []
    matches = re.findall(r'(?:Slide|슬라이드|Page|p\.|P\.)\s*([0-9\s~,\-]+)', line, re.IGNORECASE)
    for m in matches:
        parts = re.split(r'[,;\s]+', m.strip())
        for part in parts:
            if not part:
                continue
            rng = re.match(r'^(\d+)\s*[~-]\s*(\d+)$', part)
            if rng:
                start, end = int(rng.group(1)), int(rng.group(2))
                if 1 <= start <= 200 and 1 <= end <= 200 and start <= end:
                    pages.extend(range(start, end + 1))
            elif part.isdigit():
                p = int(part)
                if 1 <= p <= 200:
                    pages.append(p)
    return sorted(list(set(pages)))

def process_course_slides_dynamic(course_info, slide_paths=None):
    cname = course_info.get("course_name") or course_info.get("name") or course_info.get("folder_name")
    folder_name = course_info.get("folder_name") or cname
    if not cname:
        return

    course_dir = config_manager.get_course_dir(folder_name)
    notes_dir = os.path.join(course_dir, "강의노트")
    img_dir_1 = os.path.join(notes_dir, "images")
    img_dir_2 = os.path.join(WORKSPACE_DIR, ".markdown_cache", folder_name, "images")
    out_dirs = [img_dir_1, img_dir_2]

    slide_pdfs = find_slide_pdfs(course_dir, explicit_slide_paths=slide_paths)
    if not slide_pdfs:
        print(f"[{cname}] 슬라이드 PDF를 찾지 못했습니다.")
        return

    print(f"\n🔍 [{cname}] 감지된 슬라이드 PDF ({len(slide_pdfs)}개): {[os.path.basename(p) for p in slide_pdfs]}")

    target_notes = collect_all_markdown_notes(folder_name, course_dir)
    if not target_notes:
        print(f"[{cname}] 처리할 마크다운 강의노트를 찾지 못했습니다.")
        return

    for note_path in target_notes:
        note_filename = os.path.basename(note_path)
        try:
            with open(note_path, "r", encoding="utf-8", errors="ignore") as f:
                whole_content = f.read()
        except Exception:
            continue

        already_embedded_images = set(re.findall(r"!\[.*?\]\((images/[^)]+)\)", whole_content))
        inserted_pages_in_doc = set()

        lines = whole_content.splitlines(keepends=True)
        modified = False
        new_lines = []

        for i, line in enumerate(lines):
            new_lines.append(line)

            page_nums = parse_slide_pages_from_line(line)
            if not page_nums:
                continue

            for p_num in page_nums:
                if p_num in inserted_pages_in_doc or p_num <= 0:
                    continue

                for pdf_path in slide_pdfs:
                    try:
                        doc = fitz.open(pdf_path)
                        if p_num <= len(doc):
                            stem = os.path.splitext(os.path.basename(pdf_path))[0]
                            safe_stem = re.sub(r"[^a-zA-Z0-9가-힣_-]", "_", stem)[:30]
                            expected_filename = f"images/{safe_stem}_p{p_num:02d}.png"

                            if expected_filename in whole_content or any(f"_p{p_num:02d}.png" in img for img in already_embedded_images):
                                inserted_pages_in_doc.add(p_num)
                                break

                            ts_found = None
                            for look_ts in lines[max(0, i-2):min(len(lines), i+3)]:
                                ts_m = re.search(r"\[(?:🎙️\s*[^)]*|Spoken|Integrated)\s*\(([^)]+)\)\]", look_ts)
                                if not ts_m:
                                    ts_m = re.search(r"\((d{1,2}:d{2}(?::d{2})?)\)", look_ts)
                                if ts_m:
                                    ts_found = ts_m.group(1)
                                    break

                            img_filename = extract_slide_page(pdf_path, p_num, out_dirs, dpi=180)
                            if img_filename:
                                pdf_base = os.path.basename(pdf_path)
                                if ts_found:
                                    caption = f"Slide {p_num} 핵심 도표 ({pdf_base} | 🎙️ {ts_found} 음성 연계)"
                                else:
                                    caption = f"Slide {p_num} 핵심 도표 ({pdf_base})"
                                img_tag = f"\n![{caption}](images/{img_filename})\n\n"
                                new_lines.append(img_tag)
                                inserted_pages_in_doc.add(p_num)
                                modified = True
                                print(f"  📸 [{note_filename}] Slide {p_num} 핵심 도표 자동 임베드 완료 ({img_filename}, 출처: {pdf_base})")
                            break
                    except Exception as e_pdf:
                        print(f"[Warn] PDF 슬라이드 처리 중 오류: {e_pdf}")

        if modified:
            with open(note_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"  ✅ [{note_filename}] 슬라이드 이미지 동적 갱신 완료!")

def sync_and_embed_all_slides_dynamically(target_courses=None):
    print("======================================================")
    print("🚀 [슬라이드 핵심 도표/자료 완전 자동 동적 추출 & 임베드 시작]")
    print("======================================================")
    if not FITZ_AVAILABLE:
        print("[Warn] PyMuPDF 라이브러리가 설치되어 있지 않아 슬라이드 추출을 건너뜁니다.")
        print("       (자동 설치: pip install pymupdf)")
        print("======================================================")
        return

    settings = config_manager.load_settings()
    courses = settings.get("courses", [])

    for c in courses:
        cname = c.get("course_name") or c.get("folder_name")
        if target_courses and cname not in target_courses and c.get("folder_name") not in target_courses:
            continue
        process_course_slides_dynamic(c)

    print("======================================================")
    print("🎉 모든 강의자료 슬라이드 시각 자료의 동적 추출 및 반영 완료!")
    print("======================================================")

if __name__ == "__main__":
    sync_and_embed_all_slides_dynamically()
