#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 대학 전공 학업 관리 시스템 — URY Engine v0.7.2 (AI Academic Studio)
- 미니멀 & 직관적인 모던 UI/UX
- 3단계 사용자 주도형 맞춤 학습노트 생성 스튜디오 (음성 부재 대비 슬라이드 전용 모드 지원)
- 선택적 실전 모의시험 & D-Day 맞춤 학습 로드맵 (주차별 자료 다중 선택 지원)
- 실시간 백그라운드 작업 즉각 중단(Kill) 및 에러 복구 기능
- 수강 과목 관리 및 Gemini API Key 중앙 설정
"""

import os
import sys
import re
import time
import glob
import shutil
import base64
import json
import subprocess
import traceback
import threading
from datetime import datetime, date, timedelta

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    print("=" * 65)
    print("⚠️ [오류] 현재 Python 환경에 GUI(tkinter) 라이브러리가 포함되어 있지 않습니다.")
    print("💡 [해결 방법]:")
    print("  1) Python 공식 홈페이지 (https://www.python.org/downloads/) 지원 버전 설치")
    print("  2) 설치 시 [Add python.exe to PATH] 및 [tcl/tk and IDLE] 옵션 체크!")
    print("=" * 65)
    try:
        input("\n아무 키나 누르시면 프로그램이 종료됩니다...")
    except Exception:
        pass
    sys.exit(1)

try:
    from tkinter import colorchooser
except Exception:
    colorchooser = None

try:
    from pdf_viewer import PDFViewerDialog
except Exception:
    try:
        _cur_dir = os.path.dirname(os.path.abspath(__file__))
        if _cur_dir not in sys.path:
            sys.path.insert(0, _cur_dir)
        from pdf_viewer import PDFViewerDialog
    except Exception:
        PDFViewerDialog = None

# =========================================================================
# 🛡️ macOS Cocoa Tkinter SIGABRT 크래시 방지용 네이티브 안전 파일 다이얼로그
# =========================================================================
def _extract_apple_types(filetypes):
    if not filetypes:
        return []
    type_list = []
    has_any_only = True
    for desc, pat in filetypes:
        for p in pat.replace(";", " ").replace("*.", " ").replace("*", " ").split():
            clean = p.strip().lstrip(".")
            if clean and clean != "*":
                has_any_only = False
                if clean not in type_list:
                    type_list.append(clean)
    if has_any_only:
        return []
    return type_list

def _normalize_filetypes_win(filetypes):
    if not filetypes:
        return filetypes
    norm = []
    for desc, pat in filetypes:
        parts = [p.strip() for p in pat.replace(";", " ").split() if p.strip()]
        if parts:
            norm_pat = ";".join(parts) if len(parts) > 1 else parts[0]
            norm.append((desc, norm_pat))
    return norm

_orig_askopenfilename = filedialog.askopenfilename
_orig_askopenfilenames = filedialog.askopenfilenames

_dialog_busy = False

def safe_askopenfilename(title="파일 선택", filetypes=None, parent=None, initialdir=None, **kwargs):
    global _dialog_busy
    if _dialog_busy:
        return ""
    _dialog_busy = True
    try:
        if sys.platform == "darwin":
            type_list = _extract_apple_types(filetypes)
            type_clause = f'of type {{{", ".join(chr(34) + t + chr(34) for t in type_list)}}}' if type_list else ""
            
            loc_clause = ""
            if initialdir and os.path.exists(initialdir):
                clean_dir = os.path.abspath(initialdir).replace('"', '\"')
                loc_clause = f'default location POSIX file "{clean_dir}"'

            clean_title = (title or "파일 선택").replace('"', '\"')
            script = f"""
            tell current application
                activate
                try
                    set f to choose file with prompt "{clean_title}" {loc_clause} {type_clause}
                    return POSIX path of f
                on error
                    try
                        set f to choose file with prompt "{clean_title}" {type_clause}
                        return POSIX path of f
                    on error
                        return ""
                    end try
                end try
            end tell
            """
            try:
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
                chosen = res.stdout.strip()
                if chosen and os.path.exists(chosen):
                    return chosen
                return ""
            except Exception:
                return ""
        
        # Windows/Linux
        try:
            kw = {"title": title}
            if parent: kw["parent"] = parent
            if filetypes: kw["filetypes"] = _normalize_filetypes_win(filetypes)
            if initialdir: kw["initialdir"] = initialdir
            kw.update(kwargs)
            return _orig_askopenfilename(**kw)
        except Exception:
            return ""
    finally:
        _dialog_busy = False

def safe_askopenfilenames(title="파일 다중 선택", filetypes=None, parent=None, initialdir=None, **kwargs):
    global _dialog_busy
    if _dialog_busy:
        return ()
    _dialog_busy = True
    try:
        if sys.platform == "darwin":
            type_list = _extract_apple_types(filetypes)
            type_clause = f'of type {{{", ".join(chr(34) + t + chr(34) for t in type_list)}}}' if type_list else ""
            
            loc_clause = ""
            if initialdir and os.path.exists(initialdir):
                clean_dir = os.path.abspath(initialdir).replace('"', '\"')
                loc_clause = f'default location POSIX file "{clean_dir}"'

            clean_title = (title or "파일 다중 선택").replace('"', '\"')
            script = f"""
            tell current application
                activate
                try
                    set f_list to choose file with prompt "{clean_title}" {loc_clause} {type_clause} with multiple selections allowed
                    set res to ""
                    repeat with f in f_list
                        set res to res & (POSIX path of f) & linefeed
                    end repeat
                    return res
                on error
                    try
                        set f_list to choose file with prompt "{clean_title}" {type_clause} with multiple selections allowed
                        set res to ""
                        repeat with f in f_list
                            set res to res & (POSIX path of f) & linefeed
                        end repeat
                        return res
                    on error
                        return ""
                    end try
                end try
            end tell
            """
            try:
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
                lines = [p.strip() for p in res.stdout.splitlines() if p.strip() and os.path.exists(p.strip())]
                if lines:
                    return tuple(lines)
                return ()
            except Exception:
                return ()

        # Windows/Linux
        try:
            kw = {"title": title}
            if parent: kw["parent"] = parent
            if filetypes: kw["filetypes"] = _normalize_filetypes_win(filetypes)
            if initialdir: kw["initialdir"] = initialdir
            kw.update(kwargs)
            return _orig_askopenfilenames(**kw)
        except Exception:
            return ()
    finally:
        _dialog_busy = False

# monkey-patch filedialog methods everywhere
if sys.platform == "darwin":
    filedialog.askopenfilename = safe_askopenfilename
    filedialog.askopenfilenames = safe_askopenfilenames


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import ensure_requirements
ensure_requirements.check_and_install_dependencies()

import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR

PROMPTS_DIR = os.path.join(WORKSPACE_DIR, "system", "prompts")
if not os.path.exists(PROMPTS_DIR):
    PROMPTS_DIR = os.path.join(WORKSPACE_DIR, "prompts")

LANG_OPTIONS = [
    "국문 + 영문 모두 생성 (권장)",
    "국문 (한국어) 전용",
    "영문 (English) 전용"
]

LANG_LABEL_TO_CODE = {
    "국문 + 영문 모두 생성 (권장)": "both",
    "국문 (한국어) 전용": "ko",
    "영문 (English) 전용": "en"
}

LANG_CODE_TO_LABEL = {
    "both": "국문 + 영문 모두 생성 (권장)",
    "ko": "국문 (한국어) 전용",
    "en": "영문 (English) 전용"
}

PERIOD_OPTIONS = [
    "D-1 (벼락치기 총정리)",
    "D-3 (초단기 핵심정복)",
    "D-7 (1주일 완벽대비)",
    "D-14 (2주 체계적 마스터)"
]

PERIOD_TO_DAYS = {
    "D-1 (벼락치기 총정리)": 1,
    "D-3 (초단기 핵심정복)": 3,
    "D-7 (1주일 완벽대비)": 7,
    "D-14 (2주 체계적 마스터)": 14
}

# 64x64 미니멀 그린 북 & 리프 앱 아이콘 Base64 데이터 (v0.2)
APP_ICON_PNG = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAARGVYSWZNTQAqAAAACAABh2kABAAAAAEAAAAaAAAAAAADoAEAAwAAAAEAAQAAoAIABAAAAAEAAABAoAMABAAAAAEAAABAAAAAAEZRQrAAAAHNaVRYdFhNTDpjb20uYWRvYmUueG1wAAAAAAA8eDp4bXBtZXRhIHhtbG5zOng9ImFkb2JlOm5zOm1ldGEvIiB4OnhtcHRrPSJYTVAgQ29yZSA2LjAuMCI+CiAgIDxyZGY6UkRGIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyI+CiAgICAgIDxyZGY6RGVzY3JpcHRpb24gcmRmOmFib3V0PSIiCiAgICAgICAgICAgIHhtbG5zOmV4aWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20vZXhpZi8xLjAvIj4KICAgICAgICAgPGV4aWY6Q29sb3JTcGFjZT4xPC9leGlmOkNvbG9yU3BhY2U+CiAgICAgICAgIDxleGlmOlBpeGVsWERpbWVuc2lvbj4xMDI0PC9leGlmOlBpeGVsWERpbWVuc2lvbj4KICAgICAgICAgPGV4aWY6UGl4ZWxZRGltZW5zaW9uPjEwMjQ8L2V4aWY6UGl4ZWxZRGltZW5zaW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4Kwe07qQAAEGBJREFUeAHtW1mMHNd1vdXV1fsy3bNxRsMZjjhD0iIpyQsNWYogGAYsS4Jh2XICWTKQBTZg2PFXgAD5ypcNA/kKoAAJHAQxknwYzkc+IihK4siWLFmmNkuiZVpcNZzh7FvPTK+15JxXVT29VM00RUkhET7pTS3vvvvuPe/e+959XRS5VW4hcAuB/88IaB+A8uQRVH3W1zuG4zPClfedlc2tNHzuubwf4SLgrqNGvRrGw3/fee1VuFalfKWD+rLNQm14VzuIKOydL1xYe+t7Kh1DjaPyngMb8Wy2L3mobzieS47oRnxQjEgxoutZME5pESfmOBFDi2igdzRHU5aCbvsUqKBpmu2IY2mONHCti+VUHMvasm17zapay7VSZaE8v7pQX91aBzcqT10IRN2rJq77ll4AIA2VTqASAMnfPjCembztAT0VeyBiRE5oEhmWiAaFPXZaK9vWiWTvay0tvByXlwNoxAEgtrPkmNY7VqX+fOm9hedK5xYvgzuJCEgFteY94xJcWrgHErA9iZpG1dPDhcHi3ZN/Ek3HHtd0/YDqAaEcCubKpl59JH8gGayEf1wxTGvFrNZ+svrm7A/LV5fn8ZLWUEYlEKFuQVMOK+TMWc+gGsXjB+8s3nnob6Pp+JdglhnHBk+l+EeteYu4/vi8wgKjidip1IHcZ6PJ2DvlhY1FUDJOUflQd9gLAJo7lY/lPzZ6R/7I2D/ohj7tmFQcb2+0ApnoGpGo3m/k0p/TopFXqkubBIFBmwDQIrpKGACc/RRrLBPLD3xi6ik9ZnwMQaiLwY32gu6oRfW0kU3eVVnefMaqNhgHaAWMC11TFwaAAWL6fXToniNPxHLprzsWedwkhZZg6EPxXLq0dXnpNKTmhPrLZJsSNI+gQgAMzH4flH9C+XoQ1Y38DiAYmfjjRl9qiLp4tUviIACIFjtouamRu+BLR9Xstwacj+CepsxAa8PtLFRem0G3h/HZF64wkZ8e+ZSnNXXq0pdRsrPQLfheixWy90gkElGBr5Pqg34m7PBQy7aUnkZUl0QyIYlYTIxoVLABktWNEtq63DhUEk3XJJ7L3AuCZ1CpEwFo8+UgAEjE9/FI3Dj5UZm/ZVrEWiZuG5HJsREpFrOSyaQkHjUkacTllbfPyuLKmug6xSNaPRTGgph+HJQM6IwBnNy2JTEMgIgYRhYCjQuYfNgg0MQPDBblk3cfk4nRESipw+xt1xqw6diuVeWdc5fcPY8ygB6tAGTYLI0ZuVS+USpvQfmeXEBBnBhI57G5KF6DxYH/tRcTyk8dGpPP/d6nRIfZ89kG6LaF2YMJR7DTuzg3L5ulbW/2ex9DuUtEy6f6M4XNUnkOPXsCQNmXkUnnMPUpx/nwNj5UtNiXk/vvuUuiUJ5DceaX19akUMhLXItJFHnUwuKKigERP9foFQPXUJJ6Ol7wunT5TpgLSDRmZGFARvfWYe/RbZgMAxaB4/gRLeLWAOFJ88mTxySTSkmt0RCmi7bpSDaXxvgR8GH012RlbROeSJ4Rd/+/twjtrfCBSDQKXVTxA0jThzoBIEIKJS2mMXBovQJQrddERxDLp7PSn++TfDYLe9Nkq7wty+vrsr5dUuYdMwzQYbYBVBz3gwN9SHohD2Z/p1KWFCN/NKX8n06/vrUl5Z2qHBoeldXSpmztbNOxhXx6KcyVNCPKTR1LTxagKOF+CXbed9mh7FDmjx5+VB76zH0yMTIKAIqSjMcUerVGXVY2N+V3MzPys9d+Jc+89LxcXVlGjDUkEU9KEsucaZliIcfgKsCli/yY6UUB1GtvvSOP3v9Z+YtvfFvmF67KudkZ+Zdnn5bnwIvL4/6FCDhM6gJLEAeipDkR3YAcACCwX/MlIzjX6m899rhMHpyAE2O1YR+vYzQak3Qmj+VtQj7/mXvlT7/6uDz1rz+WHz39b1JvYEUCrdmwZWF5RcZuG1bP2AJBOV3W17elP1GUP/7io5KJGzI1dlCmbz+KhMeQ//rVS55rdcW1pmz+DWKH2tjhuXcLAAQeOOEIMIidOHpY1uCjOxWYJnz24sKsXFmehUVzFnXl17l0WgayORnIDcgoTPn73/0zOXl4Wr7/o79Ts375yoKk0nGJYo23vOh/8b05WZ3blL/587+Uof6iNOpcxrFFtetSrlXk9vFRZUWkc/cGqjngD88rFAABbe6GJ7ABJghHRVO4/vBlTU4cOyynX/+NSkUZxuNGTCaHx2EVcbWE0QV2qjsyu7Ikv5ubkUI2L8dGD8nXHnxIVsqrMrMyJ0ura/Lp8eNSq5li2qaUSjuysbgt3/39J2R4sF9MT3lfUG5zi315OTh6QC5cnt1TRsrPOOj1vQYLwATuBwCZWiriq0GAtC0HCv1qLBU71OC0u0E5MqpJ1azLu7OX5PzVS3LX1Ek5MT2lTDkWM9Ryl0tlYCX9MjBVkFNPnpC+XB4zzyO+1kLBECdgfWq/v88keRPYqjjvm9MaFgO8Effj7rHy/J2cVdKieuMJ/6sm/MEOX3QY1YmJIx5otlRqdTl/+Yo8+eAj8s0H/wArSAbRHcETAdA0TalDefJsL5wX9z8QqrsWfdpJ1ZPSoZuNRxkEgNuEZIrCe7oFMA541YYXH7zSvAUQCJosVHJ1fVP6kln5zmNfx7KZwUoAF8B+gKXZRT0F/PHHwnVPGdHelv10sAoHQHmNP0pHr+YjgSWNe/Hu1BsFOV7wXSf8ig4ALCwuywMfPyV9hT5pVHh2uVsU5xb2bPH5u1R8aq3u2+6/pAmHIBwA9vH5d3PdfQMhO2egKTdvUMjGl1694h8AsLG5LQeHsPQFFGwK3cIrGCgeqp9P7D3sJyPbw/XvTg589r1elWC+di2dlPxuo/sWL9S7Fho2Z5I4de9EkDRoRCLoaY6rpy+b3OI28u/1lFALwFkM5OIauv8QTZoODdUjujdn05NUKYZ7w4h2tfnKdLDaBYIEnki87CvjPvKHAuALsu8VUvi/eCmhfck9IdmfCrc8NllSNiZA7uz6HdEcIHSztYURvOi6SzgADNYUJECY7lE9qXhR090ipUfcJauiZaNH20rQ3d3lot77Du0R7Scj2/0uniytl3AAellifU5KFq7NSH+xOzSxSWGCQ+V0bMIM7N2Z6DBNZqLjg6p0Vn19RjizYkIEHtxgNcyGSoO5ZBp61IshHlLsh9oWJ3bZ7N518N9tcO/CAUC7N0Znn+YzRaEZuj4OR8DSeWbmXVlE+ss13ca2lspksMNLIfMbKQ7JUK6gQCETleN73HgMVoPCsyuL6L8s1UZVypWqYk4X4/nA1IFxmRyd9Hqo0dXk+vtcr6HrsocBqMPPrg7qBWZgPxfwrb05C0Ds8NC4HBmZRCpLbN2NTw1b4M1yWd5bnJW3Lv1WTk4clTHkC5xZ14815AkX5OL8rIwUhmSsOCJ5HJLEkEnyQIUT0YBFubT+lHrT02JRgYooF+Cf4BJkAS4xtttUYK/COWAEo1kzouNQD0lQQs0sTZgK6jD/LBKjPE7YxgeGZXVrA9kc9/ctKwz7I2F74PgpyeBAhcNyx2jxnAAZpga3iCH3Jz8eUtEdmAtw7J6Km9UEkgYBoAixvLgH9OHgQVCYJkyXfv6LN1/HEXRUirk+qSA1nltcwvY2JxlsccvVCjYcjgzm+3FYMiD9YM3M0ebPbR7GU2OH8WzK/OqilGAtBnKCRq2GVHtdsumUZHHClE6mZfHqrJw+85Z7GEI8KN9eMgIozXJaj8K9EV08QgHAqSy+zGjKF4gefZgU3/zKY/L8a68h1++X+05+WvQ48/+8RHHqY8H810srOCNYknWcTBOge4/dLSODE1KFJag9BGb13JV35Zdnfy07oBnu65fbkTIXMwUZ6kMANCLSl8lJHXHl9JlXZX5pQb728MPy36+8rPBr0yhAUjiim2AEqNP54yhtil+DxJL9ueloOvGIP0MBfJUB3nF0Uv7woS/Lk498BcLmZbu+LRvI/8t2TTZqJdmslDBbMTmAADg6MIgZXpKf/PRZnBvoslWBsoMD8uaFs/L0L/9Hpg+Oy8en75RCLis1u4r+W/jepYGvY2ypI6DquiOfmL5DvvqFR+FmDXnprTfk/MUrKk4Eycd39JrGTu3Z6uLm23gkEPy1uFmCLEABity+QjPdq9APTfyi859vv4hPgwxZKa0CgLJawlzg6Of0VNoqTl/gxwVkfwPFvHzv758CCAl5FimvkdDl8/ffJzPrV+Xs/AX3jNBbvHmwil8HaOtwt6hkkxnpx0qyU9lR54iu+e9hA2yyLD/T6iIMAoA6a07NKkMGRLLwfIH4PPfCq+pXGwqiIj8UdXcEnuJgxlFp6iqKo08+n5F7Tt0ps3OLOBg1pNhfkJ+++DJOhLzDDxCCza7xoS95qCCIG54aMf5cmZlX+4ZdQhB1FPZ06g7O6xTLjtbuIzElK6kaldoWrKCGEJykMEGFm57l5TVZxA8XvRelipy/MCOTk2Oytm7Jz198XfFRCvbOSJ0FcoMVXqC8rZk4Uit5NBy8rQRZgLL7+k51E7O2BeWTKlC1ddt9IAgRHF9fa5m7uiRXZhfUvHD3p5bRa2UC+r1k45xjEnfM7dqGx5q6tYEQBICyApMRCp+h4RRriH78QRcqzdosH8IYtCh8N7RSLZV9ALpGaZGgKYqPUtmqW+ddz1GYgOBmu0Ji07wkjQZjAIVX1t3UFDdhADAXtOxa/Q3V5WbT25cXSpjUwV3+qFMXAEEuQCLunLTq8sar+G19B+HX/20Nr2+egq9I65WV7Zc9iakTQWgrYRZAYru8ULpk1xsvqE9gGQhuokr/txvW6crs6rvQhTahdGrTHg97AcBdk1le2vwnfCTVtnvqZHIjPmN1MKvLpX+EbJRd6YJrlwuErV9c+uke8cZmeTlWSBv8DFVZAF7e6EXDb4zmduWfN87O/Riycub5zTBrlwuEAUCk2MYawz76TGwgW8DXosc/jCURY3xghamzWan9++qZ2b9CzowTlabyvKcrtJUwAHwittNNIpX5jZfxDe62HtPvAMKJ5oroU/5fXmGvKk7Zst3Yqfxw7Y3Lfw3l/S/F/dmnJXSVvQDw/cWPExF8fPxrx7ZegCU0MGA/4kyOiOPastHuArlr0Ot7gTyB4/lKMzbbzrxZbTy9c3XtB1vnFv4D/JlUMAGi8juooTEMbPYsVB6/XKjv7HhlVVYRzSQGEsO5o0YqeUI3IlP49wMjEKrgLplaHOkUD/2ZzIEHMheHIl9LgWb4VyOwNCZk7tLsODW4IJI0ex0HTvO2aV6wtmu/KS9tnDW3q0vgTjr6eavpEwh/MnHbXnoRijQ8I6Dy/NSEn9Gz+nsIthOUeDQZTUgsngQgceQHONCLRPGdqY7v3TwQWgwFHUKLf4SFr6RsW+N3cyZucTRg16xarWpWTSrFWfbNmmZHxfmOs00AWHkfqjzaehSIlK7CvvI+AASBlZbCSjB6ARVk77tQWb9SaYLAK5c6/8CjFRy8Di/vR1jONisV9+95bQWgFYj3MwbYNQuVZfGV9q++ufNKEHwgCEbP5XqF8xXtvFKAVt6t9z0LB0Jfefbx730AOq/XwvcW7S0EbiHgIvC/swqVeXspwtsAAAAASUVORK5CYII="


class SquareRoundButton(tk.Canvas):
    """
    macOS Apple Square-Round 스타일 부드러운 둥근 모서리 버튼
    - 직사각형이 아닌 부드러운 곡률(radius=8~10px)의 스퀘어클 버튼
    - Hover / Active / Disabled 반응형 인터랙션
    """
    def __init__(self, parent, text="", command=None, bg="#1c4732", fg="#ffffff",
                 hover_bg="#255e42", active_bg="#143525", radius=8,
                 font=("Pretendard", 10, "bold"), width=None, height=34,
                 state="normal", parent_bg=None, **kwargs):
        self.cmd = command
        self.btn_text = text
        self.radius = radius
        self.normal_bg = bg
        self.hover_bg = hover_bg or bg
        self.active_bg = active_bg or bg
        self.normal_fg = fg
        self.font = font
        self.btn_state = state
        self.h = height
        
        if parent_bg is None:
            try:
                p_bg = parent.cget("bg")
                parent_bg = p_bg if p_bg else "#ffffff"
            except Exception:
                try:
                    p_bg = parent.cget("background")
                    parent_bg = p_bg if p_bg else "#ffffff"
                except Exception:
                    parent_bg = "#ffffff"
        self.parent_bg = parent_bg
        
        if width is None:
            self.w = max(72, len(text) * 11 + radius * 2 + 20)
        else:
            self.w = width
            
        super().__init__(parent, width=self.w, height=self.h, bg=self.parent_bg,
                         highlightthickness=0, bd=0, **kwargs)
        
        self.rect_id = None
        self.text_id = None
        self.draw(self.normal_bg)
        
        if self.btn_state != "disabled":
            self.bind("<Enter>", self.on_enter)
            self.bind("<Leave>", self.on_leave)
            self.bind("<Button-1>", self.on_press)
            self.bind("<ButtonRelease-1>", self.on_release)
            self.config(cursor="hand2")
            
    def draw(self, fill_color=None):
        self.delete("all")
        fill_color = fill_color or self.normal_bg
        x1, y1 = 1, 1
        x2, y2 = self.w - 1, self.h - 1
        r = self.radius
        points = [
            x1 + r, y1, x1 + r, y1,
            x2 - r, y1, x2 - r, y1,
            x2, y1,
            x2, y1 + r, x2, y1 + r,
            x2, y2 - r, x2, y2 - r,
            x2, y2,
            x2 - r, y2, x2 - r, y2,
            x1 + r, y2, x1 + r, y2,
            x1, y2,
            x1, y2 - r, x1, y2 - r,
            x1, y1 + r, x1, y1 + r,
            x1, y1
        ]
        is_dis = (self.btn_state == "disabled")
        t_color = "#94a3b8" if is_dis else self.normal_fg
        b_color = "#e2e8f0" if is_dis else fill_color
        self.rect_id = self.create_polygon(points, fill=b_color, outline="", smooth=True)
        self.text_id = self.create_text(self.w // 2, self.h // 2, text=self.btn_text, fill=t_color, font=self.font)
        # Canvas 위젯 레벨의 self.bind로 이벤트가 일괄 처리되므로 태그 중복 바인딩 불필요 (더블 클릭 방지)

    def on_enter(self, e=None):
        if self.btn_state != "disabled" and self.rect_id:
            try:
                self.itemconfig(self.rect_id, fill=self.hover_bg)
            except Exception:
                pass

    def on_leave(self, e=None):
        if self.btn_state != "disabled" and self.rect_id:
            try:
                self.itemconfig(self.rect_id, fill=self.normal_bg)
            except Exception:
                pass

    def on_press(self, e=None):
        if self.btn_state != "disabled" and self.rect_id:
            try:
                self.itemconfig(self.rect_id, fill=self.active_bg)
            except Exception:
                pass

    def on_release(self, e=None):
        if self.btn_state != "disabled":
            if self.rect_id:
                try:
                    self.itemconfig(self.rect_id, fill=self.hover_bg)
                except Exception:
                    pass
            import time
            now = time.time()
            if getattr(self, "_last_click_time", 0) and (now - self._last_click_time < 0.35):
                return
            self._last_click_time = now
            if self.cmd:
                self.cmd()

    def config(self, **kwargs):
        redraw = False
        if "state" in kwargs:
            self.btn_state = kwargs.pop("state")
            if self.btn_state == "disabled":
                self.unbind("<Enter>")
                self.unbind("<Leave>")
                self.unbind("<Button-1>")
                self.unbind("<ButtonRelease-1>")
                super().config(cursor="")
            else:
                self.bind("<Enter>", self.on_enter)
                self.bind("<Leave>", self.on_leave)
                self.bind("<Button-1>", self.on_press)
                self.bind("<ButtonRelease-1>", self.on_release)
                super().config(cursor="hand2")
            redraw = True
        if "text" in kwargs:
            self.btn_text = kwargs.pop("text")
            new_w = max(self.w, len(self.btn_text) * 11 + self.radius * 2 + 20)
            if new_w > self.w:
                self.w = new_w
                super().config(width=self.w)
            redraw = True
        if "bg" in kwargs:
            self.normal_bg = kwargs.pop("bg")
            redraw = True
        if "background" in kwargs:
            self.normal_bg = kwargs.pop("background")
            redraw = True
        if "fg" in kwargs:
            self.normal_fg = kwargs.pop("fg")
            redraw = True
        if "foreground" in kwargs:
            self.normal_fg = kwargs.pop("foreground")
            redraw = True
        if "hover_bg" in kwargs:
            self.hover_bg = kwargs.pop("hover_bg")
        if "active_bg" in kwargs:
            self.active_bg = kwargs.pop("active_bg")
        if redraw:
            self.draw(self.normal_bg)
        # Any remaining valid Tk canvas options
        valid_canvas = {"cursor", "highlightbackground", "highlightcolor", "highlightthickness", "width", "height"}
        canvas_kwargs = {k: v for k, v in kwargs.items() if k in valid_canvas}
        if canvas_kwargs:
            super().config(**canvas_kwargs)
    configure = config

    def __setitem__(self, key, value):
        self.config(**{key: value})

    def cget(self, key):
        if key == "state":
            return self.btn_state
        elif key == "text":
            return self.btn_text
        elif key in ("bg", "background"):
            return self.normal_bg
        elif key in ("fg", "foreground"):
            return self.normal_fg
        return super().cget(key)

    def __getitem__(self, key):
        return self.cget(key)


class CinematicSplashScreen:
    """
    🌿 URY Engine — 미니멀 시네마틱 스플래시 오프닝
    - 100% 가로 중앙 정렬된 "Ultimate Result for You" 타이핑
    - U(0), R(9), Y(20) 세 글자 볼드 강조
    - 3글자 압축 머지 ➔ [ U   R   Y ] 엠블럼 완성 후 대시보드 오픈
    - 스킵버튼/체크박스/로딩바 완전 배제
    """
    def __init__(self, root, on_finish=None):
        self.root = root
        self.on_finish = on_finish
        
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg="#1c4732")
        
        w, h = 580, 340
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.win.lift()
        self.win.attributes("-topmost", True)
        
        self.canvas = tk.Canvas(self.win, width=w, height=h, bg="#1c4732", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 은은하고 얇은 단일 외곽선
        self.canvas.create_rectangle(3, 3, w-3, h-3, outline="#285a41", width=1.5)
        
        self.full_text = "Ultimate Result for You"
        self.base_y = h // 2
        
        # 1. 런타임 캔버스 폰트 메트릭으로 전 글자 너비 정밀 사전 측정
        char_meta = []
        total_text_width = 0
        for i, ch in enumerate(self.full_text):
            is_init = (i in (0, 9, 20)) # U, R, Y
            font = ("Helvetica Neue", 25, "bold") if is_init else ("Helvetica Neue", 22, "normal")
            color = "#fbf9f4" if is_init else "#cbdcd0"
            temp_id = self.canvas.create_text(0, 0, text=ch, font=font, anchor=tk.W)
            bbox = self.canvas.bbox(temp_id)
            self.canvas.delete(temp_id)
            ch_w = (bbox[2] - bbox[0]) if bbox else 14
            if ch == ' ':
                ch_w = 12
            char_meta.append((ch, is_init, font, color, ch_w))
            total_text_width += ch_w + 1
            
        # 2. 100% 완벽한 중앙 정렬 시작 x 좌표 산출
        start_x = (w - total_text_width) // 2
        
        self.char_steps = []
        cur_x = start_x
        for ch, is_init, font, color, ch_w in char_meta:
            self.char_steps.append((ch, is_init, font, color, cur_x, ch_w))
            cur_x += ch_w + 1
            
        self.char_items = []
        self.idx = 0
        
        # 초기 커서 (첫 글자 위치)
        self.cursor_id = self.canvas.create_line(start_x, self.base_y - 14, start_x, self.base_y + 14, fill="#82a585", width=2)
        
        self.win.after(100, self.step_type)
        
    def step_type(self):
        if self.idx < len(self.char_steps):
            ch, is_init, font, color, cur_x, ch_w = self.char_steps[self.idx]
            item = self.canvas.create_text(cur_x, self.base_y, text=ch, fill=color, font=font, anchor=tk.W)
            self.char_items.append((item, is_init, ch))
            
            # 커서를 방금 입력된 글자 바로 뒤로 이동
            next_x = cur_x + ch_w + 1
            self.canvas.coords(self.cursor_id, next_x, self.base_y - 13, next_x, self.base_y + 13)
            self.idx += 1
            self.win.after(34, self.step_type)
        else:
            self.canvas.delete(self.cursor_id)
            self.win.after(320, self.step_collapse)
            
    def step_collapse(self):
        for item, _, _ in self.char_items:
            self.canvas.delete(item)
                
        w, h = 580, 340
        # 중앙 모노그램 완벽 중앙 정렬
        self.mono_id = self.canvas.create_text(w//2, h//2 - 14, text="U   R   Y", fill="#fbf9f4", font=("Helvetica Neue", 48, "bold"), anchor=tk.CENTER)
        self.sub_id = self.canvas.create_text(w//2, h//2 + 38, text="U L T I M A T E   R E S U L T   F O R   Y O U", fill="#82a585", font=("Helvetica Neue", 9, "bold"), anchor=tk.CENTER)
        
        self.win.after(650, self.finish)
        
    def finish(self):
        try:
            self.win.destroy()
        except Exception:
            pass
        if self.on_finish:
            self.on_finish()


class UnifiedDashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("URY Engine — Academic Studio v0.7.2")

        # [배포 기기 보장] 앱 실행 즉시 바탕화면(~/Desktop/URY_Engine) 폴더 트리 구축 및 system 폴더 숨김 처리
        try:
            ws = config_manager.WORKSPACE_DIR
            os.makedirs(ws, exist_ok=True)
            os.makedirs(os.path.join(ws, "00_녹음_수신함"), exist_ok=True)
            sem_dir = os.path.join(ws, config_manager.get_current_semester())
            settings_data = config_manager.load_settings()
            registered_courses = [c.get("folder_name") or c.get("course_name") for c in settings_data.get("courses", []) if (c.get("folder_name") or c.get("course_name"))]
            if not registered_courses:
                registered_courses = ["마케팅원론"]
            for c in registered_courses:
                cdir = os.path.join(sem_dir, c)
                for sub in ["음성녹음", "강의자료", "강의노트", "예상문제", "과제", "강의계획서"]:
                    os.makedirs(os.path.join(cdir, sub), exist_ok=True)
            sys_p = os.path.join(ws, "system")
            os.makedirs(sys_p, exist_ok=True)
            if sys.platform == "darwin":
                import subprocess
                subprocess.run(["chflags", "hidden", sys_p], check=False)
        except Exception as e:
            print(f"Workspace auto-init notice: {e}")

        config_manager.fix_mac_quarantine()
        self.setup_icon()
        self.bind_mac_shortcuts()

        self.settings = config_manager.load_settings()
        self.theme_mode = self.settings.get("theme_mode", "light")
        self.theme_accent = self.settings.get("theme_accent", "#1c4732")

        # 창모드 해상도 자동 감지 및 1280x820 최소 해상도 보장 설정
        self.root.resizable(True, True)
        self.root.minsize(1280, 820)
        
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        default_w = min(1440, max(1280, int(sw * 0.85)))
        default_h = min(920, max(820, int(sh * 0.82)))
        x = max(0, (sw - default_w) // 2)
        y = max(35, (sh - default_h) // 2 - 10)

        self.root.minsize(1280, 820)

        saved_geo = self.settings.get("window_geometry", "")
        applied_geo = False
        if saved_geo and self.settings.get("remember_window_size", True):
            try:
                import re
                m = re.match(r"(\d+)x(\d+)(?:([+-]\d+)([+-]\d+))?", saved_geo)
                if m:
                    gw, gh = int(m.group(1)), int(m.group(2))
                    if gw <= sw and gh <= (sh - 50):
                        self.root.geometry(saved_geo)
                        applied_geo = True
            except Exception:
                pass
        if not applied_geo:
            self.root.geometry(f"{default_w}x{default_h}+{x}+{y}")

        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)
        self.root.bind("<Configure>", self.on_window_configure)

        # 시네마틱 스플래시 오프닝 구동 (메인 창 잠시 은닉)
        self.root.withdraw()
        self.splash = CinematicSplashScreen(self.root, on_finish=self.on_splash_done)
        self.courses = list(self.settings.get("courses", []))
        self.selected_courses_for_run = set()
        self.last_generated_pdf = None
        self.studio_start_time = 0
        self.studio_is_running = False
        self.studio_current_eta = 0
        self.studio_cancel_requested = False
        self.exam_material_vars = {} 

        self.setup_styles()
        self.create_header_card()
        self.create_tabs()
        self.populate_course_table()


    def on_splash_done(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.after(120, lambda: self.check_compliance_agreement(force=False))
        except Exception:
            pass

    def check_compliance_agreement(self, force=False):
        if not force and self.settings.get("compliance_agreed", False):
            return

        if getattr(self, "_compliance_dialog", None) and self._compliance_dialog.winfo_exists():
            try:
                self._compliance_dialog.deiconify()
                self._compliance_dialog.lift()
                self._compliance_dialog.attributes("-topmost", True)
                self._compliance_dialog.focus_force()
                return
            except Exception:
                pass

        dialog = tk.Toplevel(self.root)
        self._compliance_dialog = dialog
        dialog.title("URY Engine — 저작권법 준수 및 학업 윤리 서약")
        dialog.transient(self.root)
        dialog.configure(bg="#f8fafc")

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        win_w = min(640, max(480, sw - 80))
        win_h = min(540, max(360, sh - 140))
        x = max(0, (sw - win_w) // 2)
        y = max(30, (sh - win_h) // 2 - 20)
        dialog.geometry(f"{win_w}x{win_h}+{x}+{y}")
        dialog.minsize(460, 320)
        dialog.resizable(True, True)

        try:
            dialog.attributes("-topmost", True)
        except Exception:
            pass

        # 1. 상단 헤더 프레임 (상단 고정)
        hdr_frame = tk.Frame(dialog, bg="#ffffff", padx=20, pady=14, highlightthickness=1, highlightbackground="#e2e8f0")
        hdr_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Label(hdr_frame, text="🎓 URY Engine 저작권 준수 및 학업 윤리 서약서", font=("Pretendard", 12, "bold"), bg="#ffffff", fg="#1c4732").pack(anchor=tk.W)
        tk.Label(hdr_frame, text="대한민국 저작권법 제30조(사적이용을 위한 복제) 및 대학 학업 윤리 가이드라인", font=("Pretendard", 9), bg="#ffffff", fg="#64748b").pack(anchor=tk.W, pady=(3, 0))

        # 2. 하단 서약 확인 및 버튼 프레임 (하단 최우선 고정 -> 창 크기에 상관없이 항상 100% 노출!)
        btm_frame = tk.Frame(dialog, bg="#ffffff", padx=16, pady=12, highlightthickness=1, highlightbackground="#e2e8f0")
        btm_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # 3. 중앙 본문 스크롤 프레임 (남는 중간 영역 채움)
        body_frame = tk.Frame(dialog, bg="#f8fafc", padx=16, pady=10)
        body_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        txt = tk.Text(
            body_frame,
            wrap=tk.WORD,
            font=("Pretendard", 10),
            bg="#ffffff",
            fg="#1e293b",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            padx=14,
            pady=12,
            spacing1=3,
            spacing2=4,
            spacing3=3
        )
        sb = ttk.Scrollbar(body_frame, orient=tk.VERTICAL, command=txt.yview)
        txt.config(yscrollcommand=sb.set)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        terms_text = """[제1조: 사적 이용을 위한 복제 목적 한정 (저작권법 제30조)]
