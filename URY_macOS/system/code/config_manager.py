#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
학업 관리 시스템 중앙 설정 관리자 (Config Manager)
- settings.json을 로드/저장하고 각 파이프라인 모듈에 일관된 설정을 제공합니다.
- 과목별 언어 모드 ('ko', 'en', 'both'), 시간표, 모의시험 생성 여부를 제어합니다.
"""

import os
import sys
import subprocess
import re
import json
import time
import urllib.request
import urllib.error
import unicodedata
import ssl
import glob

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

def get_root_workspace():
    if os.environ.get("WORKSPACE_DIR") and os.path.exists(os.environ["WORKSPACE_DIR"]):
        ws = os.path.abspath(os.environ["WORKSPACE_DIR"])
        if ws.rstrip("/") not in ("/Applications", "/System/Applications", "/Library") and not ws.startswith("/Volumes/") and os.access(ws, os.W_OK):
            return ws
        user_ws = os.path.expanduser("~/Desktop/URY_Engine")
        os.makedirs(user_ws, exist_ok=True)
        return user_ws
    if getattr(sys, "frozen", False):
        # Inside macOS .app bundle: .../URY Engine.app/Contents/MacOS/URY Engine
        app_dir = os.path.dirname(os.path.abspath(sys.executable))
        parent_dir = os.path.abspath(os.path.join(app_dir, "../../.."))
        if parent_dir.rstrip("/") in ("/Applications", "/System/Applications", "/Library") or parent_dir.startswith("/Volumes/") or not os.access(parent_dir, os.W_OK):
            user_ws = os.path.expanduser("~/Desktop/URY_Engine")
            os.makedirs(user_ws, exist_ok=True)
            return user_ws
        return parent_dir
    curr = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.basename(curr) in ("system", "code"):
            curr = os.path.dirname(curr)
        elif any(os.path.exists(os.path.join(curr, f)) for f in ("settings.json", "설정관리자.py", "USER_GUIDE.pdf", "run_pipeline.py")):
            return curr
        else:
            p = os.path.dirname(curr)
            if p == curr:
                break
            curr = p
    return curr

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = get_root_workspace()

def find_config_file(filename):
    p1 = os.path.join(WORKSPACE_DIR, "system", filename)
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(WORKSPACE_DIR, filename)
    if os.path.exists(p2):
        return p2
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(os.path.abspath(sys.executable))
        for sub in ("../Resources/system", "../Frameworks/system", "../Resources", "../Frameworks"):
            res_p = os.path.abspath(os.path.join(app_dir, sub, filename))
            if os.path.exists(res_p):
                return res_p
    return p1

SETTINGS_PATH = find_config_file("settings.json")
DEFAULT_SETTINGS_PATH = find_config_file("settings.default.json")
ENV_PATH = find_config_file(".env")
TIMETABLE_PATH = find_config_file("시간표.json")

def get_current_semester():
    """현재 활성화된 수강 학기 반환 (기본값: '2026년 2학기')"""
    settings = load_settings()
    return settings.get("semester", "2026년 2학기")

def get_semester_dir(semester=None):
    """현재 수강 학기 디렉터리 반환 (예: /Users/.../2026년 2학기)"""
    sem = semester or get_current_semester()
    path = os.path.join(WORKSPACE_DIR, sem)
    os.makedirs(path, exist_ok=True)
    return path

def get_course_dir(folder_name, semester=None):
    """
    과목 폴더 경로 반환 (우선순위: [학기]/[과목] -> 루트/[과목])
    """
    sem_dir = get_semester_dir(semester)
    exact = os.path.join(sem_dir, folder_name)
    if os.path.exists(exact):
        return exact
    norm_target = unicodedata.normalize('NFC', folder_name).replace(' ', '').lower()
    if os.path.exists(sem_dir):
        for entry in os.listdir(sem_dir):
            if unicodedata.normalize('NFC', entry).replace(' ', '').lower() == norm_target:
                return os.path.join(sem_dir, entry)
    root_exact = os.path.join(WORKSPACE_DIR, folder_name)
    if os.path.exists(root_exact):
        return root_exact
    return exact

def load_settings():
    """settings.json 로드 (없을 경우 settings.default.json 또는 기본값 반환)"""
    data = None
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Warn] settings.json 로드 실패, 기본값 사용: {e}")

    if not data and os.path.exists(DEFAULT_SETTINGS_PATH):
        try:
            with open(DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    if not data:
        data = {
            "gemini_api_key": "",
            "global_language_mode": "both",
            "courses": []
        }

    # 기본 tutor_name 보정
    for c in data.get("courses", []):
        cname = c.get("course_name", "")
        if not c.get("tutor_name"):
            c["tutor_name"] = f"{cname} 수석 조교" if cname else "수석 조교"

    try:
        ensure_all_course_folders(data)
        rec_box = os.path.join(WORKSPACE_DIR, "00_녹음_수신함")
        os.makedirs(rec_box, exist_ok=True)
        # system 폴더가 존재할 경우 Finder 숨김 속성(chflags hidden) 적용하여 바탕화면 깔끔 유지
        sys_dir = os.path.join(WORKSPACE_DIR, "system")
        if os.path.exists(sys_dir) and sys.platform == "darwin":
            try:
                subprocess.run(["chflags", "hidden", sys_dir], check=False)
            except Exception:
                pass
        if not os.path.exists(SETTINGS_PATH):
            save_settings(data)
    except Exception:
        pass

    return data

def get_course_syllabi(course_name_or_folder):
    """
    과목의 강의계획서 파일 경로 목록 반환 (복수 지원, 없을 경우 [])
    - settings.json 내 syllabus_paths (list) 우선 확인
    - 구버전 syllabus_path (str) 하위 호환
    - 자동 스캔 (PDF/DOCX/TXT/MD/HTML)
    """
    settings = load_settings()
    target_course = None
    for c in settings.get("courses", []):
        if c.get("course_name") == course_name_or_folder or c.get("folder_name") == course_name_or_folder:
            target_course = c
            break

    folder_name = target_course.get("folder_name", course_name_or_folder) if target_course else course_name_or_folder
    cdir = get_course_dir(folder_name)
    VALID_EXT = (".pdf", ".txt", ".md", ".docx", ".html", ".htm")

    result = []

    if target_course:
        # 신규: syllabus_paths (list)
        paths = target_course.get("syllabus_paths", [])
        # 구버전 하위 호환: syllabus_path (str)
        legacy = target_course.get("syllabus_path", "")
        if not paths and legacy:
            paths = [legacy]

        for s_path in paths:
            if not s_path:
                continue
            if os.path.isabs(s_path) and os.path.exists(s_path):
                result.append(s_path)
                continue
            rel_p = os.path.join(cdir, s_path)
            if os.path.exists(rel_p):
                result.append(rel_p)
                continue
            rel_ws = os.path.join(WORKSPACE_DIR, s_path)
            if os.path.exists(rel_ws):
                result.append(rel_ws)

    # 등록된 경로가 없으면 자동 스캔
    if not result and os.path.exists(cdir):
        search_patterns = [
            os.path.join(cdir, "강의계획서", "*.*"),
            os.path.join(cdir, "강의자료", "*강의계획서*.*"),
            os.path.join(cdir, "강의자료", "*syllabus*.*"),
            os.path.join(cdir, "*강의계획서*.*"),
            os.path.join(cdir, "*syllabus*.*"),
        ]
        for pat in search_patterns:
            for f in glob.glob(pat):
                if os.path.splitext(f)[1].lower() in VALID_EXT:
                    result.append(f)

    # 중복 제거, 존재하는 파일만
    seen = set()
    final = []
    for p in result:
        if p not in seen and os.path.exists(p):
            seen.add(p)
            final.append(p)
    return final


def get_course_syllabus(course_name_or_folder):
    """하위 호환: 첫 번째 강의계획서만 반환 (없으면 None)"""
    files = get_course_syllabi(course_name_or_folder)
    return files[0] if files else None



def ensure_all_course_folders(data):
    """설정된 모든 과목의 수강학기 디렉터리 및 서브폴더를 즉시 디스크에 자동 생성"""
    sem = data.get("semester", "2026년 2학기")
    sem_dir = get_semester_dir(sem)
    for c in data.get("courses", []):
        folder_name = c.get("folder_name") or c.get("course_name")
        if folder_name:
            c_dir = os.path.join(sem_dir, folder_name)
            for sub in ("음성녹음", "강의자료", "강의노트", "예상문제", "과제", "강의계획서"):
                os.makedirs(os.path.join(c_dir, sub), exist_ok=True)

def save_settings(data):
    """settings.json 저장 및 .env, 시간표.json, 과목별 폴더트리 동기화"""
    global SETTINGS_PATH, ENV_PATH, TIMETABLE_PATH, WORKSPACE_DIR
    target_path = SETTINGS_PATH
    try:
        if os.path.dirname(target_path):
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (PermissionError, OSError):
        # Read-only location (e.g. /Applications or mounted DMG): fallback to ~/Desktop/URY_Engine
        user_ws = os.path.expanduser("~/Desktop/URY_Engine")
        os.makedirs(user_ws, exist_ok=True)
        WORKSPACE_DIR = user_ws
        target_path = os.path.join(user_ws, "settings.json")
        SETTINGS_PATH = target_path
        ENV_PATH = os.path.join(user_ws, ".env")
        TIMETABLE_PATH = os.path.join(user_ws, "시간표.json")
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # API Key가 있으면 .env 파일에도 반영
    api_key = data.get("gemini_api_key", "").strip()
    if api_key:
        lines = []
        if os.path.exists(ENV_PATH):
            try:
                with open(ENV_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip().startswith("GEMINI_API_KEY="):
                            lines.append(line)
            except Exception:
                pass
        lines.append(f"GEMINI_API_KEY={api_key}\n")
        try:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception:
            pass

    # 시간표.json 및 폴더트리 자동 동기화
    try:
        sync_timetable_from_settings(data)
        ensure_all_course_folders(data)
    except Exception:
        pass
    return True

import sys
import subprocess
import re
from datetime import datetime, date, timedelta

APP_NAME = "URY Engine"
FULL_NAME = "Ultimate Result for You"
CREATOR = "URY Engine (Ultimate Result for You)"

def get_log_file_path():
    """로그 전용 디렉터리 (system/logs/latest_run_log.txt) 경로 반환 및 자동 생성"""
    log_dir = os.path.join(WORKSPACE_DIR, "system", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "latest_run_log.txt")

def cleanup_duplicate_mac_folders():
    """macOS Finder/Archive Utility가 중복 압축해제하여 생기는 모든 ' 2', ' 3' 붙은 폴더 및 파일 자동 삭제"""
    if not os.path.exists(WORKSPACE_DIR):
        return
    try:
        for item in os.listdir(WORKSPACE_DIR):
            norm_item = unicodedata.normalize('NFC', item)
            stem, ext = os.path.splitext(norm_item)
            if re.search(r"\s+\d+$", stem) or re.search(r"\s+\d+$", norm_item):
                full_p = os.path.join(WORKSPACE_DIR, item)
                try:
                    if os.path.isdir(full_p):
                        shutil.rmtree(full_p)
                    elif os.path.isfile(full_p):
                        os.remove(full_p)
                    print(f"🧹 [자동 청소] macOS 중복 찌꺼기 삭제 완료: {item}")
                except Exception:
                    pass
    except Exception:
        pass

def fix_mac_quarantine():
    """macOS 보안 차단(Quarantine) 격리 속성 해제 및 실행 권한 부여 & 중복 찌꺼기 폴더 청소"""
    cleanup_duplicate_mac_folders()
    if sys.platform == "darwin":
        try:
            subprocess.run(f"xattr -cr '{WORKSPACE_DIR}' 2>/dev/null", shell=True)
            subprocess.run(f"chmod +x '{WORKSPACE_DIR}'/*.command '{WORKSPACE_DIR}'/code/*.py 2>/dev/null", shell=True)
        except Exception:
            pass

cleanup_duplicate_mac_folders()

def get_semester_period(semester_str, custom_start=None, custom_end=None):
    """
    수강 학기 문자열 및 커스텀 시작일/종강일(YYYYMMDD 또는 YYYY-MM-DD) 기반 개강일과 종강일 산출
    """
    if custom_start and custom_end:
        c_s = custom_start.strip().replace("-", "").replace(".", "")
        c_e = custom_end.strip().replace("-", "").replace(".", "")
        if len(c_s) == 8 and len(c_e) == 8 and c_s.isdigit() and c_e.isdigit():
            try:
                s_dt = datetime.strptime(c_s, "%Y%m%d").date()
                e_dt = datetime.strptime(c_e, "%Y%m%d").date()
                return s_dt, e_dt, f"{s_dt.strftime('%Y-%m-%d')} ~ {e_dt.strftime('%Y-%m-%d')}"
            except Exception:
                pass

    year_match = re.search(r"(\d{4})", semester_str)
    year = int(year_match.group(1)) if year_match else datetime.now().year

    if "1학기" in semester_str:
        start_d = date(year, 3, 2)
        end_d = date(year, 6, 21)
    else: # 2학기 기본값
        start_d = date(year, 9, 1)
        end_d = date(year, 12, 21)

    return start_d, end_d, f"{start_d.strftime('%Y-%m-%d')} ~ {end_d.strftime('%Y-%m-%d')}"

def calculate_end_time(start_time_str, duration_minutes=75):
    """시작 시각(HH:MM)과 수업 길이(분)를 받아 종료 시각(HH:MM) 계산"""
    try:
        parts = start_time_str.strip().split(":")
        h, m = int(parts[0]), int(parts[1])
        start_dt = datetime(2026, 1, 1, h, m)
        end_dt = start_dt + timedelta(minutes=int(duration_minutes))
        return end_dt.strftime("%H:%M")
    except Exception:
        return "10:15"

def sync_timetable_from_settings(settings):
    """settings.json의 코스 정보를 바탕으로 시간표.json 스케줄 동기화"""
    semester_name = settings.get("semester", "2026년 2학기")
    custom_start = settings.get("semester_start_date")
    custom_end = settings.get("semester_end_date")
    start_d, end_d, period_str = get_semester_period(semester_name, custom_start, custom_end)

    if not os.path.exists(TIMETABLE_PATH):
        base_timetable = {"semester": semester_name, "period": period_str, "schedule": []}
    else:
        try:
            with open(TIMETABLE_PATH, "r", encoding="utf-8") as f:
                base_timetable = json.load(f)
        except Exception:
            base_timetable = {"semester": semester_name, "period": period_str, "schedule": []}

    base_timetable["semester"] = semester_name
    base_timetable["period"] = period_str
    base_timetable["start_date"] = start_d.strftime('%Y-%m-%d')
    base_timetable["end_date"] = end_d.strftime('%Y-%m-%d')
    base_timetable["creator"] = CREATOR
    base_timetable["app_name"] = APP_NAME
    base_timetable["period"] = period_str

    day_to_num = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

    new_schedule = []
    for c in settings.get("courses", []):
        day_names = c.get("days", [])
        day_nums = [day_to_num.get(d, 0) for d in day_names if d in day_to_num]
        start_t = c.get("start_time", "09:00")
        dur = c.get("duration", 75)
        end_t = c.get("end_time") or calculate_end_time(start_t, dur)

        new_schedule.append({
            "days": day_nums,
            "day_of_week": day_nums,
            "day_names": day_names,
            "start_time": start_t,
            "end_time": end_t,
            "duration": dur,
            "course_name": c.get("course_name", ""),
            "folder_name": c.get("folder_name", c.get("course_name", "")),
            "classroom": c.get("classroom", ""),
            "professor": c.get("professor", "")
        })

    base_timetable["schedule"] = new_schedule
    with open(TIMETABLE_PATH, "w", encoding="utf-8") as f:
        json.dump(base_timetable, f, ensure_ascii=False, indent=2)

def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        settings = load_settings()
        key = settings.get("gemini_api_key", "").strip()
    if not key and os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GEMINI_API_KEY="):
                    key = line.strip().split("=", 1)[1].strip().strip("'\"")
                    break

    if key.startswith("AIzaSyDt9Jr-0GbOqLKTMbLFJ"):
        return ""
    return key

_CACHED_SUPPORTED_MODELS = None
_LAST_MODEL_QUERY_TIME = 0

DEFAULT_LATEST_MODELS = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-pro-latest"
]

def parse_model_version_score(name):
    """
    구글 Gemini 모델 이름에서 최신 버전 우선순위 스코어를 계산하는 함수:
    - 버전 숫자: gemini-3.x (300점대) > gemini-2.5 (250점) > gemini-2.0 (200점) > gemini-1.5 (150점)
    - latest 키워드: 구글 공식 최신 production alias (9999점)
    - 티어 우선순위: 고속/고효율 멀티모달 분석을 위한 Flash (2점) > Pro (1점) > 기타 (0점)
    """
    lower = name.lower()
    
    if "latest" in lower:
        ver_score = 9999
    else:
        ver_match = re.search(r"gemini-(\d+)(?:\.(\d+))?", lower)
        if ver_match:
            major = int(ver_match.group(1))
            minor = int(ver_match.group(2)) if ver_match.group(2) is not None else 0
            ver_score = major * 100 + minor
        else:
            ver_score = 0

    tier_score = 2 if "flash" in lower else (1 if "pro" in lower else 0)
    stability_score = 0 if ("exp" in lower or "preview" in lower) else 1

    return (ver_score, tier_score, stability_score)

def get_supported_gemini_models(api_key=None, force_refresh=False):
    """
    구글 공식 Gemini API(/v1beta/models)를 실시간 조회하여,
    현재 구글에서 지원하는 모델 중 '가장 최신 버전' 순서대로 정렬하여 반환합니다.
    (실시간 조회 성공 시 1시간 캐싱, 네트워크 오류 시 최신 기본 모델 목록으로 자동 안전 Fallback)
    """
    global _CACHED_SUPPORTED_MODELS, _LAST_MODEL_QUERY_TIME
    now = time.time()
    if not force_refresh and _CACHED_SUPPORTED_MODELS and (now - _LAST_MODEL_QUERY_TIME < 3600):
        return list(_CACHED_SUPPORTED_MODELS)

    if not api_key:
        api_key = get_api_key()

    if not api_key or len(api_key) < 10:
        return list(DEFAULT_LATEST_MODELS)

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models_list = data.get("models", [])
            valid_models = []
            for m in models_list:
                if "generateContent" not in m.get("supportedGenerationMethods", []):
                    continue
                raw_name = m.get("name", "").replace("models/", "").strip()
                if not raw_name.startswith("gemini-"):
                    continue
                if any(x in raw_name.lower() for x in ("embedding", "aqa", "imagen", "search", "tts", "stt")):
                    continue
                valid_models.append(raw_name)

            if valid_models:
                sorted_models = sorted(valid_models, key=parse_model_version_score, reverse=True)
                deduped = []
                for m in sorted_models:
                    if m not in deduped:
                        deduped.append(m)

                if deduped:
                    _CACHED_SUPPORTED_MODELS = deduped
                    _LAST_MODEL_QUERY_TIME = now
                    return list(deduped)
    except Exception:
        pass

    return list(DEFAULT_LATEST_MODELS)

def get_course_lang_mode(course_name):
    """
    과목별 언어 모드 반환:
    - 'ko': 한국어 전용
    - 'en': 영어 전용
    - 'both': 한국어 + 영어 둘 다 (기본값)
    """
    settings = load_settings()
    for c in settings.get("courses", []):
        if c.get("course_name") == course_name or c.get("folder_name") == course_name:
            return c.get("language_mode", "both")
    return settings.get("global_language_mode", "both")

def should_generate_korean(course_name):
    """한국어 강의노트/모의시험 생성 여부"""
    mode = get_course_lang_mode(course_name)
    return mode in ("ko", "both")

def should_generate_english(course_name):
    """영어 강의노트/모의시험 생성 여부"""
    mode = get_course_lang_mode(course_name)
    return mode in ("en", "both")

def should_generate_mock_exam(course_name):
    """모의시험 생성 여부"""
    settings = load_settings()
    for c in settings.get("courses", []):
        if c.get("course_name") == course_name or c.get("folder_name") == course_name:
            return c.get("generate_mock_exam", True)
    return True

def create_sample_test_files():
    """테스트용 샘플 데이터 (샘플 마크다운 노트 & 샘플 음성) 즉시 생성"""
    settings = load_settings()
    courses = settings.get("courses", [])
    if not courses:
        return False
    
    first_course = courses[0].get("course_name", "DB 기초 및 응용")
    folder_name = courses[0].get("folder_name", first_course)
    
    c_dir = get_course_dir(folder_name)
    rec_dir = os.path.join(c_dir, "음성녹음")
    mat_dir = os.path.join(c_dir, "강의자료")
    os.makedirs(rec_dir, exist_ok=True)
    os.makedirs(mat_dir, exist_ok=True)
    
    # 1. 샘플 강의노트 마크다운을 캐시에 작성
    cache_dir = os.path.join(WORKSPACE_DIR, ".markdown_cache", folder_name)
    os.makedirs(cache_dir, exist_ok=True)
    
    sample_md_content = f"""# 📘 [{first_course}] 1주차 강의노트 (2026-2학기)

