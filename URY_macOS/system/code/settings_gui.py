#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 대학 전공 학업 관리 시스템 — URY Engine v5.4 (AI Academic Studio)
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
import threading
import subprocess
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    from tkinter import colorchooser
except Exception:
    colorchooser = None

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

def safe_askopenfilename(title="파일 선택", filetypes=None, parent=None, initialdir=None, **kwargs):
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

def safe_askopenfilenames(title="파일 다중 선택", filetypes=None, parent=None, initialdir=None, **kwargs):
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
            
    def draw(self, fill_color):
        self.delete("all")
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

    def on_enter(self, e):
        if self.btn_state != "disabled":
            self.draw(self.hover_bg)

    def on_leave(self, e):
        if self.btn_state != "disabled":
            self.draw(self.normal_bg)

    def on_press(self, e):
        if self.btn_state != "disabled":
            self.draw(self.active_bg)

    def on_release(self, e):
        if self.btn_state != "disabled":
            self.draw(self.hover_bg)
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
        self.root.title("URY Engine — Academic Studio v0.2")
        self.root.geometry("1080x900")
        self.root.minsize(980, 780)

        config_manager.fix_mac_quarantine()
        self.setup_icon()
        self.bind_mac_shortcuts()

        self.settings = config_manager.load_settings()
        self.theme_mode = self.settings.get("theme_mode", "light")
        self.theme_accent = self.settings.get("theme_accent", "#1c4732")

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
        except Exception:
            pass

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
        left.pack(side=tk.LEFT, padx=(18, 10), fill=tk.Y)

        title_row = tk.Frame(left, bg="#ffffff")
        title_row.pack(anchor=tk.W, pady=(8, 0))
        if hasattr(self, "icon_img"):
            try:
                tk.Label(title_row, image=self.icon_img, bg="#ffffff").pack(side=tk.LEFT, padx=(0, 6))
            except Exception:
                pass
        tk.Label(title_row, text="URY Engine", font=("Pretendard", 13, "bold"), bg="#ffffff", fg="#1c4732").pack(side=tk.LEFT)
        tk.Label(title_row, text=" v0.2", font=("Pretendard", 10), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT)

        tk.Label(left, text="Academic Studio · Ultimate Result for You", font=("Pretendard", 8), bg="#ffffff", fg="#94a3b8").pack(anchor=tk.W)

        # 중앙: 시안 2 플로팅 알약형 세그먼트 탭바
        center = tk.Frame(self.header_frame, bg="#ffffff")
        center.pack(side=tk.LEFT, expand=True)

        pill_wrap = tk.Frame(center, bg="#f1f5f9", padx=3, pady=3)
        pill_wrap.pack()

        self.tab_pills = []
        self.tab_defs = [
            ("🎙️ Studio", 0),
            ("📝 Exam Prep", 1),
            ("💬 AI Tutor", 2),
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
                radius=10,
                height=32,
                font=("Pretendard", 9, "bold"),
                parent_bg="#f1f5f9"
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.tab_pills.append(btn)

        # 우측: 학기 및 API 연결 상태 배지
        right = tk.Frame(self.header_frame, bg="#ffffff")
        right.pack(side=tk.RIGHT, padx=(10, 18), fill=tk.Y)

        sem_text = self.settings.get("semester", "2026년 2학기")
        self.sem_badge_label = tk.Label(right, text=f" 📅 {sem_text} ", font=("Pretendard", 9, "bold"), bg="#f1f5f9", fg="#1e293b", relief=tk.FLAT, padx=10, pady=5)
        self.sem_badge_label.pack(side=tk.LEFT, pady=13, padx=(0, 8))

        api_key = self.settings.get("gemini_api_key", "").strip()
        has_key = len(api_key) >= 10
        api_text = " 🟢 API 연결됨 " if has_key else " 🔴 API 등록 필요 "
        api_fg = "#15803d" if has_key else "#b91c1c"
        api_bg = "#f0fdf4" if has_key else "#fef2f2"
        self.api_badge_label = tk.Label(right, text=api_text, font=("Pretendard", 9, "bold"), bg=api_bg, fg=api_fg, relief=tk.FLAT, padx=10, pady=5)
        self.api_badge_label.pack(side=tk.LEFT, pady=13)

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
    def build_studio_tab(self):
        # 🌟 시안 2 (Option 2) 2열 분할 레이아웃: 좌측 설정(Step 1,2,3) | 우측 프리뷰 및 생성(Output Summary Preview)
        studio_container = ttk.Frame(self.tab_studio)
        studio_container.pack(fill=tk.BOTH, expand=True)

        studio_container.columnconfigure(0, weight=5, uniform="studio_col")
        studio_container.columnconfigure(1, weight=5, uniform="studio_col")
        studio_container.rowconfigure(0, weight=1)

        # =============================================================
        # [LEFT COLUMN] Input & Content Setup Card
        # =============================================================
        left_card = tk.Frame(studio_container, bg="#ffffff", bd=0, highlightthickness=1, highlightbackground="#e2e8f0")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)

        left_scroll_canvas = tk.Canvas(left_card, bg="#ffffff", highlightthickness=0)
        left_sb = ttk.Scrollbar(left_card, orient=tk.VERTICAL, command=left_scroll_canvas.yview)
        left_content = tk.Frame(left_scroll_canvas, bg="#ffffff", padx=16, pady=16)

        left_content.bind("<Configure>", lambda e: left_scroll_canvas.configure(scrollregion=left_scroll_canvas.bbox("all")))
        canvas_win = left_scroll_canvas.create_window((0, 0), window=left_content, anchor="nw")
        left_scroll_canvas.configure(yscrollcommand=left_sb.set)

        def on_canvas_configure(e):
            left_scroll_canvas.itemconfig(canvas_win, width=e.width)
        left_scroll_canvas.bind("<Configure>", on_canvas_configure)

        left_scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # -------------------------------------------------------------
        # Step 1: 대상 과목 및 수업 정보
        # -------------------------------------------------------------
        s1_head = tk.Frame(left_content, bg="#ffffff")
        s1_head.pack(fill=tk.X, pady=(0, 6))
        tk.Label(s1_head, text=" 1 ", font=("Pretendard", 9, "bold"), bg="#1c4732", fg="#ffffff", padx=4, pady=1).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(s1_head, text="Step 1. Course Selection (대상 과목 선택)", font=("Pretendard", 11, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        tk.Label(left_content, text="Select Course (수강 과목):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(2, 2))
        self.studio_course_combo = ttk.Combobox(left_content, state="readonly", font=("Pretendard", 10))
        self.studio_course_combo.pack(fill=tk.X, pady=(0, 8))
        self.studio_course_combo.bind("<<ComboboxSelected>>", lambda e: self.on_studio_course_changed())

        # 일자 및 주차 행
        row_dt = tk.Frame(left_content, bg="#ffffff")
        row_dt.pack(fill=tk.X, pady=(0, 8))

        col_date = tk.Frame(row_dt, bg="#ffffff")
        col_date.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(col_date, text="Class Date (수업 일자):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 2))
        
        d_box = tk.Frame(col_date, bg="#ffffff")
        d_box.pack(fill=tk.X)
        self.studio_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.studio_date_entry = tk.Entry(
            d_box,
            textvariable=self.studio_date_var,
            font=("Pretendard", 9),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#1c4732",
            selectbackground="#d8f3dc",
            selectforeground="#14281e",
            relief=tk.SOLID,
            bd=1,
            takefocus=True
        )
        self.studio_date_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.studio_date_entry.bind("<Button-1>", lambda e: self.studio_date_entry.focus_set())
        self.add_context_menu(self.studio_date_entry)

        ttk.Button(d_box, text="◀", width=3, style="Secondary.TButton", command=lambda: self.adjust_studio_date(-1)).pack(side=tk.LEFT, padx=1)
        ttk.Button(d_box, text="오늘", width=4, style="Secondary.TButton", command=lambda: self.studio_date_var.set(datetime.now().strftime("%Y-%m-%d"))).pack(side=tk.LEFT, padx=1)
        ttk.Button(d_box, text="▶", width=3, style="Secondary.TButton", command=lambda: self.adjust_studio_date(1)).pack(side=tk.LEFT, padx=1)

        col_wk = tk.Frame(row_dt, bg="#ffffff")
        col_wk.pack(side=tk.RIGHT, fill=tk.X)
        tk.Label(col_wk, text="Week (주차):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 2))
        self.studio_week_combo = ttk.Combobox(col_wk, values=[f"{w}주차" for w in range(1, 17)], state="readonly", font=("Pretendard", 9), width=8)
        self.studio_week_combo.set("1주차")
        self.studio_week_combo.pack(fill=tk.X)

        tk.Label(left_content, text="Language Mode (출력 언어):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 2))
        self.studio_lang_combo = ttk.Combobox(left_content, values=LANG_OPTIONS, state="readonly", font=("Pretendard", 9))
        self.studio_lang_combo.set(LANG_OPTIONS[0])
        self.studio_lang_combo.pack(fill=tk.X, pady=(0, 14))

        # 구분선
        tk.Frame(left_content, bg="#f1f5f9", height=1).pack(fill=tk.X, pady=(0, 12))

        # -------------------------------------------------------------
        # Step 2: Content Input (강의 음성 및 슬라이드 자료 연동)
        # -------------------------------------------------------------
        s2_head = tk.Frame(left_content, bg="#ffffff")
        s2_head.pack(fill=tk.X, pady=(0, 6))
        tk.Label(s2_head, text=" 2 ", font=("Pretendard", 9, "bold"), bg="#1c4732", fg="#ffffff", padx=4, pady=1).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(s2_head, text="Step 2. Content Input (강의 음성 & 슬라이드 연동)", font=("Pretendard", 11, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        self.audio_select_frame = tk.Frame(left_content, bg="#ffffff")
        self.audio_select_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(self.audio_select_frame, text="Audio Recording (음성 파일):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(anchor=tk.W, pady=(0, 2))
        
        audio_btn_row = tk.Frame(self.audio_select_frame, bg="#ffffff")
        audio_btn_row.pack(fill=tk.X, pady=(0, 4))
        
        ttk.Button(audio_btn_row, text="📂 오디오 찾기...", style="Secondary.TButton", command=self.browse_studio_audio).pack(side=tk.LEFT, padx=(0, 6))
        
        self.rec_btn = SquareRoundButton(
            audio_btn_row,
            text="🔴  실시간 녹음",
            bg="#fef2f2",
            fg="#dc2626",
            hover_bg="#fee2e2",
            radius=8,
            height=30,
            font=("Pretendard", 9, "bold"),
            command=self.toggle_realtime_recording,
            parent_bg="#ffffff"
        )
        self.rec_btn.pack(side=tk.LEFT)

        self.studio_audio_var = tk.StringVar(value="")
        self.studio_audio_entry = tk.Entry(
            self.audio_select_frame,
            textvariable=self.studio_audio_var,
            font=("Pretendard", 9),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#1c4732",
            selectbackground="#d8f3dc",
            selectforeground="#14281e",
            relief=tk.SOLID,
            bd=1,
            takefocus=True
        )
        self.studio_audio_entry.pack(fill=tk.X, pady=(2, 4))
        self.studio_audio_entry.bind("<Button-1>", lambda e: self.studio_audio_entry.focus_set())
        self.add_context_menu(self.studio_audio_entry)

        tk.Label(self.audio_select_frame, text="감지된 녹음 파일 (수신함 / 과목 폴더):", font=("Pretendard", 8, "bold"), bg="#ffffff", fg="#94a3b8").pack(anchor=tk.W)
        self.audio_listbox = tk.Listbox(self.audio_select_frame, height=3, font=("Pretendard", 8), bg="#f8fafc", relief=tk.SOLID, bd=1)
        self.audio_listbox.pack(fill=tk.X, pady=(2, 8))
        self.audio_listbox.bind("<<ListboxSelect>>", self.on_audio_listbox_select)

        # 슬라이드 섹션
        slide_head_row = tk.Frame(left_content, bg="#ffffff")
        slide_head_row.pack(fill=tk.X, pady=(0, 4))
        tk.Label(slide_head_row, text="Lecture Slides (강의 슬라이드):", font=("Pretendard", 9, "bold"), bg="#ffffff", fg="#475569").pack(side=tk.LEFT)

        # 시안 2 스타일 파일 포맷 배지
        badge_box = tk.Frame(slide_head_row, bg="#ffffff")
        badge_box.pack(side=tk.RIGHT)
        for fmt in ("PDF", "PPTX", "HWPX"):
            tk.Label(badge_box, text=f" {fmt} ", font=("Pretendard", 7, "bold"), bg="#f1f5f9", fg="#64748b", relief=tk.FLAT).pack(side=tk.LEFT, padx=1)

        slide_btn_row = tk.Frame(left_content, bg="#ffffff")
        slide_btn_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(slide_btn_row, text="➕ 자료 추가...", style="Secondary.TButton", command=self.browse_studio_slides).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(slide_btn_row, text="📷 칠판 판서...", style="Secondary.TButton", command=self.browse_blackboard_photo).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(slide_btn_row, text="🔄 새로고침", style="Secondary.TButton", command=self.refresh_studio_slides).pack(side=tk.RIGHT)

        slide_canvas_frame = tk.Frame(left_content, bg="#ffffff")
        slide_canvas_frame.pack(fill=tk.X, pady=(0, 14))

        self.slide_canvas = tk.Canvas(slide_canvas_frame, height=90, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        slide_sb = ttk.Scrollbar(slide_canvas_frame, orient=tk.VERTICAL, command=self.slide_canvas.yview)
        self.slide_inner_frame = tk.Frame(self.slide_canvas, bg="#f8fafc")
        self.slide_inner_frame.bind("<Configure>", lambda e: self.slide_canvas.configure(scrollregion=self.slide_canvas.bbox("all")))
        self.slide_canvas.create_window((0, 0), window=self.slide_inner_frame, anchor="nw")
        self.slide_canvas.configure(yscrollcommand=slide_sb.set)

        self.slide_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        slide_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.slide_check_vars = {}

        # 구분선
        tk.Frame(left_content, bg="#f1f5f9", height=1).pack(fill=tk.X, pady=(0, 12))

        # -------------------------------------------------------------
        # Step 3: Process & Refine (옵션)
        # -------------------------------------------------------------
        s3_head = tk.Frame(left_content, bg="#ffffff")
        s3_head.pack(fill=tk.X, pady=(0, 6))
        tk.Label(s3_head, text=" 3 ", font=("Pretendard", 9, "bold"), bg="#1c4732", fg="#ffffff", padx=4, pady=1).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(s3_head, text="Step 3. Process & Refine (분석 모드 설정)", font=("Pretendard", 11, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        self.no_audio_var = tk.BooleanVar(value=False)
        self.no_audio_check = ttk.Checkbutton(
            left_content,
            text="☑ 음성 녹음 없음 (슬라이드 집중 분석 모드)",
            variable=self.no_audio_var,
            command=self.toggle_no_audio_mode
        )
        self.no_audio_check.pack(anchor=tk.W, pady=(0, 4))

        self.no_audio_hint = tk.Label(
            left_content,
            text="💡 슬라이드 집중 독학 모드가 켜졌습니다.\n음성 녹음 없이도 공식 슬라이드 내용만을 정밀 파싱하여 체계적인 시험 강의노트를 생성합니다.",
            font=("Pretendard", 8),
            bg="#f0f9ff",
            fg="#0284c7",
            justify=tk.LEFT,
            padx=8,
            pady=6,
            relief=tk.FLAT
        )

        # =============================================================
        # [RIGHT COLUMN] Output Summary Preview & Live Console
        # =============================================================
        right_card = tk.Frame(studio_container, bg="#ffffff", bd=0, highlightthickness=1, highlightbackground="#e2e8f0")
        right_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)

        # 시안 2 상단 타이틀
        prev_head = tk.Frame(right_card, bg="#ffffff", padx=16, pady=12)
        prev_head.pack(fill=tk.X)
        tk.Label(prev_head, text="Output Summary Preview", font=("Pretendard", 12, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)
        tk.Label(prev_head, text="· 산출물 실시간 프리뷰 & 콘솔", font=("Pretendard", 9), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT, padx=(4, 0))

        # 시안 2 스타일 구조화된 요약 프리뷰 박스
        preview_box = tk.Frame(right_card, bg="#f8fafc", bd=0, highlightthickness=1, highlightbackground="#e2e8f0", padx=14, pady=10)
        preview_box.pack(fill=tk.X, padx=16, pady=(0, 10))

        # 4대 핵심 구조 안내
        sec1 = tk.Frame(preview_box, bg="#f8fafc")
        sec1.pack(fill=tk.X, pady=2)
        tk.Label(sec1, text="Key Concepts", font=("Pretendard", 9, "bold"), bg="#f8fafc", fg="#1c4732").pack(anchor=tk.W)
        tk.Label(sec1, text="• 핵심 개념, 학술 정의 및 공식 자동 추출\n• 교수님 육성 발언 시점([🎙️ MM:SS]) 타임스탬프 색인", font=("Pretendard", 8), bg="#f8fafc", fg="#475569", justify=tk.LEFT).pack(anchor=tk.W, padx=(8, 0))

        sec2 = tk.Frame(preview_box, bg="#f8fafc")
        sec2.pack(fill=tk.X, pady=2)
        tk.Label(sec2, text="Chapter Summaries", font=("Pretendard", 9, "bold"), bg="#f8fafc", fg="#1c4732").pack(anchor=tk.W)
        tk.Label(sec2, text="• 단원별 심층 요약 및 강의 슬라이드 페이지 매핑\n• 칠판 판서 필기 텍스트 정밀 시각화", font=("Pretendard", 8), bg="#f8fafc", fg="#475569", justify=tk.LEFT).pack(anchor=tk.W, padx=(8, 0))

        sec3 = tk.Frame(preview_box, bg="#f8fafc")
        sec3.pack(fill=tk.X, pady=2)
        tk.Label(sec3, text="Practice Questions", font=("Pretendard", 9, "bold"), bg="#f8fafc", fg="#1c4732").pack(anchor=tk.W)
        tk.Label(sec3, text="• 객관식/서술형/손풀이 10문항 자동 출제 및 단계별 해설\n• 시험 직전 대비 3분 치트시트(1Page) 연계", font=("Pretendard", 8), bg="#f8fafc", fg="#475569", justify=tk.LEFT).pack(anchor=tk.W, padx=(8, 0))

        # 실시간 진행 상황 및 로그 콘솔
        console_frame = tk.Frame(right_card, bg="#ffffff", padx=16)
        console_frame.pack(fill=tk.BOTH, expand=True)

        status_row = tk.Frame(console_frame, bg="#ffffff")
        status_row.pack(fill=tk.X, pady=(2, 4))

        self.studio_progress = ttk.Progressbar(status_row, mode="determinate", length=180)
        self.studio_progress.pack(side=tk.LEFT, padx=(0, 8))

        self.studio_status_var = tk.StringVar(value="원하는 음성 및 슬라이드를 선택한 후 생성 버튼을 누르세요.")
        tk.Label(status_row, textvariable=self.studio_status_var, font=("Pretendard", 8, "bold"), bg="#ffffff", fg="#475569").pack(side=tk.LEFT)

        self.studio_eta_var = tk.StringVar(value="")
        tk.Label(status_row, textvariable=self.studio_eta_var, font=("Pretendard", 8, "bold"), bg="#ffffff", fg="#1c4732").pack(side=tk.RIGHT)

        txt_wrap = tk.Frame(console_frame, bg="#ffffff")
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

        # 시안 2 하단 액션 바: 우측 돌출형 초록색 생성 버튼
        action_bar = tk.Frame(right_card, bg="#ffffff", padx=16, pady=10)
        action_bar.pack(fill=tk.X)

        self.studio_open_folder_btn = SquareRoundButton(
            action_bar,
            text="📂  폴더 열기",
            bg="#f1f5f9",
            hover_bg="#e2e8f0",
            fg="#334155",
            radius=8,
            height=36,
            font=("Pretendard", 9, "bold"),
            command=self.open_studio_notes_folder,
            parent_bg="#ffffff"
        )
        self.studio_open_folder_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.studio_clear_log_btn = SquareRoundButton(
            action_bar,
            text="🧹  콘솔 지우기",
            bg="#f1f5f9",
            hover_bg="#e2e8f0",
            fg="#334155",
            radius=8,
            height=36,
            font=("Pretendard", 9, "bold"),
            command=self.clear_studio_log,
            parent_bg="#ffffff"
        )
        self.studio_clear_log_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.studio_stop_btn = SquareRoundButton(
            action_bar,
            text="⏹  작업 중단",
            bg="#dc2626",
            hover_bg="#b91c1c",
            active_bg="#991b1b",
            radius=8,
            height=36,
            state="disabled",
            font=("Pretendard", 9, "bold"),
            command=self.abort_studio_generation,
            parent_bg="#ffffff"
        )
        self.studio_stop_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.studio_open_pdf_btn = SquareRoundButton(
            action_bar,
            text="📄  출판용 PDF 열기",
            bg="#2e5944",
            hover_bg="#3a7056",
            active_bg="#224333",
            radius=8,
            height=36,
            state="disabled",
            font=("Pretendard", 9, "bold"),
            command=self.open_last_generated_pdf,
            parent_bg="#ffffff"
        )
        self.studio_open_pdf_btn.pack(side=tk.LEFT, padx=(0, 6))

        # 시안 2 메인 초록색 'Generate' 버튼
        self.generate_studio_btn = SquareRoundButton(
            action_bar,
            text="✨  학습노트 및 출판용 PDF 생성",
            bg="#1c4732",
            hover_bg="#265e43",
            active_bg="#143324",
            radius=9,
            height=38,
            font=("Pretendard", 10, "bold"),
            command=self.execute_studio_generation,
            parent_bg="#ffffff"
        )
        self.generate_studio_btn.pack(side=tk.RIGHT)


    

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
            self.no_audio_hint.pack(fill=tk.BOTH, expand=True, pady=10)
        else:
            self.no_audio_hint.pack_forget()
            self.audio_select_frame.pack(fill=tk.BOTH, expand=True)

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
            title="강의 슬라이드 PDF 파일 선택",
            initialdir=slides_dir if os.path.exists(slides_dir) else course_dir,
            filetypes=[("PDF 문서", "*.pdf"), ("모든 파일", "*.*")]
        )
        if fpaths:
            os.makedirs(slides_dir, exist_ok=True)
            for fp in fpaths:
                dest = os.path.join(slides_dir, os.path.basename(fp))
                if os.path.abspath(fp) != os.path.abspath(dest):
                    try:
                        shutil.copy2(fp, dest)
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
        self.audio_listbox.delete(0, tk.END)

        # 수신함 스캔
        inbox = os.path.join(WORKSPACE_DIR, "00_녹음_수신함")
        if os.path.exists(inbox):
            for ext in ("*.m4a", "*.mp3", "*.wav", "*.aac"):
                for p in sorted(glob.glob(os.path.join(inbox, ext))):
                    self.detected_audio_paths.append(p)
                    self.audio_listbox.insert(tk.END, f"[수신함] {os.path.basename(p)}")

        # 과목 음성녹음 폴더 스캔
        rec_dir = os.path.join(course_dir, "음성녹음")
        if os.path.exists(rec_dir):
            for ext in ("*.m4a", "*.mp3", "*.wav", "*.aac"):
                for p in sorted(glob.glob(os.path.join(rec_dir, ext))):
                    self.detected_audio_paths.append(p)
                    self.audio_listbox.insert(tk.END, f"[과목보관] {os.path.basename(p)}")

        # 2. 슬라이드 PDF 목록 갱신
        self.refresh_studio_slides()

    def refresh_studio_file_listboxes(self):
        """스튜디오 오디오 및 슬라이드 목록 동시 새로고침"""
        self.on_studio_course_changed()

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
        found_pdfs = []
        for sdir in search_dirs:
            if os.path.exists(sdir):
                for p in sorted(glob.glob(os.path.join(sdir, "*.pdf"))):
                    lower = os.path.basename(p).lower()
                    if "syllabus" in lower or "강의계획서" in lower:
                        continue
                    if p not in found_pdfs:
                        found_pdfs.append(p)

        if not found_pdfs:
            ttk.Label(self.slide_inner_frame, text="등록된 슬라이드 PDF가 없습니다.\n'➕ 슬라이드 PDF 추가'를 클릭하세요.", font=("Pretendard", 9), foreground="#94a3b8").pack(anchor=tk.W, pady=6)
            return

        for pdf_path in found_pdfs:
            fname = os.path.basename(pdf_path)
            var = tk.BooleanVar(value=True)
            self.slide_check_vars[pdf_path] = var
            chk = ttk.Checkbutton(self.slide_inner_frame, text=fname, variable=var)
            chk.pack(anchor=tk.W, pady=2)

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
                import process_all_lectures

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
        self.studio_status_var.set("✅ 학습노트 및 출판용 PDF 생성이 성공적으로 완료되었습니다!")

        self.append_studio_log("=" * 55, "step")
        self.append_studio_log(f"🎉 [{result.get('course_name')}] 학습노트 및 PDF 제작이 완벽하게 완료되었습니다! (총 {elapsed}초)", "success")

        pdfs = result.get("pdf_files", [])
        if pdfs:
            self.last_generated_pdf = pdfs[-1]
            self.studio_open_pdf_btn.config(state=tk.NORMAL)
            for pdf_path in pdfs:
                self.append_studio_log(f"  📄 최종 출판 문서: {os.path.basename(pdf_path)}", "highlight")

        messagebox.showinfo("완료", f"🎉 [{result.get('course_name')}] 학습노트 및 출판용 PDF 생성이 완료되었습니다!\n\n총 소요 시간: {elapsed}초\n'📄 생성된 PDF 열기' 버튼을 눌러 바로 확인하실 수 있습니다.")
        config_manager.send_system_notification(
            title="🎙️ 맞춤 강의노트 완성",
            message=f"[{result.get('course_name')}] 출판용 PDF 제작 완료! (총 {elapsed}초)"
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
        if self.last_generated_pdf and os.path.exists(self.last_generated_pdf):
            if sys.platform == "darwin":
                subprocess.call(["open", self.last_generated_pdf])
            elif sys.platform == "win32":
                os.startfile(self.last_generated_pdf)
            else:
                subprocess.call(["xdg-open", self.last_generated_pdf])
        else:
            messagebox.showinfo("안내", "생성된 PDF 파일을 찾을 수 없습니다.")

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

        # Row 2
        r2 = ttk.Frame(form)
        r2.pack(fill=tk.X, pady=4)
        ttk.Label(r2, text="출제 범위:", width=11, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.exam_scope_var = tk.StringVar(value="전범위 (Ch.1 ~ Ch.6)")
        self.exam_scope_entry = tk.Entry(
            r2,
            textvariable=self.exam_scope_var,
            width=19,
            font=("Pretendard", 10),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#1c4732",
            selectbackground="#d8f3dc",
            selectforeground="#14281e",
            relief=tk.SOLID,
            bd=1,
            takefocus=True
        )
        self.exam_scope_entry.pack(side=tk.LEFT, padx=(0, 14))
        self.exam_scope_entry.bind("<Button-1>", lambda e: self.exam_scope_entry.focus_set())
        self.add_context_menu(self.exam_scope_entry)

        ttk.Label(r2, text="문항 수:", width=14, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.q_count_combo = ttk.Combobox(r2, values=["5문항", "10문항", "15문항", "20문항"], state="readonly", width=10)
        self.q_count_combo.set("10문항")
        self.q_count_combo.pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(r2, text="문제 유형:", width=9, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.q_format_combo = ttk.Combobox(r2, values=["객관식 (4지선다)", "서술형/손풀이", "객관식 + 서술형 혼합"], state="readonly", width=18)
        self.q_format_combo.set("객관식 (4지선다)")
        self.q_format_combo.pack(side=tk.LEFT)

        # Row 3
        r3 = ttk.Frame(form)
        r3.pack(fill=tk.X, pady=4)
        ttk.Label(r3, text="일일 공부 시간:", width=11, font=("Pretendard", 10, "bold")).pack(side=tk.LEFT)
        self.exam_hours_var = tk.StringVar(value="3시간")
        self.exam_hours_entry = tk.Entry(
            r3,
            textvariable=self.exam_hours_var,
            width=10,
            font=("Pretendard", 10),
            bg="#ffffff",
            fg="#0f172a",
            insertbackground="#1c4732",
            selectbackground="#d8f3dc",
            selectforeground="#14281e",
            relief=tk.SOLID,
            bd=1,
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

        ttk.Label(mat_ctrl, text="📌 지정 과목의 주차별 학습노트 및 강의자료를 선택하세요:", font=("Pretendard", 9)).pack(side=tk.LEFT)
        ttk.Button(mat_ctrl, text="📚 전범위 통합 마스터 바이블 생성", style="Secondary.TButton", command=self.run_master_bible_generation).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(mat_ctrl, text="✅ 전범위 선택", style="Secondary.TButton", command=self.select_all_exam_materials).pack(side=tk.RIGHT, padx=(4, 0))

        ttk.Button(mat_ctrl, text="❌ 전체 해제", style="Secondary.TButton", command=self.clear_all_exam_materials).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(mat_ctrl, text="➕ 외부 자료 추가...", style="Secondary.TButton", command=self.add_custom_exam_material).pack(side=tk.RIGHT, padx=(4, 0))

        # 스크롤 가능한 체크박스 캔버스
        canvas_wrap = ttk.Frame(mat_frame)
        canvas_wrap.pack(fill=tk.X)

        self.exam_mat_canvas = tk.Canvas(canvas_wrap, height=100, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1")
        mat_sb = ttk.Scrollbar(canvas_wrap, orient=tk.VERTICAL, command=self.exam_mat_canvas.yview)
        self.exam_mat_inner = ttk.Frame(self.exam_mat_canvas)
        self.exam_mat_inner.bind("<Configure>", lambda e: self.exam_mat_canvas.configure(scrollregion=self.exam_mat_canvas.bbox("all")))
        self.exam_mat_canvas.create_window((0, 0), window=self.exam_mat_inner, anchor="nw")
        self.exam_mat_canvas.configure(yscrollcommand=mat_sb.set)

        self.exam_mat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        mat_sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.exam_course_combo.bind("<<ComboboxSelected>>", lambda e: self.populate_exam_materials())

        btn_bar = ttk.Frame(form)
        btn_bar.pack(fill=tk.X, pady=(10, 0))

        SquareRoundButton(btn_bar, text="📅  학습 로드맵 생성", bg="#1c4732", hover_bg="#265e43", radius=8, height=36, font=("Pretendard", 10, "bold"), command=self.generate_period_roadmap_action).pack(side=tk.LEFT, padx=(0, 8))
        SquareRoundButton(btn_bar, text="📝  모의시험 및 해설 PDF", bg="#205c3b", hover_bg="#2a774d", radius=8, height=36, font=("Pretendard", 10, "bold"), command=self.generate_mock_exam_now_action).pack(side=tk.LEFT, padx=(0, 8))
        SquareRoundButton(btn_bar, text="✍️  답안 제출 및 채점", bg="#285943", hover_bg="#357357", radius=8, height=36, font=("Pretendard", 10, "bold"), command=self.open_grading_dialog_action).pack(side=tk.LEFT, padx=(0, 8))
        SquareRoundButton(btn_bar, text="⚡  치트시트 생성", bg="#3a6652", hover_bg="#4a8067", radius=8, height=36, font=("Pretendard", 10, "bold"), command=self.generate_cheatsheet_action).pack(side=tk.LEFT, padx=(0, 8))
        SquareRoundButton(btn_bar, text="📂  문제 폴더 열기", bg="#e2e8f0", hover_bg="#cbd5e1", fg="#14281e", radius=8, height=36, font=("Pretendard", 10, "bold"), command=self.open_exam_folder_action).pack(side=tk.LEFT)

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
            var = tk.BooleanVar(value=True)
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
        daily_hours = self.exam_hours_var.get().strip()

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

        scope = self.exam_scope_var.get().strip()
        exam_type = self.exam_type_combo.get()
        q_count_str = self.q_count_combo.get().replace("문항", "").strip()
        try:
            q_count = int(q_count_str)
        except Exception:
            q_count = 10
        q_fmt = self.q_format_combo.get()

        selected_files = [p for p, v in self.exam_material_vars.items() if v.get()]

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
                    messagebox.showinfo("모의시험 생성 완료", f"🎉 [{cname}] {exam_type} AI 커스텀 모의시험 및 해설지 PDF가 성공적으로 생성되었습니다!\n\n• 문항 수: {q_count}문항 ({q_fmt})\n• 시험지 위치: {pdf_path}")

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
                    messagebox.showinfo(
                        "치트시트 PDF 생성 완료",
                        f"🎉 [{cname}] {exam_type} 3분 핵심 치트시트(A4 1-Page)가 성공적으로 제작되었습니다!\n\n• 파일명: {os.path.basename(pdf_file)}\n• 저장 위치: {pdf_file}\n\n(마크다운 임시 파일은 자동 정리되었습니다.)"
                    )
                    if pdf_file.endswith(".pdf") and os.path.exists(pdf_file):
                        if sys.platform == "darwin":
                            subprocess.call(["open", pdf_file])
                        elif sys.platform == "win32":
                            os.startfile(pdf_file)
                        else:
                            subprocess.call(["xdg-open", pdf_file])

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

        ttk.Label(top_bar, text="📌 대상 과목:", font=("Pretendard", 10, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        self.tutor_course_combo = ttk.Combobox(top_bar, state="readonly", width=17, font=("Pretendard", 10))
        self.tutor_course_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.tutor_course_combo.bind("<<ComboboxSelected>>", lambda e: self.on_tutor_course_changed())

        # 담당 조교 닉네임 표시 및 원클릭 변경
        self.tutor_name_badge = ttk.Label(top_bar, text="전담 조교: 수석 조교", font=("Pretendard", 10, "bold"), foreground="#1c4732")
        self.tutor_name_badge.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(top_bar, text="✏️ 닉네임 변경", style="Secondary.TButton", command=self.rename_tutor_nickname_dialog).pack(side=tk.LEFT, padx=(0, 8))

        # 강의계획서 연동 버튼/상태
        self.tutor_syllabus_btn = ttk.Button(top_bar, text="📑 강의계획서 확인", style="Secondary.TButton", command=self.manage_course_syllabus_dialog)
        self.tutor_syllabus_btn.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(top_bar, text="🗑️ 대화 초기화", style="Secondary.TButton", command=self.clear_tutor_chat).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(top_bar, text="📂 자료 폴더", style="Secondary.TButton", command=self.open_tutor_course_folder).pack(side=tk.LEFT)

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

        self.tutor_chat_text = tk.Text(chat_wrap, wrap=tk.WORD, font=("Pretendard", 12), bg="#ffffff", fg="#0f172a", relief=tk.SOLID, bd=1, padx=14, pady=12, spacing1=2, spacing2=4, spacing3=2)
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

        self.tutor_input_text = tk.Text(input_wrap, height=3, wrap=tk.WORD, font=("Pretendard", 12), bg="#ffffff", fg="#0f172a", relief=tk.SOLID, bd=1, padx=10, pady=8)
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

            s_file = config_manager.get_course_syllabus(cname)
            if s_file and os.path.exists(s_file):
                resp = messagebox.askyesnocancel(
                    "강의계획서 관리",
                    f"[{cname}] 과목에 이미 강의계획서가 등록되어 있습니다:\n• {os.path.basename(s_file)}\n\n[예]를 누르면 현재 강의계획서를 열람합니다.\n[아니오]를 누르면 새 파일로 교체 등록합니다.",
                    parent=self.root
                )
                if resp is True:
                    if sys.platform == "darwin": subprocess.call(["open", s_file])
                    elif sys.platform == "win32": os.startfile(s_file)
                    else: subprocess.call(["xdg-open", s_file])
                    return
                elif resp is False:
                    pass  # 진행하여 새 파일 선택
                else:
                    return

            fpath = self.ask_open_file_safe(
                title=f"[{cname}] 강의계획서 (Syllabus) 파일 선택 (PDF 권장)",
                filetypes=[("PDF 문서 (*.pdf)", "*.pdf"), ("학습 문서", "*.pdf *.txt *.md *.docx"), ("모든 파일", "*.*")],
                parent=self.root
            )
            if fpath and os.path.exists(fpath):
                folder = self.get_course_folder(cname)
                cdir = config_manager.get_course_dir(folder)
                s_dir = os.path.join(cdir, "강의계획서")
                os.makedirs(s_dir, exist_ok=True)
                ext = os.path.splitext(fpath)[1]
                safe_cname = cname.replace(" ", "_")
                dest_name = f"{safe_cname}_강의계획서{ext}"
                dest_path = os.path.join(s_dir, dest_name)
                try:
                    import shutil
                    shutil.copy2(fpath, dest_path)
                    cdata = self.get_course_data(cname)
                    cdata["syllabus_path"] = os.path.join("강의계획서", dest_name)
                    config_manager.save_settings(self.settings)

                    short_s = (dest_name[:12] + "...") if len(dest_name) > 14 else dest_name
                    self.tutor_syllabus_btn.config(text=f"🟢 계획서 연동됨 ({short_s})", style="Secondary.TButton")
                    self.tutor_chat_text.insert(
                        tk.END,
                        f"\n🎉 [{dest_name}] 강의계획서가 성공적으로 연동되었습니다!\n• 이제 주차별 공식 진도, 중간/기말 시험 범위, 과제 및 출석 평가 배점이 마스터 기준으로 자동 적용됩니다.\n\n",
                        "system_info"
                    )
                    self.tutor_chat_text.see(tk.END)
                    if hasattr(self, "populate_course_table"):
                        self.populate_course_table()
                    messagebox.showinfo("강의계획서 연동 완료", f"[{cname}] 강의계획서가 성공적으로 등록되었습니다!\n파일: {dest_name}", parent=self.root)
                except Exception as e:
                    messagebox.showerror("업로드 오류", f"강의계획서 저장 중 오류가 발생했습니다: {e}", parent=self.root)
        except Exception as err:
            import traceback
            traceback.print_exc()
            messagebox.showerror("오류", f"강의계획서 선택 창을 여는 도중 문제가 발생했습니다: {err}", parent=self.root)

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

        if not course_sessions:
            course_sessions = []
            for w in range(1, 17):
                course_sessions.append({"week": w, "session_number": 1, "date": f"Week {w}-1", "day_name": ""})
                course_sessions.append({"week": w, "session_number": 2, "date": f"Week {w}-2", "day_name": ""})

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
        self.dash_kpi_notes.config(text=f"{notes_count}개 주차 완료 / 16주")
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
            if sys.platform == "darwin":
                subprocess.call(["open", target_pdf])
            elif sys.platform == "win32":
                os.startfile(target_pdf)
            else:
                subprocess.call(["xdg-open", target_pdf])
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
            messagebox.showinfo(
                "치트시트 PDF 생성 완료",
                f"🎉 [{cname}] 3분 치트시트(A4 1-Page)가 생성되었습니다!\n\n• 파일: {os.path.basename(pdf_file)}\n\n(마크다운 임시 파일은 자동 정리되었습니다.)"
            )
            if pdf_file.endswith(".pdf") and os.path.exists(pdf_file):
                if sys.platform == "darwin":
                    subprocess.call(["open", pdf_file])
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
            relief=tk.SOLID,
            bd=1,
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
            relief=tk.SOLID,
            bd=1,
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
            relief=tk.SOLID,
            bd=1,
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
            relief=tk.SOLID,
            bd=1,
            takefocus=True
        )
        self.api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.api_entry.bind("<Button-1>", lambda e: self.api_entry.focus_set())
        self.add_context_menu(self.api_entry)

        SquareRoundButton(api_row, text="💾 설정 저장", bg="#1c4732", hover_bg="#265e43", radius=8, height=32, font=("Pretendard", 9, "bold"), command=self.save_settings_action).pack(side=tk.RIGHT)

        # 과목 관리 테이블
        course_frame = ttk.LabelFrame(self.tab_settings, text=" 📚 수강 과목 관리 목록 ", padding="8")
        course_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cols = ("idx", "name", "tutor", "syllabus", "folder", "days", "time", "lang")
        self.course_tree = ttk.Treeview(course_frame, columns=cols, show="headings", height=8)
        self.course_tree.heading("idx", text="#")
        self.course_tree.heading("name", text="과목명")
        self.course_tree.heading("tutor", text="전담 조교")
        self.course_tree.heading("syllabus", text="강의계획서")
        self.course_tree.heading("folder", text="폴더명")
        self.course_tree.heading("days", text="수업 요일")
        self.course_tree.heading("time", text="수업 시간")
        self.course_tree.heading("lang", text="언어 모드")

        self.course_tree.column("idx", width=30, anchor=tk.CENTER)
        self.course_tree.column("name", width=150)
        self.course_tree.column("tutor", width=110)
        self.course_tree.column("syllabus", width=90, anchor=tk.CENTER)
        self.course_tree.column("folder", width=130)
        self.course_tree.column("days", width=80, anchor=tk.CENTER)
        self.course_tree.column("time", width=110, anchor=tk.CENTER)
        self.course_tree.column("lang", width=90, anchor=tk.CENTER)

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
            days = ", ".join(c.get("days", []))
            stime = c.get("start_time", "")
            etime = c.get("end_time", "")
            time_str = f"{stime} ~ {etime}" if stime else ""
            lang = LANG_CODE_TO_LABEL.get(c.get("language_mode", "both"), c.get("language_mode", "both"))
            self.course_tree.insert("", tk.END, values=(idx + 1, cname, tutor, syllabus_status, folder, days, time_str, lang))

    def save_settings_action(self):
        self.settings["semester"] = self.semester_var.get().strip()
        self.settings["semester_start_date"] = self.start_date_var.get().strip()
        self.settings["semester_end_date"] = self.end_date_var.get().strip()
        self.settings["gemini_api_key"] = self.api_key_var.get().strip()
        self.settings["courses"] = self.courses
        config_manager.save_settings(self.settings)

        # 배지 갱신
        has_key = len(self.settings["gemini_api_key"]) >= 10
        self.api_badge_label.config(
            text=" 🟢 Gemini API 연결됨 " if has_key else " 🔴 API Key 등록 필요 ",
            fg="#4ade80" if has_key else "#f87171"
        )
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

        # 강의계획서 파일 선택 (권장)
        ttk.Label(form, text="강의계획서 (Syllabus, 권장 — 미등록 시 슬라이드 기반 자율 학습):").pack(anchor=tk.W, pady=(0, 2))
        s_row = ttk.Frame(form)
        s_row.pack(fill=tk.X, pady=(0, 6))

        cur_syllabus = config_manager.get_course_syllabus(course_data.get("folder_name") or course_data.get("course_name", ""))
        syllabus_status_var = tk.StringVar(value=os.path.basename(cur_syllabus) if cur_syllabus else "미등록 (자율 학습 모드)")
        syllabus_to_copy = [None]

        s_lbl = ttk.Label(s_row, textvariable=syllabus_status_var, font=("Pretendard", 9), foreground="#059669" if cur_syllabus else "#64748b", width=28)
        s_lbl.pack(side=tk.LEFT, padx=(0, 6))

        def pick_syllabus():
            f = self.ask_open_file_safe(
                title="강의계획서(Syllabus) 파일 선택 (권장)",
                filetypes=[("PDF 문서 (*.pdf)", "*.pdf"), ("학습 문서", "*.pdf *.txt *.md *.docx"), ("모든 파일", "*.*")],
                parent=dlg
            )
            if f and os.path.exists(f):
                syllabus_to_copy[0] = f
                syllabus_status_var.set("선택됨: " + os.path.basename(f))
                s_lbl.config(foreground="#059669")

        ttk.Button(s_row, text="➕ PDF 선택", style="Secondary.TButton", command=pick_syllabus).pack(side=tk.LEFT)

        ttk.Label(form, text="폴더명:").pack(anchor=tk.W, pady=(0, 2))
        folder_var = tk.StringVar(value=course_data.get("folder_name", ""))
        folder_entry = tk.Entry(form, textvariable=folder_var, font=("Pretendard", 10), bg="#ffffff", fg="#0f172a", insertbackground="#1c4732", selectbackground="#d8f3dc", selectforeground="#14281e", relief=tk.SOLID, bd=1, takefocus=True)
        folder_entry.pack(fill=tk.X, pady=(0, 6))
        folder_entry.bind("<Button-1>", lambda e: folder_entry.focus_set())
        self.add_context_menu(folder_entry)

        ttk.Label(form, text="수업 요일 (쉼표로 구분, 예: 화, 목):").pack(anchor=tk.W, pady=(0, 2))
        days_var = tk.StringVar(value=", ".join(course_data.get("days", ["월"])))
        days_entry = tk.Entry(form, textvariable=days_var, font=("Pretendard", 10), bg="#ffffff", fg="#0f172a", insertbackground="#1c4732", selectbackground="#d8f3dc", selectforeground="#14281e", relief=tk.SOLID, bd=1, takefocus=True)
        days_entry.pack(fill=tk.X, pady=(0, 6))
        days_entry.bind("<Button-1>", lambda e: days_entry.focus_set())
        self.add_context_menu(days_entry)

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
            days_list = [d.strip() for d in days_var.get().split(",") if d.strip()]
            lcode = LANG_LABEL_TO_CODE.get(lang_combo.get(), "both")
            s_path = course_data.get("syllabus_path", "")

            if syllabus_to_copy[0]:
                try:
                    import shutil
                    cdir = config_manager.get_course_dir(fname)
                    s_dir = os.path.join(cdir, "강의계획서")
                    os.makedirs(s_dir, exist_ok=True)
                    ext = os.path.splitext(syllabus_to_copy[0])[1]
                    safe_cname = cname.replace(" ", "_")
                    dest_name = f"{safe_cname}_강의계획서{ext}"
                    dest_path = os.path.join(s_dir, dest_name)
                    shutil.copy2(syllabus_to_copy[0], dest_path)
                    s_path = os.path.join("강의계획서", dest_name)
                except Exception as ex:
                    print(f"Error copying syllabus: {ex}")

            new_c = {
                "course_name": cname,
                "folder_name": fname,
                "tutor_name": t_name,
                "syllabus_path": s_path,
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

        ttk.Button(btn_box, text="📋 전문 복사", style="Secondary.TButton", command=self.copy_legal_notice).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_box, text="📂 파일 열기", style="Secondary.TButton", command=self.open_legal_notice_file).pack(side=tk.LEFT)

        legal_txt_wrap = ttk.Frame(frame_legal)
        legal_txt_wrap.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.legal_text = tk.Text(legal_txt_wrap, wrap=tk.WORD, font=("Pretendard", 9), bg="#f8fafc", fg="#0f172a", relief=tk.SOLID, bd=1, padx=10, pady=10)
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
                shutil.copy2(f, dest)
                count += 1
            messagebox.showinfo("사진 추가 완료", f"{count}장의 칠판/필기 판서 사진이 '{course}/칠판사진' 폴더에 보관되었습니다!")

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
