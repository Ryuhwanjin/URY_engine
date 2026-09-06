#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URY Engine macOS .dmg Installer Builder
macOS 공식 디스크 이미지(.dmg) 빌드 자동화 스크립트
"""

import os
import shutil
import subprocess
import sys

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    staging_dir = os.path.join(root_dir, 'scratch', 'dmg_staging')
    try:
        import build_release_all
        version = build_release_all.VERSION
    except Exception:
        version = "v0.7.2"
    dmg_out = os.path.join(root_dir, '배포', f'URY_Engine_{version}.dmg')
    app_src = os.path.join(root_dir, 'URY_macOS', 'URY Engine.app')

    if not os.path.exists(app_src):
        app_src = os.path.join(root_dir, '배포', 'URY_Engine_v0.7.2_macOS', 'URY Engine.app')

    if not os.path.exists(app_src):
        print(f"❌ 오류: '{app_src}'를 찾을 수 없습니다.")
        sys.exit(1)

    print('📦 [1/4] 스테이징 폴더 초기화 중...')
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir, exist_ok=True)

    print(f'📂 [2/4] URY Engine.app 복사 중: {app_src}')
    app_dst = os.path.join(staging_dir, 'URY Engine.app')
    subprocess.run(['ditto', app_src, app_dst], check=True)

    # Applications 심볼릭 링크 생성 (드래그 앤 드롭 설치용)
    app_link = os.path.join(staging_dir, 'Applications')
    if not os.path.exists(app_link):
        os.symlink('/Applications', app_link)
    print('🔗 Applications 심볼릭 링크 생성 완료.')

    # 안내 및 유틸리티 파일 복사 (01_macOS_실행하기.command 및 USER_GUIDE.pdf 포함)
    mac_src_dir = os.path.join(root_dir, 'URY_macOS')
    for extra in ['01_macOS_실행하기.command', '보안경고_자동해제.command', '설정관리자.command', '파이프라인_실행.command', 'USER_GUIDE.pdf', 'USER_GUIDE.md', '시스템_저장경로_안내.pdf', '시스템_저장경로_안내.md']:
        p = os.path.join(mac_src_dir, extra)
        if not os.path.exists(p):
            p = os.path.join(root_dir, extra)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(staging_dir, extra))
            if extra.endswith('.command'):
                os.chmod(os.path.join(staging_dir, extra), 0o755)
            print(f'📄 부속 파일 복사: {extra}')
            # 한글 파일명 가이드 '사용설명서.pdf' 추가 생성
            if extra == 'USER_GUIDE.pdf':
                shutil.copy2(p, os.path.join(staging_dir, '사용설명서.pdf'))
                print('📄 부속 파일 복사: 사용설명서.pdf')

    print('🛡️ [3/4] macOS 격리 속성(Quarantine) 제거 및 ad-hoc 코드 서명...')
    subprocess.run(['xattr', '-rc', staging_dir], check=False)
    subprocess.run(['xattr', '-rc', app_dst], check=False)
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-', app_dst], check=True)

    print(f'🗜️ [4/4] hdiutil 기반 압축 디스크 이미지(.dmg) 빌드 중...')
    if os.path.exists(dmg_out):
        os.remove(dmg_out)

    cmd = [
        'hdiutil', 'create',
        '-volname', f'URY Engine {version}',
        '-srcfolder', staging_dir,
        '-ov',
        '-format', 'UDZO',
        dmg_out
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        dmg_size_mb = os.path.getsize(dmg_out) / (1024 * 1024)
        print(f'🎉 성공! DMG 설치 파일이 완성되었습니다: {dmg_out} ({dmg_size_mb:.1f} MB)')
    else:
        print(f'❌ DMG 생성 실패: {res.stderr}')
        sys.exit(res.returncode)

if __name__ == '__main__':
    main()