## 1주차 (2026-09-01 화요일) : 오리엔테이션 및 데이터베이스 기초 개념

### 📌 1. 수업 공지사항 및 운영 규칙 [🎙️ 음성]
- 중간고사 40%, 기말고사 40%, 과제 10%, 출석 10% 비중 반영.
- 영문 객관식 시험으로 출제되며 교재 용어 암기 필수.

### 💡 2. 데이터(Data) vs 정보(Information)의 차이 [💡 통합]
- **데이터 (Data)**: 가공되지 않은 순수한 사실이나 수치 (예: 오레/Iron Ore).
- **정보 (Information)**: 의사결정에 유용하도록 맥락이 부여된 가공물 (예: 강철/Steel).

| 항목 | 데이터 (Data) | 정보 (Information) |
| :--- | :--- | :--- |
| **정의** | 단순 개별 측정값 | 의미가 부여된 가공 자료 |
| **비유** | 철광석 (Iron Ore) | 강철 (Steel) |
| **목적** | 획득 및 저장 | 분석 및 의사결정 |

### 🎯 3. 핵심 키워드 정리 & 단원 종합 요약
#### 3.1 🔑 필수 핵심 키워드 사전
| 핵심 키워드 (Key Term) | 영문 표기 | 핵심 정의 및 시험 출제 포인트 |
| :--- | :--- | :--- |
| **DBMS** | DBMS | 데이터의 중복을 방지하고 통합 관리하는 소프트웨어 패키지 |
| **데이터 중복성** | Redundancy | 동일 데이터가 여러 곳에 중복 저장되어 불일치를 유발하는 현상 |