본 소프트웨어(URY Engine)로 처리되는 강의 음성 녹음, 강의 슬라이드, 필기 사진 및 AI가 생성한 모든 산출물(학습노트, 모의고사, 치트시트)은 수강생 본인의 '개인 학업 복습 및 시험 대비'를 위한 사적 이용 목적으로만 사용되어야 합니다.

[제2조: 무단 배포, 공유 및 상업적 판매 엄금 (저작권법 제136조)]
교수자의 강의 및 강의자료는 저작권법의 보호를 받는 지적재산입니다. 수강생은 생성된 강의노트나 모의고사, 원본 자료를 에브리타임, 카카오톡 단톡방, 인터넷 카페, SNS, 해피캠퍼스 등에 배포·공유·전재·판매할 수 없으며, 이를 위반하여 발생하는 모든 민·형사상 법적 책임은 이용자 본인에게 귀속됩니다.

[제3조: 강의 음성 녹음 윤리 준수 (통신비밀보호법 및 학칙)]
강의 음성 녹음은 교수자의 사전 수업 안내 및 동의 범위 내에서 본인의 복습을 위해 진행해야 하며, 교수자 및 동료 수강생의 인격권(음성권·초상권)을 침해하지 않도록 각별히 유의해야 합니다.

[제4조: 로컬 독립 실행 및 개발자 면책 (Legal Disclaimer)]
URY Engine은 사용자의 로컬 컴퓨터 내에서만 독립적으로 동작하며, 어떠한 강의 음성이나 자료도 중앙 서버에 수집·보관하지 않습니다. AI 결과물은 학업 보조용 조교일 뿐 최종 시험 평가 기준을 대체하지 않습니다."""

        txt.insert(tk.END, terms_text)
        txt.config(state=tk.DISABLED)

        is_already_agreed = self.settings.get("compliance_agreed", False)
        agree_var = tk.BooleanVar(value=True)

        # 클릭 가능한 인터랙티브 서약 동의 카드 (전체 영역 반응형)
        card_agree = tk.Frame(
            btm_frame,
            bg="#f0fdf4",
            highlightthickness=1,
            highlightbackground="#86efac",
            padx=12,
            pady=8,
            cursor="hand2"
        )
        card_agree.pack(fill=tk.X, pady=(0, 10))

        chk_icon = tk.Label(
            card_agree,
            text="☑",
            font=("Pretendard", 12, "bold"),
            bg="#f0fdf4",
            fg="#166534",
            cursor="hand2"
        )
        chk_icon.pack(side=tk.LEFT, padx=(0, 8))

        chk_text = tk.Label(
            card_agree,
            text="[필수] 상기 저작권법 제30조 준수 및 외부 배포 금지 서약 내용을 확인하였으며, 전적으로 동의합니다.",
            font=("Pretendard", 9, "bold"),
            bg="#f0fdf4",
            fg="#166534",
            cursor="hand2"
        )
        chk_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def update_toggle_ui():
            if agree_var.get():
                card_agree.config(bg="#f0fdf4", highlightbackground="#86efac")
                chk_icon.config(text="☑", bg="#f0fdf4", fg="#166534")
                chk_text.config(bg="#f0fdf4", fg="#166534")
            else:
                card_agree.config(bg="#f8fafc", highlightbackground="#cbd5e1")
                chk_icon.config(text="☐", bg="#f8fafc", fg="#64748b")
                chk_text.config(bg="#f8fafc", fg="#475569")

        def toggle_agree(event=None):
            agree_var.set(not agree_var.get())
            update_toggle_ui()

        card_agree.bind("<Button-1>", toggle_agree)
        chk_icon.bind("<Button-1>", toggle_agree)
        chk_text.bind("<Button-1>", toggle_agree)

        def cleanup_bindings():
            try:
                self.root.unbind("<FocusIn>", root_focus_id)
            except Exception:
                pass
            try:
                self.root.unbind("<Unmap>", root_unmap_id)
            except Exception:
                pass
            try:
                self.root.unbind("<Map>", root_map_id)
            except Exception:
                pass
            self._compliance_dialog = None

        def on_confirm(event=None):
            self.settings["compliance_agreed"] = True
            self.settings["compliance_agreed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                config_manager.save_settings(self.settings)
            except Exception as ex:
                print(f"[Warning] Failed to save compliance settings: {ex}")
            cleanup_bindings()
            try:
                dialog.attributes("-topmost", False)
            except Exception:
                pass
            dialog.destroy()
            try:
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass

        def on_close(event=None):
            if not self.settings.get("compliance_agreed", False):
                if messagebox.askyesno("서약 종료", "저작권 준수 서약을 완료하지 않으면 프로그램을 이용할 수 없습니다.\n\n프로그램을 종료하시겠습니까?", parent=dialog):
                    cleanup_bindings()
                    dialog.destroy()
                    self.root.destroy()
            else:
                cleanup_bindings()
                try:
                    dialog.attributes("-topmost", False)
                except Exception:
                    pass
                dialog.destroy()

        btn_row = tk.Frame(btm_frame, bg="#ffffff")
        btn_row.pack(fill=tk.X)

        cancel_text = "✕  닫기" if is_already_agreed else "✕  동의하지 않고 종료"
        SquareRoundButton(
            btn_row,
            text=cancel_text,
            bg="#f1f5f9",
            hover_bg="#e2e8f0",
            fg="#475569",
            radius=8,
            height=34,
            font=("Pretendard", 9, "bold"),
            command=on_close,
            parent_bg="#ffffff"
        ).pack(side=tk.LEFT)

        SquareRoundButton(
            btn_row,
            text="✍️  서약 및 전체 동의하고 URY Engine 시작",
            bg="#1c4732",
            hover_bg="#265e43",
            radius=8,
            height=34,
            font=("Pretendard", 10, "bold"),
            command=on_confirm,
            parent_bg="#ffffff"
        ).pack(side=tk.RIGHT)

        dialog.bind("<Return>", on_confirm)
        dialog.bind("<KP_Enter>", on_confirm)
        dialog.bind("<Escape>", on_close)
        dialog.protocol("WM_DELETE_WINDOW", on_close)

        # 🌟 최소화 및 포커스 동기화 (grab_set을 배제하여 맥OS 최소화 프리징 원천 차단!)
        def refocus_dialog(event=None):
            if dialog.winfo_exists():
                try:
                    dialog.lift()
                    dialog.attributes("-topmost", True)
                except Exception:
                    pass

        def on_root_unmap(e):
            if e.widget == self.root and dialog.winfo_exists():
                try:
                    dialog.withdraw()
                except Exception:
                    pass

        def on_root_map(e):
            if e.widget == self.root and dialog.winfo_exists():
                try:
                    dialog.deiconify()
                    dialog.lift()
                    dialog.attributes("-topmost", True)
                    dialog.focus_force()
                except Exception:
                    pass

        root_focus_id = self.root.bind("<FocusIn>", refocus_dialog, add="+")
        root_unmap_id = self.root.bind("<Unmap>", on_root_unmap, add="+")
        root_map_id = self.root.bind("<Map>", on_root_map, add="+")

        dialog.focus_force()

    def open_pdf_viewer(self, pdf_path, title=None, initial_page=0):
        """인라인 PDF 라이브 뷰어 창 띄우기 (실패 시 시스템 외장 뷰어 fallback)"""
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showinfo("안내", "열람할 PDF 파일이 존재하지 않습니다.", parent=self.root)
            return
        if PDFViewerDialog is not None:
            try:
                PDFViewerDialog(self.root, pdf_path, title=title, initial_page=initial_page)
                return
            except Exception as err:
                print(f"⚠️ [인라인 PDF 뷰어 예외]: {err}")
        # Fallback to system default viewer
        try:
            if sys.platform == "darwin":
                subprocess.call(["open", pdf_path])
            elif sys.platform == "win32":
                os.startfile(pdf_path)
            else:
                subprocess.call(["xdg-open", pdf_path])
        except Exception as sub_err:
            messagebox.showerror("오류", f"PDF를 여는 중 오류가 발생했습니다:\n{sub_err}", parent=self.root)

    def set_theme_accent(self, color_hex):
        if not color_hex or not color_hex.startswith("#"):
            return
        self.theme_accent = color_hex
        self.settings["theme_accent"] = color_hex
        config_manager.save_settings(self.settings)
        self.setup_styles()
        self.refresh_theme_widgets()

    def choose_custom_color(self):
        curr = getattr(self, "theme_accent", "#1c4732")
        try:
            if colorchooser is not None:
                picked = colorchooser.askcolor(color=curr, title="포인트 테마 색상 선택")
                if picked and picked[1]:
                    self.set_theme_accent(picked[1])
                    return
        except Exception:
            pass
        try:
            res = self.root.tk.call("tk_chooseColor", "-initialcolor", curr, "-title", "포인트 테마 색상 선택")
            if res:
                self.set_theme_accent(str(res))
        except Exception:
            pass

    def toggle_theme(self):
        self.theme_mode = "dark" if self.theme_mode == "light" else "light"
        self.settings["theme_mode"] = self.theme_mode
        config_manager.save_settings(self.settings)
        self.setup_styles()
        self.refresh_theme_widgets()

    def refresh_theme_widgets(self):
        is_dark = (self.theme_mode == "dark")
        accent = getattr(self, "theme_accent", "#1c4732")
        if hasattr(self, "theme_toggle_btn"):
            self.theme_toggle_btn.config(
                text=" ☀️ 라이트 모드 " if is_dark else " 🌙 다크 모드 ",
                bg="#26543e" if is_dark else "#143324",
                fg="#fbf9f4"
            )
        if hasattr(self, "tab_theme_toggle_btn"):
            self.tab_theme_toggle_btn.config(
                text=" ☀️ 라이트 모드로 전환 " if is_dark else " 🌙 다크 모드로 전환 ",
                bg="#26543e" if is_dark else "#e2e8f0",
                fg="#fbf9f4" if is_dark else "#14281e"
            )
        if hasattr(self, "header_frame"):
            self.header_frame.configure(style="Header.TFrame")
        if hasattr(self, "sem_badge_label"):
            self.sem_badge_label.config(
                bg="#143324" if not is_dark else "#1a382b",
                fg="#d8f3dc"
            )
        if hasattr(self, "api_badge_label"):
            has_key = len(self.settings.get("gemini_api_key", "").strip()) >= 10
            api_fg = "#4ade80" if has_key else "#f87171"
            self.api_badge_label.config(
                bg="#143324" if not is_dark else "#1a382b",
                fg=api_fg
            )
        if hasattr(self, "accent_preview_chip"):
            self.accent_preview_chip.config(bg=accent)
        if hasattr(self, "accent_hex_label"):
            self.accent_hex_label.config(text=f"현재 선택된 포인트 색상: {accent}")

    def setup_icon(self):
        try:
            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("URY.Engine.AcademicStudio.v063")
                except Exception:
                    pass
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.abspath(os.path.join(cur_dir, "..", ".."))
            ico_file = os.path.join(root_dir, "app_icon.ico")
            png_file = os.path.join(root_dir, "app_icon.png")
            if os.path.exists(ico_file) and sys.platform == "win32":
                self.root.iconbitmap(ico_file)
            elif os.path.exists(png_file):
                self.icon_img = tk.PhotoImage(file=png_file)
                self.root.iconphoto(True, self.icon_img)
            else:
                icon_data = base64.b64decode(APP_ICON_PNG)
                self.icon_img = tk.PhotoImage(data=icon_data)
                self.root.iconphoto(True, self.icon_img)
        except Exception:
            pass

    def bind_mac_shortcuts(self):
        try:
            self.root.event_add("<<Paste>>", "<Command-v>")
            self.root.event_add("<<Copy>>", "<Command-c>")
            self.root.event_add("<<Cut>>", "<Command-x>")
            self.root.event_add("<<SelectAll>>", "<Command-a>")

            for widget_name in ("Entry", "TEntry", "Text"):
                self.root.bind_class(widget_name, "<Command-v>", lambda e: e.widget.event_generate("<<Paste>>"))
                self.root.bind_class(widget_name, "<Command-c>", lambda e: e.widget.event_generate("<<Copy>>"))
                self.root.bind_class(widget_name, "<Command-x>", lambda e: e.widget.event_generate("<<Cut>>"))
            self.root.bind_class("Entry", "<Command-a>", lambda e: (e.widget.select_range(0, tk.END), "break")[1])
            self.root.bind_class("Text", "<Command-a>", lambda e: (e.widget.tag_add("sel", "1.0", "end"), "break")[1])

            # ── 한글 IME 오타 수정 (macOS tkinter Hangul 자모 분리 버그) ──────────
            # 증상: '마' 입력 시 'ㅁㅏ'로 분리되어 삽입되는 현상 (맨 처음 입력 시)
            # 원인: macOS Cocoa IME가 첫 키 이벤트를 raw Jamo로 전달하는 Tk 버그
            # 해결: KeyRelease 후 NFC 정규화(Jamo 결합)로 즉시 교정
            # ── 한글 IME 오타 수정 (macOS tkinter Hangul 자모 분리 버그) ──────────
            # 증상: '마' 입력 시 'ㅁㅏ'로 분리되어 삽입되는 현상 (맨 처음 입력 시)
            # 원인: macOS Cocoa IME가 첫 키 이벤트를 호환 자모(Compatibility Jamo)로 삽입하는 Tk 버그
            # 해결: 호환 자모(초성+중성+종성) 및 NFD 자모를 완성형 한글 음절로 합성
            import unicodedata as _ud

            _CHOS = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
            _JUNGS = ['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ']
            _JONGS = ['', 'ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ','ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']

            def _compose_hangul(text):
                text = _ud.normalize('NFC', text)
                result = []
                i = 0
                n = len(text)
                while i < n:
                    c1 = text[i]
                    if c1 in _CHOS and i + 1 < n and text[i+1] in _JUNGS:
                        c2 = text[i+1]
                        cho_idx = _CHOS.index(c1)
                        jung_idx = _JUNGS.index(c2)
                        jong_idx = 0
                        if i + 2 < n and text[i+2] in _JONGS:
                            if i + 3 < n and text[i+3] in _JUNGS:
                                jong_idx = 0
                                result.append(chr(0xAC00 + (cho_idx * 21 + jung_idx) * 28 + jong_idx))
                                i += 2
                                continue
                            else:
                                jong_idx = _JONGS.index(text[i+2])
                                result.append(chr(0xAC00 + (cho_idx * 21 + jung_idx) * 28 + jong_idx))
                                i += 3
                                continue
                        result.append(chr(0xAC00 + (cho_idx * 21 + jung_idx) * 28 + jong_idx))
                        i += 2
                    else:
                        result.append(c1)
                        i += 1
                return ''.join(result)

            def _nfc_entry(event):
                w = event.widget
                try:
                    cur = w.get()
                    nfc = _compose_hangul(cur)
                    if nfc != cur:
                        try:
                            pos = w.index(tk.INSERT)
                        except Exception:
                            pos = len(nfc)
                        w.delete(0, tk.END)
                        w.insert(0, nfc)
                        try:
                            w.icursor(min(pos, len(nfc)))
                        except Exception:
                            pass
                except Exception:
                    pass

            def _nfc_text(event):
                w = event.widget
                try:
                    cur = w.get("1.0", tk.END)
                    nfc = _compose_hangul(cur)
                    if nfc != cur:
                        try:
                            pos = w.index(tk.INSERT)
                        except Exception:
                            pos = "1.0"
                        w.delete("1.0", tk.END)
                        w.insert("1.0", nfc.rstrip("\n"))
                        try:
                            w.mark_set(tk.INSERT, pos)
                        except Exception:
                            pass
                except Exception:
                    pass

            if sys.platform == "darwin":
                self.root.bind_class("Entry", "<KeyRelease>", _nfc_entry, add=True)
                self.root.bind_class("Entry", "<FocusOut>", _nfc_entry, add=True)
                self.root.bind_class("TEntry", "<KeyRelease>", _nfc_entry, add=True)
                self.root.bind_class("TEntry", "<FocusOut>", _nfc_entry, add=True)
                self.root.bind_class("Text", "<FocusOut>", _nfc_text, add=True)
            # ────────────────────────────────────────────────────────────────────────

            self.root.bind("<Command-f>", self.toggle_fullscreen)
            self.root.bind("<F11>", self.toggle_fullscreen)
        except Exception:
            pass


    def add_context_menu(self, widget):
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="복사 (Copy)", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="붙여넣기 (Paste)", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_command(label="잘라내기 (Cut)", command=lambda: widget.event_generate("<<Cut>>"))

        if sys.platform == "darwin":
            widget.bind("<Button-2>", lambda e: menu.post(e.x_root, e.y_root))
            widget.bind("<Control-Button-1>", lambda e: menu.post(e.x_root, e.y_root))
        widget.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))

    def on_window_configure(self, event):
        if event.widget == self.root:
            w = event.width
            h = event.height
            if hasattr(self, "res_status_label"):
                self.res_status_label.config(text=f"현재 창 크기: {w} × {h} px  (마우스 드래그로 자유롭게 조절 가능)")
            if hasattr(self, "res_width_var") and hasattr(self, "res_height_var"):
                if not getattr(self, "_res_editing", False):
                    self.res_width_var.set(str(w))
                    self.res_height_var.set(str(h))

    def save_current_window_state(self):
        try:
            if self.settings.get("remember_window_size", True):
                is_full = False
                if sys.platform == "darwin":
                    try:
                        is_full = bool(self.root.attributes("-fullscreen"))
                    except Exception:
                        pass
                if not is_full:
                    geo = self.root.geometry()
                    self.settings["window_geometry"] = geo
                    config_manager.save_settings(self.settings)
        except Exception:
            pass

    def on_app_close(self):
        try:
            self.save_current_window_state()
        except Exception:
            pass
        self.root.destroy()

    def apply_resolution(self, width, height):
        try:
            if sys.platform == "darwin":
                try:
                    if self.root.attributes("-fullscreen"):
                        self.root.attributes("-fullscreen", False)
                except Exception:
                    pass
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = max(0, (screen_w - width) // 2)
            y = max(30, (screen_h - height) // 2 - 20)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            if hasattr(self, "res_status_label"):
                self.res_status_label.config(text=f"현재 창 크기: {width} × {height} px  (마우스 드래그로 자유롭게 조절 가능)")
            self.save_current_window_state()
        except Exception as e:
            messagebox.showwarning("해상도 변경 오류", f"창 크기를 적용할 수 없습니다: {e}")

    def toggle_fullscreen(self, event=None):
        try:
            if sys.platform == "darwin":
                cur = bool(self.root.attributes("-fullscreen"))
                self.root.attributes("-fullscreen", not cur)
            else:
                is_full = getattr(self, "_is_fullscreen", False)
                self.root.state("zoomed" if not is_full else "normal")
                self._is_fullscreen = not is_full
        except Exception:
            pass

    def show_resolution_quick_menu(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="🖥️ 창모드 해상도 빠른 선택", state="disabled")
        menu.add_separator()

        presets = [
            ("📱 1024 × 680 (콤팩트 · 13인치 노트북)", 1024, 680),
            ("💻 1160 × 800 (표준 모드)", 1160, 800),
            ("🖥️ 1280 × 820 (권장 창모드)", 1280, 820),
            ("✨ 1440 × 900 (맥북 레티나 최적)", 1440, 900),
            ("🖥️ 1600 × 980 (대화면 모니터)", 1600, 980),
        ]
        for label, w, h in presets:
            menu.add_command(label=label, command=lambda width=w, height=h: self.apply_resolution(width, height))

        menu.add_separator()
        menu.add_command(label="⛶ 전체 화면 전환 (Cmd+F)", command=self.toggle_fullscreen)
        menu.add_command(label="⚙️ 상세 해상도 설정...", command=lambda: self.switch_to_tab(4))

        try:
            x = self.res_quick_btn.winfo_rootx()
            y = self.res_quick_btn.winfo_rooty() + self.res_quick_btn.winfo_height() + 4
            menu.post(x, y)
        except Exception:
            menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def toggle_remember_window_size(self):
        self.settings["remember_window_size"] = self.remember_window_var.get()
        config_manager.save_settings(self.settings)

    ask_open_file_safe = staticmethod(safe_askopenfilename)
    ask_open_files_safe = staticmethod(safe_askopenfilenames)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # 🌟 시안 2 (Apple Clean Light) + 포레스트 그린 팔레트
        bg_main = "#f6f8fa"        # 은은하고 편안한 Apple 라이트 그레이
        bg_card = "#ffffff"        # 퓨어 화이트 카드
        bg_header = "#ffffff"      # 퓨어 화이트 상단 바
        border_c = "#e2e8f0"       # 정갈한 1px 슬레이트 보더
        fg_main = "#0f172a"        # 또렷한 슬레이트 차콜 텍스트
        fg_muted = "#64748b"       # 소프트 슬레이트 그레이
        accent = "#1c4732"         # 앱 아이콘 원색 딥 포레스트 그린

        self.root.configure(bg=bg_main)

        # 폰트 계층
        f_title = ("Pretendard", 11, "bold")
        f_body = ("Pretendard", 10)
        f_small = ("Pretendard", 9)

        style.configure(".", background=bg_main, foreground=fg_main, font=f_body)
        style.configure("TFrame", background=bg_main)
        style.configure("Card.TFrame", background=bg_card, relief=tk.FLAT, borderwidth=0)
        style.configure("TLabel", background=bg_main, foreground=fg_main, font=f_body)
        style.configure("Card.TLabel", background=bg_card, foreground=fg_main, font=f_body)
        style.configure("Muted.TLabel", background=bg_main, foreground=fg_muted, font=f_small)
        style.configure("CardMuted.TLabel", background=bg_card, foreground=fg_muted, font=f_small)
        style.configure("Card.TCheckbutton", background=bg_card, foreground=fg_main, font=f_body)

        # 숨겨진 노트북 탭 (상단 플로팅 알약 세그먼트 바로 직접 제어)
        style.layout("Hidden.TNotebook.Tab", [])
        style.configure("Hidden.TNotebook", background=bg_main, borderwidth=0, tabmargins=0)

        # 기본 ttk.Notebook 스타일 유지보수
        style.configure("TNotebook", background=bg_main, borderwidth=0)
        style.configure("TNotebook.Tab", font=f_title, padding=[16, 8], background="#e2e8f0", foreground=fg_muted)
        style.map("TNotebook.Tab", background=[("selected", accent)], foreground=[("selected", "#ffffff")])

        # 버튼들
        style.configure("Primary.TButton", font=f_title, background=accent, foreground="#ffffff", borderwidth=0)
        style.map("Primary.TButton", background=[("active", "#265e43"), ("disabled", "#94a3b8")])

        style.configure("Action.TButton", font=("Pretendard", 10, "bold"), background=accent, foreground="#ffffff", borderwidth=0)
        style.map("Action.TButton", background=[("active", "#265e43"), ("disabled", "#94a3b8")])

        style.configure("Secondary.TButton", font=f_body, background="#e2e8f0", foreground=fg_main, borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#cbd5e1")])

        style.configure("Danger.TButton", font=f_body, background="#dc2626", foreground="#ffffff", borderwidth=0)
        style.map("Danger.TButton", background=[("active", "#b91c1c"), ("disabled", "#94a3b8")])

        # 트리뷰 (과목 테이블)
        style.configure("Treeview.Heading", font=("Pretendard", 10, "bold"), background="#f1f5f9", foreground=fg_main)
        style.configure("Treeview", font=f_body, rowheight=28, background=bg_card, fieldbackground=bg_card, foreground=fg_main)
        style.map("Treeview", background=[("selected", "#e8f5ed")], foreground=[("selected", "#1c4732")])

        # 라벨프레임
        style.configure("TLabelframe", background=bg_card, bordercolor=border_c, borderwidth=1)
        style.configure("TLabelframe.Label", background=bg_card, foreground=fg_main, font=f_title)

    def create_header_card(self):
        # 🌟 시안 2 상단 헤더: 화이트 클린 탑바 + 중앙 플로팅 알약 탭 세그먼트
        self.header_frame = tk.Frame(self.root, bg="#ffffff", height=62, bd=0, highlightthickness=1, highlightbackground="#e2e8f0")
        self.header_frame.pack(fill=tk.X)
        self.header_frame.pack_propagate(False)

        # 좌측: 모노그램 로고 & 앱 타이틀
        left = tk.Frame(self.header_frame, bg="#ffffff")
        left.pack(side=tk.LEFT, padx=(14, 6), fill=tk.Y)

        title_row = tk.Frame(left, bg="#ffffff")
        title_row.pack(anchor=tk.W, pady=(12, 0))
        if hasattr(self, "icon_img"):
            try:
                tk.Label(title_row, image=self.icon_img, bg="#ffffff").pack(side=tk.LEFT, padx=(0, 6))
            except Exception:
                pass
        tk.Label(title_row, text="URY Engine", font=("Pretendard", 12, "bold"), bg="#ffffff", fg="#1c4732").pack(side=tk.LEFT)
        tk.Label(title_row, text=" v0.7.2", font=("Pretendard", 9), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT)
        tk.Label(left, text="Academic Studio", font=("Pretendard", 8), bg="#ffffff", fg="#94a3b8").pack(anchor=tk.W)

        # 우측: 해상도 선택기 / 학기 / API 연결 상태 배지 (오른쪽에 영구 고정되도록 center보다 먼저 pack)
        right = tk.Frame(self.header_frame, bg="#ffffff")
        right.pack(side=tk.RIGHT, padx=(6, 14), fill=tk.Y)

        self.res_quick_btn = SquareRoundButton(
            right,
            text="🖥️ 창 크기 ▾",
            bg="#f1f5f9",
            fg="#1e293b",
            hover_bg="#e2e8f0",
            radius=8,
            height=28,
            font=("Pretendard", 8, "bold"),
            command=self.show_resolution_quick_menu,
            parent_bg="#ffffff"
        )
        self.res_quick_btn.pack(side=tk.LEFT, pady=16, padx=(0, 6))

        sem_text = self.settings.get("semester", "2026년 2학기")
        self.sem_badge_label = tk.Label(right, text=f" 📅 {sem_text} ", font=("Pretendard", 8, "bold"), bg="#f1f5f9", fg="#1e293b", relief=tk.FLAT, padx=6, pady=4)
        self.sem_badge_label.pack(side=tk.LEFT, pady=16, padx=(0, 6))

        api_key = self.settings.get("gemini_api_key", "").strip()
        has_key = len(api_key) >= 10
        api_text = " 🟢 API 연결됨 " if has_key else " 🔴 API 등록 필요 "
        api_fg = "#15803d" if has_key else "#b91c1c"
        api_bg = "#f0fdf4" if has_key else "#fef2f2"
        self.api_badge_label = tk.Label(right, text=api_text, font=("Pretendard", 8, "bold"), bg=api_bg, fg=api_fg, relief=tk.FLAT, padx=8, pady=4, cursor="hand2")
        self.api_badge_label.pack(side=tk.LEFT, pady=16)
        self.api_badge_label.bind("<Button-1>", lambda e: self.switch_to_tab(4))

        # 중앙: 시안 2 플로팅 알약형 세그먼트 탭바 (반응형 콤팩트 크기)
        center = tk.Frame(self.header_frame, bg="#ffffff")
        center.pack(side=tk.LEFT, expand=True)

        pill_wrap = tk.Frame(center, bg="#f1f5f9", padx=3, pady=3)
        pill_wrap.pack()

        self.tab_pills = []
        self.tab_defs = [
            ("🎙️ Studio", 0),
            ("📝 Exam", 1),
            ("💬 Tutor", 2),
            ("📊 Dashboard", 3),
            ("⚙️ Settings", 4),
            ("🛠️ Advanced", 5),
        ]

        for text, idx in self.tab_defs:
            is_active = (idx == 0)
            btn = SquareRoundButton(
                pill_wrap,
                text=text,
                command=lambda i=idx: self.switch_to_tab(i),
                bg="#1c4732" if is_active else "#f1f5f9",
                fg="#ffffff" if is_active else "#475569",
                hover_bg="#265e43" if is_active else "#e2e8f0",
                radius=9,
                height=30,
                font=("Pretendard", 9, "bold"),
                parent_bg="#f1f5f9"
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.tab_pills.append(btn)

    def update_api_status_badge(self):
        """헤더의 API 상태 배지를 현재 설정값에 맞춰 갱신"""
        if not hasattr(self, "api_badge_label"):
            return
        api_key = self.settings.get("gemini_api_key", "").strip()
        has_key = len(api_key) >= 10
        api_text = " 🟢 API 연결됨 " if has_key else " 🔴 API 등록 필요 "
        api_fg = "#15803d" if has_key else "#b91c1c"
        api_bg = "#f0fdf4" if has_key else "#fef2f2"
        self.api_badge_label.config(text=api_text, bg=api_bg, fg=api_fg)


    def switch_to_tab(self, idx):
        try:
            self.notebook.select(idx)
            for i, pill in enumerate(self.tab_pills):
                if i == idx:
                    pill.config(bg="#1c4732", fg="#ffffff", hover_bg="#265e43")
                else:
                    pill.config(bg="#f1f5f9", fg="#475569", hover_bg="#e2e8f0")
            self.on_tab_changed()
        except Exception:
            pass

    def create_tabs(self):
        self.notebook = ttk.Notebook(self.root, style="Hidden.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=(12, 16))

        # 탭 1: 🎙️ 학습노트 생성 스튜디오
        self.tab_studio = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_studio, text=" 학습노트 스튜디오 ")
        self.build_studio_tab()

        # 탭 2: 📝 실전 모의시험 & 공부기간 로드맵
        self.tab_exam = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_exam, text=" 시험 대비 & 로드맵 ")
        self.build_exam_tab()

        # 탭 3: 💬 AI 강의 튜터 (교수님 Q&A)
        self.tab_tutor = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_tutor, text=" 조교 Q&A ")
        self.build_tutor_tab()

        # 탭 4: 📊 주차별 진도 대시보드
        self.tab_dashboard = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_dashboard, text=" 학업 진도 ")
        self.build_dashboard_tab()

        # 탭 5: ⚙️ 과목 및 시스템 설정
        self.tab_settings = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_settings, text=" 설정 ")
        self.build_settings_tab()

        # 탭 6: 🛠️ 고급 도구 (프롬프트 / 보관함 / 법적고지)
        self.tab_advanced = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab_advanced, text=" 고급 도구 ")
        self.build_advanced_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def on_tab_changed(self, event=None):
        self.refresh_course_combos()
        try:
            cur_idx = self.notebook.index(self.notebook.select())
            if hasattr(self, "tab_pills"):
                for i, pill in enumerate(self.tab_pills):
                    if i == cur_idx:
                        pill.config(bg="#1c4732", fg="#ffffff", hover_bg="#265e43")
                    else:
                        pill.config(bg="#f1f5f9", fg="#475569", hover_bg="#e2e8f0")
            current_tab = self.notebook.tab(self.notebook.select(), "text").strip()
            if any(k in current_tab for k in ("진도", "대시보드")) and hasattr(self, "refresh_dashboard"):
                self.refresh_dashboard()
            elif any(k in current_tab for k in ("조교", "튜터", "Q&A")) and hasattr(self, "on_tutor_course_changed"):
                self.on_tutor_course_changed()
        except Exception:
            pass

    def refresh_course_combos(self):
        course_names = [c["course_name"] for c in self.courses if c.get("course_name")]
        for combo_name in ("studio_course_combo", "exam_course_combo", "dash_course_combo", "tutor_course_combo"):
            if hasattr(self, combo_name):
                combo = getattr(self, combo_name)
                combo.config(values=course_names)
                if course_names and (not combo.get() or combo.get() not in course_names):
                    combo.set(course_names[0])
        if hasattr(self, "on_studio_course_changed"):
            self.on_studio_course_changed()
        if hasattr(self, "populate_exam_materials"):
            self.populate_exam_materials()
        if hasattr(self, "on_tutor_course_changed"):
            self.on_tutor_course_changed()

    # =========================================================================
    # 탭 1: 🎙️ 학습노트 생성 스튜디오 (사용자 주도형 3단계 워크플로우)
    # =========================================================================
    # =========================================================================
    # 탭 1: 🎙️ 학습노트 생성 스튜디오 (Apple Clean Light 2.0 감성 룩)
    # =========================================================================
    def build_studio_tab(self):
        # 🌟 Apple Clean Light 2.0: 포근한 캔버스 배경 (#f5f6f8) 위 2열 분할 워크스페이스
        studio_container = tk.Frame(self.tab_studio, bg="#f5f6f8")
        studio_container.pack(fill=tk.BOTH, expand=True)

        studio_container.columnconfigure(0, weight=5, uniform="studio_col")
        studio_container.columnconfigure(1, weight=5, uniform="studio_col")
        studio_container.rowconfigure(0, weight=1)

        # =============================================================
        # [LEFT COLUMN] 넉넉하고 정갈한 Content Setup Card (한눈에 직접 확인)
        # =============================================================
        left_card = tk.Frame(studio_container, bg="#ffffff", bd=0, highlightthickness=1, highlightbackground="#edf2f7")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=8)

        left_content = tk.Frame(left_card, bg="#ffffff", padx=18, pady=14)
        left_content.pack(fill=tk.BOTH, expand=True)

        # -------------------------------------------------------------
        # Step 1: 과목 및 강의 정보 설정
        # -------------------------------------------------------------
        s1_head = tk.Frame(left_content, bg="#ffffff")
        s1_head.pack(fill=tk.X, pady=(0, 10))
        tk.Label(s1_head, text=" 1 ", font=("Pretendard", 9, "bold"), bg="#1c4732", fg="#ffffff", padx=5, pady=2).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(s1_head, text="Step 1. Course Selection (과목 및 수업 정보)", font=("Pretendard", 11, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)
        tk.Label(s1_head, text="2026년 2학기", font=("Pretendard", 8), bg="#ffffff", fg="#94a3b8").pack(side=tk.RIGHT)

        tk.Label(left_content, text="Select Course (수강 과목):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 3))
        self.studio_course_combo = ttk.Combobox(left_content, state="readonly", font=("Pretendard", 10))
        self.studio_course_combo.pack(fill=tk.X, pady=(0, 10))
        self.studio_course_combo.bind("<<ComboboxSelected>>", lambda e: self.on_studio_course_changed())

        # 일자 및 주차 행
        row_dt = tk.Frame(left_content, bg="#ffffff")
        row_dt.pack(fill=tk.X, pady=(0, 8))

        # 일자 선택기
        col_date = tk.Frame(row_dt, bg="#ffffff")
        col_date.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(col_date, text="Class Date (수업 일자):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 2))
        
        d_box = tk.Frame(col_date, bg="#f8fafc", highlightthickness=1, highlightbackground="#cbd5e1", padx=4, pady=2)
        d_box.pack(fill=tk.X)
        self.studio_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.studio_date_entry = tk.Entry(
            d_box,
            textvariable=self.studio_date_var,
            font=("Pretendard", 9),
            bg="#f8fafc",
            fg="#0f172a",
            insertbackground="#1c4732",
            relief=tk.FLAT,
            bd=0,
            takefocus=True
        )
        self.studio_date_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        self.studio_date_entry.bind("<Button-1>", lambda e: self.studio_date_entry.focus_set())
        self.add_context_menu(self.studio_date_entry)

        ttk.Button(d_box, text="◀", width=2, style="Secondary.TButton", command=lambda: self.adjust_studio_date(-1)).pack(side=tk.LEFT, padx=1)
        ttk.Button(d_box, text="오늘", width=4, style="Secondary.TButton", command=lambda: self.studio_date_var.set(datetime.now().strftime("%Y-%m-%d"))).pack(side=tk.LEFT, padx=1)
        ttk.Button(d_box, text="▶", width=2, style="Secondary.TButton", command=lambda: self.adjust_studio_date(1)).pack(side=tk.LEFT, padx=1)

        # 주차 및 차시 선택기
        col_wk = tk.Frame(row_dt, bg="#ffffff")
        col_wk.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(col_wk, text="Week & Session (주차 및 차시):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 2))
        
        default_weeks = []
        for w in range(1, 17):
            default_weeks.append(f"{w}주차 1차시")
            default_weeks.append(f"{w}주차 2차시")
        default_weeks.extend(["🚨 보강 / 특강", "🚫 휴강 정보"])
        
        self.studio_week_combo = ttk.Combobox(col_wk, values=default_weeks, state="normal", font=("Pretendard", 9, "bold"))
        self.studio_week_combo.set("1주차 1차시")
        self.studio_week_combo.pack(fill=tk.X)
        self.studio_week_combo.bind("<<ComboboxSelected>>", lambda e: self.update_preview_paper_header())

        # 수업 파트 선택기 (1부, 2부, 3부)
        col_part = tk.Frame(row_dt, bg="#ffffff")
        col_part.pack(side=tk.RIGHT, fill=tk.X)
        tk.Label(col_part, text="Part (수업 파트):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 2))
        PART_OPTIONS = ["1부 (전반부)", "2부 (후반부)", "3부 (마무리)", "통합 (단일 음성)"]
        self.studio_part_combo = ttk.Combobox(col_part, values=PART_OPTIONS, state="readonly", font=("Pretendard", 9, "bold"), width=12)
        self.studio_part_combo.set(PART_OPTIONS[0])
        self.studio_part_combo.pack(fill=tk.X)
        self.studio_part_combo.bind("<<ComboboxSelected>>", lambda e: self.update_preview_paper_header())

        # 출력 언어 (전체 폭을 활용하여 어떤 해상도에서도 텍스트 잘림 절대 방지)
        row_lang = tk.Frame(left_content, bg="#ffffff")
        row_lang.pack(fill=tk.X, pady=(0, 12))
        tk.Label(row_lang, text="Output Language (생성 출력 언어):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 2))
        self.studio_lang_combo = ttk.Combobox(row_lang, values=LANG_OPTIONS, state="readonly", font=("Pretendard", 9))
        self.studio_lang_combo.set(LANG_OPTIONS[0])
        self.studio_lang_combo.pack(fill=tk.X)

        # 부드러운 구분선
        tk.Frame(left_content, bg="#f1f5f9", height=1).pack(fill=tk.X, pady=(0, 12))

        # -------------------------------------------------------------
        # Step 2: Content Input (강의 음성 및 슬라이드 투입 센터)
        # -------------------------------------------------------------
        self.s2_head = tk.Frame(left_content, bg="#ffffff")
        self.s2_head.pack(fill=tk.X, pady=(0, 10))
        tk.Label(self.s2_head, text=" 2 ", font=("Pretendard", 9, "bold"), bg="#1c4732", fg="#ffffff", padx=5, pady=2).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(self.s2_head, text="Step 2. Content Input (음성 & 슬라이드 투입)", font=("Pretendard", 11, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        self.audio_select_frame = tk.Frame(left_content, bg="#ffffff")
        self.audio_select_frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(self.audio_select_frame, text="Audio Center (수업 실시간 녹음 및 오디오 연동):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 6))

        # 오디오 액션 바: 녹음 버튼 & 찾기 버튼
        audio_btn_row = tk.Frame(self.audio_select_frame, bg="#ffffff")
        audio_btn_row.pack(fill=tk.X, pady=(0, 8))

        self.rec_btn = SquareRoundButton(
            audio_btn_row,
            text="🔴  실시간 마이크 녹음",
            bg="#fef2f2",
            fg="#dc2626",
            hover_bg="#fee2e2",
            active_bg="#fecaca",
            radius=9,
            height=34,
            font=("Pretendard", 9, "bold"),
            command=self.toggle_realtime_recording,
            parent_bg="#ffffff"
        )
        self.rec_btn.pack(side=tk.LEFT, padx=(0, 8))

        SquareRoundButton(
            audio_btn_row,
            text="📂  오디오 파일 찾기...",
            bg="#f1f5f9",
            hover_bg="#e2e8f0",
            fg="#334155",
            radius=9,
            height=34,
            font=("Pretendard", 9, "bold"),
            command=self.browse_studio_audio,
            parent_bg="#ffffff"
        ).pack(side=tk.LEFT)

        # 등록된 오디오 캡슐 칩 컨테이너 (말랑하고 유려한 디자인)
        self.audio_chip_frame = tk.Frame(self.audio_select_frame, bg="#f0fdf4", highlightthickness=1, highlightbackground="#bbf7d0", padx=12, pady=10)
        self.audio_chip_frame.pack(fill=tk.X, pady=(2, 8))

        self.audio_chip_title = tk.Label(self.audio_chip_frame, text="🎙️ 선택된 음성 파일이 없습니다.", font=("Pretendard", 9, "bold"), bg="#f0fdf4", fg="#166534")
        self.audio_chip_title.pack(side=tk.LEFT)

        self.audio_chip_badge = tk.Label(self.audio_chip_frame, text="미연동", font=("Pretendard", 8, "bold"), bg="#dcfce7", fg="#15803d", padx=6, pady=2)
        self.audio_chip_badge.pack(side=tk.RIGHT)

        # 숨겨진 데이터 변수 및 이전 호환용 더미 리스트박스
        self.studio_audio_var = tk.StringVar(value="")
        self.studio_audio_var.trace_add("write", lambda *args: self.update_audio_chip_display())
        self.studio_audio_entry = tk.Entry(self.audio_select_frame, textvariable=self.studio_audio_var)
        self.audio_listbox = tk.Listbox(self.audio_select_frame)  # 호환성 유지

        # 최근 감지된 오디오 빠른 선택 콤보
        recent_row = tk.Frame(self.audio_select_frame, bg="#ffffff")
        recent_row.pack(fill=tk.X, pady=(2, 4))
        tk.Label(recent_row, text="최근 발견된 녹음:", font=("Pretendard", 8, "bold"), bg="#ffffff", fg="#94a3b8").pack(side=tk.LEFT, padx=(0, 6))
        self.detected_audio_combo = ttk.Combobox(recent_row, state="readonly", font=("Pretendard", 8), width=35)
        self.detected_audio_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.detected_audio_combo.bind("<<ComboboxSelected>>", self.on_detected_audio_combo_select)

        # 슬라이드 섹션
        slide_head_row = tk.Frame(left_content, bg="#ffffff")
        slide_head_row.pack(fill=tk.X, pady=(10, 6))
        tk.Label(slide_head_row, text="Lecture Slides (강의 슬라이드 PDF):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(side=tk.LEFT)

        badge_box = tk.Frame(slide_head_row, bg="#ffffff")
        badge_box.pack(side=tk.RIGHT)
        for fmt in ("PDF", "PPTX", "HWPX"):
            tk.Label(badge_box, text=f" {fmt} ", font=("Pretendard", 7, "bold"), bg="#f1f5f9", fg="#64748b").pack(side=tk.LEFT, padx=1)

        # 슬라이드 조작 버튼
        slide_btn_row = tk.Frame(left_content, bg="#ffffff")
        slide_btn_row.pack(fill=tk.X, pady=(0, 8))
        SquareRoundButton(slide_btn_row, text="➕  슬라이드 추가...", bg="#f1f5f9", hover_bg="#e2e8f0", fg="#334155", radius=8, height=30, font=("Pretendard", 9, "bold"), command=self.browse_studio_slides, parent_bg="#ffffff").pack(side=tk.LEFT, padx=(0, 4))
        SquareRoundButton(slide_btn_row, text="📷  칠판 판서...", bg="#f1f5f9", hover_bg="#e2e8f0", fg="#334155", radius=8, height=30, font=("Pretendard", 9, "bold"), command=self.browse_blackboard_photo, parent_bg="#ffffff").pack(side=tk.LEFT, padx=(0, 4))
        SquareRoundButton(slide_btn_row, text="☐ 전체 해제", bg="#fef2f2", hover_bg="#fee2e2", fg="#dc2626", radius=8, height=30, font=("Pretendard", 8, "bold"), command=self.deselect_all_studio_slides, parent_bg="#ffffff").pack(side=tk.RIGHT, padx=(2, 0))
        SquareRoundButton(slide_btn_row, text="☑️ 전체 선택", bg="#f0fdf4", hover_bg="#dcfce7", fg="#166534", radius=8, height=30, font=("Pretendard", 8, "bold"), command=self.select_all_studio_slides, parent_bg="#ffffff").pack(side=tk.RIGHT, padx=(2, 0))
        SquareRoundButton(slide_btn_row, text="🔄 새로고침", bg="#f1f5f9", hover_bg="#e2e8f0", fg="#64748b", radius=8, height=30, font=("Pretendard", 8), command=self.refresh_studio_slides, parent_bg="#ffffff").pack(side=tk.RIGHT, padx=(2, 0))

        # 등록된 슬라이드 카드 칩 컨테이너
        slide_canvas_frame = tk.Frame(left_content, bg="#ffffff")
        slide_canvas_frame.pack(fill=tk.X, pady=(0, 14))

        self.slide_canvas = tk.Canvas(slide_canvas_frame, height=105, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        slide_sb = ttk.Scrollbar(slide_canvas_frame, orient=tk.VERTICAL, command=self.slide_canvas.yview)
        self.slide_inner_frame = tk.Frame(self.slide_canvas, bg="#f8fafc", padx=6, pady=6)
        self.slide_inner_frame.bind("<Configure>", lambda e: self.slide_canvas.configure(scrollregion=self.slide_canvas.bbox("all")))
        self.slide_canvas.create_window((0, 0), window=self.slide_inner_frame, anchor="nw")
        self.slide_canvas.configure(yscrollcommand=slide_sb.set)

        self.slide_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        slide_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.slide_check_vars = {}

        def _on_slide_wheel(e):
            if sys.platform == "darwin":
                self.slide_canvas.yview_scroll(int(-1 * e.delta), "units")
            else:
                self.slide_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            return "break"
        slide_canvas_frame.bind("<Enter>", lambda e: self.slide_canvas.bind_all("<MouseWheel>", _on_slide_wheel))
        slide_canvas_frame.bind("<Leave>", lambda e: self.slide_canvas.unbind_all("<MouseWheel>"))

        # 부드러운 구분선
        tk.Frame(left_content, bg="#f1f5f9", height=1).pack(fill=tk.X, pady=(0, 16))

        # -------------------------------------------------------------
        # Step 3: Process & Refine (분석 모드 설정)
        # -------------------------------------------------------------
        s3_head = tk.Frame(left_content, bg="#ffffff")
        s3_head.pack(fill=tk.X, pady=(0, 6))
        tk.Label(s3_head, text=" 3 ", font=("Pretendard", 9, "bold"), bg="#1c4732", fg="#ffffff", padx=5, pady=2).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(s3_head, text="Step 3. Process & Refine (분석 모드)", font=("Pretendard", 11, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        self.no_audio_var = tk.BooleanVar(value=False)
        self.no_audio_check = ttk.Checkbutton(
            left_content,
            text="☑  음성 녹음 생략 (슬라이드 집중 독학 분석 모드)",
            variable=self.no_audio_var,
            command=self.toggle_no_audio_mode
        )
        self.no_audio_check.pack(anchor=tk.W, pady=(0, 6))

        self.no_audio_hint = tk.Label(
            left_content,
            text="💡 슬라이드 집중 독학 모드가 활성화되었습니다.\n음성 녹음 없이도 공식 슬라이드 내용만을 정밀 파싱하여 체계적인 시험 강의노트를 생성합니다.",
            font=("Pretendard", 8),
            bg="#f0fdf4",
            fg="#166534",
            justify=tk.LEFT,
            padx=10,
            pady=8
        )

        # =============================================================
        # [RIGHT COLUMN] Inspiring Live Study Note Paper & Console
        # =============================================================
        right_card = tk.Frame(studio_container, bg="#ffffff", bd=0, highlightthickness=1, highlightbackground="#edf2f7")
        right_card.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=8)

        # 1. 하단 액션 바: 2열 구조로 배치하여 화면 크기에 따른 버튼 겹침 및 잘림 원천 방지
        action_bar = tk.Frame(right_card, bg="#ffffff", padx=16, pady=8)
        action_bar.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Frame(right_card, bg="#f1f5f9", height=1).pack(side=tk.BOTTOM, fill=tk.X)

        # 액션 상단 행: 시원한 전폭 메인 Generate 버튼
        act_row_top = tk.Frame(action_bar, bg="#ffffff")
        act_row_top.pack(fill=tk.X, pady=(0, 6))

        self.generate_studio_btn = SquareRoundButton(
            act_row_top,
            text="✨  완벽 학습노트 및 출판용 PDF 생성",
            bg="#1c4732",
            hover_bg="#265e43",
            active_bg="#143324",
            radius=9,
            height=38,
            font=("Pretendard", 10, "bold"),
            command=self.execute_studio_generation,
            parent_bg="#ffffff"
        )
        self.generate_studio_btn.pack(fill=tk.X)

        # 액션 하단 행: 보조 유틸리티 버튼들
        act_row_bot = tk.Frame(action_bar, bg="#ffffff")
        act_row_bot.pack(fill=tk.X)

        self.studio_open_pdf_btn = SquareRoundButton(
            act_row_bot,
            text="📄 PDF 열기",
            bg="#2e5944",
            hover_bg="#3a7056",
            active_bg="#224333",
            radius=8,
            height=28,
            state="disabled",
            font=("Pretendard", 8, "bold"),
            command=self.open_last_generated_pdf,
            parent_bg="#ffffff"
        )
        self.studio_open_pdf_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.studio_open_folder_btn = SquareRoundButton(
            act_row_bot,
            text="📂 폴더 열기",
            bg="#f1f5f9",
            hover_bg="#e2e8f0",
            fg="#334155",
            radius=8,
            height=28,
            font=("Pretendard", 8, "bold"),
            command=self.open_studio_notes_folder,
            parent_bg="#ffffff"
        )
        self.studio_open_folder_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.studio_clear_log_btn = SquareRoundButton(
            act_row_bot,
            text="🧹 콘솔 비우기",
            bg="#f1f5f9",
            hover_bg="#e2e8f0",
            fg="#334155",
            radius=8,
            height=28,
            font=("Pretendard", 8, "bold"),
            command=self.clear_studio_log,
            parent_bg="#ffffff"
        )
        self.studio_clear_log_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.studio_stop_btn = SquareRoundButton(
            act_row_bot,
            text="⏹ 작업 중단",
            bg="#dc2626",
            hover_bg="#b91c1c",
            active_bg="#991b1b",
            radius=8,
            height=28,
            state="disabled",
            font=("Pretendard", 8, "bold"),
            command=self.abort_studio_generation,
            parent_bg="#ffffff"
        )
        self.studio_stop_btn.pack(side=tk.RIGHT)

        # 2. 상단: 실물 규격 라이브 프리뷰 헤더 배너
        paper_banner = tk.Frame(right_card, bg="#ffffff")
        paper_banner.pack(fill=tk.X, padx=16, pady=(4, 6))

        b_left = tk.Frame(paper_banner, bg="#ffffff")
        b_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(b_left, text="📖  LIVE STUDY NOTE PREVIEW", font=("Pretendard", 8, "bold"), bg="#dcfce7", fg="#166534", padx=6, pady=2).pack(anchor=tk.W)
        self.preview_title_label = tk.Label(b_left, text="제 1강: 핵심 강의노트 및 시험 족보 프리뷰", font=("Pretendard", 12, "bold"), bg="#ffffff", fg="#0f172a")
        self.preview_title_label.pack(anchor=tk.W, pady=(2, 0))
        tk.Label(b_left, text="교수님 육성 강조 포인트 & 실전 모의시험 10문항 자동 색인", font=("Pretendard", 8), bg="#ffffff", fg="#64748b").pack(anchor=tk.W)

        tk.Label(paper_banner, text="A4 출판 규격", font=("Pretendard", 8, "bold"), bg="#f1f5f9", fg="#475569", padx=8, pady=3).pack(side=tk.RIGHT)

        # 3대 핵심 구조화 프리뷰 카드 스택 (여백 최적화)
        p_stack = tk.Frame(right_card, bg="#ffffff")
        p_stack.pack(fill=tk.X, padx=16, pady=(0, 6))

        # 1. Key Concepts 카드
        card_kc = tk.Frame(p_stack, bg="#f8fafc", highlightthickness=1, highlightbackground="#edf2f7", padx=10, pady=6)
        card_kc.pack(fill=tk.X, pady=(0, 4))
        tk.Label(card_kc, text="📌  핵심 개념 요약 (Key Concepts)", font=("Pretendard", 9, "bold"), bg="#f8fafc", fg="#1c4732").pack(anchor=tk.W)
        tk.Label(card_kc, text="• 데이터 독립성: 논리적 구조 변경 시 응용 프로그램 영향 차단\n• 3단계 스키마 구조: 외부(개별 뷰) ➔ 개념(전체 논리) ➔ 내부(물리 저장)\n• DBMS 필수 특징: 자기 기술성, 동시성 제어(ACID), 무결성 보장", font=("Pretendard", 8), bg="#f8fafc", fg="#334155", justify=tk.LEFT).pack(anchor=tk.W, padx=(10, 0), pady=(1, 0))

        # 2. Exam Tips 카드 (따뜻한 앰버 톤)
        card_tip = tk.Frame(p_stack, bg="#fffbeb", highlightthickness=1, highlightbackground="#fef3c7", padx=10, pady=6)
        card_tip.pack(fill=tk.X, pady=(0, 4))
        tk.Label(card_tip, text="🎯  교수님 육성 시험 팁 (Exam Predictions)", font=("Pretendard", 9, "bold"), bg="#fffbeb", fg="#92400e").pack(anchor=tk.W)
        tk.Label(card_tip, text='• "중간고사 1번 서술형으로 외부 스키마와 개념 스키마의 차이점 출제 예정"\n• "슬라이드 8페이지의 스키마 사상(Mapping) 다이어그램 반드시 암기할 것"', font=("Pretendard", 8, "bold"), bg="#fffbeb", fg="#78350f", justify=tk.LEFT).pack(anchor=tk.W, padx=(10, 0), pady=(1, 0))

        # 3. Practice Questions 카드 (차분한 인디고 톤)
        card_q = tk.Frame(p_stack, bg="#f0f4ff", highlightthickness=1, highlightbackground="#e0e7ff", padx=10, pady=6)
        card_q.pack(fill=tk.X, pady=(0, 4))
        tk.Label(card_q, text="✍️  실전 모의 문제 (Practice Questions)", font=("Pretendard", 9, "bold"), bg="#f0f4ff", fg="#3730a3").pack(anchor=tk.W)
        tk.Label(card_q, text="• Q1. 파일 시스템과 데이터베이스 시스템의 무결성 유지 방식 차이를 서술하시오.\n• Q2. 물리적 데이터 독립성이란 내부 스키마 변경이 (        )에 영향을 미치지 않는 특성이다.", font=("Pretendard", 8), bg="#f0f4ff", fg="#312e81", justify=tk.LEFT).pack(anchor=tk.W, padx=(10, 0), pady=(1, 0))

        # 실시간 진행 상황 및 터미널 콘솔 로그 영역 (하단 여백을 시원하게 채움)
        console_box = tk.Frame(right_card, bg="#ffffff")
        console_box.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 12))

        c_status_row = tk.Frame(console_box, bg="#ffffff")
        c_status_row.pack(fill=tk.X, pady=(0, 4))

        self.studio_progress = ttk.Progressbar(c_status_row, mode="determinate", length=160)
        self.studio_progress.pack(side=tk.LEFT, padx=(0, 8))

        self.studio_status_var = tk.StringVar(value="자료 준비 완료: [학습노트 및 출판용 PDF 생성]을 클릭하세요.")
        tk.Label(c_status_row, textvariable=self.studio_status_var, font=("Pretendard", 8, "bold"), bg="#ffffff", fg="#475569").pack(side=tk.LEFT)

        self.studio_eta_var = tk.StringVar(value="")
        tk.Label(c_status_row, textvariable=self.studio_eta_var, font=("Pretendard", 8, "bold"), bg="#ffffff", fg="#1c4732").pack(side=tk.RIGHT)

        # 터미널 콘솔 로그 창 (fill=tk.BOTH, expand=True로 하단 빈 공간 완벽 활용)
        txt_wrap = tk.Frame(console_box, bg="#ffffff")
        txt_wrap.pack(fill=tk.BOTH, expand=True)

        term_font = ("Menlo", 9) if sys.platform == "darwin" else ("Consolas", 9)
        self.studio_log_text = tk.Text(
            txt_wrap,
            wrap=tk.WORD,
            font=term_font,
            bg="#0f172a",
            fg="#f8fafc",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=8
        )
        sb = ttk.Scrollbar(txt_wrap, orient=tk.VERTICAL, command=self.studio_log_text.yview)
        self.studio_log_text.config(yscrollcommand=sb.set)

        self.studio_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.add_context_menu(self.studio_log_text)

        # 로그 컬러 태그
        self.studio_log_text.tag_config("time", foreground="#94a3b8")
        self.studio_log_text.tag_config("step", foreground="#38bdf8", font=(term_font[0], term_font[1], "bold"))
        self.studio_log_text.tag_config("success", foreground="#4ade80", font=(term_font[0], term_font[1], "bold"))
        self.studio_log_text.tag_config("warning", foreground="#facc15")
        self.studio_log_text.tag_config("error", foreground="#f87171", font=(term_font[0], term_font[1], "bold"))
        self.studio_log_text.tag_config("highlight", foreground="#c084fc")
        self.studio_log_text.tag_config("normal", foreground="#e2e8f0")

        self.append_studio_log("준비 완료: 음성/슬라이드를 선택한 뒤 [학습노트 및 출판용 PDF 생성]을 클릭하세요.", "normal")

    def update_preview_paper_header(self):
        """과목 및 주차 변경 시 우측 페이퍼 제목 실시간 갱신"""
        cname = getattr(self, "studio_course_combo", None) and self.studio_course_combo.get().strip() or "강의"
        wk = getattr(self, "studio_week_combo", None) and self.studio_week_combo.get().strip() or "1주차"
        if hasattr(self, "preview_title_label"):
            self.preview_title_label.config(text=f"제 {wk}: {cname} 핵심 학습노트 및 시험 족보")

    def update_audio_chip_display(self):
        """선택된 오디오 파일에 맞춰 둥근 캡슐 칩 UI 실시간 갱신"""
        if not hasattr(self, "audio_chip_title"):
            return
        fpath = self.studio_audio_var.get().strip()
        if fpath and os.path.exists(fpath):
            fname = os.path.basename(fpath)
            fsize_mb = os.path.getsize(fpath) / (1024 * 1024)
            self.audio_chip_frame.config(bg="#f0fdf4", highlightbackground="#bbf7d0")
            self.audio_chip_title.config(text=f"🎙️  {fname} ({fsize_mb:.1f} MB)", bg="#f0fdf4", fg="#166534")
            self.audio_chip_badge.config(text="✓ 연동 완료", bg="#dcfce7", fg="#15803d")
        elif fpath:
            fname = os.path.basename(fpath)
            self.audio_chip_frame.config(bg="#fefce8", highlightbackground="#fef08a")
            self.audio_chip_title.config(text=f"🎙️  {fname}", bg="#fefce8", fg="#854d0e")
            self.audio_chip_badge.config(text="경로 지정됨", bg="#fef9c3", fg="#a16207")
        else:
            self.audio_chip_frame.config(bg="#f8fafc", highlightbackground="#e2e8f0")
            self.audio_chip_title.config(text="🎙️  선택된 음성 녹음 파일이 없습니다.", bg="#f8fafc", fg="#94a3b8")
            self.audio_chip_badge.config(text="미연동", bg="#f1f5f9", fg="#64748b")

    def on_detected_audio_combo_select(self, event=None):
        sel_idx = self.detected_audio_combo.current()
        if sel_idx >= 0 and hasattr(self, "detected_audio_paths") and sel_idx < len(self.detected_audio_paths):
            full_path = self.detected_audio_paths[sel_idx]
            self.studio_audio_var.set(full_path)
            self.auto_detect_date_from_name(full_path)


    

    def adjust_studio_date(self, days_delta):
        try:
            curr = datetime.strptime(self.studio_date_var.get().strip(), "%Y-%m-%d").date()
        except Exception:
            curr = datetime.now().date()
        new_date = curr + timedelta(days=days_delta)
        self.studio_date_var.set(new_date.strftime("%Y-%m-%d"))

    def toggle_no_audio_mode(self):
        if self.no_audio_var.get():
            self.audio_select_frame.pack_forget()
            if hasattr(self, "no_audio_hint"):
                self.no_audio_hint.pack(after=self.no_audio_check, fill=tk.X, pady=(4, 10))
        else:
            if hasattr(self, "no_audio_hint"):
                self.no_audio_hint.pack_forget()
            if hasattr(self, "s2_head"):
                self.audio_select_frame.pack(after=self.s2_head, fill=tk.X, pady=(0, 14))
            else:
                self.audio_select_frame.pack(fill=tk.X, pady=(0, 14))

    def browse_studio_audio(self):
        fpath = self.ask_open_file_safe(
            title="수업 녹음 파일 선택",
            initialdir=os.path.join(WORKSPACE_DIR, "00_녹음_수신함"),
            filetypes=[("오디오 파일", "*.m4a *.mp3 *.wav *.aac"), ("모든 파일", "*.*")]
        )
        if fpath:
            self.studio_audio_var.set(fpath)
            self.auto_detect_date_from_name(fpath)

    def auto_detect_date_from_name(self, filename):
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(filename))
        if date_match:
            self.studio_date_var.set(date_match.group(1))

    def on_audio_listbox_select(self, event=None):
        sel = self.audio_listbox.curselection()
        if sel:
            full_path = self.detected_audio_paths[sel[0]]
            self.studio_audio_var.set(full_path)
            self.auto_detect_date_from_name(full_path)

    def browse_studio_slides(self):
        cname = self.studio_course_combo.get().strip()
        folder = self.get_course_folder(cname)
        course_dir = config_manager.get_course_dir(folder)
        slides_dir = os.path.join(course_dir, "강의자료")

        fpaths = self.ask_open_files_safe(
            title="강의 슬라이드 및 자료 선택 (PDF, PPTX, HWPX, IPYNB, PY, DOCX, SQL 등)",
            initialdir=slides_dir if os.path.exists(slides_dir) else course_dir,
            filetypes=[
                ("모든 지원 자료", "*.pdf *.pptx *.ppt *.hwpx *.hwp *.ipynb *.py *.sql *.docx"),
                ("PDF 문서", "*.pdf"),
                ("PPT 슬라이드", "*.pptx *.ppt"),
                ("한글 문서", "*.hwpx *.hwp"),
                ("파이썬/주피터", "*.ipynb *.py"),
                ("SQL 쿼리", "*.sql"),
                ("Word 문서", "*.docx"),
                ("모든 파일", "*.*")
            ]
        )
        if fpaths:
            os.makedirs(slides_dir, exist_ok=True)
            for fp in fpaths:
                dest = os.path.join(slides_dir, os.path.basename(fp))
                if os.path.abspath(fp) != os.path.abspath(dest):
                    try:
                        shutil.move(fp, dest)
                    except Exception:
                        try:
                            shutil.copy2(fp, dest)
                            os.remove(fp)
                        except Exception:
                            pass
            self.refresh_studio_slides()

    def get_course_folder(self, cname):
        for c in self.courses:
            if c.get("course_name") == cname:
                return c.get("folder_name", cname)
        return cname

    def on_studio_course_changed(self):
        cname = self.studio_course_combo.get().strip()
        if not cname:
            return
        folder = self.get_course_folder(cname)
        course_dir = config_manager.get_course_dir(folder)

        # 1. 감지된 오디오 파일 목록 갱신
        self.detected_audio_paths = []
        if hasattr(self, "audio_listbox"):
            self.audio_listbox.delete(0, tk.END)

        # 수신함 스캔
        inbox = os.path.join(WORKSPACE_DIR, "00_녹음_수신함")
        if os.path.exists(inbox):
            for ext in ("*.m4a", "*.mp3", "*.wav", "*.aac"):
                for p in sorted(glob.glob(os.path.join(inbox, ext))):
                    self.detected_audio_paths.append(p)
                    if hasattr(self, "audio_listbox"):
                        self.audio_listbox.insert(tk.END, f"[수신함] {os.path.basename(p)}")

        # 과목 음성녹음 폴더 스캔
        rec_dir = os.path.join(course_dir, "음성녹음")
        if os.path.exists(rec_dir):
            for ext in ("*.m4a", "*.mp3", "*.wav", "*.aac"):
                for p in sorted(glob.glob(os.path.join(rec_dir, ext))):
                    self.detected_audio_paths.append(p)
                    if hasattr(self, "audio_listbox"):
                        self.audio_listbox.insert(tk.END, f"[과목보관] {os.path.basename(p)}")

        # 콤보박스 및 오디오 칩 UI 업데이트
        if hasattr(self, "studio_week_combo"):
            cdata = self.get_course_data(cname)
            tot_w = cdata.get("total_weeks", 16)
            w_vals = []
            for w in range(1, tot_w + 1):
                w_vals.append(f"{w}주차 1차시")
                w_vals.append(f"{w}주차 2차시")
            w_vals.extend(["🚨 보강 / 특강", "🚫 휴강 정보"])
            cur_w = self.studio_week_combo.get()
            self.studio_week_combo["values"] = w_vals
            if not cur_w or (cur_w not in w_vals and not any(k in cur_w for k in ("주차", "Ch", "강", "회차", "차시"))):
                self.studio_week_combo.set(w_vals[0] if w_vals else "1주차 1차시")

        if hasattr(self, "detected_audio_combo"):
            combo_vals = []
            for p in self.detected_audio_paths:
                tag = "수신함" if inbox in p else "과목보관"
                combo_vals.append(f"[{tag}] {os.path.basename(p)}")
            self.detected_audio_combo["values"] = combo_vals
            if combo_vals:
                self.detected_audio_combo.set(combo_vals[0])
                self.studio_audio_var.set(self.detected_audio_paths[0])
                self.auto_detect_date_from_name(self.detected_audio_paths[0])
            else:
                self.detected_audio_combo.set("감지된 음성 파일 없음")
                self.studio_audio_var.set("")

        self.update_audio_chip_display()
        self.update_preview_paper_header()

        # 2. 슬라이드 목록 갱신
        self.refresh_studio_slides()

    def select_all_studio_slides(self):
        """스튜디오 강의 슬라이드 전체 선택"""
        for var in self.slide_check_vars.values():
            var.set(True)

    def deselect_all_studio_slides(self):
        """스튜디오 강의 슬라이드 전체 선택 해제"""
        for var in self.slide_check_vars.values():
            var.set(False)

    def refresh_studio_slides(self):
        for widget in self.slide_inner_frame.winfo_children():
            widget.destroy()
        self.slide_check_vars.clear()

        cname = self.studio_course_combo.get().strip()
        if not cname:
            return
        folder = self.get_course_folder(cname)
        course_dir = config_manager.get_course_dir(folder)

        search_dirs = [os.path.join(course_dir, "강의자료"), course_dir]
        SUPPORTED_EXTS = (".pdf", ".pptx", ".ppt", ".hwpx", ".hwp", ".ipynb", ".py", ".sql", ".docx")
        found_files = []
        for sdir in search_dirs:
            if os.path.exists(sdir):
                for fname in sorted(os.listdir(sdir)):
                    fpath = os.path.join(sdir, fname)
                    if not os.path.isfile(fpath):
                        continue
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in SUPPORTED_EXTS:
                        lower = fname.lower()
                        if "syllabus" in lower or "강의계획서" in lower:
                            continue
                        if fpath not in found_files:
                            found_files.append(fpath)

        if not found_files:
            empty_lbl = tk.Label(
                self.slide_inner_frame,
                text="📂 등록된 강의 슬라이드/자료가 없습니다.\n'➕ 슬라이드 추가'를 클릭하여 PDF, PPTX, IPYNB, PY 등 자료를 등록하세요.",
                font=("Pretendard", 9),
                bg="#f8fafc",
                fg="#94a3b8",
                justify=tk.LEFT,
                pady=10,
                padx=6
            )
            empty_lbl.pack(anchor=tk.W, fill=tk.X)
            return

        EXT_ICONS = {
            ".pdf": ("📄", "PDF"),
            ".pptx": ("📊", "PPTX"),
            ".ppt": ("📊", "PPT"),
            ".hwpx": ("📝", "HWPX"),
            ".hwp": ("📝", "HWP"),
            ".ipynb": ("📓", "IPYNB"),
            ".py": ("🐍", "PY"),
            ".sql": ("🗄️", "SQL"),
            ".docx": ("📘", "DOCX")
        }

        for file_path in found_files:
            fname = os.path.basename(file_path)
            ext = os.path.splitext(fname)[1].lower()
            icon, tag = EXT_ICONS.get(ext, ("📁", ext[1:].upper()))

            var = tk.BooleanVar(value=True)
            self.slide_check_vars[file_path] = var

            # 부드러운 카드 타일 UI
            card = tk.Frame(self.slide_inner_frame, bg="#ffffff", highlightthickness=1, highlightbackground="#e2e8f0", padx=8, pady=6)
            card.pack(fill=tk.X, expand=True, pady=3)

            chk = ttk.Checkbutton(card, text=f" {icon} [{tag}]  {fname}", variable=var, style="Card.TCheckbutton")
            chk.pack(side=tk.LEFT, fill=tk.X, expand=True)

            badge = tk.Label(card, text="✓ 포함", font=("Pretendard", 8, "bold"), bg="#eff6ff", fg="#2563eb", padx=6, pady=1)
            badge.pack(side=tk.RIGHT)

            def make_toggle_cb(b=badge, v=var):
                def on_toggle(*_):
                    if v.get():
                        b.config(text="✓ 포함", bg="#eff6ff", fg="#2563eb")
                    else:
                        b.config(text="제외됨", bg="#f1f5f9", fg="#94a3b8")
                return on_toggle
            var.trace_add("write", make_toggle_cb())

    def execute_studio_generation(self):
        cname = self.studio_course_combo.get().strip()
        if not cname:
            messagebox.showwarning("선택 필요", "대상 과목을 선택해주세요.")
            return

        is_no_audio = self.no_audio_var.get()
        audio_path = None if is_no_audio else self.studio_audio_var.get().strip()

        if not is_no_audio and (not audio_path or not os.path.exists(audio_path)):
            messagebox.showwarning("음성 파일 확인", "올바른 음성 파일을 선택하거나, 음성이 없는 경우\n'☑ 음성 녹음 없음' 체크박스를 선택해 주세요.")
            return

        selected_slides = [p for p, v in self.slide_check_vars.items() if v.get()]
        date_str = self.studio_date_var.get().strip()
        week_str = self.studio_week_combo.get().replace("주차", "").strip()
        lang_mode = LANG_LABEL_TO_CODE.get(self.studio_lang_combo.get(), "both")

        # UI 상태 변경
        self.studio_cancel_requested = False
        self.generate_studio_btn.config(state=tk.DISABLED)
        self.studio_stop_btn.config(state=tk.NORMAL)
        self.studio_open_pdf_btn.config(state=tk.DISABLED)
        self.studio_progress["value"] = 5
        self.studio_status_var.set("🚀 Gemini AI 분석 및 학습노트 생성 준비 중...")
        if audio_path:
            self.studio_current_eta = 110 if lang_mode == "both" else 65
        else:
            self.studio_current_eta = 50 if lang_mode == "both" else 30
        self.studio_start_time = time.time()
        self.studio_is_running = True
        self.studio_eta_var.set("⏱️ 경과: 00:00 | 남은 시간: 계산 중...")
        self.update_studio_timer()

        self.studio_log_text.config(state=tk.NORMAL)
        self.studio_log_text.delete("1.0", tk.END)
        self.studio_log_text.config(state=tk.DISABLED)
        self.append_studio_log(f"🚀 [{cname}] 맞춤형 학습노트 생성 파이프라인 가동", "step")

        def worker():
            try:
                import importlib
                import process_all_lectures
                try:
                    process_all_lectures = importlib.reload(process_all_lectures)
                except Exception:
                    pass

                def log_cb(msg, step=None, eta=None):
                    self.root.after(0, lambda: self.on_studio_log_event(msg, step, eta))

                result = process_all_lectures.generate_custom_lecture_note(
                    cname=cname,
                    audio_path=audio_path,
                    slide_paths=selected_slides,
                    date_str=date_str,
                    week_num=week_str,
                    lang_mode=lang_mode,
                    log_callback=log_cb,
                    cancel_check=lambda: self.studio_cancel_requested
                )
                self.root.after(0, lambda: self.on_studio_generation_success(result))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self.on_studio_generation_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_studio_log_event(self, msg, step=None, eta=None):
        if step is not None:
            step_progress = {1: 20, 2: 55, 3: 80, 4: 95, 5: 100}
            self.studio_progress["value"] = step_progress.get(step, self.studio_progress["value"])
        else:
            # 키워드 기반 프로그레스 바 자동 전진
            if any(k in msg for k in ["시작", "준비", "가동", "업로드"]):
                self.studio_progress["value"] = max(self.studio_progress["value"], 15)
            elif any(k in msg for k in ["전송", "클라우드", "음성", "슬라이드"]):
                self.studio_progress["value"] = max(self.studio_progress["value"], 30)
            elif any(k in msg for k in ["Gemini", "AI", "작성 중", "분석", "생성 시작"]):
                self.studio_progress["value"] = max(self.studio_progress["value"], 60)
            elif any(k in msg for k in ["도표", "추출", "임베드", "마크다운"]):
                self.studio_progress["value"] = max(self.studio_progress["value"], 80)
            elif any(k in msg for k in ["PDF", "컴파일", "렌더링"]):
                self.studio_progress["value"] = max(self.studio_progress["value"], 90)
            elif any(k in msg for k in ["완료", "성공", "축하"]):
                self.studio_progress["value"] = 100

        if eta is not None:
            self.studio_current_eta = eta

        self.append_studio_log(msg)

        clean_msg = msg.strip().replace("\n", " ")
        if len(clean_msg) > 55:
            clean_msg = clean_msg[:52] + "..."
        self.studio_status_var.set(clean_msg)

    def update_studio_timer(self):
        if not getattr(self, "studio_is_running", False):
            return

        elapsed = int(time.time() - getattr(self, "studio_start_time", time.time()))
        el_min = elapsed // 60
        el_sec = elapsed % 60

        if hasattr(self, "studio_current_eta") and self.studio_current_eta > 0:
            self.studio_current_eta = max(1, self.studio_current_eta - 1)
            eta_str = f"약 {self.studio_current_eta}초"
        elif hasattr(self, "studio_current_eta") and self.studio_current_eta == 0:
            eta_str = "마무리 조판 중..."
        else:
            eta_str = "진행 중..."

        self.studio_eta_var.set(f"⏱️ 경과: {el_min:02d}:{el_sec:02d} | 남은 시간: {eta_str}")

        if getattr(self, "studio_is_running", False):
            self.root.after(1000, self.update_studio_timer)

    def abort_studio_generation(self):
        """진행 중인 백그라운드 AI 생성 작업을 즉시 강제 종료(Kill)하고 UI를 복원"""
        if not self.studio_is_running:
            return
        self.studio_cancel_requested = True
        self.studio_is_running = False
        self.studio_progress["value"] = 0
        self.studio_status_var.set("🛑 사용자에 의해 작업이 강제 중단되었습니다.")
        self.studio_eta_var.set("🛑 작업 중단됨 (Kill)")
        self.generate_studio_btn.config(state=tk.NORMAL)
        self.studio_stop_btn.config(state=tk.DISABLED)

        self.append_studio_log("=" * 55, "error")
        self.append_studio_log("🛑 [작업 즉시 중단] 사용자가 생성을 강제 취소하였습니다.", "error")
        self.append_studio_log("   작업 스레드를 종료하고 모든 버튼 상태를 정상으로 복구했습니다.", "highlight")
        self.append_studio_log("   앱을 재시작할 필요 없이 설정을 변경하여 즉시 다시 생성할 수 있습니다.", "step")
        messagebox.showwarning("작업 중단", "학습노트 생성이 즉시 중단되었습니다.\n\n앱을 껐다 켤 필요 없이 옵션을 변경하여 다시 실행할 수 있습니다.")

    def append_studio_log(self, text, tag="normal"):
        if not hasattr(self, "studio_log_text"):
            return
        self.studio_log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("[%H:%M:%S] ")
        self.studio_log_text.insert(tk.END, timestamp, "time")

        if tag == "normal":
            if any(k in text for k in ["시작", "가동", "Step", "단계"]):
                tag = "step"
            elif any(k in text for k in ["✅", "성공", "🎉", "완료", "완성"]):
                tag = "success"
            elif any(k in text for k in ["⚠️", "주의", "경고"]):
                tag = "warning"
            elif any(k in text for k in ["❌", "오류", "실패"]):
                tag = "error"
            elif any(k in text for k in ["•", "📌", "📄", "📂", "🤖", "🖨️", "🎯", "⚡"]):
                tag = "highlight"

        self.studio_log_text.insert(tk.END, text + "\n", tag)
        self.studio_log_text.see(tk.END)

    def clear_studio_log(self):
        """실시간 콘솔 로그 화면 비우기"""
        self.studio_log_text.config(state=tk.NORMAL)
        self.studio_log_text.delete("1.0", tk.END)
        self.studio_log_text.config(state=tk.DISABLED)
        self.studio_status_var.set("콘솔 로그가 초기화되었습니다.")

    def on_studio_generation_success(self, result):
        self.studio_is_running = False
        self.studio_progress["value"] = 100
        self.generate_studio_btn.config(state=tk.NORMAL)
        self.studio_stop_btn.config(state=tk.DISABLED)
        elapsed = int(time.time() - self.studio_start_time)
        self.studio_eta_var.set(f"⏱️ 총 소요 시간: {elapsed // 60:02d}:{elapsed % 60:02d} (완료)")
        self.studio_status_var.set("✅ 학습노트 생성이 성공적으로 완료되었습니다!")

        self.append_studio_log("=" * 55, "step")
        self.append_studio_log(f"🎉 [{result.get('course_name')}] 학습노트 생성이 완벽하게 완료되었습니다! (총 {elapsed}초)", "success")

        pdfs = result.get("pdf_files", [])
        mds = result.get("markdown_files", [])
        notes_dir = result.get("notes_dir", "")

        if pdfs:
            self.last_generated_pdf = pdfs[-1]
            self.studio_open_pdf_btn.config(state=tk.NORMAL)
            for pdf_path in pdfs:
                self.append_studio_log(f"  📑 출판용 PDF 문서: {os.path.basename(pdf_path)}", "highlight")
        elif mds:
            self.last_generated_pdf = mds[0]
            self.studio_open_pdf_btn.config(state=tk.NORMAL)

        if mds:
            for md_path in mds:
                self.append_studio_log(f"  📄 마크다운 강의노트: {os.path.basename(md_path)}", "highlight")

        if notes_dir:
            self.append_studio_log(f"  📂 저장 폴더: {notes_dir}", "step")

        view_now = messagebox.askyesno(
            "🎉 학습노트 완성",
            f"[{result.get('course_name')}] 학습노트 생성이 성공적으로 완료되었습니다!\n\n• 저장 위치: {notes_dir or '강의노트 폴더'}\n• 총 소요 시간: {elapsed}초\n\n생성된 파일이 있는 폴더를 지금 바로 여시겠습니까?",
            parent=self.root
        )
        if view_now:
            if notes_dir and os.path.exists(notes_dir):
                if sys.platform == "darwin":
                    subprocess.call(["open", notes_dir])
                elif sys.platform == "win32":
                    os.startfile(notes_dir)
            elif hasattr(self, "last_generated_pdf") and self.last_generated_pdf:
                self.open_last_generated_pdf()
        config_manager.send_system_notification(
            title="🎙️ 맞춤 강의노트 완성",
            message=f"[{result.get('course_name')}] 학습노트 제작 완료! (총 {elapsed}초)"
        )

    def on_studio_generation_error(self, err_msg):
        self.studio_is_running = False
        self.studio_progress["value"] = 0
        self.generate_studio_btn.config(state=tk.NORMAL)
        self.studio_stop_btn.config(state=tk.DISABLED)
        self.studio_status_var.set(f"❌ 오류 발생: {err_msg}")
        self.studio_eta_var.set("⚠️ 작업 중단됨")
        self.append_studio_log(f"❌ 오류가 발생하여 작업이 중단되었습니다: {err_msg}", "error")
        messagebox.showerror("오류", f"학습노트 생성 중 문제가 발생했습니다:\n\n{err_msg}")

    def open_last_generated_pdf(self):
        if hasattr(self, "last_generated_pdf") and self.last_generated_pdf and os.path.exists(self.last_generated_pdf):
            if self.last_generated_pdf.endswith(".pdf"):
                self.open_pdf_viewer(self.last_generated_pdf, title=f"학습노트 — {os.path.basename(self.last_generated_pdf)}")
            else:
                if sys.platform == "darwin":
                    subprocess.call(["open", self.last_generated_pdf])
                else:
                    self.open_studio_notes_folder()
        else:
            self.open_studio_notes_folder()

    def open_studio_notes_folder(self):
        cname = self.studio_course_combo.get().strip()
        folder = self.get_course_folder(cname)
        course_dir = config_manager.get_course_dir(folder)
        notes_dir = os.path.join(course_dir, "강의노트")
        os.makedirs(notes_dir, exist_ok=True)

        if sys.platform == "darwin":
            subprocess.call(["open", notes_dir])
        elif sys.platform == "win32":
            os.startfile(notes_dir)
        else:
            subprocess.call(["xdg-open", notes_dir])

    # =========================================================================
    # 탭 2: 📝 실전 모의시험 & 공부 기간 로드맵 (사용자 선택형)
    # =========================================================================
    def build_exam_tab(self):
        frame = ttk.LabelFrame(self.tab_exam, text=" 📝 실전 모의시험 생성 & D-Day 맞춤 로드맵 ", padding="12")
        frame.pack(fill=tk.BOTH, expand=True)

        form = ttk.Frame(frame)
        form.pack(fill=tk.X, pady=(0, 10))

        # Row 1
        r1 = ttk.Frame(form)
        r1.pack(fill=tk.X, pady=4)
        ttk.Label(r1, text="대상 과목:", width=11, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.exam_course_combo = ttk.Combobox(r1, state="readonly", width=18)
        self.exam_course_combo.pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(r1, text="공부 기간 (D-Day):", width=14, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.period_combo = ttk.Combobox(r1, values=PERIOD_OPTIONS, state="readonly", width=20)
        self.period_combo.set(PERIOD_OPTIONS[2])
        self.period_combo.pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(r1, text="시험 종류:", width=9, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.exam_type_combo = ttk.Combobox(r1, values=["중간고사", "기말고사", "주차별 퀴즈"], state="readonly", width=12)
        self.exam_type_combo.set("중간고사")
        self.exam_type_combo.pack(side=tk.LEFT)

        # Row 2 (모호한 출제범위 텍스트창 제거 -> 문항 수 직접 입력 + 문제유형 + 공부시간 배치)
        self.exam_scope_var = tk.StringVar(value="선택한 학습자료 기반")

        r2 = ttk.Frame(form)
        r2.pack(fill=tk.X, pady=4)

        ttk.Label(r2, text="문항 수:", width=11, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.q_count_combo = ttk.Combobox(r2, values=["5", "10", "15", "20", "25", "30"], state="normal", width=8)
        self.q_count_combo.set("10")
        self.q_count_combo.pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(r2, text="문제 유형:", width=14, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.q_format_combo = ttk.Combobox(r2, values=["객관식 (4지선다)", "서술형/손풀이", "객관식 + 서술형 혼합"], state="readonly", width=20)
        self.q_format_combo.set("객관식 (4지선다)")
        self.q_format_combo.pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(r2, text="일일 공부 시간:", width=11, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.exam_hours_var = tk.StringVar(value="3시간")
        self.exam_hours_entry = tk.Entry(
            r2,
            textvariable=self.exam_hours_var,
            width=10,
            font=("Pretendard", 10),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#1c4732",
            selectbackground="#d8f3dc",
            selectforeground="#14281e",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            takefocus=True
        )
        self.exam_hours_entry.pack(side=tk.LEFT)
        self.exam_hours_entry.bind("<Button-1>", lambda e: self.exam_hours_entry.focus_set())
        self.add_context_menu(self.exam_hours_entry)

        # Row 4: 출제 범위에 포함할 학습자료 및 주차별 학습노트 다중 선택 영역
        mat_frame = ttk.LabelFrame(form, text=" 📂 출제 범위에 포함할 학습자료 및 주차별 학습노트 다중 선택 (복수 선택 지원) ", padding="6")
        mat_frame.pack(fill=tk.X, pady=(6, 4))

        mat_ctrl = ttk.Frame(mat_frame)
        mat_ctrl.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(mat_ctrl, text="📌 출제 범위 포함 학습자료 선택:", font=("Pretendard", 9, "bold")).pack(side=tk.LEFT)
        ttk.Button(mat_ctrl, text="📚 마스터 바이블", style="Secondary.TButton", command=self.run_master_bible_generation).pack(side=tk.RIGHT, padx=(3, 0))
        ttk.Button(mat_ctrl, text="✅ 전범위 선택", style="Secondary.TButton", command=self.select_all_exam_materials).pack(side=tk.RIGHT, padx=(3, 0))
        ttk.Button(mat_ctrl, text="❌ 전체 해제", style="Secondary.TButton", command=self.clear_all_exam_materials).pack(side=tk.RIGHT, padx=(3, 0))
        ttk.Button(mat_ctrl, text="➕ 자료 추가", style="Secondary.TButton", command=self.add_custom_exam_material).pack(side=tk.RIGHT, padx=(3, 0))

        # 스크롤 가능한 체크박스 캔버스 (높이 85로 여백 최적화)
        canvas_wrap = ttk.Frame(mat_frame)
        canvas_wrap.pack(fill=tk.X)

        self.exam_mat_canvas = tk.Canvas(canvas_wrap, height=85, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1")
        mat_sb = ttk.Scrollbar(canvas_wrap, orient=tk.VERTICAL, command=self.exam_mat_canvas.yview)
        self.exam_mat_inner = ttk.Frame(self.exam_mat_canvas)
        self.exam_mat_inner.bind("<Configure>", lambda e: self.exam_mat_canvas.configure(scrollregion=self.exam_mat_canvas.bbox("all")))
        self.exam_mat_canvas.create_window((0, 0), window=self.exam_mat_inner, anchor="nw")
        self.exam_mat_canvas.configure(yscrollcommand=mat_sb.set)

        self.exam_mat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        mat_sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.exam_course_combo.bind("<<ComboboxSelected>>", lambda e: self.populate_exam_materials())

        btn_bar = ttk.Frame(form)
        btn_bar.pack(fill=tk.X, pady=(8, 0))

        SquareRoundButton(btn_bar, text="📅 학습 로드맵 생성", bg="#1c4732", hover_bg="#265e43", radius=8, height=34, font=("Pretendard", 9, "bold"), command=self.generate_period_roadmap_action).pack(side=tk.LEFT, padx=(0, 6))
        SquareRoundButton(btn_bar, text="📝 모의시험 PDF", bg="#205c3b", hover_bg="#2a774d", radius=8, height=34, font=("Pretendard", 9, "bold"), command=self.generate_mock_exam_now_action).pack(side=tk.LEFT, padx=(0, 6))
        SquareRoundButton(btn_bar, text="✍️ 답안 채점", bg="#285943", hover_bg="#357357", radius=8, height=34, font=("Pretendard", 9, "bold"), command=self.open_grading_dialog_action).pack(side=tk.LEFT, padx=(0, 6))
        SquareRoundButton(btn_bar, text="⚡ 치트시트 생성", bg="#3a6652", hover_bg="#4a8067", radius=8, height=34, font=("Pretendard", 9, "bold"), command=self.generate_cheatsheet_action).pack(side=tk.LEFT, padx=(0, 6))
        SquareRoundButton(btn_bar, text="📂 문제 폴더", bg="#e2e8f0", hover_bg="#cbd5e1", fg="#14281e", radius=8, height=34, font=("Pretendard", 9, "bold"), command=self.open_exam_folder_action).pack(side=tk.LEFT, padx=(0, 6))
        self.exam_open_pdf_btn = SquareRoundButton(btn_bar, text="📄 시험지 열기", bg="#e2e8f0", hover_bg="#cbd5e1", fg="#14281e", radius=8, height=34, state="disabled", font=("Pretendard", 9, "bold"), command=self.open_last_exam_pdf)
        self.exam_open_pdf_btn.pack(side=tk.LEFT)

        # 실시간 진행 상황 및 로그 콘솔 프레임 (ETA & Progress Bar)
        exam_log_frame = ttk.LabelFrame(frame, text=" 💻 모의시험 & 로드맵 실시간 진행 로그 및 소요 시간 (Live Logs & ETA) ", padding="6")
        exam_log_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        status_row = ttk.Frame(exam_log_frame)
        status_row.pack(fill=tk.X, pady=(2, 6))

        self.exam_progress = ttk.Progressbar(status_row, mode="determinate", length=220)
        self.exam_progress.pack(side=tk.LEFT, padx=(0, 10))

        self.exam_status_var = tk.StringVar(value="과목 및 범위를 선택하고 위의 생성 버튼을 클릭하세요.")
        ttk.Label(status_row, textvariable=self.exam_status_var, font=("Pretendard", 9, "bold"), foreground="#475569").pack(side=tk.LEFT)

        self.exam_eta_var = tk.StringVar(value="")
        ttk.Label(status_row, textvariable=self.exam_eta_var, font=("Pretendard", 9, "bold"), foreground="#2563eb").pack(side=tk.RIGHT)

        ttk.Button(status_row, text="🗑️ 콘솔 지우기", style="Secondary.TButton", command=self.clear_exam_log).pack(side=tk.RIGHT, padx=(0, 8))

        txt_wrap = ttk.Frame(exam_log_frame)
        txt_wrap.pack(fill=tk.BOTH, expand=True)

        term_font = ("Menlo", 9) if sys.platform == "darwin" else ("Consolas", 9)
        self.exam_log_text = tk.Text(
            txt_wrap,
            wrap=tk.WORD,
            font=term_font,
            bg="#0f172a",
            fg="#f8fafc",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=8
        )
        txt_sb = ttk.Scrollbar(txt_wrap, orient=tk.VERTICAL, command=self.exam_log_text.yview)
        self.exam_log_text.config(yscrollcommand=txt_sb.set)

        self.exam_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        txt_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.add_context_menu(self.exam_log_text)

        # 로그 컬러 태그
        self.exam_log_text.tag_config("time", foreground="#94a3b8")
        self.exam_log_text.tag_config("step", foreground="#38bdf8", font=(term_font[0], term_font[1], "bold"))
        self.exam_log_text.tag_config("success", foreground="#4ade80", font=(term_font[0], term_font[1], "bold"))
        self.exam_log_text.tag_config("warning", foreground="#facc15")
        self.exam_log_text.tag_config("error", foreground="#f87171", font=(term_font[0], term_font[1], "bold"))
        self.exam_log_text.tag_config("highlight", foreground="#c084fc")
        self.exam_log_text.tag_config("normal", foreground="#e2e8f0")

        # 기존 코드 호환용 숨김 Text 위젯 및 콘텐츠 캐시
        self.exam_preview_text = tk.Text(self.root)
        self.last_exam_content = ""

        self.append_exam_log("준비 완료: 과목과 출제 범위를 설정하고 [모의시험 생성] 또는 [학습 로드맵 생성]을 클릭하세요.", "normal")

    def populate_exam_materials(self):
        """선택된 과목의 주차별 마크다운 학습노트, PDF 강의노트, 슬라이드 자료들을 동적 스캔하여 체크박스 배치"""
        if not hasattr(self, "exam_mat_inner"):
            return
        for w in self.exam_mat_inner.winfo_children():
            w.destroy()
        self.exam_material_vars = {}

        cname = self.exam_course_combo.get().strip()
        if not cname:
            ttk.Label(self.exam_mat_inner, text="과목을 선택하시면 주차별 강의노트 및 자료 목록이 표시됩니다.", style="Muted.TLabel").pack(anchor=tk.W, padx=8, pady=6)
            return

        folder = self.get_course_folder(cname)
        cdir = config_manager.get_course_dir(folder)

        found_items = [] # list of (display_label, full_path)

        # 1. .markdown_cache 내 주차별 마크다운 노트
        cache_dir = os.path.join(config_manager.WORKSPACE_DIR, ".markdown_cache", folder)
        if not os.path.exists(cache_dir):
            cache_dir = os.path.join(config_manager.WORKSPACE_DIR, ".markdown_cache", cname)
        if os.path.exists(cache_dir):
            for mdf in sorted(glob.glob(os.path.join(cache_dir, "*.md"))):
                fname = os.path.basename(mdf)
                found_items.append((f"📘 [학습노트 MD] {fname}", mdf))

        # 2. 강의노트/ 내 주차별 PDF
        notes_dir = os.path.join(cdir, "강의노트")
        if os.path.exists(notes_dir):
            for pdf in sorted(glob.glob(os.path.join(notes_dir, "**", "*.pdf"), recursive=True)):
                fname = os.path.basename(pdf)
                found_items.append((f"📄 [출판용 PDF] {fname}", pdf))

        # 3. 강의자료/ 및 교재/ 내 슬라이드 PDF
        for sub in ("강의자료", "교재", "슬라이드", "자료"):
            sdir = os.path.join(cdir, sub)
            if os.path.exists(sdir):
                for f in sorted(glob.glob(os.path.join(sdir, "**", "*.pdf"), recursive=True)):
                    fname = os.path.basename(f)
                    found_items.append((f"📑 [슬라이드/교재] {fname}", f))

        if not found_items:
            ttk.Label(self.exam_mat_inner, text="해당 과목 폴더에 등록된 강의노트나 슬라이드가 없습니다. [➕ 외부 자료 추가]를 이용해 직접 선택할 수 있습니다.", style="Muted.TLabel").pack(anchor=tk.W, padx=8, pady=6)
            return

        # 중복 경로 제거
        seen_paths = set()
        for label, fpath in found_items:
            if fpath in seen_paths:
                continue
            seen_paths.add(fpath)
            # 사용자가 원하는 주차만 쉽게 체크할 수 있도록 기본 선택 해제(value=False)로 설정
            var = tk.BooleanVar(value=False)
            self.exam_material_vars[fpath] = var
            chk = ttk.Checkbutton(
                self.exam_mat_inner,
                text=f"{label} ({os.path.basename(fpath)})",
                variable=var,
                command=self.on_exam_material_toggled
            )
            chk.pack(anchor=tk.W, padx=6, pady=2)

        self.on_exam_material_toggled()

    def on_exam_material_toggled(self):
        """체크박스 변경 시 '출제 범위' 입력창 텍스트 자동 동기화"""
        selected = [p for p, v in self.exam_material_vars.items() if v.get()]
        if not selected:
            self.exam_scope_var.set("학습 자료 선택 대기 중 ([✅ 전범위 선택] 또는 개별 클릭)")
            return

        weeks = set()
        for p in selected:
            m = re.search(r"(\d+)주차|[Ww]eek\s*(\d+)", os.path.basename(p))
            if m:
                w_num = m.group(1) or m.group(2)
                weeks.add(f"{w_num}주차")

        if weeks:
            try:
                sorted_weeks = sorted(list(weeks), key=lambda x: int(re.search(r"\d+", x).group()))
                week_str = ", ".join(sorted_weeks)
                self.exam_scope_var.set(f"{week_str} (선택 자료 {len(selected)}건 반영)")
            except Exception:
                self.exam_scope_var.set(f"선택 자료 {len(selected)}건 범위")
        else:
            self.exam_scope_var.set(f"선택한 학습 자료 {len(selected)}건 범위")

    def select_all_exam_materials(self):
        for v in self.exam_material_vars.values():
            v.set(True)
        self.on_exam_material_toggled()

    def clear_all_exam_materials(self):
        for v in self.exam_material_vars.values():
            v.set(False)
        self.exam_scope_var.set("사용자 직접 지정 범위")

    def add_custom_exam_material(self):
        fpaths = self.ask_open_files_safe(
            title="출제 범위에 추가할 학습 자료 (마크다운 또는 PDF) 선택",
            filetypes=[("학습 자료", "*.md *.pdf *.txt"), ("모든 파일", "*.*")]
        )
        if not fpaths:
            return
        for fpath in fpaths:
            if fpath not in self.exam_material_vars:
                var = tk.BooleanVar(value=True)
                self.exam_material_vars[fpath] = var
                fname = os.path.basename(fpath)
                chk = ttk.Checkbutton(
                    self.exam_mat_inner,
                    text=f"📂 [추가자료] {fname}",
                    variable=var,
                    command=self.on_exam_material_toggled
                )
                chk.pack(anchor=tk.W, padx=6, pady=2)
        self.on_exam_material_toggled()

    def append_exam_log(self, text, tag="normal"):
        if not hasattr(self, "exam_log_text"):
            return
        self.exam_log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("[%H:%M:%S] ")
        self.exam_log_text.insert(tk.END, timestamp, "time")

        if tag == "normal":
            if any(k in text for k in ["시작", "가동", "Step", "단계"]):
                tag = "step"
            elif any(k in text for k in ["✅", "성공", "🎉", "완료", "완성"]):
                tag = "success"
            elif any(k in text for k in ["⚠️", "주의", "경고"]):
                tag = "warning"
            elif any(k in text for k in ["❌", "오류", "실패"]):
                tag = "error"
            elif any(k in text for k in ["•", "📌", "📄", "📂", "🤖", "🖨️", "🎯", "⚡"]):
                tag = "highlight"

        self.exam_log_text.insert(tk.END, f"{text}\n", tag)
        self.exam_log_text.see(tk.END)
        self.exam_log_text.config(state=tk.DISABLED)

    def on_exam_log_event(self, msg, step=None, eta=None):
        if step is not None:
            step_progress = {1: 25, 2: 50, 3: 75, 4: 95, 5: 100}
            self.exam_progress["value"] = step_progress.get(step, self.exam_progress["value"])
        else:
            # 키워드 기반 프로그레스 바 자동 전진
            if any(k in msg for k in ["시작", "준비", "가동"]):
                self.exam_progress["value"] = max(self.exam_progress["value"], 20)
            elif any(k in msg for k in ["분석", "수집", "취합", "스캔", "일정"]):
                self.exam_progress["value"] = max(self.exam_progress["value"], 40)
            elif any(k in msg for k in ["Gemini", "AI", "요청", "출제", "생성 중", "요약"]):
                self.exam_progress["value"] = max(self.exam_progress["value"], 65)
            elif any(k in msg for k in ["마크다운", "PDF", "컴파일", "조판", "렌더링"]):
                self.exam_progress["value"] = max(self.exam_progress["value"], 85)
            elif any(k in msg for k in ["완료", "완성", "성공"]):
                self.exam_progress["value"] = 100

        if eta is not None:
            self.exam_current_eta = eta

        self.append_exam_log(msg)

        clean_msg = msg.strip().replace("\n", " ")
        if len(clean_msg) > 55:
            clean_msg = clean_msg[:52] + "..."
        self.exam_status_var.set(clean_msg)

    def update_exam_timer(self):
        if not getattr(self, "exam_is_running", False):
            return

        elapsed = int(time.time() - getattr(self, "exam_start_time", time.time()))
        el_min = elapsed // 60
        el_sec = elapsed % 60

        if hasattr(self, "exam_current_eta") and self.exam_current_eta > 0:
            self.exam_current_eta = max(1, self.exam_current_eta - 1)
            eta_str = f"약 {self.exam_current_eta}초"
        elif hasattr(self, "exam_current_eta") and self.exam_current_eta == 0:
            eta_str = "마무리 중..."
        else:
            eta_str = "계산 중..."

        self.exam_eta_var.set(f"⏱️ 경과 {el_min:02d}:{el_sec:02d} | 남은 시간: {eta_str}")
        self.root.after(1000, self.update_exam_timer)

    def clear_exam_log(self):
        """실시간 콘솔 로그 화면 비우기"""
        if hasattr(self, "exam_log_text"):
            self.exam_log_text.config(state=tk.NORMAL)
            self.exam_log_text.delete("1.0", tk.END)
            self.exam_log_text.config(state=tk.DISABLED)

    @staticmethod
    def normalize_study_hours(text: str) -> str:
        """사용자가 입력한 일일 공부 시간('1.5시간', '1시간 30분', '90분', '1.5' 등)을 지능적으로 표준화"""
        raw = str(text).strip()
        if not raw:
            return "3시간"

        # 1. "1시간 30분" or "1시간 30" or "1시간30분"
        m = re.match(r"^(\d+(?:\.\d+)?)\s*시간\s*(\d+(?:\.\d+)?)\s*분?$", raw)
        if m:
            h = float(m.group(1))
            m_val = float(m.group(2))
            total_h = h + m_val / 60.0
            if total_h.is_integer():
                return f"{int(total_h)}시간"
            return f"{total_h:.1f}시간 ({int(h)}시간 {int(m_val)}분)"

        # 2. "90분", "45분" 등 분 단위 입력
        m = re.match(r"^(\d+(?:\.\d+)?)\s*분$", raw)
        if m:
            m_val = float(m.group(1))
            h = int(m_val // 60)
            rem_m = int(m_val % 60)
            total_h = m_val / 60.0
            if h > 0 and rem_m > 0:
                return f"{total_h:.1f}시간 ({h}시간 {rem_m}분)"
            elif h > 0:
                return f"{h}시간 ({int(m_val)}분)"
            return f"{int(m_val)}분 ({total_h:.1f}시간)"

        # 3. "1.5시간" or "2시간"
        m = re.match(r"^(\d+(?:\.\d+)?)\s*시간$", raw)
        if m:
            val = float(m.group(1))
            if val.is_integer():
                return f"{int(val)}시간"
            h = int(val)
            rem_m = int(round((val - h) * 60))
            return f"{val}시간 ({h}시간 {rem_m}분)"

        # 4. 순수 숫자만 입력한 경우 ("1.5", "2", "0.5" -> 시간으로 간주)
        m = re.match(r"^(\d+(?:\.\d+)?)$", raw)
        if m:
            val = float(m.group(1))
            if val.is_integer():
                return f"{int(val)}시간"
            h = int(val)
            rem_m = int(round((val - h) * 60))
            return f"{val}시간 ({h}시간 {rem_m}분)"

        return raw

    def generate_period_roadmap_action(self):
        if getattr(self, "exam_is_running", False):
            messagebox.showwarning("작업 진행 중", "이미 모의시험 또는 로드맵 생성이 진행 중입니다. 완료 후 다시 시도해주세요.")
            return

        cname = self.exam_course_combo.get().strip()
        if not cname:
            messagebox.showwarning("선택 오류", "대상 과목을 선택해주세요.")
            return

        period_label = self.period_combo.get()
        d_day = PERIOD_TO_DAYS.get(period_label, 7)
        exam_type = self.exam_type_combo.get()
        scope = self.exam_scope_var.get().strip()
        daily_hours_raw = self.exam_hours_var.get().strip()
        daily_hours = self.normalize_study_hours(daily_hours_raw)
        self.exam_hours_var.set(daily_hours)

        self.exam_is_running = True
        self.exam_start_time = time.time()
        self.exam_current_eta = 15
        self.exam_progress["value"] = 15
        self.exam_status_var.set(f"[{cname}] D-{d_day} 맞춤 학습 로드맵 생성 가동...")
        self.exam_eta_var.set("⏱️ 경과: 00:00 | 남은 시간: 약 15초")
        self.update_exam_timer()

        self.exam_log_text.config(state=tk.NORMAL)
        self.exam_log_text.delete("1.0", tk.END)
        self.exam_log_text.config(state=tk.DISABLED)

        self.append_exam_log(f"🚀 [{cname}] {period_label} 맞춤형 학습 로드맵 생성 시작", "step")
        self.append_exam_log(f"   • 시험 구분: {exam_type} | 출제 범위: {scope} | 일일 목표: {daily_hours}", "normal")

        def worker():
            try:
                import generate_roadmap
                def log_cb(m):
                    self.root.after(0, lambda: self.on_exam_log_event(m))

                pdf_file, content = generate_roadmap.generate_dday_custom_roadmap(
                    cname=cname,
                    d_day=d_day,
                    exam_type=exam_type,
                    scope=scope,
                    daily_hours=daily_hours,
                    log_func=log_cb
                )

                def on_success():
                    self.exam_is_running = False
                    self.exam_progress["value"] = 100
                    elapsed = int(time.time() - self.exam_start_time)
                    self.exam_eta_var.set(f"✅ 완성 (총 {elapsed}초)")
                    self.exam_status_var.set(f"✅ [{cname}] 학습 로드맵 PDF 제작 완료!")
                    self.append_exam_log(f"🎉 [{cname}] {period_label} 맞춤 로드맵 PDF 완성: {os.path.basename(pdf_file)}", "success")
                    self.append_exam_log(f"   • 저장 위치: {pdf_file}", "highlight")

                    self.last_exam_content = content
                    self.exam_preview_text.delete("1.0", tk.END)
                    self.exam_preview_text.insert(tk.END, content)

                    config_manager.send_system_notification(
                        title="📅 맞춤 로드맵 완성",
                        message=f"[{cname}] {period_label} 학습 로드맵 PDF 제작 완료!"
                    )
                    messagebox.showinfo(
                        "로드맵 PDF 생성 완료",
                        f"[{cname}] {period_label} 맞춤 학습 로드맵 PDF가 성공적으로 제작되었습니다!\n\n• 저장 파일: {os.path.basename(pdf_file)}\n• 저장 위치: {pdf_file}\n\n(마크다운 임시 파일은 자동 정리되었습니다.)"
                    )

                self.root.after(0, on_success)
            except Exception as e:
                def on_error():
                    self.exam_is_running = False
                    self.exam_progress["value"] = 0
                    self.exam_status_var.set("❌ 로드맵 생성 중 오류 발생")
                    self.exam_eta_var.set("❌ 오류")
                    self.append_exam_log(f"❌ 오류 발생: {e}", "error")
                    messagebox.showerror("생성 오류", f"로드맵 생성 중 오류 발생: {e}")
                self.root.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()

    def generate_mock_exam_now_action(self):
        if getattr(self, "exam_is_running", False):
            messagebox.showwarning("작업 진행 중", "이미 모의시험 또는 로드맵 생성이 진행 중입니다. 잠시만 기다려주세요.")
            return

        cname = self.exam_course_combo.get().strip()
        if not cname:
            messagebox.showwarning("선택 오류", "대상 과목을 선택해주세요.")
            return

        selected_files = [p for p, v in self.exam_material_vars.items() if v.get()]
        scope = f"선택한 학습 자료 {len(selected_files)}건 기반" if selected_files else "과목 전체 학습 자료 기반"
        self.exam_scope_var.set(scope)
        exam_type = self.exam_type_combo.get()
        
        import re
        raw_qc = self.q_count_combo.get().strip()
        m = re.search(r'\d+', raw_qc)
        try:
            q_count = max(1, min(100, int(m.group()))) if m else 10
        except Exception:
            q_count = 10
        q_fmt = self.q_format_combo.get()

        self.exam_is_running = True
        self.exam_start_time = time.time()
        self.exam_current_eta = 25 if q_count <= 10 else 35
        self.exam_progress["value"] = 15
        self.exam_status_var.set(f"[{cname}] {exam_type} AI 커스텀 모의시험 출제 준비 중...")
        self.exam_eta_var.set(f"⏱️ 경과: 00:00 | 남은 시간: 약 {self.exam_current_eta}초")
        self.update_exam_timer()

        self.exam_log_text.config(state=tk.NORMAL)
        self.exam_log_text.delete("1.0", tk.END)
        self.exam_log_text.config(state=tk.DISABLED)

        self.append_exam_log(f"🚀 [{cname}] {exam_type} AI 실전 모의시험 출제 파이프라인 가동", "step")
        self.append_exam_log(f"   • 문항수: {q_count}문항 | 문제유형: {q_fmt} | 출제범위: {scope}", "normal")
        if selected_files:
            self.append_exam_log(f"   • 선택된 학습자료/강의노트: {len(selected_files)}개 항목 반영", "highlight")

        def worker():
            try:
                import generate_mock_exams
                def log_cb(m):
                    self.root.after(0, lambda: self.on_exam_log_event(m))

                md_path, pdf_path, content = generate_mock_exams.generate_custom_mock_exam(
                    cname=cname,
                    scope=scope,
                    question_count=q_count,
                    question_format=q_fmt,
                    exam_type=exam_type,
                    selected_files=selected_files,
                    log_func=log_cb
                )

                def on_success():
                    self.exam_is_running = False
                    self.exam_progress["value"] = 100
                    elapsed = int(time.time() - self.exam_start_time)
                    self.exam_eta_var.set(f"✅ 완성 (총 {elapsed}초)")
                    self.exam_status_var.set(f"🎉 [{cname}] {exam_type} {q_count}문항 모의시험 출제 완료!")
                    self.append_exam_log(f"🎉 [{cname}] 모의시험 및 해설 PDF 제작 완료: {os.path.basename(pdf_path)}", "success")
                    self.append_exam_log(f"   • 시험지/해설지 위치: {pdf_path}", "highlight")

                    self.last_exam_content = content
                    self.exam_preview_text.delete("1.0", tk.END)
                    self.exam_preview_text.insert(tk.END, content)

                    config_manager.send_system_notification(
                        title="📝 실전 모의시험 출제 완료",
                        message=f"[{cname}] {exam_type} {q_count}문항 모의시험 & 해설 PDF 출제 완료!"
                    )
                    self.last_exam_pdf = pdf_path
                    if hasattr(self, "exam_open_pdf_btn"):
                        self.exam_open_pdf_btn.config(state="normal")
                    view_now = messagebox.askyesno(
                        "모의시험 생성 완료",
                        f"🎉 [{cname}] {exam_type} AI 커스텀 모의시험 및 해설지 PDF가 성공적으로 생성되었습니다!\n\n• 문항 수: {q_count}문항 ({q_fmt})\n• 시험지: {os.path.basename(pdf_path)}\n\n지금 바로 앱 내 라이브 뷰어로 시험지를 확인하시겠습니까?",
                        parent=self.root
                    )
                    if view_now:
                        self.open_last_exam_pdf()

                self.root.after(0, on_success)
            except Exception as e:
                def on_error():
                    self.exam_is_running = False
                    self.exam_progress["value"] = 0
                    self.exam_status_var.set("❌ 모의시험 출제 중 오류 발생")
                    self.exam_eta_var.set("❌ 오류")
                    self.append_exam_log(f"❌ 오류 발생: {e}", "error")
                    messagebox.showerror("생성 오류", f"모의시험 생성 중 오류 발생: {e}")
                self.root.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()

    def open_last_exam_pdf(self):
        if hasattr(self, "last_exam_pdf") and self.last_exam_pdf and os.path.exists(self.last_exam_pdf):
            self.open_pdf_viewer(self.last_exam_pdf, title=f"시험지 — {os.path.basename(self.last_exam_pdf)}")
        else:
            messagebox.showinfo("안내", "출제된 시험지/해설지 PDF 파일을 찾을 수 없습니다.")

    def open_exam_folder_action(self):
        cname = self.exam_course_combo.get().strip()
        if not cname:
            return
        folder = self.get_course_folder(cname)
        cdir = config_manager.get_course_dir(folder)
        exam_dir = os.path.join(cdir, "예상문제")
        os.makedirs(exam_dir, exist_ok=True)

        if sys.platform == "darwin":
            subprocess.call(["open", exam_dir])
        elif sys.platform == "win32":
            os.startfile(exam_dir)
        else:
            subprocess.call(["xdg-open", exam_dir])

    def generate_cheatsheet_action(self):
        if getattr(self, "exam_is_running", False):
            messagebox.showwarning("작업 진행 중", "이미 모의시험 또는 로드맵 생성이 진행 중입니다. 잠시만 기다려주세요.")
            return

        cname = self.exam_course_combo.get().strip()
        if not cname:
            messagebox.showwarning("선택 오류", "대상 과목을 선택해주세요.")
            return

        scope = self.exam_scope_var.get().strip()
        exam_type = self.exam_type_combo.get()
        selected_files = [p for p, v in self.exam_material_vars.items() if v.get()]

        self.exam_is_running = True
        self.exam_start_time = time.time()
        self.exam_current_eta = 20
        self.exam_progress["value"] = 15
        self.exam_status_var.set(f"[{cname}] {exam_type} 3분 치트시트(1-Page) 분석 및 생성 준비 중...")
        self.exam_eta_var.set("⏱️ 경과: 00:00 | 남은 시간: 약 20초")
        self.update_exam_timer()

        self.exam_log_text.config(state=tk.NORMAL)
        self.exam_log_text.delete("1.0", tk.END)
        self.exam_log_text.config(state=tk.DISABLED)

        self.append_exam_log(f"🚀 [{cname}] {exam_type} A4 1-Page 초고밀도 치트시트 파이프라인 가동", "step")
        self.append_exam_log(f"   • 시험 구분: {exam_type} | 출제 범위: {scope}", "normal")
        if selected_files:
            self.append_exam_log(f"   • 선택된 학습자료: {len(selected_files)}개 항목 반영", "highlight")

        def worker():
            try:
                import generate_cheatsheet
                def log_cb(m):
                    self.root.after(0, lambda: self.on_exam_log_event(m))

                pdf_file, content = generate_cheatsheet.generate_custom_cheatsheet(
                    cname=cname,
                    scope=scope,
                    exam_type=exam_type,
                    target_grade="A+",
                    selected_files=selected_files,
                    log_func=log_cb
                )

                def on_success():
                    self.exam_is_running = False
                    self.exam_progress["value"] = 100
                    elapsed = int(time.time() - self.exam_start_time)
                    self.exam_eta_var.set(f"✅ 완성 (총 {elapsed}초)")
                    self.exam_status_var.set(f"🎉 [{cname}] 3분 치트시트(A4 1-Page) 제작 완료!")
                    self.append_exam_log(f"🎉 [{cname}] 3분 치트시트 PDF 제작 완료: {os.path.basename(pdf_file)}", "success")
                    self.append_exam_log(f"   • 저장 위치: {pdf_file}", "highlight")

                    self.last_exam_content = content
                    self.exam_preview_text.delete("1.0", tk.END)
                    self.exam_preview_text.insert(tk.END, content)

                    config_manager.send_system_notification(
                        title="⚡ 3분 치트시트 제작 완료",
                        message=f"[{cname}] {exam_type} A4 1페이지 초고밀도 치트시트 제작 완료!"
                    )
                    self.last_exam_pdf = pdf_file
                    if hasattr(self, "exam_open_pdf_btn"):
                        self.exam_open_pdf_btn.config(state="normal")
                    view_now = messagebox.askyesno(
                        "치트시트 PDF 생성 완료",
                        f"🎉 [{cname}] {exam_type} 3분 핵심 치트시트(A4 1-Page)가 성공적으로 제작되었습니다!\n\n• 파일명: {os.path.basename(pdf_file)}\n\n지금 바로 앱 내 라이브 뷰어로 확인하시겠습니까?",
                        parent=self.root
                    )
                    if view_now:
                        self.open_pdf_viewer(pdf_file, title=f"치트시트 — {os.path.basename(pdf_file)}")

                self.root.after(0, on_success)
            except Exception as e:
                def on_error():
                    self.exam_is_running = False
                    self.exam_progress["value"] = 0
                    self.exam_status_var.set("❌ 치트시트 생성 중 오류 발생")
                    self.exam_eta_var.set("❌ 오류")
                    self.append_exam_log(f"❌ 오류 발생: {e}", "error")
                    messagebox.showerror("생성 오류", f"치트시트 생성 중 오류 발생: {e}")
                self.root.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()

    def open_grading_dialog_action(self):
        cname = self.exam_course_combo.get().strip()
        if not cname:
            messagebox.showwarning("선택 오류", "대상 과목을 먼저 선택해주세요.")
            return

        folder = self.get_course_folder(cname)
        cdir = config_manager.get_course_dir(folder)
        exam_dir = os.path.join(cdir, "예상문제")
        os.makedirs(exam_dir, exist_ok=True)

        exam_files = sorted(glob.glob(os.path.join(exam_dir, "*.md")))
        exam_files = [f for f in exam_files if "채점리포트" not in os.path.basename(f)]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"✍️ [{cname}] 실전 모의시험 AI 정밀 채점")
        dialog.geometry("860x700")
        dialog.minsize(700, 520)
        dialog.configure(bg="#f8fafc")
        dialog.transient(self.root)

        # Header banner
        header = ttk.Frame(dialog, padding="12 10")
        header.pack(fill=tk.X)
        ttk.Label(header, text=f"[{cname}] 실전 모의시험 정밀 채점기", font=("Pretendard", 12, "bold"), foreground="#1c4732").pack(anchor=tk.W)
        ttk.Label(header, text="학생 답안을 입력하시면 AI 채점관이 공식 정답표 1:1 대조 및 서술형 키워드(60%)+논리(40%) 기준표에 따라 예상 등급과 취약점을 분석합니다.", style="Muted.TLabel").pack(anchor=tk.W, pady=(2, 0))

        # Selection bar
        sel_frame = ttk.Frame(dialog, padding="12 4")
        sel_frame.pack(fill=tk.X)

        ttk.Label(sel_frame, text="📌 채점 대상 시험:", font=("Pretendard", 10, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        combo_options = []
        preview_text_content = getattr(self, "last_exam_content", "").strip() or self.exam_preview_text.get("1.0", tk.END).strip()
        if preview_text_content and ("Part 1" in preview_text_content or "모의시험" in preview_text_content or "Q1" in preview_text_content):
            combo_options.append("(방금 생성된 실전 모의시험)")
        for f in exam_files:
            combo_options.append(os.path.basename(f))
        if not combo_options:
            combo_options.append("(생성된 모의시험 없음)")

        exam_combo = ttk.Combobox(sel_frame, values=combo_options, state="readonly", width=42, font=("Pretendard", 9))
        exam_combo.set(combo_options[0])
        exam_combo.pack(side=tk.LEFT, padx=(0, 10))

        # Main Paned window: Top (Answer Input) & Bottom (Grading Report)
        paned = ttk.PanedWindow(dialog, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # 1. Answer Input Frame
        in_frame = ttk.LabelFrame(paned, text=" ✏️ 학생 제출 답안 입력 (객관식 번호 및 서술형 답변) ", padding="8")
        paned.add(in_frame, weight=1)

        txt_in_wrap = ttk.Frame(in_frame)
        txt_in_wrap.pack(fill=tk.BOTH, expand=True)

        answer_text = tk.Text(txt_in_wrap, wrap=tk.WORD, font=("Pretendard", 10), bg="#ffffff", fg="#0f172a", relief=tk.SOLID, bd=1, padx=8, pady=8, height=8)
        ans_sb = ttk.Scrollbar(txt_in_wrap, orient=tk.VERTICAL, command=answer_text.yview)
        answer_text.config(yscrollcommand=ans_sb.set)
        answer_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ans_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.add_context_menu(answer_text)

        # Template insert button
        def insert_template():
            tmpl = "1. ③\n2. ①\n3. ④\n4. ②\n5. (서술형) 핵심 원리 설명: ...\n"
            answer_text.insert(tk.END, tmpl)

        in_ctrl = ttk.Frame(in_frame)
        in_ctrl.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(in_ctrl, text="📋 답안 템플릿 입력", style="Secondary.TButton", command=insert_template).pack(side=tk.LEFT)
        ttk.Button(in_ctrl, text="🧹 지우기", style="Secondary.TButton", command=lambda: answer_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=(6, 0))

        # 2. Report Output Frame
        out_frame = ttk.LabelFrame(paned, text=" 📊 AI 정밀 채점 결과 리포트 & 취약점 분석 ", padding="8")
        paned.add(out_frame, weight=2)

        txt_out_wrap = ttk.Frame(out_frame)
        txt_out_wrap.pack(fill=tk.BOTH, expand=True)

        report_text = tk.Text(txt_out_wrap, wrap=tk.WORD, font=("Pretendard", 10), bg="#f8fafc", fg="#0f172a", relief=tk.SOLID, bd=1, padx=8, pady=8)
        rep_sb = ttk.Scrollbar(txt_out_wrap, orient=tk.VERTICAL, command=report_text.yview)
        report_text.config(yscrollcommand=rep_sb.set)
        report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rep_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.add_context_menu(report_text)

        # Bottom control bar
        bot_bar = ttk.Frame(dialog, padding="12 10")
        bot_bar.pack(fill=tk.X)

        status_lbl = ttk.Label(bot_bar, text="채점 준비 완료. 학생 답안을 입력하고 [AI 채점 시작]을 클릭하세요.", style="Muted.TLabel")
        status_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        open_rep_btn = ttk.Button(bot_bar, text="📂 [채점 파일 열기]", style="Secondary.TButton", state="disabled")
        open_rep_btn.pack(side=tk.RIGHT, padx=(6, 0))

        def open_report_file():
            rp = getattr(dialog, "report_path", None)
            if rp and os.path.exists(rp):
                if sys.platform == "darwin": subprocess.call(["open", rp])
                elif sys.platform == "win32": os.startfile(rp)
                else: subprocess.call(["xdg-open", rp])

        open_rep_btn.config(command=open_report_file)

        grade_btn = ttk.Button(bot_bar, text="🚀 [AI 채점 시작]", style="Action.TButton")
        grade_btn.pack(side=tk.RIGHT, padx=(6, 0))

        def run_grading():
            student_ans = answer_text.get("1.0", tk.END).strip()
            if not student_ans:
                messagebox.showwarning("답안 입력 필요", "학생 제출 답안을 입력해주세요.", parent=dialog)
                return

            sel = exam_combo.get().strip()
            exam_content = ""
            exam_type = "모의시험"
            if sel in ["(현재 미리보기 창의 모의시험)", "(방금 생성된 실전 모의시험)"]:
                exam_content = preview_text_content
                exam_type = self.exam_type_combo.get()
            elif sel and sel != "(생성된 모의시험 없음)":
                target_path = os.path.join(exam_dir, sel)
                if os.path.exists(target_path):
                    with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                        exam_content = f.read()
                if "중간고사" in sel: exam_type = "중간고사"
                elif "기말고사" in sel: exam_type = "기말고사"
                elif "퀴즈" in sel: exam_type = "주차별 퀴즈"

            if not exam_content:
                messagebox.showwarning("시험 원문 없음", "채점할 모의시험 원문을 찾을 수 없습니다.\n먼저 [AI 맞춤 모의시험]을 생성해주세요.", parent=dialog)
                return

            grade_btn.config(state="disabled")
            status_lbl.config(text="답안 분석 및 평가 리포트 생성 중입니다... (약 10~20초 소요)", foreground="#1c4732")

            def worker():
                try:
                    import generate_mock_exams
                    rep_path, rep_cnt = generate_mock_exams.grade_mock_exam_submission(
                        cname=cname,
                        exam_type=exam_type,
                        exam_content=exam_content,
                        student_answers=student_ans,
                        log_func=lambda m: self.root.after(0, lambda: status_lbl.config(text=m))
                    )
                    def success():
                        grade_btn.config(state="normal")
                        status_lbl.config(text=f"✅ 채점 완료! 리포트: {os.path.basename(rep_path)}", foreground="#10b981")
                        report_text.delete("1.0", tk.END)
                        report_text.insert(tk.END, rep_cnt)
                        self.exam_preview_text.delete("1.0", tk.END)
                        self.exam_preview_text.insert(tk.END, rep_cnt)
                        dialog.report_path = rep_path
                        open_rep_btn.config(state="normal")
                        messagebox.showinfo("채점 완료", f"🎉 [{cname}] {exam_type} 정밀 채점이 완료되었습니다!\n\n총점 및 취약점 분석 리포트가 생성되었습니다.", parent=dialog)
                    self.root.after(0, success)
                except Exception as ex:
                    def failure():
                        grade_btn.config(state="normal")
                        status_lbl.config(text=f"❌ 채점 오류: {ex}", foreground="#ef4444")
                        messagebox.showerror("채점 오류", f"채점 중 오류가 발생했습니다:\n{ex}", parent=dialog)
                    self.root.after(0, failure)

            threading.Thread(target=worker, daemon=True).start()

        grade_btn.config(command=run_grading)

    # =========================================================================
    # 탭 3: 조교 Q&A (과목별 독립 세션 & 커스텀 조교 닉네임 & 강의계획서 연동)
    # =========================================================================
    def build_tutor_tab(self):
        self.tutor_histories = {}  # cname -> list of {"role": ..., "text": ...}
        self.tutor_snapshots = {}  # cname -> formatted chat string
        self.current_tutor_course = None

        container = ttk.Frame(self.tab_tutor)
        container.pack(fill=tk.BOTH, expand=True)

        # 1. 상단 컨트롤 바 (과목 선택 / 조교 닉네임 / 강의계획서 상태 / 도구)
        top_bar = ttk.Frame(container)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        # 우측 도구 버튼들 먼저 pack하여 우측 고정 유지
        ttk.Button(top_bar, text="📂 자료 폴더", style="Secondary.TButton", command=self.open_tutor_course_folder).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(top_bar, text="🗑️ 대화 초기화", style="Secondary.TButton", command=self.clear_tutor_chat).pack(side=tk.RIGHT, padx=(4, 0))
        self.tutor_syllabus_btn = ttk.Button(top_bar, text="📑 강의계획서", style="Secondary.TButton", command=self.manage_course_syllabus_dialog)
        self.tutor_syllabus_btn.pack(side=tk.RIGHT, padx=(4, 0))

        # 좌측: 과목 선택 및 조교 닉네임
        ttk.Label(top_bar, text="📌 과목:", font=("Pretendard", 10, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        self.tutor_course_combo = ttk.Combobox(top_bar, state="readonly", width=15, font=("Pretendard", 10))
        self.tutor_course_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.tutor_course_combo.bind("<<ComboboxSelected>>", lambda e: self.on_tutor_course_changed())

        # 담당 조교 닉네임 표시 및 변경
        self.tutor_name_badge = ttk.Label(top_bar, text="전담: 수석 조교", font=("Pretendard", 10, "bold"), foreground="#1c4732")
        self.tutor_name_badge.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(top_bar, text="✏️ 닉네임", style="Secondary.TButton", command=self.rename_tutor_nickname_dialog).pack(side=tk.LEFT)

        # 안전 면책 및 듀얼 모드 안내 배너 (Disclaimer)
        disclaimer_frame = tk.Frame(container, bg="#fffbeb", highlightthickness=1, highlightbackground="#fde68a", padx=10, pady=5)
        disclaimer_frame.pack(fill=tk.X, pady=(0, 6))
        self.tutor_disclaimer_lbl = ttk.Label(
            disclaimer_frame,
            text="⚠️ [안내] 본 튜터는 복습 보조용입니다. 강의 외 전공 기초 이론도 친절히 해설하며, 공식 시험 일정/범위는 e-캠퍼스 공식 공지를 반드시 최종 확인하세요.",
            font=("Pretendard", 9),
            foreground="#92400e",
            background="#fffbeb"
        )
        self.tutor_disclaimer_lbl.pack(side=tk.LEFT)

        # 2. 대화 내역 표시창 (Chat View)


        # 3. 대화 내역 표시창 (Chat View)
        chat_frame = ttk.LabelFrame(container, text=" 💬 1:1 과목 전담 AI 튜터 대화창 ", padding="8")
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        chat_wrap = ttk.Frame(chat_frame)
        chat_wrap.pack(fill=tk.BOTH, expand=True)

        self.tutor_chat_text = tk.Text(chat_wrap, wrap=tk.WORD, font=("Pretendard", 12), bg="#ffffff", fg="#0f172a", relief=tk.FLAT, highlightthickness=1, highlightbackground="#e2e8f0", padx=16, pady=14, spacing1=2, spacing2=4, spacing3=2)
        chat_sb = ttk.Scrollbar(chat_wrap, orient=tk.VERTICAL, command=self.tutor_chat_text.yview)
        self.tutor_chat_text.config(yscrollcommand=chat_sb.set)
        self.tutor_chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chat_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.add_context_menu(self.tutor_chat_text)

        # Configure tags for styling chat messages & rich markdown (12pt high-readability)
        self.tutor_chat_text.tag_configure("user_hdr", font=("Pretendard", 12, "bold"), foreground="#2563eb")
        self.tutor_chat_text.tag_configure("user_body", font=("Pretendard", 12), foreground="#0f172a", lmargin1=14, lmargin2=14)
        self.tutor_chat_text.tag_configure("tutor_hdr", font=("Pretendard", 12, "bold"), foreground="#7c3aed")
        self.tutor_chat_text.tag_configure("tutor_body", font=("Pretendard", 12), foreground="#0f172a", lmargin1=14, lmargin2=14)
        self.tutor_chat_text.tag_configure("system_info", font=("Pretendard", 10, "italic"), foreground="#64748b")
        self.tutor_chat_text.tag_configure("time_tag", font=("Pretendard", 11, "bold"), foreground="#b45309", background="#fef3c7")
        self.tutor_chat_text.tag_configure("ref_quote", font=("Pretendard", 11), foreground="#475569", background="#f8fafc", lmargin1=18, lmargin2=18)

        # Markdown typography tags (12pt scale)
        self.tutor_chat_text.tag_configure("tutor_h1", font=("Pretendard", 15, "bold"), foreground="#1e1b4b", lmargin1=14, lmargin2=14)
        self.tutor_chat_text.tag_configure("tutor_h2", font=("Pretendard", 13, "bold"), foreground="#312e81", lmargin1=14, lmargin2=14)
        self.tutor_chat_text.tag_configure("tutor_h3", font=("Pretendard", 12, "bold"), foreground="#4338ca", lmargin1=14, lmargin2=14)
        self.tutor_chat_text.tag_configure("tutor_h4", font=("Pretendard", 12, "bold"), foreground="#4338ca", lmargin1=14, lmargin2=14)
        self.tutor_chat_text.tag_configure("tutor_bold", font=("Pretendard", 12, "bold"), foreground="#0f172a")
        self.tutor_chat_text.tag_configure("tutor_code", font=("Menlo", 11), foreground="#be123c", background="#f1f5f9")
        self.tutor_chat_text.tag_configure("tutor_code_block", font=("Menlo", 11), foreground="#0f172a", background="#f8fafc", lmargin1=24, lmargin2=24)
        self.tutor_chat_text.tag_configure("tutor_quote", font=("Pretendard", 11, "italic"), foreground="#475569", background="#f1f5f9", lmargin1=24, lmargin2=24)
        self.tutor_chat_text.tag_configure("tutor_hr", font=("Pretendard", 10), foreground="#cbd5e1", lmargin1=14, lmargin2=14)
        self.tutor_chat_text.tag_configure("tutor_bullet", font=("Pretendard", 12), foreground="#0f172a", lmargin1=18, lmargin2=32)

        # 4. 하단 질문 입력 및 전송
        bottom_frame = ttk.Frame(container)
        bottom_frame.pack(fill=tk.X)

        input_wrap = ttk.Frame(bottom_frame)
        input_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self.tutor_input_text = tk.Text(input_wrap, height=3, wrap=tk.WORD, font=("Pretendard", 12), bg="#ffffff", fg="#0f172a", relief=tk.FLAT, highlightthickness=1, highlightbackground="#cbd5e1", padx=12, pady=10)
        self.tutor_input_text.pack(fill=tk.BOTH, expand=True)
        self.add_context_menu(self.tutor_input_text)
        self.tutor_input_text.bind("<Return>", self.on_tutor_input_return)

        btn_box = ttk.Frame(bottom_frame)
        btn_box.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(btn_box, text="📎 자료 첨부...", style="Secondary.TButton", command=self.attach_tutor_material_file).pack(fill=tk.X, pady=(0, 4))
        self.tutor_send_btn = SquareRoundButton(btn_box, text="질문 전송 (Enter)", bg="#1c4732", hover_bg="#265e43", radius=8, height=36, font=("Pretendard", 10, "bold"), command=self.send_tutor_message)
        self.tutor_send_btn.pack(fill=tk.BOTH, expand=True, ipadx=10)


        self.on_tutor_course_changed()

    def get_course_data(self, cname):
        for c in self.courses:
            if c.get("course_name") == cname:
                return c
        new_c = {"course_name": cname, "folder_name": cname, "tutor_name": f"{cname} 수석 조교"}
        self.courses.append(new_c)
        return new_c

    @staticmethod
    def clean_latex_math(text):
        r"""LaTeX 수식($...$, $$...$$, \mathbf, \mathbb 등)을 깔끔한 유니코드 기호로 정제"""
        if not text:
            return ""
        sup_map = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "n": "ⁿ", "T": "ᵀ", "t": "ᵗ", "+": "⁺", "-": "⁻"}
        sub_map = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉", "i": "ᵢ", "j": "ⱼ", "k": "ₖ", "n": "ₙ", "m": "ₘ"}

        replacements = [
            (r"\\mathbb\{R\}", "ℝ"),
            (r"\\mathbb\{C\}", "ℂ"),
            (r"\\mathbb\{Z\}", "ℤ"),
            (r"\\mathbb\{N\}", "ℕ"),
            (r"\\mathbb\{Q\}", "ℚ"),
            (r"\\neq", "≠"),
            (r"\\leq", "≤"),
            (r"\\geq", "≥"),
            (r"\\approx", "≈"),
            (r"\\times", "×"),
            (r"\\div", "÷"),
            (r"\\pm", "±"),
            (r"\\in", "∈"),
            (r"\\notin", "∉"),
            (r"\\subset", "⊂"),
            (r"\\subseteq", "⊆"),
            (r"\\cup", "∪"),
            (r"\\cap", "∩"),
            (r"\\infty", "∞"),
            (r"\\rightarrow", "→"),
            (r"\\to", "→"),
            (r"\\leftarrow", "←"),
            (r"\\Rightarrow", "⇒"),
            (r"\\Leftrightarrow", "⇔"),
            (r"\\forall", "∀"),
            (r"\\exists", "∃"),
            (r"\\mid", "|"),
            (r"\\cdot", "·"),
            (r"\\cdots", "···"),
            (r"\\dots", "…"),
            (r"\\{", "{"),
            (r"\\}", "}"),
        ]
        for pat, rep in replacements:
            text = re.sub(pat, rep, text)

        # Convert \mathbf{x}, \text{x}, \mathrm{x}, \mathit{x}, \textbf{x}
        text = re.sub(r"\\(?:mathbf|text|mathrm|mathit|textbf|bm)\{([^}]+)\}", r"\1", text)

        # Superscripts: ^2 -> ², ^{2} -> ², ^T -> ᵀ
        def sup_repl(m):
            val = m.group(1) or m.group(2)
            return "".join(sup_map.get(c, c) for c in val)
        text = re.sub(r"\^\{([0-9nTt\+\-]+)\}|\^([0-9nTt\+\-])", sup_repl, text)

        # Subscripts: _1 -> ₁, _{1} -> ₁
        def sub_repl(m):
            val = m.group(1) or m.group(2)
            return "".join(sub_map.get(c, c) for c in val)
        text = re.sub(r"_\{([0-9ijknm]+)\}|_([0-9ijknm])", sub_repl, text)

        # Clean remaining $ and $$
        text = re.sub(r"\$\$([^\$]+)\$\$", r"\1", text)
        text = re.sub(r"\$([^\$]+)\$", r"\1", text)
        text = text.replace("$", "")
        return text

    @staticmethod
    def parse_inline_tokens(text):
        """인라인 마크다운 토큰(타임스탬프, 볼드, 코드, 일반 텍스트) 분리"""
        pattern = re.compile(r"(\[🎙️[^\]]+\]|\*\*[^*]+\*\*|`[^`]+`)")
        parts = pattern.split(text)
        tokens = []
        for p in parts:
            if not p:
                continue
            if p.startswith("[🎙️") and p.endswith("]"):
                tokens.append((p, "time_tag"))
            elif p.startswith("**") and p.endswith("**") and len(p) >= 4:
                tokens.append((p[2:-2], "bold"))
            elif p.startswith("`") and p.endswith("`") and len(p) >= 2:
                tokens.append((p[1:-1], "code"))
            else:
                tokens.append((p, "normal"))
        return tokens

    def insert_markdown_text(self, text_widget, md_text, base_tag="tutor_body"):
        """마크다운 문법 및 수식을 파싱하여 가독성 높은 서식 텍스트로 렌더링"""
        md_text = self.clean_latex_math(md_text)
        lines = md_text.splitlines()
        in_code_block = False

        for line in lines:
            stripped = line.strip()

            # 1. 코드 블록 (```)
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue

            if in_code_block:
                text_widget.insert(tk.END, f"  {line}\n", ("tutor_code_block",))
                continue

            # 2. 구분선 (---, ***, ___)
            if re.match(r"^(\-{3,}|\*{3,}|_{3,})$", stripped):
                text_widget.insert(tk.END, "  " + "─" * 46 + "\n", ("tutor_hr",))
                continue

            # 3. 제목 태그 (#, ##, ###, ####, #####)
            line_tag = base_tag
            content_to_parse = line
            header_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if header_match:
                hashes, h_text = header_match.groups()
                level = len(hashes)
                if level == 1: line_tag = "tutor_h1"
                elif level == 2: line_tag = "tutor_h2"
                elif level == 3: line_tag = "tutor_h3"
                else: line_tag = "tutor_h4"
                content_to_parse = h_text
            elif stripped.startswith("> "):
                line_tag = "tutor_quote"
                content_to_parse = stripped[2:]
            else:
                # 불릿 리스트 (*, -, +, •)
                bullet_match = re.match(r"^(\s*)([\*\-\+•])\s+(.*)$", line)
                if bullet_match:
                    indent, _, b_text = bullet_match.groups()
                    line_tag = "tutor_bullet"
                    content_to_parse = f"{indent}• {b_text}"

            # 4. 인라인 토큰 파싱 (**, `, [🎙️ ...])
            tokens = self.parse_inline_tokens(content_to_parse)
            for text, token_type in tokens:
                if token_type == "time_tag":
                    text_widget.insert(tk.END, text, ("time_tag", line_tag))
                elif token_type == "bold":
                    applied_tag = line_tag if line_tag in ("tutor_h1", "tutor_h2", "tutor_h3", "tutor_h4") else "tutor_bold"
                    text_widget.insert(tk.END, text, (applied_tag, line_tag))
                elif token_type == "code":
                    text_widget.insert(tk.END, f" {text} ", ("tutor_code", line_tag))
                else:
                    text_widget.insert(tk.END, text, (line_tag,))

            text_widget.insert(tk.END, "\n", (line_tag,))

    def on_tutor_course_changed(self):
        if not hasattr(self, "tutor_course_combo") or not hasattr(self, "tutor_chat_text"):
            return

        # 이전 과목 텍스트 스냅샷 저장
        if self.current_tutor_course and self.current_tutor_course in self.tutor_snapshots:
            self.tutor_snapshots[self.current_tutor_course] = self.tutor_chat_text.get("1.0", tk.END)

        cname = self.tutor_course_combo.get().strip()
        if not cname:
            return

        self.current_tutor_course = cname
        if cname not in self.tutor_histories:
            self.tutor_histories[cname] = []

        cdata = self.get_course_data(cname)
        tutor_name = cdata.get("tutor_name") or f"{cname} 수석 조교"
        self.tutor_name_badge.config(text=f"🤖 조교: {tutor_name}")

        # 강의계획서 연동 여부 점검
        s_file = config_manager.get_course_syllabus(cname)
        if s_file and os.path.exists(s_file):
            s_name = os.path.basename(s_file)
            short_s = (s_name[:12] + "...") if len(s_name) > 14 else s_name
            self.tutor_syllabus_btn.config(text=f"🟢 계획서 연동됨 ({short_s})", style="Secondary.TButton")
        else:
            self.tutor_syllabus_btn.config(text="💡 [강의계획서 등록 (권장)]", style="Primary.TButton")

        # 기존 대화 스냅샷 복원 또는 환영 메시지 생성
        self.tutor_chat_text.delete("1.0", tk.END)
        history = self.tutor_histories.get(cname, [])
        if history:
            s_status = f"🟢 강의계획서({os.path.basename(s_file)}) 연동 완료" if s_file else "🟡 강의계획서 미등록"
            welcome = (
                f"🎓 [{cname}] 1:1 전담 조교 '{tutor_name}' 대화 세션 ({s_status})\n"
                f"───────────────────────────────────────────────\n\n"
            )
            self.tutor_chat_text.insert(tk.END, welcome, "system_info")
            for turn in history:
                role = turn.get("role")
                txt = turn.get("text", "")
                if role == "user":
                    self.tutor_chat_text.insert(tk.END, f"\n👤 나 (질문):\n", "user_hdr")
                    self.tutor_chat_text.insert(tk.END, f"{txt}\n\n", "user_body")
                elif role == "model":
                    self.tutor_chat_text.insert(tk.END, f"🤖 [{tutor_name}] (답변):\n", "tutor_hdr")
                    self.insert_markdown_text(self.tutor_chat_text, txt, base_tag="tutor_body")
                    self.tutor_chat_text.insert(tk.END, "\n")
            self.tutor_chat_text.see(tk.END)
        else:
            s_status = f"🟢 강의계획서({os.path.basename(s_file)}) 연동 완료 (공식 진도/배점 1순위 적용)" if s_file else "🟡 강의계획서 미등록 (자율 학습 모드: 슬라이드/교재 기반 진행)"
            welcome = (
                f"🎓 안녕하세요! [{cname}] 1:1 전담 조교 '{tutor_name}'입니다!\n"
                f"• 📌 현재 상태: {s_status}\n"
                f"• 🎙️ [수업 연계 질문]: 주차별 학습노트와 교수님 실제 육성 발언 시점([🎙️ 음성 (MM:SS)])을 바탕으로 개념 설명과 시험 팁을 답변합니다.\n"
                f"• 📚 [원론적 기초 질문]: 강의 슬라이드에 없는 전공 기본 지식이나 원론적 배경 이론도 친절하게 보충 설명해 드립니다.\n"
                f"• 💡 상단의 [✏️ 닉네임 변경]으로 제 이름을 언제든 편하게 바꿔주실 수 있으며, [강의계획서]를 등록하시면 더 정밀한 안내가 가능합니다!\n\n"
            )
            self.tutor_chat_text.insert(tk.END, welcome, "system_info")
            self.tutor_snapshots[cname] = self.tutor_chat_text.get("1.0", tk.END)

    def reapply_chat_highlights(self):
        search_pos = "1.0"
        while True:
            match_pos = self.tutor_chat_text.search(r"\[🎙️[^\]]+\]", search_pos, tk.END, regexp=True)
            if not match_pos:
                break
            close_pos = self.tutor_chat_text.search("]", match_pos, tk.END)
            end_pos = f"{close_pos}+1c" if close_pos else f"{match_pos}+15c"
            self.tutor_chat_text.tag_add("time_tag", match_pos, end_pos)
            search_pos = end_pos

    def rename_tutor_nickname_dialog(self):
        cname = self.tutor_course_combo.get().strip()
        if not cname:
            return
        cdata = self.get_course_data(cname)
        cur_name = cdata.get("tutor_name", f"{cname} 수석 조교")

        import tkinter.simpledialog as sd
        new_name = sd.askstring(
            "조교 닉네임 변경",
            f"[{cname}] 전담 튜터의 새로운 이름을 입력하세요:\n(예: 데베박사, 회계요정, SQL마스터, 자비스)",
            initialvalue=cur_name,
            parent=self.root
        )
        if new_name and new_name.strip():
            clean_name = new_name.strip()
            cdata["tutor_name"] = clean_name
            config_manager.save_settings(self.settings)
            self.tutor_name_badge.config(text=f"🤖 조교: {clean_name}")
            self.tutor_chat_text.insert(tk.END, f"\n🔔 전담 조교 닉네임이 '{clean_name}'(으)로 변경되었습니다!\n\n", "system_info")
            self.tutor_chat_text.see(tk.END)
            if hasattr(self, "populate_course_table"):
                self.populate_course_table()

    def manage_course_syllabus_dialog(self):
        try:
            cname = self.tutor_course_combo.get().strip()
            if not cname:
                return

            folder = self.get_course_folder(cname)
            cdir = config_manager.get_course_dir(folder)
            s_dir = os.path.join(cdir, "강의계획서")
            os.makedirs(s_dir, exist_ok=True)

            dlg = tk.Toplevel(self.root)
            dlg.title(f"[{cname}] 강의계획서 (Syllabus) 관리")
            dlg.transient(self.root)
            dlg.configure(bg="#f8fafc")
            dlg.geometry("520x360")
            dlg.minsize(440, 300)
            dlg.grab_set()

            top_f = tk.Frame(dlg, bg="#ffffff", padx=16, pady=12, highlightthickness=1, highlightbackground="#e2e8f0")
            top_f.pack(fill=tk.X)
            tk.Label(top_f, text=f"📑 [{cname}] 공식 강의계획서 관리", font=("Pretendard", 11, "bold"), bg="#ffffff", fg="#1c4732").pack(anchor=tk.W)
            tk.Label(top_f, text="PDF, HTML(웹 강의계획서), DOCX, MD 등 복수 등록이 가능합니다.", font=("Pretendard", 8), bg="#ffffff", fg="#64748b").pack(anchor=tk.W, pady=(2, 0))

            body_f = tk.Frame(dlg, bg="#f8fafc", padx=16, pady=12)
            body_f.pack(fill=tk.BOTH, expand=True)

            # 현재 등록된 목록 불러오기
            existing_paths = list(config_manager.get_course_syllabi(folder))

            lb_frame = tk.Frame(body_f, bg="#f8fafc")
            lb_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            sb = ttk.Scrollbar(lb_frame, orient=tk.VERTICAL)
            lb = tk.Listbox(
                lb_frame,
                font=("Pretendard", 9),
                selectmode=tk.SINGLE,
                yscrollcommand=sb.set,
                bg="#ffffff", fg="#1e293b",
                selectbackground="#d8f3dc", selectforeground="#14281e",
                relief=tk.SOLID, bd=1
            )
            sb.config(command=lb.yview)
            lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            def _refresh():
                lb.delete(0, tk.END)
                for p in existing_paths:
                    lb.insert(tk.END, f"  📄 {os.path.basename(p)}")
                if not existing_paths:
                    lb.insert(tk.END, "  (등록된 강의계획서가 없습니다 — 자율 학습 모드)")

            _refresh()

            def _save_changes():
                cdata = self.get_course_data(cname)
                # 상대경로 목록으로 정돈
                rel_paths = []
                for p in existing_paths:
                    try:
                        rel = os.path.relpath(p, cdir)
                        if not rel.startswith(".."):
                            rel_paths.append(rel)
                        else:
                            rel_paths.append(p)
                    except Exception:
                        rel_paths.append(p)
                cdata["syllabus_paths"] = rel_paths
                cdata["syllabus_path"] = rel_paths[0] if rel_paths else ""
                config_manager.save_settings(self.settings)

                # UI 갱신
                if hasattr(self, "tutor_syllabus_btn"):
                    if rel_paths:
                        self.tutor_syllabus_btn.config(text=f"🟢 계획서 {len(rel_paths)}개 연동됨", style="Secondary.TButton")
                    else:
                        self.tutor_syllabus_btn.config(text="➕ 강의계획서 연동", style="Secondary.TButton")
                if hasattr(self, "populate_course_table"):
                    self.populate_course_table()

            def _add():
                files = self.ask_open_files_safe(
                    title=f"[{cname}] 강의계획서(Syllabus) 파일 선택 (복수 선택 가능)",
                    filetypes=[
                        ("지원 형식", "*.pdf *.html *.htm *.docx *.txt *.md"),
                        ("PDF 문서", "*.pdf"),
                        ("HTML 문서", "*.html *.htm"),
                        ("Word 문서", "*.docx"),
                        ("텍스트/마크다운", "*.txt *.md"),
                        ("모든 파일", "*.*")
                    ],
                    parent=dlg
                )
                if files:
                    import shutil
                    added_count = 0
                    for f in files:
                        if f and os.path.exists(f):
                            ext = os.path.splitext(f)[1]
                            safe_cname = cname.replace(" ", "_")
                            idx = len(existing_paths) + 1
                            dest_name = f"{safe_cname}_강의계획서_{idx}{ext}"
                            dest_path = os.path.join(s_dir, dest_name)
                            try:
                                shutil.copy2(f, dest_path)
                                existing_paths.append(dest_path)
                                added_count += 1
                            except Exception as e:
                                messagebox.showerror("추가 오류", f"강의계획서 저장 중 오류 ({os.path.basename(f)}): {e}", parent=dlg)
                    if added_count > 0:
                        _save_changes()
                        _refresh()
                        self.tutor_chat_text.insert(
                            tk.END,
                            f"\n🎉 {added_count}개의 강의계획서가 성공적으로 추가 연동되었습니다!\n",
                            "system_info"
                        )
                        self.tutor_chat_text.see(tk.END)

            def _remove():
                sel = lb.curselection()
                if not sel:
                    return
                idx = sel[0]
                if idx < len(existing_paths):
                    removed = existing_paths.pop(idx)
                    _save_changes()
                    _refresh()
                    self.tutor_chat_text.insert(
                        tk.END,
                        f"\n🗑 [{os.path.basename(removed)}] 강의계획서가 연동 해제되었습니다.\n",
                        "system_info"
                    )
                    self.tutor_chat_text.see(tk.END)

            def _open():
                sel = lb.curselection()
                if not sel:
                    return
                idx = sel[0]
                if idx < len(existing_paths):
                    p = existing_paths[idx]
                    if os.path.exists(p):
                        if p.lower().endswith(".pdf"):
                            self.open_pdf_viewer(p, title=f"강의계획서 — {os.path.basename(p)}")
                        elif sys.platform == "darwin":
                            subprocess.call(["open", p])
                        elif sys.platform == "win32":
                            os.startfile(p)
                        else:
                            subprocess.call(["xdg-open", p])

            btn_row = tk.Frame(body_f, bg="#f8fafc")
            btn_row.pack(fill=tk.X)

            ttk.Button(btn_row, text="➕ 파일 추가...", style="Secondary.TButton", command=_add).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(btn_row, text="🗑 선택 삭제", style="Secondary.TButton", command=_remove).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(btn_row, text="📂 열기", style="Secondary.TButton", command=_open).pack(side=tk.LEFT)
            ttk.Button(btn_row, text="완료", style="Primary.TButton", command=dlg.destroy).pack(side=tk.RIGHT)

        except Exception as err:
            import traceback
            traceback.print_exc()
            messagebox.showerror("오류", f"강의계획서 창을 여는 도중 문제가 발생했습니다: {err}", parent=self.root)

    def on_tutor_input_return(self, event):
        if event.state & 0x0001:  # Shift pressed -> allow newline
            return None
        self.send_tutor_message()
        return "break"  # prevent default newline insertion

    def ask_tutor_quick_prompt(self, q_text):
        if hasattr(self, "tutor_input_text"):
            self.tutor_input_text.delete("1.0", tk.END)
            self.tutor_input_text.insert(tk.END, q_text)
            self.send_tutor_message()

    def clear_tutor_chat(self):
        cname = self.tutor_course_combo.get().strip() if hasattr(self, "tutor_course_combo") else ""
        if cname:
            self.tutor_histories[cname] = []
            if cname in self.tutor_snapshots:
                del self.tutor_snapshots[cname]
        self.on_tutor_course_changed()

    def open_tutor_course_folder(self):
        cname = self.tutor_course_combo.get().strip()
        if not cname:
            return
        folder = self.get_course_folder(cname)
        cdir = config_manager.get_course_dir(folder)
        if sys.platform == "darwin": subprocess.call(["open", cdir])
        elif sys.platform == "win32": os.startfile(cdir)
        else: subprocess.call(["xdg-open", cdir])

    def send_tutor_message(self):
        cname = self.tutor_course_combo.get().strip()
        if not cname:
            messagebox.showwarning("과목 선택", "대상 과목을 선택해주세요.")
            return

        query = self.tutor_input_text.get("1.0", tk.END).strip()
        if not query:
            return

        cdata = self.get_course_data(cname)
        tutor_name = cdata.get("tutor_name") or f"{cname} 수석 조교"

        self.tutor_input_text.delete("1.0", tk.END)

        self.tutor_chat_text.insert(tk.END, f"\n👤 나 (질문):\n", "user_hdr")
        self.tutor_chat_text.insert(tk.END, f"{query}\n\n", "user_body")

        loading_marker = f"🤖 {tutor_name}: 강의계획서 및 수업 자료를 분석 중입니다... ⏳\n\n"
        start_idx = self.tutor_chat_text.index(tk.END + "-1c")
        self.tutor_chat_text.insert(tk.END, loading_marker, "system_info")
        self.tutor_chat_text.see(tk.END)

        self.tutor_send_btn.config(state="disabled")

        def worker():
            try:
                import lecture_tutor
                history = self.tutor_histories.get(cname, [])
                answer = lecture_tutor.ask_lecture_tutor(
                    cname=cname,
                    user_query=query,
                    conversation_history=history,
                    tutor_name=tutor_name
                )
                def on_done():
                    self.tutor_chat_text.delete(start_idx, tk.END)
                    self.tutor_chat_text.insert(tk.END, f"🤖 [{tutor_name}] (답변):\n", "tutor_hdr")

                    self.insert_markdown_text(self.tutor_chat_text, answer, base_tag="tutor_body")
                    self.tutor_chat_text.insert(tk.END, "\n")
                    self.tutor_chat_text.see(tk.END)
                    if cname not in self.tutor_histories:
                        self.tutor_histories[cname] = []
                    self.tutor_histories[cname].append({"role": "user", "text": query})
                    self.tutor_histories[cname].append({"role": "model", "text": answer})
                    self.tutor_snapshots[cname] = self.tutor_chat_text.get("1.0", tk.END)
                    self.tutor_send_btn.config(state="normal")
                self.root.after(0, on_done)
            except Exception as ex:
                def on_err():
                    self.tutor_chat_text.delete(start_idx, tk.END)
                    self.tutor_chat_text.insert(tk.END, f"❌ 오류 발생: {ex}\n\n", "system_info")
                    self.tutor_send_btn.config(state="normal")
                self.root.after(0, on_err)

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # 탭 4: 📊 주차별/차시별 진도 모니터링 대시보드
    # =========================================================================
    # =========================================================================
    # 탭 4: 📊 주차별/차시별 진도 모니터링 대시보드
    # =========================================================================
    def build_dashboard_tab(self):
        frame = ttk.Frame(self.tab_dashboard)
        frame.pack(fill=tk.BOTH, expand=True)

        # 1. 상단 컨트롤 바 (과목 선택 / 새로고침 / 폴더 열기)
        top_bar = ttk.Frame(frame)
        top_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(top_bar, text="📌 대상 과목 선택:", font=("Pretendard", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        self.dash_course_combo = ttk.Combobox(top_bar, width=22, state="readonly", font=("Pretendard", 10))
        self.dash_course_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.dash_course_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_dashboard())

        ttk.Button(top_bar, text="🔄 [진도 현황 새로고침]", style="Primary.TButton", command=self.refresh_dashboard).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top_bar, text="📂 [과목 폴더 열기]", style="Secondary.TButton", command=self.open_current_dash_course_folder).pack(side=tk.LEFT)

        # 2. KPI 요약 카드 프레임 (4개 카드)
        kpi_frame = ttk.Frame(frame)
        kpi_frame.pack(fill=tk.X, pady=(0, 10))

        def create_kpi_card(parent, title, bg_color, border_color):
            card = tk.Frame(parent, bg=bg_color, highlightthickness=1, highlightbackground=border_color, padx=10, pady=6)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            lbl_title = tk.Label(card, text=title, font=("Pretendard", 8, "bold"), bg=bg_color, fg="#475569")
            lbl_title.pack(anchor=tk.W)
            lbl_val = tk.Label(card, text="-", font=("Pretendard", 12, "bold"), bg=bg_color, fg="#0f172a")
            lbl_val.pack(anchor=tk.W, pady=(2, 0))
            return lbl_val

        self.dash_kpi_total = create_kpi_card(kpi_frame, "📅 총 정규 차시", "#f8fafc", "#cbd5e1")
        self.dash_kpi_audio = create_kpi_card(kpi_frame, "🎙️ 녹음 파일 처리율", "#eff6ff", "#93c5fd")
        self.dash_kpi_notes = create_kpi_card(kpi_frame, "📗 강의노트 제작 현황", "#f0fdf4", "#86efac")
        self.dash_kpi_exam  = create_kpi_card(kpi_frame, "🎯 시험대비 산출물 (모의/치트)", "#faf5ff", "#d8b4fe")

        # 3. 주차별/차시별 진도 테이블 (Treeview)
        table_frame = ttk.LabelFrame(frame, text=" 📋 1~16주차 전 차시 상세 진행 현황 (녹음 · 강의노트 · 슬라이드 · 시험자료) ", padding="6")
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("week", "session", "date", "audio", "note_ko", "note_en", "slides", "exam_prep")
        self.dash_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse", height=14)

        col_defs = [
            ("week", "주차", 65, "center"),
            ("session", "차시", 55, "center"),
            ("date", "수업 일자 (요일)", 125, "center"),
            ("audio", "음성 녹음 수신 상태", 160, "w"),
            ("note_ko", "국문 강의노트", 125, "w"),
            ("note_en", "영문 강의노트", 125, "w"),
            ("slides", "강의 슬라이드·교재", 150, "w"),
            ("exam_prep", "시험 대비 산출물", 140, "w"),
        ]
        for col_id, col_text, col_width, col_anchor in col_defs:
            self.dash_tree.heading(col_id, text=col_text)
            self.dash_tree.column(col_id, width=col_width, minwidth=col_width, anchor=col_anchor)

        tree_y_sb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.dash_tree.yview)
        tree_x_sb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.dash_tree.xview)
        self.dash_tree.configure(yscrollcommand=tree_y_sb.set, xscrollcommand=tree_x_sb.set)

        self.dash_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        tree_y_sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree_x_sb.pack(side=tk.BOTTOM, fill=tk.X)

        self.dash_tree.bind("<Double-1>", lambda e: self.dash_open_note_action())

        # 태그 스타일
        self.dash_tree.tag_configure("even", background="#ffffff")
        self.dash_tree.tag_configure("odd", background="#f8fafc")
        self.dash_tree.tag_configure("completed", background="#f0fdf4")

        # 4. 하단 빠른 실행 액션 바
        act_bar = ttk.Frame(frame)
        act_bar.pack(fill=tk.X, pady=(8, 0))

        SquareRoundButton(act_bar, text="📖  선택 강의노트 PDF 열기", bg="#1c4732", hover_bg="#265e43", radius=8, height=36, font=("Pretendard", 9, "bold"), command=self.dash_open_note_action).pack(side=tk.LEFT, padx=(0, 8))
        SquareRoundButton(act_bar, text="📂  선택 주차 폴더 열기", bg="#e2e8f0", hover_bg="#cbd5e1", fg="#14281e", radius=8, height=36, font=("Pretendard", 9, "bold"), command=self.dash_open_folder_action).pack(side=tk.LEFT, padx=(0, 8))
        SquareRoundButton(act_bar, text="⚡  3분 치트시트 생성", bg="#205c3b", hover_bg="#2a774d", radius=8, height=36, font=("Pretendard", 9, "bold"), command=self.dash_generate_cheatsheet_action).pack(side=tk.LEFT, padx=(0, 8))
        SquareRoundButton(act_bar, text="📝  맞춤 모의시험 출제", bg="#285943", hover_bg="#357357", radius=8, height=36, font=("Pretendard", 9, "bold"), command=self.dash_goto_exam_action).pack(side=tk.LEFT)

    def open_current_dash_course_folder(self):
        cname = self.dash_course_combo.get().strip()
        if not cname:
            return
        folder = self.get_course_folder(cname)
        cdir = config_manager.get_course_dir(folder)
        if sys.platform == "darwin":
            subprocess.call(["open", cdir])
        elif sys.platform == "win32":
            os.startfile(cdir)
        else:
            subprocess.call(["xdg-open", cdir])

    def refresh_dashboard(self):
        cname = self.dash_course_combo.get().strip()
        if not cname:
            course_names = [c["course_name"] for c in self.courses if c.get("course_name")]
            if course_names:
                cname = course_names[0]
                self.dash_course_combo.set(cname)
            else:
                return

        folder_name = self.get_course_folder(cname)
        cdir = config_manager.get_course_dir(folder_name)
        cache_c = os.path.join(config_manager.WORKSPACE_DIR, ".markdown_cache", folder_name)

        timetable = {}
        if os.path.exists(config_manager.TIMETABLE_PATH):
            try:
                with open(config_manager.TIMETABLE_PATH, "r", encoding="utf-8") as f:
                    timetable = json.load(f)
            except Exception:
                pass

        all_sessions = timetable.get("calendar_sessions", [])
        course_sessions = [s for s in all_sessions if s.get("course_name") == cname or s.get("folder_name") == folder_name]

        cdata = self.get_course_data(cname)
        tot_w = cdata.get("total_weeks", 16) if cdata else 16
        days = cdata.get("days", []) if cdata else []
        if not days:
            days = ["월"]

        if not course_sessions:
            course_sessions = []
            for w in range(1, tot_w + 1):
                if len(days) == 1:
                    course_sessions.append({"week": w, "session_number": 1, "date": f"{w}주차", "day_name": days[0]})
                else:
                    for s_idx, d_name in enumerate(days, 1):
                        course_sessions.append({"week": w, "session_number": s_idx, "date": f"{w}주차-{s_idx}", "day_name": d_name})

        for item in self.dash_tree.get_children():
            self.dash_tree.delete(item)

        inbox_dir = os.path.join(config_manager.WORKSPACE_DIR, "00_녹음_수신함")
        audio_dir = os.path.join(cdir, "음성녹음")
        notes_dir = os.path.join(cdir, "강의노트")
        slides_dir = os.path.join(cdir, "강의자료")
        exam_dir = os.path.join(cdir, "예상문제")

        inbox_files = os.listdir(inbox_dir) if os.path.exists(inbox_dir) else []
        audio_files = os.listdir(audio_dir) if os.path.exists(audio_dir) else []
        slides_files = os.listdir(slides_dir) if os.path.exists(slides_dir) else []
        exam_files = os.listdir(exam_dir) if os.path.exists(exam_dir) else []

        total_sessions = len(course_sessions)
        audio_count = 0
        completed_weeks = set()

        for idx, s in enumerate(course_sessions):
            w = s.get("week", 1)
            sess_no = s.get("session_number", (idx % 2) + 1)
            d_str = s.get("date", "")
            day_str = s.get("day_name", "")
            date_display = f"{d_str} ({day_str})" if day_str else d_str

            # 1. 음성 녹음 확인
            audio_status = "⏳ 대기"
            matched_audio = None
            for af in audio_files + inbox_files:
                if d_str and d_str in af:
                    matched_audio = af
                    break
            if matched_audio:
                audio_status = f"✅ 완료 ({matched_audio[:16]}...)" if len(matched_audio) > 16 else f"✅ 완료 ({matched_audio})"
                audio_count += 1

            # 2. 강의노트 (KO / EN) 확인
            w_dir = os.path.join(notes_dir, f"{w}주차")
            w_files = os.listdir(w_dir) if os.path.exists(w_dir) else []

            note_ko_status = "❌ 미생성"
            for wf in w_files:
                if "강의노트.pdf" in wf:
                    ko_p = os.path.join(w_dir, wf)
                    sz = round(os.path.getsize(ko_p) / 1024, 1)
                    note_ko_status = f"📗 PDF ({sz}KB)"
                    break
            if note_ko_status == "❌ 미생성" and os.path.exists(cache_c):
                for cf in os.listdir(cache_c):
                    if f"{w}주차" in cf and cf.endswith(".md"):
                        note_ko_status = "📝 MD 작성됨"
                        break

            note_en_status = "❌ 미생성"
            for wf in w_files:
                if "Lecture_Notes.pdf" in wf or "Lecture_Note.pdf" in wf:
                    sz = round(os.path.getsize(os.path.join(w_dir, wf)) / 1024, 1)
                    note_en_status = f"📘 PDF ({sz}KB)"
                    break

            if "📗" in note_ko_status or "📘" in note_en_status:
                completed_weeks.add(w)

            # 3. 슬라이드
            slides_status = "-"
            for sf in slides_files:
                if f"0{w}" in sf or f"ch{w}" in sf.lower() or f"chapter{w}" in sf.lower() or f"chapter-0{w}" in sf.lower() or f"chapter-{w}" in sf.lower() or f"{w}주" in sf:
                    slides_status = f"📄 {sf[:16]}..." if len(sf) > 16 else f"📄 {sf}"
                    break
            if slides_status == "-" and slides_files and w == 1:
                slides_status = f"📄 {slides_files[0][:16]}..."

            # 4. 시험 대비 산출물
            exam_status_parts = []
            for ef in exam_files:
                if "모의시험" in ef and ef.endswith(".pdf"):
                    exam_status_parts.append("📝 모의시험")
                    break
            for ef in exam_files:
                if "치트시트" in ef and ef.endswith(".pdf"):
                    exam_status_parts.append("⚡ 치트시트")
                    break
            for ef in os.listdir(cdir) if os.path.exists(cdir) else []:
                if "로드맵.pdf" in ef:
                    exam_status_parts.append("📅 로드맵")
                    break
            exam_status = " | ".join(exam_status_parts) if exam_status_parts else "-"

            row_tag = "even" if idx % 2 == 0 else "odd"
            if "📗" in note_ko_status and "✅" in audio_status:
                row_tag = "completed"

            self.dash_tree.insert(
                "",
                tk.END,
                values=(f"{w}주차", f"{sess_no}차시", date_display, audio_status, note_ko_status, note_en_status, slides_status, exam_status),
                tags=(row_tag,)
            )

        notes_count = len(completed_weeks)
        audio_pct = round((audio_count / total_sessions) * 100, 1) if total_sessions else 0
        exam_total_count = len([f for f in exam_files if f.endswith(".pdf")])

        self.dash_kpi_total.config(text=f"{total_sessions}회 정규수업")
        self.dash_kpi_audio.config(text=f"{audio_count} / {total_sessions}회 ({audio_pct}%)")
        self.dash_kpi_notes.config(text=f"{notes_count}개 주차 완료 / {tot_w}주")
        self.dash_kpi_exam.config(text=f"총 {exam_total_count}건 제작 완료")

    def dash_open_note_action(self):
        selected = self.dash_tree.selection()
        if not selected:
            messagebox.showinfo("안내", "열람할 차시 또는 주차를 목록에서 선택해주세요.")
            return

        item = self.dash_tree.item(selected[0])
        vals = item["values"]
        week_str = str(vals[0])
        cname = self.dash_course_combo.get().strip()
        folder = self.get_course_folder(cname)
        cdir = config_manager.get_course_dir(folder)
        w_dir = os.path.join(cdir, "강의노트", week_str)

        pdf_candidates = []
        if os.path.exists(w_dir):
            for f in os.listdir(w_dir):
                if f.endswith(".pdf"):
                    pdf_candidates.append(os.path.join(w_dir, f))

        if pdf_candidates:
            target_pdf = pdf_candidates[0]
            self.open_pdf_viewer(target_pdf, title=f"[{cname}] {week_str} 강의노트")
        else:
            messagebox.showwarning("파일 없음", f"[{cname}] {week_str}에 생성된 강의노트 PDF 파일이 아직 없습니다.\n'학습노트 생성 스튜디오' 탭에서 노트를 먼저 생성해주세요.")

    def dash_open_folder_action(self):
        selected = self.dash_tree.selection()
        week_sub = "1주차"
        if selected:
            item = self.dash_tree.item(selected[0])
            week_sub = str(item["values"][0])

        cname = self.dash_course_combo.get().strip()
        folder = self.get_course_folder(cname)
        cdir = config_manager.get_course_dir(folder)
        w_dir = os.path.join(cdir, "강의노트", week_sub)
        os.makedirs(w_dir, exist_ok=True)

        if sys.platform == "darwin":
            subprocess.call(["open", w_dir])
        elif sys.platform == "win32":
            os.startfile(w_dir)
        else:
            subprocess.call(["xdg-open", w_dir])

    def dash_generate_cheatsheet_action(self):
        cname = self.dash_course_combo.get().strip()
        if not cname:
            return
        selected = self.dash_tree.selection()
        scope = "전범위"
        if selected:
            item = self.dash_tree.item(selected[0])
            scope = f"{item['values'][0]} 중심"

        import generate_cheatsheet
        try:
            pdf_file, content = generate_cheatsheet.generate_custom_cheatsheet(
                cname=cname,
                scope=scope,
                exam_type="중간고사",
                target_grade="A+"
            )
            self.refresh_dashboard()
            view_now = messagebox.askyesno(
                "치트시트 PDF 생성 완료",
                f"🎉 [{cname}] 3분 치트시트(A4 1-Page)가 생성되었습니다!\n\n• 파일: {os.path.basename(pdf_file)}\n\n지금 바로 앱 내 라이브 뷰어로 확인하시겠습니까?",
                parent=self.root
            )
            if view_now and pdf_file.endswith(".pdf") and os.path.exists(pdf_file):
                self.open_pdf_viewer(pdf_file, title=f"치트시트 — {os.path.basename(pdf_file)}")
        except Exception as e:
            messagebox.showerror("생성 오류", f"치트시트 생성 실패: {e}")

    def dash_goto_exam_action(self):
        cname = self.dash_course_combo.get().strip()
        if not cname:
            return
        selected = self.dash_tree.selection()
        scope = "1~7주차"
        if selected:
            item = self.dash_tree.item(selected[0])
            scope = f"{item['values'][0]} 중심"

        self.exam_course_combo.set(cname)
        self.exam_scope_var.set(scope)
        self.populate_exam_materials()
        self.notebook.select(self.tab_exam)

    # =========================================================================
    # 탭 4: ⚙️ 과목 및 시스템 설정
    # =========================================================================
    def build_settings_tab(self):
        # 상단 설정 카드 (학기 & API Key)
        top_frame = ttk.LabelFrame(self.tab_settings, text=" 학기 및 Gemini API 설정 ", padding="10")
        top_frame.pack(fill=tk.X, pady=(0, 8))

        sem_row = ttk.Frame(top_frame)
        sem_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(sem_row, text="수강 학기:", font=("Pretendard", 10, "bold"), width=9).pack(side=tk.LEFT)
        self.semester_var = tk.StringVar(value=self.settings.get("semester", "2026년 2학기"))
        self.semester_entry = tk.Entry(
            sem_row,
            textvariable=self.semester_var,
            width=14,
            font=("Pretendard", 10),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#1c4732",
            selectbackground="#d8f3dc",
            selectforeground="#14281e",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            takefocus=True
        )
        self.semester_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.semester_entry.bind("<Button-1>", lambda e: self.semester_entry.focus_set())
        self.add_context_menu(self.semester_entry)

        ttk.Label(sem_row, text="개강일:", font=("Pretendard", 10, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        self.start_date_var = tk.StringVar(value=self.settings.get("semester_start_date", "2026-09-01"))
        self.start_date_entry = tk.Entry(
            sem_row,
            textvariable=self.start_date_var,
            width=11,
            font=("Pretendard", 10),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#1c4732",
            selectbackground="#d8f3dc",
            selectforeground="#14281e",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            takefocus=True
        )
        self.start_date_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.start_date_entry.bind("<Button-1>", lambda e: self.start_date_entry.focus_set())
        self.add_context_menu(self.start_date_entry)

        ttk.Label(sem_row, text="종강일:", font=("Pretendard", 10, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        self.end_date_var = tk.StringVar(value=self.settings.get("semester_end_date", "2026-12-21"))
        self.end_date_entry = tk.Entry(
            sem_row,
            textvariable=self.end_date_var,
            width=11,
            font=("Pretendard", 10),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#1c4732",
            selectbackground="#d8f3dc",
            selectforeground="#14281e",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            takefocus=True
        )
        self.end_date_entry.pack(side=tk.LEFT)
        self.end_date_entry.bind("<Button-1>", lambda e: self.end_date_entry.focus_set())
        self.add_context_menu(self.end_date_entry)

        api_row = ttk.Frame(top_frame)
        api_row.pack(fill=tk.X, pady=(4, 0))

        ttk.Label(api_row, text="Gemini Key:", width=9, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar(value=self.settings.get("gemini_api_key", "").strip())
        self.api_entry = tk.Entry(
            api_row,
            textvariable=self.api_key_var,
            show="",
            font=("Pretendard", 10),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#1c4732",
            selectbackground="#d8f3dc",
            selectforeground="#14281e",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            takefocus=True
        )
        self.api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.api_entry.bind("<Button-1>", lambda e: self.api_entry.focus_set())
        self.add_context_menu(self.api_entry)

        SquareRoundButton(api_row, text="💾 설정 저장", bg="#1c4732", hover_bg="#265e43", radius=8, height=32, font=("Pretendard", 9, "bold"), command=self.save_settings_action).pack(side=tk.RIGHT)

        # 화면 해상도 및 창모드 크기 조절 카드
        res_frame = ttk.LabelFrame(self.tab_settings, text=" 🖥️ 화면 해상도 및 창모드 크기 조절 (Window Resolution) ", padding="10")
        res_frame.pack(fill=tk.X, pady=(0, 8))

        res_info_row = ttk.Frame(res_frame)
        res_info_row.pack(fill=tk.X, pady=(0, 6))

        cur_w = self.root.winfo_width() if self.root.winfo_width() > 100 else 1180
        cur_h = self.root.winfo_height() if self.root.winfo_height() > 100 else 820
        self.res_status_label = ttk.Label(
            res_info_row,
            text=f"현재 창 크기: {cur_w} × {cur_h} px  (모서리 드래그로 자유롭게 크기 조절 가능)",
            font=("Pretendard", 9, "bold"),
            foreground="#1c4732"
        )
        self.res_status_label.pack(side=tk.LEFT)

        # 프리셋 버튼 모음
        preset_row = ttk.Frame(res_frame)
        preset_row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(preset_row, text="빠른 프리셋:", font=("Pretendard", 9, "bold"), width=10).pack(side=tk.LEFT)

        res_presets = [
            ("1024×680 콤팩트", 1024, 680),
            ("1160×800 표준", 1160, 800),
            ("1280×820 권장", 1280, 820),
            ("1440×900 레티나", 1440, 900),
            ("1600×980 대화면", 1600, 980),
        ]
        for p_label, pw, ph in res_presets:
            SquareRoundButton(
                preset_row,
                text=p_label,
                bg="#f1f5f9",
                hover_bg="#e2e8f0",
                fg="#334155",
                radius=8,
                height=28,
                font=("Pretendard", 8, "bold"),
                command=lambda w=pw, h=ph: self.apply_resolution(w, h),
                parent_bg="#ffffff"
            ).pack(side=tk.LEFT, padx=(0, 6))

        SquareRoundButton(
            preset_row,
            text="⛶ 전체 화면",
            bg="#f1f5f9",
            hover_bg="#e2e8f0",
            fg="#1e293b",
            radius=8,
            height=28,
            font=("Pretendard", 8, "bold"),
            command=self.toggle_fullscreen,
            parent_bg="#ffffff"
        ).pack(side=tk.LEFT)

        # 수치 직접 입력 행
        custom_row = ttk.Frame(res_frame)
        custom_row.pack(fill=tk.X, pady=(2, 0))

        ttk.Label(custom_row, text="직접 입력:", font=("Pretendard", 9, "bold"), width=10).pack(side=tk.LEFT)

        ttk.Label(custom_row, text="너비(W):", font=("Pretendard", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self.res_width_var = tk.StringVar(value=str(cur_w))
        w_entry = tk.Entry(
            custom_row,
            textvariable=self.res_width_var,
            width=6,
            font=("Pretendard", 9),
            bg="#ffffff",
            fg="#0f172a",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#cbd5e1"
        )
        w_entry.pack(side=tk.LEFT, padx=(0, 10))
        w_entry.bind("<FocusIn>", lambda e: setattr(self, "_res_editing", True))
        w_entry.bind("<FocusOut>", lambda e: setattr(self, "_res_editing", False))

        ttk.Label(custom_row, text="높이(H):", font=("Pretendard", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self.res_height_var = tk.StringVar(value=str(cur_h))
        h_entry = tk.Entry(
            custom_row,
            textvariable=self.res_height_var,
            width=6,
            font=("Pretendard", 9),
            bg="#ffffff",
            fg="#0f172a",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#cbd5e1"
        )
        h_entry.pack(side=tk.LEFT, padx=(0, 10))
        h_entry.bind("<FocusIn>", lambda e: setattr(self, "_res_editing", True))
        h_entry.bind("<FocusOut>", lambda e: setattr(self, "_res_editing", False))

        def apply_custom_res():
            try:
                w = int(self.res_width_var.get().strip())
                h = int(self.res_height_var.get().strip())
                if w < 700 or h < 500:
                    messagebox.showwarning("입력 확인", "너비는 최소 700px, 높이는 최소 500px 이상이어야 합니다.")
                    return
                self.apply_resolution(w, h)
            except ValueError:
                messagebox.showwarning("입력 오류", "너비와 높이는 숫자만 입력해 주세요.")

        SquareRoundButton(
            custom_row,
            text="크기 적용",
            bg="#1c4732",
            hover_bg="#265e43",
            radius=8,
            height=28,
            font=("Pretendard", 9, "bold"),
            command=apply_custom_res,
            parent_bg="#ffffff"
        ).pack(side=tk.LEFT, padx=(0, 14))

        self.remember_window_var = tk.BooleanVar(value=self.settings.get("remember_window_size", True))
        chk_remember = ttk.Checkbutton(
            custom_row,
            text="마지막 창 크기 및 위치 자동 저장 (재실행 시 복원)",
            variable=self.remember_window_var,
            command=self.toggle_remember_window_size
        )
        chk_remember.pack(side=tk.LEFT)

        # 과목 관리 테이블
        course_frame = ttk.LabelFrame(self.tab_settings, text=" 📚 수강 과목 관리 목록 ", padding="8")
        course_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cols = ("idx", "name", "tutor", "syllabus", "folder", "lang")
        self.course_tree = ttk.Treeview(course_frame, columns=cols, show="headings", height=8)
        self.course_tree.heading("idx", text="#")
        self.course_tree.heading("name", text="과목명")
        self.course_tree.heading("tutor", text="전담 조교")
        self.course_tree.heading("syllabus", text="강의계획서")
        self.course_tree.heading("folder", text="폴더명")
        self.course_tree.heading("lang", text="언어 모드")

        self.course_tree.column("idx", width=35, anchor=tk.CENTER)
        self.course_tree.column("name", width=180)
        self.course_tree.column("tutor", width=130)
        self.course_tree.column("syllabus", width=100, anchor=tk.CENTER)
        self.course_tree.column("folder", width=150)
        self.course_tree.column("lang", width=100, anchor=tk.CENTER)

        tree_sb = ttk.Scrollbar(course_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=tree_sb.set)
        self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # 과목 편집 버튼들
        c_btn_row = ttk.Frame(self.tab_settings)
        c_btn_row.pack(fill=tk.X, pady=(0, 8))

        SquareRoundButton(c_btn_row, text="➕  과목 추가", bg="#1c4732", hover_bg="#265e43", radius=8, height=34, font=("Pretendard", 9, "bold"), command=self.add_course_dialog).pack(side=tk.LEFT, padx=(0, 8))
        SquareRoundButton(c_btn_row, text="✏️  선택 과목 수정", bg="#e2e8f0", hover_bg="#cbd5e1", fg="#14281e", radius=8, height=34, font=("Pretendard", 9, "bold"), command=self.edit_course_dialog).pack(side=tk.LEFT, padx=(0, 8))
        SquareRoundButton(c_btn_row, text="🗑️  과목 삭제", bg="#fee2e2", hover_bg="#fecaca", fg="#dc2626", radius=8, height=34, font=("Pretendard", 9, "bold"), command=self.delete_course_action).pack(side=tk.LEFT)

        # 하단 전체 파이프라인 일괄 수동 실행 옵션 (사용자가 원할 때만 실행)
        batch_frame = ttk.LabelFrame(self.tab_settings, text=" 🚀 전체 파이프라인 일괄 수동 실행 (옵션) ", padding="8")
        batch_frame.pack(fill=tk.X)
        ttk.Label(batch_frame, text="전체 수신함 녹음 파일 자동 정리 및 모든 과목 일괄 파이프라인을 구동합니다.", style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(batch_frame, text="▶ 전체 파이프라인 수동 구동", style="Secondary.TButton", command=self.run_pipeline_thread).pack(side=tk.RIGHT)

    def populate_course_table(self):
        for item in self.course_tree.get_children():
            self.course_tree.delete(item)
        for idx, c in enumerate(self.courses):
            cname = c.get("course_name", "")
            tutor = c.get("tutor_name", f"{cname} 수석 조교")
            folder = c.get("folder_name", cname)
            s_file = config_manager.get_course_syllabus(folder)
            syllabus_status = "🟢 연동됨" if s_file else "⚪ 미등록"
            lang = LANG_CODE_TO_LABEL.get(c.get("language_mode", "both"), c.get("language_mode", "both"))
            self.course_tree.insert("", tk.END, values=(idx + 1, cname, tutor, syllabus_status, folder, lang))

    def save_settings_action(self):
        self.settings["semester"] = self.semester_var.get().strip()
        self.settings["semester_start_date"] = self.start_date_var.get().strip()
        self.settings["semester_end_date"] = self.end_date_var.get().strip()
        self.settings["gemini_api_key"] = self.api_key_var.get().strip()
        self.settings["courses"] = self.courses
        config_manager.save_settings(self.settings)

        # 배지 갱신
        self.update_api_status_badge()
        self.sem_badge_label.config(text=f" 📅 {self.settings['semester']} ")
        messagebox.showinfo("저장 완료", "설정이 성공적으로 저장되었습니다.")

    def add_course_dialog(self):
        self.show_course_dialog(is_edit=False)

    def edit_course_dialog(self):
        sel = self.course_tree.selection()
        if not sel:
            messagebox.showwarning("선택 필요", "수정할 과목을 목록에서 선택해주세요.")
            return
        item_vals = self.course_tree.item(sel[0], "values")
        cname = item_vals[1]
        target_course = None
        for c in self.courses:
            if c.get("course_name") == cname:
                target_course = c
                break
        if target_course:
            self.show_course_dialog(is_edit=True, course=target_course)

    def delete_course_action(self):
        sel = self.course_tree.selection()
        if not sel:
            messagebox.showwarning("선택 필요", "삭제할 과목을 목록에서 선택해주세요.")
            return
        cname = self.course_tree.item(sel[0], "values")[1]
        if messagebox.askyesno("과목 삭제", f"'{cname}' 과목을 설정에서 삭제하시겠습니까?"):
            self.courses = [c for c in self.courses if c.get("course_name") != cname]
            self.populate_course_table()
            self.refresh_course_combos()
            self.save_settings_action()

    def show_course_dialog(self, is_edit=False, course=None):
        dlg = tk.Toplevel(self.root)
        dlg.title("과목 수정" if is_edit else "새 과목 추가")
        dlg.geometry("480x480")
        dlg.transient(self.root)
        dlg.grab_set()

        form = ttk.Frame(dlg, padding="16")
        form.pack(fill=tk.BOTH, expand=True)

        course_data = course or {}

        ttk.Label(form, text="과목명:").pack(anchor=tk.W, pady=(0, 2))
        name_var = tk.StringVar(value=course_data.get("course_name", ""))
        name_entry = tk.Entry(form, textvariable=name_var, font=("Pretendard", 10), bg="#ffffff", fg="#0f172a", insertbackground="#1c4732", selectbackground="#d8f3dc", selectforeground="#14281e", relief=tk.SOLID, bd=1, takefocus=True)
        name_entry.pack(fill=tk.X, pady=(0, 6))
        name_entry.bind("<Button-1>", lambda e: name_entry.focus_set())
        self.add_context_menu(name_entry)

        ttk.Label(form, text="전담 조교 닉네임 (예: 데베박사, 회계요정):").pack(anchor=tk.W, pady=(0, 2))
        tutor_var = tk.StringVar(value=course_data.get("tutor_name", f"{course_data.get('course_name', '')} 수석 조교" if course_data.get('course_name') else "수석 조교"))
        tutor_entry = tk.Entry(form, textvariable=tutor_var, font=("Pretendard", 10), bg="#ffffff", fg="#0f172a", insertbackground="#1c4732", selectbackground="#d8f3dc", selectforeground="#14281e", relief=tk.SOLID, bd=1, takefocus=True)
        tutor_entry.pack(fill=tk.X, pady=(0, 6))
        tutor_entry.bind("<Button-1>", lambda e: tutor_entry.focus_set())
        self.add_context_menu(tutor_entry)

        # 강의계획서 파일 선택 (복수 등록 가능, HTML 포함)
        ttk.Label(form, text="강의계획서 (Syllabus) — PDF/HTML/DOCX/MD 복수 등록 가능:").pack(anchor=tk.W, pady=(0, 2))

        syl_outer = ttk.Frame(form)
        syl_outer.pack(fill=tk.X, pady=(0, 6))

        # 현재 등록된 목록 불러오기 (신규 list + 구버전 str 하위 호환)
        _folder_for_syl = course_data.get("folder_name") or course_data.get("course_name", "")
        _existing = config_manager.get_course_syllabi(_folder_for_syl)
        syllabi_list = list(_existing)          # 기존 경로들
        syllabi_to_add = []                     # 이번에 새로 추가할 원본 파일 경로들

        # 목록 표시 Listbox
        syl_lb_frame = ttk.Frame(syl_outer)
        syl_lb_frame.pack(fill=tk.X, pady=(0, 4))
        syl_scrollbar = tk.Scrollbar(syl_lb_frame, orient=tk.VERTICAL)
        syl_listbox = tk.Listbox(
            syl_lb_frame,
            font=("Pretendard", 9),
            height=4,
            selectmode=tk.SINGLE,
            yscrollcommand=syl_scrollbar.set,
            bg="#f8fafc", fg="#1e293b",
            selectbackground="#d8f3dc", selectforeground="#14281e",
            relief=tk.SOLID, bd=1,
        )
        syl_scrollbar.config(command=syl_listbox.yview)
        syl_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        syl_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _refresh_syl_lb():
            syl_listbox.delete(0, tk.END)
            for p in syllabi_list:
                syl_listbox.insert(tk.END, f"  {os.path.basename(p)}")
            if not syllabi_list:
                syl_listbox.insert(tk.END, "  (미등록 — 자율 학습 모드)")

        _refresh_syl_lb()

        syl_btn_row = ttk.Frame(syl_outer)
        syl_btn_row.pack(fill=tk.X)

        def add_syllabus():
            files = self.ask_open_files_safe(
                title="강의계획서(Syllabus) 파일 선택 (복수 선택 가능)",
                filetypes=[
                    ("지원 형식", "*.pdf *.html *.htm *.docx *.txt *.md"),
                    ("PDF 문서", "*.pdf"),
                    ("HTML 문서", "*.html *.htm"),
                    ("Word 문서", "*.docx"),
                    ("텍스트/마크다운", "*.txt *.md"),
                    ("모든 파일", "*.*"),
                ],
                parent=dlg
            )
            if files:
                for f in files:
                    if f and os.path.exists(f) and f not in syllabi_list:
                        syllabi_to_add.append(f)
                        syllabi_list.append(f)          # 미리보기용 (임시 전체경로)
                _refresh_syl_lb()

        def remove_syllabus():
            sel = syl_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx < len(syllabi_list):
                syllabi_list.pop(idx)
                # syllabi_to_add에서도 제거 (있을 경우)
                if idx < len(syllabi_to_add):
                    syllabi_to_add.pop(idx)
                _refresh_syl_lb()

        def open_syllabus():
            sel = syl_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx < len(syllabi_list):
                p = syllabi_list[idx]
                if os.path.exists(p):
                    if sys.platform == "darwin":
                        subprocess.call(["open", p])
                    elif sys.platform == "win32":
                        os.startfile(p)
                    else:
                        subprocess.call(["xdg-open", p])

        ttk.Button(syl_btn_row, text="➕ 파일 추가", style="Secondary.TButton", command=add_syllabus).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(syl_btn_row, text="🗑 선택 삭제", style="Secondary.TButton", command=remove_syllabus).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(syl_btn_row, text="📂 열기", style="Secondary.TButton", command=open_syllabus).pack(side=tk.LEFT)


        ttk.Label(form, text="폴더명:").pack(anchor=tk.W, pady=(0, 2))
        folder_var = tk.StringVar(value=course_data.get("folder_name", ""))
        folder_entry = tk.Entry(form, textvariable=folder_var, font=("Pretendard", 10), bg="#ffffff", fg="#0f172a", insertbackground="#1c4732", selectbackground="#d8f3dc", selectforeground="#14281e", relief=tk.SOLID, bd=1, takefocus=True)
        folder_entry.pack(fill=tk.X, pady=(0, 6))
        folder_entry.bind("<Button-1>", lambda e: folder_entry.focus_set())
        self.add_context_menu(folder_entry)



        ttk.Label(form, text="총 강의/학습 차시 수 (기본 16차시, 개인공부/자격증 시 자유 변경):").pack(anchor=tk.W, pady=(0, 2))
        weeks_var = tk.StringVar(value=str(course_data.get("total_weeks", 16)))
        weeks_entry = tk.Entry(form, textvariable=weeks_var, font=("Pretendard", 10), bg="#ffffff", fg="#0f172a", insertbackground="#1c4732", selectbackground="#d8f3dc", selectforeground="#14281e", relief=tk.SOLID, bd=1, takefocus=True)
        weeks_entry.pack(fill=tk.X, pady=(0, 6))
        weeks_entry.bind("<Button-1>", lambda e: weeks_entry.focus_set())
        self.add_context_menu(weeks_entry)

        ttk.Label(form, text="수업 언어 모드:").pack(anchor=tk.W, pady=(0, 2))
        lang_combo = ttk.Combobox(form, values=LANG_OPTIONS, state="readonly")
        lang_combo.set(LANG_CODE_TO_LABEL.get(course_data.get("language_mode", "both"), LANG_OPTIONS[0]))
        lang_combo.pack(fill=tk.X, pady=(0, 14))

        btn_row = ttk.Frame(form)
        btn_row.pack(fill=tk.X)

        def save_course():
            cname = name_var.get().strip()
            if not cname:
                messagebox.showwarning("입력 오류", "과목명을 입력해주세요.")
                return
            fname = folder_var.get().strip() or cname
            t_name = tutor_var.get().strip() or f"{cname} 수석 조교"
            days_list = course_data.get("days", ["월"])
            lcode = LANG_LABEL_TO_CODE.get(lang_combo.get(), "both")

            # ── 복수 강의계획서 파일 복사 후 상대경로 목록 구성 ──────────────
            import shutil
            cdir = config_manager.get_course_dir(fname)
            s_dir = os.path.join(cdir, "강의계획서")
            os.makedirs(s_dir, exist_ok=True)

            saved_paths = []   # settings.json에 저장할 상대경로들
            safe_cname = cname.replace(" ", "_")

            for i, src in enumerate(syllabi_to_add):
                try:
                    ext = os.path.splitext(src)[1]
                    suffix = f"_{i+1}" if i > 0 else ""
                    dest_name = f"{safe_cname}_강의계획서{suffix}{ext}"
                    dest_path = os.path.join(s_dir, dest_name)
                    shutil.copy2(src, dest_path)
                    saved_paths.append(os.path.join("강의계획서", dest_name))
                except Exception as ex:
                    print(f"Error copying syllabus [{src}]: {ex}")

            # 기존에 이미 저장된 경로들 (새로 추가하지 않은 것들) 보존
            # syllabi_list에서 syllabi_to_add에 없는 항목 = 기존 보존 경로
            existing_kept = []
            for p in syllabi_list:
                if p not in syllabi_to_add:
                    # 절대경로를 상대경로로 변환 (가능하면)
                    for base in (cdir, config_manager.WORKSPACE_DIR):
                        try:
                            rel = os.path.relpath(p, base)
                            if not rel.startswith(".."):
                                existing_kept.append(rel)
                                break
                        except Exception:
                            pass
                    else:
                        existing_kept.append(p)  # 절대경로 그대로

            final_paths = existing_kept + saved_paths
            # ─────────────────────────────────────────────────────────────────

            try:
                tot_w = max(1, min(52, int(weeks_var.get().strip())))
            except Exception:
                tot_w = 16

            new_c = {
                "course_name": cname,
                "folder_name": fname,
                "tutor_name": t_name,
                "syllabus_paths": final_paths,       # 복수 지원 (신규 키)
                "syllabus_path": final_paths[0] if final_paths else "",  # 하위 호환
                "total_weeks": tot_w,
                "days": days_list,
                "start_time": course_data.get("start_time", "09:00"),
                "end_time": course_data.get("end_time", "10:15"),
                "duration": course_data.get("duration", 75),
                "language_mode": lcode,
                "generate_mock_exam": True
            }


            if is_edit:
                for i, c in enumerate(self.courses):
                    if c.get("course_name") == course_data.get("course_name"):
                        self.courses[i] = new_c
                        break
            else:
                self.courses.append(new_c)

            self.populate_course_table()
            self.refresh_course_combos()
            self.save_settings_action()
            dlg.destroy()

        ttk.Button(btn_row, text="저장", style="Primary.TButton", command=save_course).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_row, text="취소", style="Secondary.TButton", command=dlg.destroy).pack(side=tk.RIGHT)

    def run_pipeline_thread(self):
        if messagebox.askyesno("파이프라인 구동", "전체 과목 마스터 파이프라인을 실행하시겠습니까?"):
            t = threading.Thread(target=self.execute_pipeline_subprocess, daemon=True)
            t.start()

    def execute_pipeline_subprocess(self):
        if getattr(sys, "frozen", False):
            try:
                import run_pipeline
                run_pipeline.main()
                self.root.after(0, lambda: messagebox.showinfo("완료", "파이프라인 구동이 완료되었습니다!"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("오류", f"파이프라인 실행 중 오류: {e}"))
            return
        run_script = os.path.join(WORKSPACE_DIR, "run_pipeline.py")
        if not os.path.exists(run_script):
            run_script = os.path.join(WORKSPACE_DIR, "code", "run_pipeline.py")
        cmd = [sys.executable, run_script]
        try:
            subprocess.check_call(cmd, cwd=WORKSPACE_DIR)
            self.root.after(0, lambda: messagebox.showinfo("완료", "파이프라인 구동이 완료되었습니다!"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("오류", f"파이프라인 실행 중 오류: {e}"))

    # =========================================================================
    # 탭 4: 🛠️ 고급 도구 (프롬프트 / 보관함 동기화 / 윤리 및 법적고지)
    # =========================================================================
    def build_advanced_tab(self):
        sub_nb = ttk.Notebook(self.tab_advanced)
        sub_nb.pack(fill=tk.BOTH, expand=True)

        # ---------------------------------------------------------------------
        # 서브탭 1: AI 시스템 프롬프트 관리 & 마크다운 동기화
        # ---------------------------------------------------------------------
        sub_tab_prompt = ttk.Frame(sub_nb, padding="8")
        sub_nb.add(sub_tab_prompt, text=" 🤖 AI 시스템 프롬프트 관리 ")

        frame_prompt = ttk.LabelFrame(sub_tab_prompt, text=" 🛠️ AI 프롬프트 커스터마이징 & 보관함 ", padding="10")
        frame_prompt.pack(fill=tk.BOTH, expand=True)

        top_bar = ttk.Frame(frame_prompt)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(top_bar, text="편집할 프롬프트 파일:", font=("Pretendard", 10, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        self.prompt_file_combo = ttk.Combobox(top_bar, state="readonly", width=34)
        self.prompt_file_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.prompt_file_combo.bind("<<ComboboxSelected>>", self.on_prompt_file_selected)

        ttk.Button(top_bar, text="💾 프롬프트 저장", style="Primary.TButton", command=self.save_current_prompt).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top_bar, text="📁 마크다운 보관함 동기화", style="Secondary.TButton", command=self.sync_markdown_vault_action).pack(side=tk.RIGHT)

        txt_wrap = ttk.Frame(frame_prompt)
        txt_wrap.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.prompt_text = tk.Text(txt_wrap, wrap=tk.WORD, font=("JetBrains Mono", 10), bg="#ffffff", fg="#0f172a", relief=tk.SOLID, bd=1, padx=8, pady=8)
        sb = ttk.Scrollbar(txt_wrap, orient=tk.VERTICAL, command=self.prompt_text.yview)
        self.prompt_text.config(yscrollcommand=sb.set)
        self.prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.add_context_menu(self.prompt_text)

        self.load_available_prompt_files()

        # ---------------------------------------------------------------------
        # 서브탭 2: ⚖️ 법적 고지 및 윤리적 학습 유의사항
        # ---------------------------------------------------------------------
        sub_tab_legal = ttk.Frame(sub_nb, padding="8")
        sub_nb.add(sub_tab_legal, text=" ⚖️ 법적 고지 및 윤리적 학습 유의사항 ")

        frame_legal = ttk.LabelFrame(sub_tab_legal, text=" 📜 대한민국 저작권법 및 학업 윤리 준수 서약 ", padding="10")
        frame_legal.pack(fill=tk.BOTH, expand=True)

        legal_top_bar = ttk.Frame(frame_legal)
        legal_top_bar.pack(fill=tk.X, pady=(0, 8))

        lbl_desc = ttk.Label(
            legal_top_bar,
            text="⚠️ [필독] 본 시스템(URY Engine)으로 녹음 및 생성된 모든 자료는 '개인 학업 목적(저작권법 제30조)'으로만 이용 가능하며,\n외부 무단 배포 및 공유는 엄격히 금지됩니다. (저작권법 제136조, 통신비밀보호법 제3조)",
            font=("Pretendard", 9, "bold"),
            foreground="#b91c1c",
            justify=tk.LEFT
        )
        lbl_desc.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_box = ttk.Frame(legal_top_bar)
        btn_box.pack(side=tk.RIGHT)

        ttk.Button(btn_box, text="📜 서약서 다시 확인", style="Secondary.TButton", command=lambda: self.check_compliance_agreement(force=True)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_box, text="📋 전문 복사", style="Secondary.TButton", command=self.copy_legal_notice).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_box, text="📂 파일 열기", style="Secondary.TButton", command=self.open_legal_notice_file).pack(side=tk.LEFT)

        legal_txt_wrap = ttk.Frame(frame_legal)
        legal_txt_wrap.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.legal_text = tk.Text(legal_txt_wrap, wrap=tk.WORD, font=("Pretendard", 9), bg="#f8fafc", fg="#0f172a", relief=tk.FLAT, highlightthickness=1, highlightbackground="#cbd5e1", padx=12, pady=12)
        legal_sb = ttk.Scrollbar(legal_txt_wrap, orient=tk.VERTICAL, command=self.legal_text.yview)
        self.legal_text.config(yscrollcommand=legal_sb.set)
        self.legal_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        legal_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.add_context_menu(self.legal_text)

        self.load_legal_notice()

    def get_legal_notice_path(self):
        candidates = [
            os.path.join(WORKSPACE_DIR, "system", "공지사항_윤리및법적고지.txt"),
            os.path.join(WORKSPACE_DIR, "system", "prompts", "공지사항_윤리및법적고지.txt"),
            os.path.join(WORKSPACE_DIR, "prompts", "공지사항_윤리및법적고지.txt"),
            os.path.join(WORKSPACE_DIR, "공지사항_윤리및법적고지.txt"),
            config_manager.find_config_file("공지사항_윤리및법적고지.txt")
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        for pat in ["*공지사항*", "*윤리*", "*법적*"]:
            for root in [WORKSPACE_DIR, os.path.join(WORKSPACE_DIR, "system"), PROMPTS_DIR]:
                if os.path.exists(root):
                    matches = glob.glob(os.path.join(root, f"{pat}.txt"))
                    if matches:
                        return matches[0]
        return os.path.join(WORKSPACE_DIR, "공지사항_윤리및법적고지.txt")

    def load_legal_notice(self):
        fpath = self.get_legal_notice_path()
        content = ""
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                pass
        if not content:
            content = """================================================================================
