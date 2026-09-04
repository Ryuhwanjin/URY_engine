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
APP_ICON_PNG = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAARGVYSWZNTQAqAAAACAABh2kABAAAAAEAAAAaAAAAAAADoAEAAwAAAAEAAQAAoAIABAAAAAEAAABAoAMABAAAAAEAAABAAAAAAEZRQrAAAAHNaVRYdFhNTDpjb20uYWRvYmUueG1wAAAAAAA8eDp4bXBtZXRhIHhtbG5zOng9ImFkb2JlOm5zOm1ldGEvIiB4OnhtcHRrPSJYTVAgQ29yZSA2LjAuMCI+CiAgIDxyZGY6UkRGIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyI+CiAgICAgIDxyZGY6RGVzY3JpcHRpb24gcmRmOmFib3V0PSIiCiAgICAgICAgICAgIHhtbG5zOmV4aWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20vZXhpZi8xLjAvIj4KICAgICAgICAgPGV4aWY6Q29sb3JTcGFjZT4xPC9leGlmOkNvbG9yU3BhY2U+CiAgICAgICAgIDxleGlmOlBpeGVsWERpbWVuc2lvbj4xMDI0PC9leGlmOlBpeGVsWERpbWVuc2lvbj4KICAgICAgICAgPGV4aWY6UGl4ZWxZRGltZW5zaW9uPjEwMjQ8L2V4aWY6UGl4ZWxZRGltZW5zaW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4Kwe07qQAAEGpJREFUeAHtW2tsHNd1PvPY94NcvkmRsijrQSlJazuyYztNm8ZuAjgtigQIECTNr/wp0CII8jMIgqIoCgRFUbRFC/VfjSBIWyd9JnYSJW4c25Fku7YrubYo2SEpiXqYb3LfO49+352d1ezuzJKUIlRGdai7M3Mf557z3XPPPffOSOQu3UXgLgL/nxHQblF5tu9MZBnkG7y/me7cQCP/ntfOFKi289ubEc4AeyazedVx9QXDrSKfr39lZvDeq9X7N8jTv/evfkvydJDsZrKaz531kB1OuxEqBhbxZvKVTmZHCwOJicJYPJMY12PmkJh6QTe0rGhGCirH0EEMV8N18ctWOyGopGkA1RUbmjRwRbIrjusWxXLW7Zq1XN+qXqutrF8rXV5bBstaky3BqDcTwdgWiJ0AQLETSCkkNer97588nJkYfsxMmb+m6cYhTdeGNE2Liw52iqPPdtv+wXInFOBHlkDTddyG67orYjsXrFrjxcriyk9Wzl58E6VUnBZRQaoiEZRI8jlHVaDy6WbSc/dO7O8/PP4HZjL+O5qp5xS+FAZpe6yjurjJ/CbQAF+B7tpOya41ntl8+9rfrJ+7fA5cCVW5mQhIKHEuRxG7oPJZJHPkQwce6zsw9nexVPzDUDghDoBViv+yRjlKjF75BB7JQYIFGonY0eRg7olEIbtYurT8DuVGooCR06EXADR7pfzwA/d+JDs1fBzmPgykPZYovKOIahIIXcvEssnHY/nUbHlx9RfIpRXTAghCF0UBwEYZpGR6vG+if2byuGYaYy5H/U4nWISmwx2n4w86VetEfaNUhMiEp9G8tmlARcOIHp8WoPfP3PMFPWHub408Wd3hibICgom+g+NfpA5NXTgduqgXAGZ6qG80lkt8Wi1GXU3v7AwXC6iRTvxuamJgCpLS0rmEdzn9MFQIisrP7h85phn65HvC9CF0G2Eq6IY+mNs38kjlyuo8yqgTdWtbEXoBoJv55IdUREJP+14kjHcsk3wYoj+FFApA2BSguTCljFjsqFpm8PCeJKwKesyYgex06NSpS98oC9Bj6XQO0d0etbTcBguw7BuWiH7E0Ltku2XMXSxa4D2WGsn1V97dWm+C0MY3DAA6Ci0xnOrHctKnory2Ju0PNpZGhKUh7qW9XusJVQ1Dl6MHpmXf5LgQiPNzl2T+8pVWlR3dgI+OKFDvBRyXRE1ysb7MAABYAN8dO0ExE4k8lE/1iqQdKL5valzumRoTB0tP3IyJq3EPw568P18Zh4xc5KEwn0tLOpWQN2Z/IalEXD76yP2yvLJfyrWqkpAWwRuX9cGN/FwMp/eEBd22EO/ocu78vLy7stobBCznRjLR15Sjy8yiLEC0uIkdnbca+Ep0XinosfcflscfelRy6ZwsXL8kK6U1qVuWAsSG0LQgHX+mYUgykZCBTJ/MvrMgr507J1NjE9JoWPLK62/Jbz3ysAwM5KVYKUkFQNSdOhTH1EBbQzOU1cRjMRntH5apoQlZXLkm39eflxMvnO6e2AFB1fSKmblmFi2AiZgq6gTAryCGie0s6/aY/xwd/js2/T7JJLNy/95D4qBJDUpV6jUAUcNmzVIKuK4uK8U1OTs3K8l4Sv7iy1+T7/z4aZnZOy3jAOKHL/1URgoF+fChhwBmUlBddW3ohsQNE5aSkoQJcTHlEvG0ZPD8785PPVVa6jS1Cl6oka5xT0PiUxt1AtAqxG4vodGcewDAymbclL///r/JybNn5AtP/Lb85v2PwkYdqRcrkoCQtm7K4vJVubh0HQuwIzOTB+T3PnpU0pmCrG0UZRPpU489IAcn9sjp2TPyyvn/llwqIwcn98tgtiB2tS62gSjWSEq5UZfvPPeM/OD5n8vjH3lIzJgJjah9DwRgpYhlGNVS+R0BoCrC/GLUvZf+Ophze/Avz/2n/Onvf1nuO3yEcbhUKjVZ3tyQoYKJ+Z6XA5P3ytF7Dko+lQVgGF3MYXHrakpwuovbkMF8QZ548Ddg/mUp1WA56HttfU2W11Ykn8mIhtHvy/XL5z7xKYnBOL/73NMyvXdSyddLRmIDCBjah1KkBejiNsui0WXHtmOr+T1eGJSBfB7K2dKfSsnU8Dj6RgU4Mnp9umPLqsvc1Tmp1htyZJrLs8pWV4785OCojBVGJJVMY2VxZCiThSUwkqW3x1gjT48nZBR90fvTOpsuUvEI/4EMuq9Ld41IAFy6WerOFEV06SSMokNTQLq6toQ1HQ4PIw2JpQGHuFUtyWpxU9ZKG5JOJGVmYj8awTkCFDV6uI4PjcjslQU5tzgvfemsDOb64FfSABcrCyqVYBmJWFyG+gcBOvpip758vWREmebCi3qkrFt13syIBADMt51eHg/0wH9KHk3WS5vK/AmIA+uAbpJOpqQvk5dDe6YlS7/AIKi5Qvg8xuDdxzH6bL+4cl0ur12XWo3He1z8YAFQYd/IHjwO4ckn1akHhJ/Vee0FDuqGAXCDfwviTq43ntUI8ocd4Tozca9oe+AboCCJyxD/aKocOUvNf1XEwpbwyoKQncdqUpjKqwo3TJwxrA6eBM5WvDzTUZ2ibi8tVZ2ATs2+m5cwAPwamtKrF+9mTVUFXVAfi4ozMrxJIlAWpk0nqUAKmb4t++XbyghRvKHwW7RfewGAmlSklzJhwKI+szua8bGttnoI1FXTuqMR2rSRasMAgf+8utvPU9aLhiAaALZhW6+fNjnaHpSyqMR/IfXpG1rUk5fHo1W346bFx+en+gIMIX22NWV5tP49o8g2PlEPvjxh5ew7SP6zrwydnNpIBSs17/267WbTLGx12roJ4bCzrEgL4JxTTkhB3ItZuBBKgWARMoKP5BhDcKPOLOk8OijgH712ZOhXUxOfRkcL8FJH8xuP28iPCXWL1BSmkwtlZZjQSoEKKnxAu4FCTi5cuhgoCdwqBL32zFW6M0/l+0g08wPNdnsbDQBWHDXBlILoNeraGhYIc0MuTzJmBPN86dTwutgEjcrPXntZ5i9elFgyibXeUMsmqyk91Y/fKMiKBc3CKLmC+TftA/x+oq5KNhSyXCnaVFghEbhvAsHwlamOkJim25/Pimu48pdPPSln335LljdWsde3JRaPq+kRhp0Hx40S6qn673X1GoX+RvoAKNTiHdoSmcqU/VFWOOAoGvOawY/n3BhO8o97BkdWEQqfX5yXJOp88PB9OEAx5PCBffIOzhGeOvk0NjkxRIoZGUj0y8NHflUOT09LA/uGdqKmJA8EX28vL/y3hwGERoIeF8bbvhmF80W8o7RGKR0RTmwwurOX5hD/11XMz+1EDVvYteJGcx+Qlv1jU7IHmx7basizJ0/Lof175bWzswomVJf16qZcXV+SJ7/3r/L5jz0hX/zMZ8WqexbjicGR8fYRKnrcRkalgxI0XIkwH+BD7GsX3hK5PBJ78eSrsrlZxI6PxqRJIZtXO7ciNi9b1TJGHnMdCj86c7/8+tFjsndsL8JhR/7o+N/Kt//jexLDnn567x65en1JdFOH6RvSl8/IAx88Ij94+UV588IF7ufbZDDR18XLV+Xl/3pDHY21FYY9eNFSWEm0BQBlBN3EwMejuz3fTFMQHlXFsFPDXlVGB4ZVaoXD6vU1FdDFqpXkZ6dfkL/+9rfk2ZdOydBAv+I/OjKAs701sXCSRCvi9Bkq9En6A0n5w2/8sXzjS1+RB+87hnkEz6wn1RS7cvVd7DgTyqf0kpFliOnp0kMp0gdgdBtUPVp9j58Bz80t71f/6s/l4488KvtwskMQ+vM5NUu3yiW5urwk5+YX5MSpF+TUmddVfQpPX4FoA6Ouy/DgAA5SKpLKpHCEBrCgbDoTl9xwWo4/9U8Sx2HK4rUrcn5hTv75JycU6Pw2gLFAT0IxAPUdSZdKkQAANZxs7gABVOFcf/blU/LjUz8XEyZM5VJY1uj+qjgbLFeraoPDg5EYrIX7ekpSLntl6TS2yOjOpUPFUZCGD2u4m7QsR37lyCH51j8+Lc+8+DxWj4YCJo5pw2mwne4KGFiAY7cAUFnBn/bJ5ZUoSB3LrtKxeb34wEVfE1AslUzAk5tqy7tZ3JINHILU4QRjsBKWcar4vptjV4dzu7hwDWYPqFDAo69Gw8ZZ4QZnjMrLptMyPFQAzwbamzhbSKgTqJ3KxSkAPfipTCiFAcCKmtuwy5DRs7BovbvlYGP80SqYvEUQmSE8+DbolVffkCWc7ceVVbg4M8S+H1Zg1XCYQhQAziB8xS7Goq0vujC3YZWUWF4Jbm9QJwC+mBRgC9DhSIZZt4foA4o4PT7xo5OyurKOVYDnh4YMFvpxFI6jMCzFPFafwosXTh8uf7sijj7WSrvubDXbdTHoPF9gPb5HT6LDdHI4/2m42RTN6HYRDzs3t4py4e0FtQJQeb5Awad2eMfgmWB/Nidz84uyVSwrx7ljWTjfXCmXllaftLdqS3jiVPA/qVNswgCgY0xZdt1I7xn6JELXwdtoBEoIThW+IZqbW5QLFxZkaWlVSmV85UY/gAXM5IEgpsv8/OXdAYBJBG96vTx//Umn4fBTGX46568Iqu+wVYDDjeNcKSEwn4fHOXQ7p4GSAj90gibMnEHV2Tdmkc5jT2Cq940GlknuIXY7DdSiYtuXGuUGpwD16jLlMADo+pkaVrV+xkjFP97dDKW3iXhUrquoEkLAGVbxes2XmmVdxLzIKYppVLPOoA3N3terjUUYAIyaeCqp1de3Tpu5dAN9RL5ZaeN2Ox7Qua+2D0RbN5HKAxfswGprW6ea9alTV0TYuQqwLpFiRbd4cXUW0cirCnh29B5KyjAs682txXVaAIk6Ubc2igKAjoKIVasrW99EKBkKfhunO+0BEtfWKt+Ed6Xzoy7UqQuAsFWAqtDq1LeCtdXiFSyHY0bCPNLa4LDGHUzcPdqV+g9Xzy4ch5hU3P9mmEC0URQAHHGW0UcYjfXq6/GBzEF8fHjProORtu5u/wN3k/ho+qX1c4tfd+rWJnrk2k8AuAR2WXIvAGgFLDccC1HB2uYL8XwmgQ8nZhC7e+262KH2/wVBUkaV+LWcSuO76+cX/8QqVleQQe9P5RkKt63/eFYUBQALfY9JzrpjOXbl2vopRCWvGHHTBNJDACKlNjKooPpnq26QVe4v7werglIYfXITxR5t/CeKuv1cbWnzz9bfuvQPGHkqHFSeVhA6XGzfiwgQ/6MEv7PjFe+8GZ/hG6qBzERqKH9UT8Xfp5vmNDYtoxAIHyNpaTCNQzITrhNLNz52UftctNotYU+OD6UcKMxjAwsacG9SwWq04Vruu/gWYc4q19+sLhf/p7a2uQj2vqOjwjR5f+77g9klwXYAsAEVpuIEgJ+aMHG/4K8g5KEcppk0k0Yc77/jelyP4XgI59y6i48TGMaReEa6U1LHWNjJOAiG8UkJQtkGvpyqYaSrVhUHDN7cplPzPTuvfJ/O5JfzGqk8ynYsEAWnQ/SVp8J8Vk4SV1oKldy5gqh8C0RzpsJMBIFKcvSZfBB4H2r2yG/RbgVmfSoapjzzfRCCfIP3rY53cRNUgvdB5QkAlWfygeB9sA0eo+lWhWP7sMQeg7yD99HSdJd0KuIDEHbtbn035y4CdxHYDoH/Ba4DOvfj3lbvAAAAAElFTkSuQmCC"

