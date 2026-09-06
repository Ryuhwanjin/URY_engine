#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine — 전범위 통합 마스터 바이블 생성기 v1.0 (generate_master_bible.py)
- 시험 전 1~7주차(중간고사) / 9~15주차(기말고사) 흩어진 마크다운 노트 통합
- 중복 개념 자동 정제, 전범위 통합 개념 구조 트리 및 마스터 용어 색인(Glossary) 작성
- Chrome/Edge Headless 기반 A4 초고품질 출판용 마스터 바이블 PDF 발행
"""

import os
import sys
import glob
import re
import json
import urllib.request
import unicodedata
from datetime import datetime


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config_manager
import generate_pdfs

WORKSPACE_DIR = config_manager.WORKSPACE_DIR
CACHE_DIR = os.path.join(WORKSPACE_DIR, ".markdown_cache")


def generate_master_bible(course_folder_name: str, target_weeks: list = None, exam_type: str = "중간고사"):
    """
    지정된 과목의 선택된 주차 노트들을 통합하여 마스터 바이블 마크다운 및 PDF 생성
    """
    settings = config_manager.load_settings()
    api_key = config_manager.get_api_key() or os.environ.get("GEMINI_API_KEY", "")
    
    course_dir = config_manager.get_course_dir(course_folder_name)
    cache_c = os.path.join(CACHE_DIR, course_folder_name)

    if not os.path.exists(cache_c):
        return {"status": "error", "message": f"마크다운 캐시 폴더가 존재하지 않습니다: {cache_c}"}

    # 캐시 내의 주차별 노트 탐색
    all_mds = sorted(glob.glob(os.path.join(cache_c, "*_주차_강의노트.md")))
    if not all_mds:
        # 통합노트 fallback
        comb = os.path.join(cache_c, f"{course_folder_name}_통합강의노트.md")
        if os.path.exists(comb):
            all_mds = [comb]

    if not all_mds:
        return {"status": "error", "message": "통합할 강의노트 마크다운 파일이 없습니다."}

    # 선택된 주차 파일 필터링
    selected_files = []
    for f in all_mds:
        if target_weeks:
            fname = os.path.basename(f)
            w_match = re.search(r"(\d+)주차", fname)
            if w_match:
                w_num = int(w_match.group(1))
                if w_num in target_weeks:
                    selected_files.append(f)
            else:
                selected_files.append(f)
        else:
            selected_files.append(f)

    if not selected_files:
        selected_files = all_mds

    print(f"📚 [{course_folder_name}] {exam_type} 전범위 마스터 바이블 생성 중 (대상 파일: {len(selected_files)}개)...")

    combined_text_parts = []
    for sf in selected_files:
        with open(sf, "r", encoding="utf-8") as f:
            combined_text_parts.append(f.read())

    raw_combined_text = "\n\n---\n\n".join(combined_text_parts)

    # Gemini AI로 전범위 마스터 바이블 보정 프롬프트 작성
    prompt = f"""
당신은 해당 전공 분야의 수석 교수이자 시험 출제위원입니다.
아래 전달된 내용은 [{course_folder_name}] 과목의 {exam_type} 전범위 강의노트 요약본들입니다.

[전범위 마스터 바이블 생성 규칙]
1. 기존 내용의 출처 태그(`[🎙️ 음성 (MM:SS)]`, `[📖 교재]`, `[💡 통합]`)를 100% 보존하세요.
2. 여러 주차에 걸쳐 반복 서술된 중복 개념을 깔끔하게 하나로 결합 및 정제하세요.
3. 문서 상단에 전체 시험 범위를 한눈에 파악할 수 있는 **'📌 [{exam_type}] 전범위 마스터 개념 구조 트리 (Mindmap)'** 단원을 추가하세요. (Mermaid `flowchart TD` 활용)
4. 문서 최하단에 시험 직전 암기용 **'📚 A4 1-Page 전범위 마스터 용어 색인 사전 (Glossary Table)'**을 완성하세요.

=== 전범위 원본 강의노트 ===
{raw_combined_text[:35000]}
========================
"""

    refined_markdown = raw_combined_text
    if api_key and len(api_key) > 10:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            req_data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192}
            }
            req = urllib.request.Request(url, data=json.dumps(req_data).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                candidates = res_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        refined_markdown = parts[0].get("text", raw_combined_text)
        except Exception as e:
            print(f"⚠️ Gemini 마스터 바이블 정제 중 알림 (원본 병합본 유지): {e}")

    # 마스터 바이블 마크다운 저장
    title_str = f"📘 [{course_folder_name}] {exam_type} 전범위 마스터 바이블"
    header_block = f"# {title_str}\n\n> 🎓 **발행일자**: {datetime.now().strftime('%Y-%m-%d')} | **시험 범위**: {exam_type} 전범위\n\n---\n\n"
    final_md_content = header_block + refined_markdown

    output_md_path = os.path.join(cache_c, f"{course_folder_name}_{exam_type}_마스터_바이블.md")
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(final_md_content)

    # PDF 컴파일
    target_pdf_dir = os.path.join(course_dir, "강의노트")
    os.makedirs(target_pdf_dir, exist_ok=True)
    output_pdf_path = os.path.join(target_pdf_dir, f"[{course_folder_name}]_{exam_type}_마스터_바이블.pdf")

    try:
        generate_pdfs.convert_single_md_to_pdf(output_md_path, output_pdf_path, title_str, course_dir)
        print(f"✅ 마스터 바이블 PDF 생성 완료: {output_pdf_path}")
        return {
            "status": "success",
            "md_path": output_md_path,
            "pdf_path": output_pdf_path
        }
    except Exception as e:
        print(f"⚠️ 마스터 바이블 PDF 조판 오류: {e}")
        return {
            "status": "partial_success",
            "md_path": output_md_path,
            "error": str(e)
        }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cname = sys.argv[1]
        generate_master_bible(cname)
