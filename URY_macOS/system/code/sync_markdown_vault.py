#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
모든 과목의 마크다운 강의노트 및 모의시험 파일을 하나의 중앙 저장소('마크다운_강의노트/')에 자동 수집/동기화하는 스크립트
"""

import os
import sys
import shutil
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR
VAULT_DIR = os.path.join(WORKSPACE_DIR, ".마크다운_강의노트")

def sync_markdown_files():
    print("======================================================")
    print("📁 [마크다운 통합 보관함(Vault) 동기화 시작]")
    print("======================================================")
    os.makedirs(VAULT_DIR, exist_ok=True)
    synced_count = 0
    semester = config_manager.get_current_semester()

    settings = config_manager.load_settings()
    courses = [c.get("folder_name") or c.get("course_name") for c in settings.get("courses", []) if (c.get("folder_name") or c.get("course_name"))]
    if not courses:
        courses = ["마케팅원론"]

    for cname in courses:
        src_dir = config_manager.get_course_dir(cname)
        dst_dir = os.path.join(VAULT_DIR, cname)
        os.makedirs(dst_dir, exist_ok=True)

        # 1. .markdown_cache 내 강의노트 동기화
        cache_src = os.path.join(WORKSPACE_DIR, ".markdown_cache", cname)
        if os.path.exists(cache_src):
            for md_file in glob.glob(os.path.join(cache_src, "*.md")):
                fname = os.path.basename(md_file)
                shutil.copy2(md_file, os.path.join(dst_dir, fname))
                synced_count += 1

        # 2. 모의시험 등 과목 폴더 내 마크다운 파일 동기화
        md_files = glob.glob(os.path.join(src_dir, "**", "*.md"), recursive=True)
        for md_file in md_files:
            fname = os.path.basename(md_file)
            target_path = os.path.join(dst_dir, fname)
            shutil.copy2(md_file, target_path)
            synced_count += 1

        # 2. 이미지 폴더 동기화 (마크다운 뷰어에서 그림이 정상 로드되도록)
        src_img_dir = os.path.join(src_dir, "강의노트", "images")
        if not os.path.exists(src_img_dir):
            src_img_dir = os.path.join(src_dir, "images")
        dst_img_dir = os.path.join(dst_dir, "images")
        if os.path.exists(src_img_dir):
            os.makedirs(dst_img_dir, exist_ok=True)
            for img in glob.glob(os.path.join(src_img_dir, "*.png")):
                shutil.copy2(img, os.path.join(dst_img_dir, os.path.basename(img)))

        print(f"  • [{cname}] {len(md_files)}개 마크다운 문서 동기화 완료 -> .마크다운_강의노트/{cname}/")

    print(f"\n✅ 총 {synced_count}개의 마크다운 파일이 '{os.path.basename(VAULT_DIR)}'에 깔끔하게 모였습니다.")
    print("======================================================")

if __name__ == "__main__":
    sync_markdown_files()
