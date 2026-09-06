#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine v0.6.0 — macOS & Windows 듀얼 동시 배포 자동화 통합 빌더 (build_release_all.py)
- macOS 패키지 (URY_macOS -> URY_Engine_v0.6.0_macOS.zip & .dmg)
- Windows 패키지 (URY_Windows -> URY_Engine_v0.6.0_Windows.zip)
- 소스코드 및 문서 100% 최신 동기화 후 '배포/' 디렉터리에 배포본 일괄 출판
"""

import os
import sys
import shutil
import zipfile
import subprocess
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
MACOS_DIR = os.path.join(ROOT_DIR, "URY_macOS")
WIN_DIR = os.path.join(ROOT_DIR, "URY_Windows")
DIST_DIR = os.path.join(ROOT_DIR, "배포")

VERSION = "v0.6.0"

def sync_system_files():
    """macOS 및 Windows 배포 폴더 간 system(code, prompts 등) 및 App bundle 내부 소스 1:1 동기화"""
    print("🔄 [1/4] macOS 및 Windows 릴리즈 소스코드 동기화 중...")
    win_system = os.path.join(WIN_DIR, "system")
    mac_system = os.path.join(MACOS_DIR, "system")

    if os.path.exists(win_system):
        if os.path.exists(mac_system):
            shutil.rmtree(mac_system)
        shutil.copytree(win_system, mac_system)
        print("  ✅ macOS system (code/prompts) 소스코드 100% 동기화 완료!")

    # macOS URY Engine.app Bundle 내부 code 및 설정관리자.py 동기화
    src_code = os.path.join(win_system, "code")
    app_code = os.path.join(MACOS_DIR, "URY Engine.app", "Contents", "Resources", "code")
    if os.path.exists(src_code) and os.path.exists(os.path.dirname(app_code)):
        if os.path.exists(app_code):
            shutil.rmtree(app_code)
        shutil.copytree(src_code, app_code)
        print("  ✅ macOS URY Engine.app 번들 내부 code 동기화 완료!")

    runner_src = os.path.join(ROOT_DIR, "설정관리자.py")
    if os.path.exists(runner_src):
        shutil.copy2(runner_src, os.path.join(MACOS_DIR, "설정관리자.py"))
        app_res_runner = os.path.join(MACOS_DIR, "URY Engine.app", "Contents", "Resources", "설정관리자.py")
        if os.path.exists(os.path.dirname(app_res_runner)):
            shutil.copy2(runner_src, app_res_runner)
        print("  ✅ 설정관리자.py 최신 스크립트 이식 완료!")

    # 루트 매뉴얼 & PDF 가이드 동기화
    for doc_name in ["USER_GUIDE.md", "USER_GUIDE.pdf", "시스템_저장경로_안내.md", "시스템_저장경로_안내.pdf"]:
        for d in [MACOS_DIR, WIN_DIR]:
            sp = os.path.join(ROOT_DIR, doc_name)
            if not os.path.exists(sp):
                sp = os.path.join(WIN_DIR, doc_name)
            dp = os.path.join(d, doc_name)
            if os.path.exists(sp) and os.path.abspath(sp) != os.path.abspath(dp):
                shutil.copy2(sp, dp)
    print("  ✅ USER_GUIDE.pdf 및 시스템 안내 PDF 최신화 동기화 완료!")

def make_zip_archive(source_dir, output_zip_path):
    """지정 폴더를 릴리즈 ZIP 파일로 압축"""
    print(f"📦 압축 파일 생성 중: {os.path.basename(output_zip_path)}...")
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.startswith('.') or file.endswith('.pyc') or file == '.DS_Store':
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(source_dir))
                zipf.write(file_path, arcname)
    print(f"  ✅ 압축 완료! ({round(os.path.getsize(output_zip_path)/1024/1024, 1)}MB)")

def build_all_releases():
    os.makedirs(DIST_DIR, exist_ok=True)
    print("=========================================================")
    print(f"🚀 URY Engine {VERSION} macOS & Windows 듀얼 동시 배포 파이프라인 가동")
    print("=========================================================\n")

    # 1. 소스코드 동기화
    sync_system_files()

    # 2. macOS 전용 빌드 (DMG + ZIP)
    print("\n🍏 [2/4] macOS 배포 패키징 중...")
    mac_zip_path = os.path.join(DIST_DIR, f"URY_Engine_{VERSION}_macOS.zip")
    
    # macOS 권한 부여 및 서명
    try:
        subprocess.call(["chmod", "+x"] + [os.path.join(MACOS_DIR, f) for f in os.listdir(MACOS_DIR) if f.endswith(".command")])
        app_path = os.path.join(MACOS_DIR, "URY Engine.app")
        if os.path.exists(app_path):
            subprocess.call(["xattr", "-cr", app_path])
            subprocess.call(["codesign", "--force", "--deep", "--sign", "-", app_path])
            print("  🛡️ macOS URY Engine.app ad-hoc 서명 적용 완료!")
    except Exception as e:
        print(f"  ⚠️ 서명 처리 알림: {e}")

    make_zip_archive(MACOS_DIR, mac_zip_path)

    # DMG 빌드 시도 (build_dmg.py 구동)
    dmg_script = os.path.join(ROOT_DIR, "build_dmg.py")
    if os.path.exists(dmg_script):
        try:
            print("🍏 macOS .dmg 디스크 이미지 자동 빌드 중...")
            subprocess.call([sys.executable, dmg_script], cwd=ROOT_DIR)
        except Exception as e:
            print(f"  ⚠️ DMG 빌드 알림: {e}")

    # 3. Windows 전용 빌드 (ZIP)
    print("\n🪟 [3/4] Windows 배포 패키징 중...")
    win_zip_path = os.path.join(DIST_DIR, f"URY_Engine_{VERSION}_Windows.zip")
    make_zip_archive(WIN_DIR, win_zip_path)

    # 4. 결과 리포트
    print("\n=========================================================")
    print("🎉 [완료] macOS & Windows 듀얼 동시 배포 패키지가 생성되었습니다!")
    print(f"📂 [최종 배포 저장소]: {DIST_DIR}")
    print("=========================================================")
    for f in sorted(os.listdir(DIST_DIR)):
        fpath = os.path.join(DIST_DIR, f)
        if os.path.isfile(fpath):
            size_mb = round(os.path.getsize(fpath) / 1024 / 1024, 2)
            print(f"  📦 배포 파일: {f} ({size_mb}MB)")

if __name__ == "__main__":
    build_all_releases()
