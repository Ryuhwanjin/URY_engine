#!/bin/bash
# =============================================================================
# 🎓 URY Engine — 원클릭 파이프라인 더블클릭 실행기 (macOS)
# Engine: URY Academic Engine
# =============================================================================
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# macOS 보안 격리 차단 자동 해제
xattr -d com.apple.quarantine "$0" 2>/dev/null || true
xattr -cr "$DIR" 2>/dev/null || true

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
        PY="$c"
        break
    fi
done

if [ -z "$PY" ]; then
    PY="python3"
fi

echo "======================================================"
echo "🚀 URY Engine 파이프라인 구동 중..."
echo "📍 실행 Python: $PY"
echo "======================================================"

export PYTHONPATH="$DIR/system/code:$DIR/system:$DIR/code:$DIR:$PYTHONPATH"

if [ -f "$DIR/system/run_pipeline.py" ]; then
    "$PY" "$DIR/system/run_pipeline.py"
elif [ -f "$DIR/run_pipeline.py" ]; then
    "$PY" "$DIR/run_pipeline.py"
elif [ -f "$DIR/system/code/run_pipeline.py" ]; then
    "$PY" "$DIR/system/code/run_pipeline.py"
fi

echo ""
echo "======================================================"
echo "🎉 작업 완료! 창을 닫으시려면 엔터(Enter) 키를 누르세요."
echo "======================================================"
read
