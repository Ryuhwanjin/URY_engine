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

def extract_slide_page(pdf_path, page_num, out_dirs, dpi=180, crop_diagram_only=True):
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
                
                # 1. 텍스트 전용 슬라이드 100% 스킵 검사
                img_list = page.get_images()
                drawings = page.get_drawings() if hasattr(page, "get_drawings") else []
                
                if not img_list and len(drawings) < 3:
                    print(f"  ⏭️ [{os.path.basename(pdf_path)}] Slide P.{page_num} 텍스트 전용 슬라이드 자동 스킵 (도표 없음)")
                    return None

                # 2. PPT 상단 제목 테두리 및 하단 저작권/페이지번호 제외 정밀 크롭
                rect = page.rect
                page_w, page_h = rect.width, rect.height
                
                # 기본 탐색 영역: 상단 15%, 하단 10% 제외한 중앙 영역
                clip_rect = fitz.Rect(
                    10,
                    page_h * 0.15,
                    page_w - 10,
                    page_h * 0.90
                )
                
                # 실제 개체(Drawing / Image) Bounding Box 중 중앙 본문 영역만 필터링 수집
                candidate_rects = []
                
                # A. Drawing 개체 탐지 (상단/하단 띠 배너 및 전면 배경 사각형 제외)
                for d in drawings:
                    r = d.get("rect")
                    if not r:
                        continue
                    # 전체 화면을 가리는 배경 사각형 제거
                    if r.width > page_w * 0.85 and r.height > page_h * 0.85:
                        continue
                    # 상단 15% 내 헤더 제목 배너 제거
                    if r.y1 <= page_h * 0.15:
                        continue
                    # 하단 10% 내 풋터 제거
                    if r.y0 >= page_h * 0.90:
                        continue
                    if r.width > 20 and r.height > 20:
                        candidate_rects.append(r)
                
                # B. Image 개체 탐지 (배경 통이미지 및 헤더/풋터 제외)
                for img in img_list:
                    try:
                        bbox = page.get_image_bbox(img)
                        if not bbox:
                            continue
                        if bbox.width > page_w * 0.85 and bbox.height > page_h * 0.85:
                            continue
                        if bbox.y1 <= page_h * 0.15 or bbox.y0 >= page_h * 0.90:
                            continue
                        if bbox.width > 20 and bbox.height > 20:
                            candidate_rects.append(bbox)
                    except Exception:
                        pass
                
                # 후보 개체들이 존재하면 해당 개체들만 핀포인트 통합 크롭
                if candidate_rects:
                    diagram_box = candidate_rects[0]
                    for r in candidate_rects[1:]:
                        diagram_box |= r
                    # 여백 10px 부여
                    clip_rect = fitz.Rect(
                        max(0, diagram_box.x0 - 10),
                        max(0, diagram_box.y0 - 10),
                        min(page_w, diagram_box.x1 + 10),
                        min(page_h, diagram_box.y1 + 10)
                    )
                
                pix = page.get_pixmap(clip=clip_rect, dpi=dpi)
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
    """슬라이드 이미지 자동 추출 100% 비활성화 (100% 순수 텍스트 강의노트 모드)"""
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
                                caption = f"참고 도표 (P.{p_num})"
                                img_tag = f"\n![{caption}](images/{img_filename})\n\n"
                                new_lines.append(img_tag)
                                inserted_pages_in_doc.add(p_num)
                                modified = True
                                print(f"  📸 [{note_filename}] Slide {p_num} 핵심 도표 정밀 크롭 임베드 완료 ({img_filename})")
                            break
                    except Exception as e_pdf:
                        print(f"[Warn] PDF 슬라이드 처리 중 오류: {e_pdf}")

        if modified:
            with open(note_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"  ✅ [{note_filename}] 슬라이드 이미지 동적 갱신 완료!")

def sync_and_embed_all_slides_dynamically(target_courses=None):
    print("======================================================")
    print("ℹ️ [슬라이드 이미지 자동 추출 비활성화 (100% 순수 텍스트 강의노트 모드)]")
    print("======================================================")
    return

if __name__ == "__main__":
    sync_and_embed_all_slides_dynamically()