🎓 [필독] 강의 음성 녹음 및 학습자료 이용에 관한 윤리 및 법적 공지사항
   URY Engine (Ultimate Result for You Engine)
================================================================================

본 시스템(URY Engine)을 이용하는 모든 수강생은 교수자의 강의 저작권과
인격권, 그리고 수업 자료의 지식재산권을 보호하기 위해 대한민국 법률 및
대학 윤리 규정을 반드시 준수해야 합니다.

1. 강의 음성 녹음에 관한 법적 및 윤리적 유의사항
   - '사적 이용을 위한 복제'의 한계 (저작권법 제30조): 개인적인 복습 및 학습 보조 목적 한정
   - 음성 파일 및 요약본의 외부 유출/배포 절대 금지 (저작권법 제136조 및 민법)
     : 카카오톡, 에브리타임, 카페, SNS 등 공유·배포·유료 판매 엄금
   - 비공개 대화 녹음 금지 (통신비밀보호법 제3조)

2. 교수 제공 강의자료 및 교재 저작권 보호 안내
   - 슬라이드, PDF, 교재 및 유인물 무단 전재 금지
   - 족보 및 시험 문제 형태의 외부 유출 금지

3. AI 결과물 면책 조항 (Legal Disclaimer)
   - 본 도구는 학습 보조 조교일 뿐이며, 주 학습 수단 및 최종 시험 평가 기준을 대체하지 않습니다.
   - AI 결과물의 정확성이나 시험 결과에 대해 시스템은 어떠한 법적·행정적 책임도 지지 않습니다.