#### 3.2 📋 단원 종합 핵심 요약 (Exam Key Takeaways)
- 데이터와 정보의 차이 이해: 가공되지 않은 순수 사실(데이터)에 맥락을 부여한 것이 정보임.
- 파일 시스템의 한계(데이터 중복, 불일치)를 극복하기 위해 DBMS가 필수적으로 도입됨.

### 📝 4. 금주 체크리스트 & 과제
- [x] 1주차 슬라이드 및 URY 요약노트 1회독 완료
- [ ] URY 주차별 모의고사 문제 풀이 및 정답 확인
"""
    
    md_file = os.path.join(cache_dir, f"{first_course}_1주차_강의노트.md")
    comb_file = os.path.join(cache_dir, f"{first_course}_통합강의노트.md")
    
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(sample_md_content)
    with open(comb_file, "w", encoding="utf-8") as f:
        f.write(sample_md_content)

    # 2. 과목 음성녹음 폴더 및 수신함에 샘플 더미 파일 생성
    sample_rec = os.path.join(rec_dir, f"2026-09-01_{folder_name}_1주차_수업녹음.m4a")
    if not os.path.exists(sample_rec):
        with open(sample_rec, "w", encoding="utf-8") as f:
            f.write("SAMPLE AUDIO DUMMY DATA FOR TESTING")

    inbox_dir = os.path.join(WORKSPACE_DIR, "00_녹음_수신함")
    os.makedirs(inbox_dir, exist_ok=True)
    inbox_rec = os.path.join(inbox_dir, "2026-09-01_샘플강의녹음_테스트.m4a")
    if not os.path.exists(inbox_rec):
        with open(inbox_rec, "w", encoding="utf-8") as f:
            f.write("SAMPLE INBOX AUDIO DUMMY DATA FOR TESTING")

    return True

def send_system_notification(title, message, subtitle=""):
    """macOS 상단 알림센터 팝업 알림 (Windows/Linux 호환 처리)"""
    if sys.platform == "darwin":
        try:
            title_esc = title.replace('"', '\\"')
            msg_esc = message.replace('"', '\\"')
            sub_esc = subtitle.replace('"', '\\"')
            if subtitle:
                script = f'display notification "{msg_esc}" with title "{title_esc}" subtitle "{sub_esc}" sound name "Glass"'
            else:
                script = f'display notification "{msg_esc}" with title "{title_esc}" sound name "Glass"'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
        except Exception:
            pass

if __name__ == "__main__":
    s = load_settings()
    print("현재 로드된 설정 과목 수:", len(s.get("courses", [])))
    for c in s.get("courses", []):
        print(f"  • {c['course_name']}: 언어모드={c.get('language_mode')}, 모의시험={c.get('generate_mock_exam')}")
