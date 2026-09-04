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
chmod +x "$DIR"/code/*.py 2>/dev/null || true
chmod -R +x "$DIR/URY Engine.app/Contents/MacOS" 2>/dev/null || true

echo ""
echo "======================================================"
echo "✅ 보안 차단 속성(Quarantine) 및 권한 해제 완료!"
echo "   이제 'URY Engine.app' 또는 '설정관리자.command'를 실행하세요."
echo ""
echo "💡 만약 계속해서 '확인되지 않은 개발자' 경고가 뜬다면:"
echo "   1) Mac 화면 좌측 상단  ➔ [시스템 설정] 클릭"
echo "   2) [개인정보 보호 및 보안] ➔ [보안] 항목으로 이동"
echo "   3) '설정관리자.command 사용이 차단되었습니다' 옆"
echo "      [확인 없이 열기] (또는 [열기]) 버튼을 클릭하세요!"
echo "======================================================"
echo "창을 닫으시려면 엔터(Enter) 키를 누르세요."
read
