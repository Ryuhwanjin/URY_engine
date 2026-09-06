#!/bin/bash
# =============================================================================
# 🎓 URY Engine v0.6.6 — macOS 원클릭 즉시 실행 스크립트
# =============================================================================
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "======================================================"
echo "🚀 URY Engine v0.6.6 macOS 구동 준비 중..."
echo "======================================================"

# Gatekeeper quarantine 격리 속성 제거 및 실행 권한 부여
xattr -cr "$DIR/URY Engine.app" 2>/dev/null || true
chmod +x "$DIR/URY Engine.app/Contents/MacOS/URY Engine" 2>/dev/null || true

# URY Engine 실행
echo "✨ URY Engine GUI를 실행합니다..."
"$DIR/URY Engine.app/Contents/MacOS/URY Engine" &

exit 0