4. 수강생 준수 서약 (Compliance Agreement)
   - 본 프로그램을 사용하는 것은 위의 법적·윤리적 공지사항을 숙지하고 동의한 것으로 간주됩니다."""

        self.legal_text.config(state="normal")
        self.legal_text.delete("1.0", tk.END)
        self.legal_text.insert(tk.END, content)
        self.legal_text.config(state="disabled")

    def copy_legal_notice(self):
        self.legal_text.config(state="normal")
        content = self.legal_text.get("1.0", tk.END).strip()
        self.legal_text.config(state="disabled")
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("복사 완료", "법적 고지 및 윤리적 유의사항 전문이 클립보드에 복사되었습니다.")

    def open_legal_notice_file(self):
        fpath = self.get_legal_notice_path()
        if os.path.exists(fpath):
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", fpath])
                elif sys.platform == "win32":
                    os.startfile(fpath)
                else:
                    subprocess.Popen(["xdg-open", fpath])
            except Exception as e:
                messagebox.showerror("오류", f"파일 열기 실패: {e}")
        else:
            messagebox.showwarning("안내", f"파일을 찾을 수 없습니다: {fpath}")

    def load_available_prompt_files(self):
        if not os.path.exists(PROMPTS_DIR):
            return
        files = sorted(glob.glob(os.path.join(PROMPTS_DIR, "*.txt")))
        fnames = [os.path.basename(f) for f in files]
        self.prompt_file_combo.config(values=fnames)
        if fnames:
            self.prompt_file_combo.set(fnames[0])
            self.on_prompt_file_selected()

    def on_prompt_file_selected(self, event=None):
        fname = self.prompt_file_combo.get().strip()
        if not fname:
            return
        fpath = os.path.join(PROMPTS_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            self.prompt_text.delete("1.0", tk.END)
            self.prompt_text.insert(tk.END, content)

    def save_current_prompt(self):
        fname = self.prompt_file_combo.get().strip()
        if not fname:
            return
        fpath = os.path.join(PROMPTS_DIR, fname)
        content = self.prompt_text.get("1.0", tk.END).strip()
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        messagebox.showinfo("저장 완료", f"'{fname}' 프롬프트가 성공적으로 저장되었습니다.")

    def sync_markdown_vault_action(self):
        try:
            import sync_markdown_vault
            sync_markdown_vault.sync_markdown_files()
            messagebox.showinfo("동기화 완료", "모든 마크다운 문서가 '.마크다운_강의노트' 중앙 보관함에 동기화되었습니다!")
        except Exception as e:
            messagebox.showerror("오류", f"동기화 중 오류 발생: {e}")

    def toggle_realtime_recording(self):
        try:
            import audio_recorder
            rec = audio_recorder.recorder_instance
            if not rec.is_recording:
                course = self.studio_course_combo.get()
                if not course:
                    messagebox.showwarning("과목 선택", "녹음할 대상 과목을 먼저 선택해 주세요.")
                    return
                res = rec.start_recording(course)
                if res.get("status") == "success":
                    self.rec_is_active = True
                    self.rec_start_time = time.time()
                    self.studio_audio_var.set(res["output_file"])
                    self.update_rec_timer_loop()
                    self.append_studio_log(f"🔴 [실시간 녹음 시작] {res['file_name']}")
                    messagebox.showinfo("실시간 녹음 시작", f"마이크 실시간 녹음이 시작되었습니다.\n\n저장 대상: {res['file_name']}\n녹음 완료 후 [녹음 중지] 버튼을 누르면 파일이 자동 등록됩니다.")
                else:
                    messagebox.showerror("녹음 오류", res.get("message", "녹음 시작 실패"))
            else:
                self.rec_is_active = False
                res = rec.stop_recording()
                if hasattr(self, "rec_btn"):
                    self.rec_btn.config(
                        text="🔴  실시간 녹음",
                        bg="#fef2f2",
                        fg="#dc2626",
                        hover_bg="#fee2e2",
                        active_bg="#fecaca"
                    )
                if res.get("status") == "success":
                    self.append_studio_log(f"⏹️ [실시간 녹음 완료] {res.get('duration_sec', 0)}초 녹음 완료 -> {res.get('output_file')}")
                    out_f = res.get("output_file")
                    if out_f and os.path.exists(out_f):
                        self.studio_audio_var.set(out_f)
                        self.auto_detect_date_from_name(out_f)
                    self.refresh_studio_file_listboxes()
                    messagebox.showinfo("녹음 완료", f"실시간 오디오가 해당 과목 폴더에 성공적으로 저장되었습니다.\n(경과 시간: {res.get('duration_sec', 0)}초)")
                else:
                    messagebox.showerror("녹음 중지 오류", res.get("message", "녹음 중지 실패"))
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("녹음 오류", f"실시간 녹음 처리 중 오류: {e}")

    def update_rec_timer_loop(self):
        if getattr(self, "rec_is_active", False):
            elapsed = int(time.time() - getattr(self, "rec_start_time", time.time()))
            m, s = divmod(elapsed, 60)
            if hasattr(self, "rec_btn"):
                self.rec_btn.config(
                    text=f"⏹️  녹음 중지 ({m:02d}:{s:02d})",
                    bg="#dc2626",
                    fg="#ffffff",
                    hover_bg="#b91c1c",
                    active_bg="#991b1b"
                )
            self.root.after(1000, self.update_rec_timer_loop)

    

    def browse_blackboard_photo(self):
        course = self.studio_course_combo.get()
        if not course:
            messagebox.showwarning("과목 선택", "대상 과목을 먼저 선택해 주세요.")
            return
        cdir = config_manager.get_course_dir(course)
        photo_dir = os.path.join(cdir, "칠판사진")
        os.makedirs(photo_dir, exist_ok=True)
        files = filedialog.askopenfilenames(
            title="칠판/필기 판서 사진 추가 (최대 5장)",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.JPG *.PNG")]
        )
        if files:
            count = 0
            for f in files:
                dest = os.path.join(photo_dir, os.path.basename(f))
                if os.path.abspath(f) != os.path.abspath(dest):
                    try:
                        shutil.move(f, dest)
                    except Exception:
                        try:
                            shutil.copy2(f, dest)
                            os.remove(f)
                        except Exception:
                            pass
                count += 1
            messagebox.showinfo("사진 이동 완료", f"{count}장의 칠판/필기 판서 사진이 '{course}/칠판사진' 폴더로 이동 정렬되었습니다!")

    def run_master_bible_generation(self):
        cname = self.exam_course_combo.get()
        if not cname:
            messagebox.showwarning("과목 선택", "마스터 바이블을 생성할 과목을 선택해 주세요.")
            return

        def work():
            try:
                import generate_master_bible
                res = generate_master_bible.generate_master_bible(cname)
                if res.get("status") in ["success", "partial_success"]:
                    messagebox.showinfo("마스터 바이블 생성 완료", f"[{cname}] 전범위 마스터 바이블 PDF 출판 완료!\n\n경로: {res.get('pdf_path', '')}")
                else:
                    messagebox.showerror("생성 오류", res.get("message", "생성 실패"))
            except Exception as e:
                messagebox.showerror("오류", f"마스터 바이블 생성 중 예외 발생: {e}")

        threading.Thread(target=work, daemon=True).start()

    def attach_tutor_material_file(self):
        file_path = filedialog.askopenfilename(
            title="AI 튜터에게 제공할 과제/자료 파일 첨부",
            filetypes=[("Supported Documents", "*.pdf *.pptx *.hwpx *.hwp *.ipynb *.docx *.py *.sql *.txt")]
        )
        if file_path:
            fname = os.path.basename(file_path)
            try:
                import doc_parser
                parsed = doc_parser.parse_document(file_path)
                p_text = parsed.get("full_text", "")
                if p_text:
                    cname = self.tutor_course_combo.get()
                    history = self.tutor_histories.get(cname, [])
                    history.append({"role": "user", "text": f"[📎 첨부 파일: {fname}]\n{p_text[:8000]}"})
                    self.tutor_histories[cname] = history
                    self.append_tutor_chat_message("system", f"📎 첨부 자료 [{fname}] 파싱 완료! (텍스트 {len(p_text)}자 전달됨)")
                else:
                    messagebox.showwarning("첨부 실패", f"'{fname}' 파일에서 텍스트를 추출할 수 없습니다.")
            except Exception as e:
                messagebox.showerror("첨부 오류", f"파일 파싱 중 오류: {e}")


def main():
    root = tk.Tk()
    app = UnifiedDashboardApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