class CinematicSplashScreen:
    """
    🌿 URY Engine — 미니멀 논-사이버네틱 시네마틱 스플래시 오프닝
    - 2번 앱 아이콘과 100% 동일한 포레스트 그린(#1c4732) & 웜 아이보리(#fbf9f4) 팔레트
    - 타이핑: "Ultimate Result for You" (U, R, Y 볼드 강조)
    - 중간 문자 소멸 후 중앙 모노그램 [ U   R   Y ] 완성 및 메인 화면 자동 전환
    - 순수 미니멀리즘 (AI 체크박스, 로딩바, 스킵버튼 완전 배제)
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
        self.char_items = []
        self.idx = 0
        self.cur_x = 75
        self.base_y = h // 2
        
        # 세이지 타이핑 커서
        self.cursor_id = self.canvas.create_line(self.cur_x, self.base_y - 14, self.cur_x, self.base_y + 14, fill="#82a585", width=2)
        
        self.win.after(100, self.step_type)
        
    def step_type(self):
        if self.idx < len(self.full_text):
            char = self.full_text[self.idx]
            is_initial = (self.idx in (0, 9, 20)) # U, R, Y
            
            font = ("Helvetica Neue", 25, "bold") if is_initial else ("Helvetica Neue", 22, "normal")
            color = "#fbf9f4" if is_initial else "#cbdcd0"
            
            item = self.canvas.create_text(self.cur_x, self.base_y, text=char, fill=color, font=font, anchor=tk.W)
            self.char_items.append((item, is_initial, char))
            
            bbox = self.canvas.bbox(item)
            char_w = (bbox[2] - bbox[0]) if bbox else 14
            if char == ' ':
                char_w = 12
            self.cur_x += char_w + 1
            
            self.canvas.coords(self.cursor_id, self.cur_x + 1, self.base_y - 13, self.cur_x + 1, self.base_y + 13)
            self.idx += 1
            self.win.after(34, self.step_type)
        else:
            self.canvas.delete(self.cursor_id)
            self.win.after(320, self.step_collapse)
            
    def step_collapse(self):
        for item, _, _ in self.char_items:
            self.canvas.delete(item)
                
        w, h = 580, 340
        self.mono_id = self.canvas.create_text(w//2, h//2 - 14, text="U   R   Y", fill="#fbf9f4", font=("Helvetica Neue", 48, "bold"))
        self.sub_id = self.canvas.create_text(w//2, h//2 + 38, text="U L T I M A T E   R E S U L T   F O R   Y O U", fill="#82a585", font=("Helvetica Neue", 9, "bold"))
        
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

        # 🌿 2번 앱 아이콘과 100% 통일된 포레스트 그린 테마 시스템
        is_dark = (getattr(self, "theme_mode", "light") == "dark")
        accent = getattr(self, "theme_accent", "#1c4732")

        if is_dark:
            bg_main = "#0e1f16"        # 다크 포레스트 배경
            bg_card = "#163024"        # 카드 배경
            bg_header = "#11261d"      # 헤더 배경
            border_c = "#26543e"       # 카드 보더
            fg_main = "#fbf9f4"        # 웜 아이보리 텍스트
            fg_muted = "#8fa896"       # 세이지 그레이
            tab_inactive = "#1a382b"   # 비활성 탭
            tab_active = accent        # 활성 탭 (사용자 지정 포인트)
            tab_active_fg = "#ffffff"
            btn_primary = accent
            btn_primary_act = "#235c41"
        else:
            bg_main = "#f4f7f5"        # 산뜻한 라이트 세이지 틴트
            bg_card = "#ffffff"        # 퓨어 화이트 카드
            bg_header = "#1c4732"      # 아이콘 원색 매칭 딥 포레스트 헤더
            border_c = "#d4e0d8"       # 부드러운 보더
            fg_main = "#14281e"        # 포레스트 차콜 텍스트
            fg_muted = "#566b5e"       # 차분한 세이지 그레이
            tab_inactive = "#e2e8f0"   # 비활성 탭
            tab_active = accent        # 활성 탭 (포레스트 그린)
            tab_active_fg = "#ffffff"
            btn_primary = accent
            btn_primary_act = "#143324"

        self.root.configure(bg=bg_main)

        # 폰트 계층
        f_title = ("Pretendard", 11, "bold")
        f_body = ("Pretendard", 10)
        f_small = ("Pretendard", 9)

        style.configure(".", background=bg_main, foreground=fg_main, font=f_body)
        style.configure("TFrame", background=bg_main)
        style.configure("Card.TFrame", background=bg_card, relief=tk.SOLID, borderwidth=1)
        style.configure("TLabel", background=bg_main, foreground=fg_main, font=f_body)
        style.configure("Card.TLabel", background=bg_card, foreground=fg_main, font=f_body)
        style.configure("Muted.TLabel", background=bg_main, foreground=fg_muted, font=f_small)
        style.configure("CardMuted.TLabel", background=bg_card, foreground=fg_muted, font=f_small)

        # 헤더
        style.configure("Header.TFrame", background=bg_header)
        style.configure("HeaderTitle.TLabel", background=bg_header, foreground="#fbf9f4", font=("Pretendard", 14, "bold"))
        style.configure("HeaderSub.TLabel", background=bg_header, foreground="#d8f3dc", font=f_small)

        # 모던 알약형 플로팅 세그먼트 탭
        style.configure("TNotebook", background=bg_main, borderwidth=0)
        style.configure("TNotebook.Tab", font=f_title, padding=[18, 9], background=tab_inactive, foreground=fg_muted)
        style.map("TNotebook.Tab",
                  background=[("selected", tab_active), ("active", "#cbd5e1" if not is_dark else "#224737")],
                  foreground=[("selected", tab_active_fg), ("active", fg_main)])

        # 버튼들
        style.configure("Primary.TButton", font=f_title, background=btn_primary, foreground="#ffffff", borderwidth=0)
        style.map("Primary.TButton", background=[("active", btn_primary_act), ("disabled", "#94a3b8")])

        style.configure("Action.TButton", font=("Pretendard", 11, "bold"), background="#10b981", foreground="#ffffff", borderwidth=0)
        style.map("Action.TButton", background=[("active", "#059669"), ("disabled", "#94a3b8")])

        style.configure("Secondary.TButton", font=f_body, background="#e2e8f0" if not is_dark else "#224737", foreground=fg_main, borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#cbd5e1" if not is_dark else "#2a5743")])

        style.configure("Danger.TButton", font=f_body, background="#ef4444", foreground="#ffffff", borderwidth=0)
        style.map("Danger.TButton", background=[("active", "#dc2626"), ("disabled", "#94a3b8")])

        # 트리뷰 (과목 테이블)
        style.configure("Treeview.Heading", font=("Pretendard", 10, "bold"), background="#f1f5f9" if not is_dark else "#1a382b", foreground=fg_main)
        style.configure("Treeview", font=f_body, rowheight=28, background=bg_card, fieldbackground=bg_card, foreground=fg_main)
        style.map("Treeview", background=[("selected", "#d8f3dc" if not is_dark else "#235c41")], foreground=[("selected", "#14281e" if not is_dark else "#ffffff")])

        # 라벨프레임
        style.configure("TLabelframe", background=bg_card, bordercolor=border_c, borderwidth=1)
        style.configure("TLabelframe.Label", background=bg_card, foreground=fg_main, font=f_title)

    def create_header_card(self):
        self.header_frame = ttk.Frame(self.root, style="Header.TFrame", padding="16 12 16 12")
        self.header_frame.pack(fill=tk.X)

        left = ttk.Frame(self.header_frame, style="Header.TFrame")
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text="🌿 URY Engine v0.2", style="HeaderTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(left, text="Academic Management Studio · Ultimate Result for You", style="HeaderSub.TLabel").pack(anchor=tk.W)

        right = ttk.Frame(self.header_frame, style="Header.TFrame")
        right.pack(side=tk.RIGHT, fill=tk.Y)

        # ☀️/🌙 실시간 듀얼 테마 토글 버튼
        is_dark = (getattr(self, "theme_mode", "light") == "dark")
        btn_text = " ☀️ 라이트 모드 " if is_dark else " 🌙 다크 모드 "
        self.theme_toggle_btn = tk.Button(
            right,
            text=btn_text,
            font=("Pretendard", 9, "bold"),
            bg="#26543e" if is_dark else "#143324",
            fg="#d8f3dc",
            activebackground="#2f664b",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.toggle_theme
        )
        self.theme_toggle_btn.pack(side=tk.LEFT, padx=(0, 8))

        sem_text = self.settings.get("semester", "2026년 2학기")
        self.sem_badge_label = tk.Label(right, text=f" 📅 {sem_text} ", font=("Pretendard", 9, "bold"), bg="#143324" if not is_dark else "#1a382b", fg="#d8f3dc", relief=tk.FLAT, padx=8, pady=4)
        self.sem_badge_label.pack(side=tk.LEFT, padx=(0, 8))

        api_key = self.settings.get("gemini_api_key", "").strip()
        has_key = len(api_key) >= 10
        api_text = " 🟢 Gemini API 연결됨 " if has_key else " 🔴 API Key 등록 필요 "
        api_fg = "#4ade80" if has_key else "#f87171"
        self.api_badge_label = tk.Label(right, text=api_text, font=("Pretendard", 9, "bold"), bg="#143324" if not is_dark else "#1a382b", fg=api_fg, relief=tk.FLAT, padx=8, pady=4)
        self.api_badge_label.pack(side=tk.LEFT)

    def create_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 12))

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
        # 상단 안내 바
        banner = ttk.Frame(self.tab_studio)
        banner.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(banner, text="학습노트 스튜디오", font=("Pretendard", 11, "bold"), foreground=getattr(self, "theme_accent", "#1c4732")).pack(side=tk.LEFT)
        ttk.Label(banner, text="— 과목 지정 · 강의 음성 기록 · 슬라이드 연동 · 출판용 PDF 생성", style="Muted.TLabel").pack(side=tk.LEFT, padx=6)

        main_paned = ttk.PanedWindow(self.tab_studio, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        top_container = ttk.Frame(main_paned)
        main_paned.add(top_container, weight=3)

        # 3단계 카드 배치 (그리드 레이아웃)
        top_container.columnconfigure(0, weight=1)
        top_container.columnconfigure(1, weight=1)
        top_container.columnconfigure(2, weight=1)

        # -------------------------------------------------------------
        # Step 1: 대상 과목 및 수업 정보
        # -------------------------------------------------------------
        card1 = ttk.LabelFrame(top_container, text=" 01 · 대상 과목 및 수업 정보 ", padding="10")
        card1.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        ttk.Label(card1, text="대상 과목:", font=("Pretendard", 9, "bold")).pack(anchor=tk.W, pady=(0, 2))
        self.studio_course_combo = ttk.Combobox(card1, state="readonly", font=("Pretendard", 10))
        self.studio_course_combo.pack(fill=tk.X, pady=(0, 8))
        self.studio_course_combo.bind("<<ComboboxSelected>>", lambda e: self.on_studio_course_changed())

        date_header_row = ttk.Frame(card1)
        date_header_row.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(date_header_row, text="수업 날짜 (YYYY-MM-DD):", font=("Pretendard", 9, "bold")).pack(side=tk.LEFT)

        date_btn_box = ttk.Frame(date_header_row)
        date_btn_box.pack(side=tk.RIGHT)
        ttk.Button(date_btn_box, text="◀", width=3, style="Secondary.TButton", command=lambda: self.adjust_studio_date(-1)).pack(side=tk.LEFT, padx=1)
        ttk.Button(date_btn_box, text="오늘", width=4, style="Secondary.TButton", command=lambda: self.studio_date_var.set(datetime.now().strftime("%Y-%m-%d"))).pack(side=tk.LEFT, padx=1)
        ttk.Button(date_btn_box, text="▶", width=3, style="Secondary.TButton", command=lambda: self.adjust_studio_date(1)).pack(side=tk.LEFT, padx=1)

        self.studio_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.studio_date_entry = tk.Entry(
            card1,
            textvariable=self.studio_date_var,
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
        self.studio_date_entry.pack(fill=tk.X, pady=(0, 8))
        self.studio_date_entry.bind("<Button-1>", lambda e: self.studio_date_entry.focus_set())
        self.add_context_menu(self.studio_date_entry)

        ttk.Label(card1, text="수업 주차:", font=("Pretendard", 9, "bold")).pack(anchor=tk.W, pady=(0, 2))
        self.studio_week_combo = ttk.Combobox(card1, values=[f"{w}주차" for w in range(1, 17)], state="readonly", font=("Pretendard", 10))
        self.studio_week_combo.set("1주차")
        self.studio_week_combo.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(card1, text="출력 언어 모드:", font=("Pretendard", 9, "bold")).pack(anchor=tk.W, pady=(0, 2))
        self.studio_lang_combo = ttk.Combobox(card1, values=LANG_OPTIONS, state="readonly", font=("Pretendard", 9))
        self.studio_lang_combo.set(LANG_OPTIONS[0])
        self.studio_lang_combo.pack(fill=tk.X)

        # -------------------------------------------------------------
        # Step 2: 음성 녹음 자료 선택 (음성 부재 대비 옵션 포함)
        # -------------------------------------------------------------
        card2 = ttk.LabelFrame(top_container, text=" 02 · 강의 음성 기록 ", padding="10")
        card2.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        self.no_audio_var = tk.BooleanVar(value=False)
        self.no_audio_check = ttk.Checkbutton(
            card2,
            text="☑ 음성 녹음 없음 (슬라이드 집중 분석 모드)",
            variable=self.no_audio_var,
            command=self.toggle_no_audio_mode
        )
        self.no_audio_check.pack(anchor=tk.W, pady=(0, 6))

        self.audio_select_frame = ttk.Frame(card2)
        self.audio_select_frame.pack(fill=tk.BOTH, expand=True)

        audio_btn_row = ttk.Frame(self.audio_select_frame)
        audio_btn_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(audio_btn_row, text="📂 오디오 찾기...", style="Secondary.TButton", command=self.browse_studio_audio).pack(side=tk.LEFT, padx=(0, 4))
        self.rec_btn = ttk.Button(audio_btn_row, text="🔴 실시간 녹음", style="Secondary.TButton", command=self.toggle_realtime_recording)
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
        self.studio_audio_entry.pack(fill=tk.X, pady=(0, 6))
        self.studio_audio_entry.bind("<Button-1>", lambda e: self.studio_audio_entry.focus_set())
        self.add_context_menu(self.studio_audio_entry)

        ttk.Label(self.audio_select_frame, text="감지된 녹음 파일 (수신함 / 과목 폴더):", font=("Pretendard", 8, "bold"), foreground="#64748b").pack(anchor=tk.W)
        self.audio_listbox = tk.Listbox(self.audio_select_frame, height=4, font=("Pretendard", 9), bg="#ffffff", relief=tk.SOLID, bd=1)
        self.audio_listbox.pack(fill=tk.BOTH, expand=True)
        self.audio_listbox.bind("<<ListboxSelect>>", self.on_audio_listbox_select)

        self.no_audio_hint = ttk.Label(
            card2,
            text="💡 슬라이드 집중 독학 모드가 켜졌습니다.\n음성 녹음 없이도 공식 슬라이드 내용만을\n정밀 파싱하여 체계적인 시험 강의노트를 생성합니다.",
            font=("Pretendard", 9),
            foreground="#0284c7"
        )

        # -------------------------------------------------------------
        # Step 3: 연계 강의자료(슬라이드 PDF) 선택
        # -------------------------------------------------------------
        card3 = ttk.LabelFrame(top_container, text=" 03 · 강의 슬라이드 연동 ", padding="10")
        card3.grid(row=0, column=2, sticky="nsew", padx=4, pady=4)

        slide_btn_row = ttk.Frame(card3)
        slide_btn_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(slide_btn_row, text="➕ 자료/슬라이드 추가...", style="Secondary.TButton", command=self.browse_studio_slides).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(slide_btn_row, text="📷 칠판 판서 사진...", style="Secondary.TButton", command=self.browse_blackboard_photo).pack(side=tk.LEFT)
        ttk.Button(slide_btn_row, text="🔄 새로고침", style="Secondary.TButton", command=self.refresh_studio_slides).pack(side=tk.RIGHT)


        ttk.Label(card3, text="분석에 포함할 슬라이드 파일 (체크):", font=("Pretendard", 8, "bold"), foreground="#64748b").pack(anchor=tk.W, pady=(0, 2))

        # 슬라이드 체크박스 목록용 스크롤 프레임
        slide_canvas_frame = ttk.Frame(card3)
        slide_canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.slide_canvas = tk.Canvas(slide_canvas_frame, bg="#ffffff", highlightthickness=1, highlightbackground="#e2e8f0")
        slide_sb = ttk.Scrollbar(slide_canvas_frame, orient=tk.VERTICAL, command=self.slide_canvas.yview)
        self.slide_inner_frame = ttk.Frame(self.slide_canvas)
        self.slide_inner_frame.bind("<Configure>", lambda e: self.slide_canvas.configure(scrollregion=self.slide_canvas.bbox("all")))
        self.slide_canvas.create_window((0, 0), window=self.slide_inner_frame, anchor="nw")
        self.slide_canvas.configure(yscrollcommand=slide_sb.set)

        self.slide_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        slide_sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.slide_check_vars = {} # {pdf_path: BooleanVar}

        # -------------------------------------------------------------
        # Action Card: 생성 실행 & 실시간 상태 & 결과 뷰어
        # -------------------------------------------------------------
        bottom_container = ttk.Frame(main_paned)
        main_paned.add(bottom_container, weight=4)

        action_bar = ttk.Frame(bottom_container)
        action_bar.pack(fill=tk.X, pady=(6, 6))

        self.generate_studio_btn = ttk.Button(
            action_bar,
            text="학습노트 및 출판용 PDF 생성",
            style="Action.TButton",
            command=self.execute_studio_generation
        )
        self.generate_studio_btn.pack(side=tk.LEFT, ipady=6, padx=(0, 8))

        self.studio_stop_btn = ttk.Button(
            action_bar,
            text="작업 중단",
            style="Danger.TButton",
            state=tk.DISABLED,
            command=self.abort_studio_generation
        )
        self.studio_stop_btn.pack(side=tk.LEFT, ipady=6, padx=(0, 8))

        self.studio_open_pdf_btn = ttk.Button(
            action_bar,
            text="출판용 PDF 열기",
            style="Primary.TButton",
            state=tk.DISABLED,
            command=self.open_last_generated_pdf
        )
        self.studio_open_pdf_btn.pack(side=tk.LEFT, ipady=6, padx=(0, 8))

        self.studio_open_folder_btn = ttk.Button(
            action_bar,
            text="📂 [강의노트 폴더 열기]",
            style="Secondary.TButton",
            command=self.open_studio_notes_folder
        )
        self.studio_open_folder_btn.pack(side=tk.LEFT, ipady=6, padx=(0, 8))

        self.studio_clear_log_btn = ttk.Button(
            action_bar,
            text="🧹 [콘솔 비우기]",
            style="Secondary.TButton",
            command=self.clear_studio_log
        )
        self.studio_clear_log_btn.pack(side=tk.LEFT, ipady=6)

        # 프로그레스바 및 상태/ETA 메시지
        status_row = ttk.Frame(bottom_container)
        status_row.pack(fill=tk.X, pady=(2, 4))

        self.studio_progress = ttk.Progressbar(status_row, mode="determinate", length=220)
        self.studio_progress.pack(side=tk.LEFT, padx=(0, 10))

        self.studio_status_var = tk.StringVar(value="원하는 음성 및 슬라이드를 선택한 후 생성 버튼을 누르세요.")
        ttk.Label(status_row, textvariable=self.studio_status_var, font=("Pretendard", 9, "bold"), foreground="#475569").pack(side=tk.LEFT)

        self.studio_eta_var = tk.StringVar(value="")
        ttk.Label(status_row, textvariable=self.studio_eta_var, font=("Pretendard", 9, "bold"), foreground="#2563eb").pack(side=tk.RIGHT)

        # 실시간 진행 로그 콘솔
        console_box = ttk.LabelFrame(bottom_container, text=" 💻 실시간 생성 로그 및 소요 시간 (Live Logs & ETA) ", padding="6")
        console_box.pack(fill=tk.BOTH, expand=True)

        txt_wrap = ttk.Frame(console_box)
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
        txt_sb = ttk.Scrollbar(txt_wrap, orient=tk.VERTICAL, command=self.studio_log_text.yview)
        self.studio_log_text.config(yscrollcommand=txt_sb.set)

        self.studio_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        txt_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.add_context_menu(self.studio_log_text)

        # 로그 컬러 태그
        self.studio_log_text.tag_config("time", foreground="#94a3b8")
        self.studio_log_text.tag_config("step", foreground="#38bdf8", font=(term_font[0], term_font[1], "bold"))
        self.studio_log_text.tag_config("success", foreground="#4ade80", font=(term_font[0], term_font[1], "bold"))
        self.studio_log_text.tag_config("warning", foreground="#facc15")
        self.studio_log_text.tag_config("error", foreground="#f87171", font=(term_font[0], term_font[1], "bold"))
        self.studio_log_text.tag_config("highlight", foreground="#c084fc")
        self.studio_log_text.tag_config("normal", foreground="#e2e8f0")

        self.append_studio_log("준비 완료: 음성 파일과 슬라이드 자료를 선택하고 [⚡ 맞춤형 학습노트 생성 시작]을 클릭하세요.", "normal")

    def append_studio_log(self, text, tag="normal"):
        if not hasattr(self, "studio_log_text"):
            return
        self.studio_log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("[%H:%M:%S] ")
        self.studio_log_text.insert(tk.END, timestamp, "time")

        if tag == "normal":
            if "Step" in text or "단계" in text or "과목:" in text:
                tag = "step"
            elif "✅" in text or "성공" in text or "🎉" in text:
                tag = "success"
            elif "⚠️" in text or "주의" in text:
                tag = "warning"
            elif "❌" in text or "오류" in text or "실패" in text:
                tag = "error"
            elif "•" in text or "📌" in text or "📄" in text:
                tag = "highlight"

        self.studio_log_text.insert(tk.END, f"{text}\n", tag)
        self.studio_log_text.see(tk.END)
        self.studio_log_text.config(state=tk.DISABLED)

    def on_studio_log_event(self, msg, step=None, eta=None):
        if step is not None:
            step_progress = {1: 25, 2: 55, 3: 80, 4: 95}
            self.studio_progress["value"] = step_progress.get(step, 50)
        if eta is not None:
            self.studio_current_eta = eta

        self.append_studio_log(msg)

        clean_msg = msg.strip().replace("\n", " ")
        if len(clean_msg) > 55:
            clean_msg = clean_msg[:52] + "..."
        self.studio_status_var.set(clean_msg)

    def update_studio_timer(self):
        if not self.studio_is_running:
            return

        elapsed = int(time.time() - self.studio_start_time)
        el_min = elapsed // 60
        el_sec = elapsed % 60

        if self.studio_current_eta > 0:
            self.studio_current_eta = max(2, self.studio_current_eta - 1)
            eta_str = f"약 {self.studio_current_eta}초"
        elif self.studio_current_eta == 0:
            eta_str = "마무리 중..."
        else:
            eta_str = "계산 중..."

        self.studio_eta_var.set(f"⏱️ 경과 {el_min:02d}:{el_sec:02d} | 남은 시간: {eta_str}")
        self.root.after(1000, self.update_studio_timer)

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

        ttk.Button(btn_bar, text="📅 [공부 기간 맞춤 학습 로드맵 생성]", style="Primary.TButton", command=self.generate_period_roadmap_action).pack(side=tk.LEFT, ipady=5, padx=(0, 8))
        ttk.Button(btn_bar, text="📝 [AI 맞춤 모의시험 & 해설 PDF 생성]", style="Action.TButton", command=self.generate_mock_exam_now_action).pack(side=tk.LEFT, ipady=5, padx=(0, 8))
        ttk.Button(btn_bar, text="✍️ [답안 제출 및 AI 자동 채점]", style="Action.TButton", command=self.open_grading_dialog_action).pack(side=tk.LEFT, ipady=5, padx=(0, 8))
        ttk.Button(btn_bar, text="⚡ [3분 치트시트(1Page) 생성]", style="Primary.TButton", command=self.generate_cheatsheet_action).pack(side=tk.LEFT, ipady=5, padx=(0, 8))
        ttk.Button(btn_bar, text="📂 [과목 예상문제 폴더 열기]", style="Secondary.TButton", command=self.open_exam_folder_action).pack(side=tk.LEFT, ipady=5)

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
        self.tutor_send_btn = ttk.Button(btn_box, text="🚀 [질문 전송]\n(Enter)", style="Primary.TButton", command=self.send_tutor_message)
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

        ttk.Button(act_bar, text="📖 [선택 차시 강의노트 PDF 열기]", style="Primary.TButton", command=self.dash_open_note_action).pack(side=tk.LEFT, ipady=4, padx=(0, 8))
        ttk.Button(act_bar, text="📂 [선택 주차 폴더 열기]", style="Secondary.TButton", command=self.dash_open_folder_action).pack(side=tk.LEFT, ipady=4, padx=(0, 8))
        ttk.Button(act_bar, text="⚡ [이 주차 3분 치트시트 생성]", style="Action.TButton", command=self.dash_generate_cheatsheet_action).pack(side=tk.LEFT, ipady=4, padx=(0, 8))
        ttk.Button(act_bar, text="📝 [이 주차 맞춤 모의시험 출제]", style="Primary.TButton", command=self.dash_goto_exam_action).pack(side=tk.LEFT, ipady=4)

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
        # 상단 테마 및 포인트 컬러 커스텀 카드
        theme_card = ttk.LabelFrame(self.tab_settings, text=" UI 테마 및 포인트 색상 커스텀 ", padding="10")
        theme_card.pack(fill=tk.X, pady=(0, 8))

        theme_row = ttk.Frame(theme_card)
        theme_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(theme_row, text="테마 모드:", font=("Pretendard", 9, "bold"), width=11).pack(side=tk.LEFT)
        is_dark = (getattr(self, "theme_mode", "light") == "dark")
        t_btn_text = " ☀️ 라이트 모드로 전환 " if is_dark else " 🌙 다크 모드로 전환 "
        self.tab_theme_toggle_btn = tk.Button(
            theme_row,
            text=t_btn_text,
            font=("Pretendard", 9, "bold"),
            bg="#26543e" if is_dark else "#e2e8f0",
            fg="#fbf9f4" if is_dark else "#14281e",
            activebackground="#2f664b" if is_dark else "#cbd5e1",
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.toggle_theme
        )
        self.tab_theme_toggle_btn.pack(side=tk.LEFT, padx=(0, 16))

        color_row = ttk.Frame(theme_card)
        color_row.pack(fill=tk.X, pady=(4, 2))

        ttk.Label(color_row, text="포인트 컬러:", font=("Pretendard", 9, "bold"), width=11).pack(side=tk.LEFT)

        presets = [
            ("🌿 URY Forest", "#1c4732", "#fbf9f4"),
            ("🌲 Emerald", "#105e46", "#ffffff"),
            ("🍵 Sage", "#3d6753", "#fbf9f4"),
            ("🌊 Slate", "#1e3a5f", "#ffffff"),
            ("🌌 Charcoal", "#2b303a", "#ffffff"),
        ]

        for label, hex_c, fg_c in presets:
            btn = tk.Button(
                color_row,
                text=label,
                font=("Pretendard", 8, "bold"),
                bg=hex_c,
                fg=fg_c,
                activebackground=hex_c,
                activeforeground=fg_c,
                relief=tk.FLAT,
                bd=0,
                padx=8,
                pady=3,
                cursor="hand2",
                command=lambda c=hex_c: self.set_theme_accent(c)
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))

        picker_btn = tk.Button(
            color_row,
            text="🎨 직접 색상 선택...",
            font=("Pretendard", 8, "bold"),
            bg="#334155",
            fg="#ffffff",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.choose_custom_color
        )
        picker_btn.pack(side=tk.LEFT, padx=(6, 12))

        accent = getattr(self, "theme_accent", "#1c4732")
        self.accent_preview_chip = tk.Label(color_row, text="  ", bg=accent, width=3, relief=tk.SOLID, bd=1)
        self.accent_preview_chip.pack(side=tk.LEFT, padx=(0, 6))

        self.accent_hex_label = ttk.Label(color_row, text=f"현재 선택된 포인트 색상: {accent}", style="Muted.TLabel")
        self.accent_hex_label.pack(side=tk.LEFT)

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

        ttk.Button(api_row, text="💾 설정 저장", style="Primary.TButton", command=self.save_settings_action).pack(side=tk.RIGHT)

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

        ttk.Button(c_btn_row, text="➕ 과목 추가", style="Secondary.TButton", command=self.add_course_dialog).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(c_btn_row, text="✏️ 선택 과목 수정", style="Secondary.TButton", command=self.edit_course_dialog).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(c_btn_row, text="🗑️ 과목 삭제", style="Danger.TButton", command=self.delete_course_action).pack(side=tk.LEFT)

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
                    self.rec_btn.config(text="⏹️ 녹음 중지 및 저장", style="Danger.TButton")
                    self.studio_audio_var.set(res["output_file"])
                    messagebox.showinfo("실시간 녹음 시작", f"마이크 실시간 녹음이 시작되었습니다.\n저장 대상: {res['file_name']}")
            else:
                res = rec.stop_recording()
                self.rec_btn.config(text="🔴 실시간 녹음", style="Secondary.TButton")
                if res.get("status") == "success":
                    messagebox.showinfo("녹음 완료", f"실시간 오디오가 해당 과목 폴더에 성공적으로 저장되었습니다.\n(경과 시간: {res.get('duration_sec', 0)}초)")
                    self.refresh_studio_file_listboxes()
        except Exception as e:
            messagebox.showerror("녹음 오류", f"실시간 녹음 처리 중 오류: {e}")

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
