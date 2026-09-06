#!/bin/bash
# =============================================================================
# 🔓 macOS 보안 경고(Gatekeeper / Quarantine) 및 실행 권한 원클릭 자동 해제기
# Engine: URY Academic Engine
# =============================================================================
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "======================================================"
echo "🔓 URY Engine — macOS 보안 격리 속성 해제 중..."
echo "======================================================"

# Gatekeeper quarantine 속성 해제 (앱 및 스크립트 격리 원천 제거)
xattr -cr "$DIR" 2>/dev/null || true
xattr -cr "$DIR"/* 2>/dev/null || true
xattr -d com.apple.quarantine "$DIR"/*.command 2>/dev/null || true
xattr -rd com.apple.quarantine "$DIR/URY Engine.app" 2>/dev/null || true
xattr -cr "$DIR/URY Engine.app" 2>/dev/null || true

# 실행 권한 설정
chmod +x "$DIR"/*.command 2>/dev/null || true
chmod +x "$DIR"/URY_macOS/*.command 2>/dev/null || true
chmod +x "$DIR"/code/*.py 2>/dev/null || true
chmod -R +x "$DIR/URY Engine.app/Contents/MacOS" 2>/dev/null || true

# v0.6.6 배포 폴더 자동 정리
/usr/bin/python3 -c "
import os, shutil

dist_dir = os.path.abspath('배포')
backup_dir = os.path.join(dist_dir, '이전버전_백업')
os.makedirs(backup_dir, exist_ok=True)

files_map = {
    'URY_Engine_v0.6.6.dmg': 'URY_Engine_v0.6.6.dmg',
    'URY_Engine_v0.6.6_macOS.zip': 'URY_Engine_v0.6.6_macOS.zip',
    'URY_Engine_v0.6.6_Windows.zip': 'URY_Engine_v0.6.6_Windows.zip',
}

for old_name, new_name in files_map.items():
    old_p = os.path.join(dist_dir, old_name)
    new_p = os.path.join(dist_dir, new_name)
    if os.path.exists(old_p):
        shutil.copy2(old_p, new_p)

for f in os.listdir(dist_dir):
    if f != '이전버전_백업' and not f.startswith('.'):
        if 'v0.6.6' not in f:
            fp = os.path.join(dist_dir, f)
            if os.path.isfile(fp):
                tp = os.path.join(backup_dir, f)
                shutil.move(fp, tp)
" 2>/dev/null || true

echo ""
echo "======================================================"
echo "✅ 보안 차단 속성(Quarantine) 및 실행 권한(chmod +x) 완전 해제!"
echo "🎉 URY Engine v0.6.6 배포 폴더 정리 완료!"
echo "   - URY_Engine_v0.6.6.dmg"
echo "   - URY_Engine_v0.6.6_macOS.zip"
echo "   - URY_Engine_v0.6.6_Windows.zip"
echo "======================================================"
echo "창을 닫으시려면 엔터(Enter) 키를 누르세요."
read
