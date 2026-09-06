#!/bin/bash
# 🎓 URY Engine v0.6.2 - 버전 자동 업그레이드 및 배포 폴더 정리 스크립트

cd "$(dirname "$0")"

echo "========================================================="
echo "🚀 URY Engine v0.6.2 최신 배포 버전 정리 시작"
echo "========================================================="

/usr/bin/python3 -c "
import os, shutil

dist_dir = os.path.abspath('배포')
backup_dir = os.path.join(dist_dir, '이전버전_백업')
os.makedirs(backup_dir, exist_ok=True)

files_map = {
    'URY_Engine_v0.6.2.dmg': 'URY_Engine_v0.6.2.dmg',
    'URY_Engine_v0.6.2_macOS.zip': 'URY_Engine_v0.6.2_macOS.zip',
    'URY_Engine_v0.6.2_Windows.zip': 'URY_Engine_v0.6.2_Windows.zip',
}

for old_name, new_name in files_map.items():
    old_p = os.path.join(dist_dir, old_name)
    new_p = os.path.join(dist_dir, new_name)
    if os.path.exists(old_p):
        shutil.copy2(old_p, new_p)
        print(f'  ✅ v0.6.2 릴리즈 생성: {new_name}')

for f in os.listdir(dist_dir):
    if f != '이전버전_백업' and not f.startswith('.'):
        if 'v0.6.2' not in f:
            fp = os.path.join(dist_dir, f)
            if os.path.isfile(fp):
                tp = os.path.join(backup_dir, f)
                shutil.move(fp, tp)
                print(f'  📦 구버전 백업 이동: {f} -> 이전버전_백업/')

print('\n🎉 URY Engine v0.6.2 최신 버전 정리가 완벽히 완료되었습니다!')
"

echo "========================================================="
