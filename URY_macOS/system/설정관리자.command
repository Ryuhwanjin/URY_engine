#!/bin/bash
# =============================================================================
# 🎓 URY Engine — GUI 설정 관리자 더블클릭 실행기 (macOS)
# Engine: URY Academic Engine
# =============================================================================
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# macOS 보안 격리 차단 자동 해제
xattr -d com.apple.quarantine "$0" 2>/dev/null || true
xattr -cr "$DIR" 2>/dev/null || true

# 최적의 Python 인터프리터 자동 탐색 (Anaconda / Homebrew / Conda / 시스템 Python)
PY=""
CANDIDATES=(
    "/opt/anaconda3/bin/python3"
    "$HOME/anaconda3/bin/python3"
    "$HOME/miniconda3/bin/python3"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
    "$(which python3 2>/dev/null)"
    "python3"
)

for c in "${CANDIDATES[@]}"; do
    if [ -x "$c" ]; then
        if "$c" -c "import tkinter" >/dev/null 2>&1; then
            PY="$c"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    PY="python3"
fi

echo "======================================================"
echo "🎓 URY Engine 대시보드 구동 중..."
echo "📍 실행 Python: $PY"
echo "======================================================"

export PYTHONPATH="$DIR/system/code:$DIR/system:$DIR/code:$DIR:$PYTHONPATH"

if [ -f "$DIR/system/설정관리자.py" ]; then
    "$PY" "$DIR/system/설정관리자.py"
elif [ -f "$DIR/설정관리자.py" ]; then
    "$PY" "$DIR/설정관리자.py"
elif [ -f "$DIR/system/code/settings_gui.py" ]; then
    "$PY" "$DIR/system/code/settings_gui.py"
fi

echo ""
echo "프로그램이 종료되었습니다."
