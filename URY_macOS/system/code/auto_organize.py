#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
대학 전공 강의 녹음 파일 자동 분류 및 정리 스크립트
- macOS 음성 메모(Voice Memos) 및 수신함(00_녹음_수신함) 폴더 감지
- 시간표(시간표.json) 기반 과목 자동 매칭 (시각 매칭 + 당일 순차 매칭)
- 과목 폴더별 일자 정리 (음성녹음/YYYY-MM-DD_과목명.m4a)
"""

import os
import sys
import json
import glob
import shutil
import re
import struct
import unicodedata
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR
TIMETABLE_PATH = config_manager.find_config_file("시간표.json")
INBOX_DIR = os.path.join(WORKSPACE_DIR, "00_녹음_수신함")
VOICE_MEMOS_DIR = os.path.expanduser("~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings")
PROCESSED_LOG = os.path.join(WORKSPACE_DIR, ".processed_recordings.json")

# 요일 매핑 (Python weekday: 0=월, 1=화, 2=수, 3=목, 4=금, 5=토, 6=일)
WEEKDAY_MAP = {
    0: "월",
    1: "화",
    2: "수",
    3: "목",
    4: "금",
    5: "토",
    6: "일"
}

def load_timetable_data():
    """시간표.json 전체 데이터 로드"""
    if not os.path.exists(TIMETABLE_PATH):
        print(f"[Error] 시간표 파일이 없습니다: {TIMETABLE_PATH}")
        return {}
    with open(TIMETABLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_timetable():
    """하위 호환용 주간 schedule 리스트 로드"""
    data = load_timetable_data()
    return data.get("schedule", [])

def load_processed_files():
    if os.path.exists(PROCESSED_LOG):
        try:
            with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_processed_files(processed):
    with open(PROCESSED_LOG, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)

def resolve_course_dir(folder_name):
    """
    수강 학기 디렉터리 기반 과목 폴더 경로 자동 해결 및 5대 서브폴더 자동 생성
    (예: 2026년 2학기/마케팅원론/[음성녹음, 강의자료, 강의노트, 예상문제, 과제])
    """
    cdir = config_manager.get_course_dir(folder_name)
    for sub in ("음성녹음", "강의자료", "강의노트", "예상문제", "과제"):
        os.makedirs(os.path.join(cdir, sub), exist_ok=True)
    return cdir

def get_audio_info(file_path):
    """
    .m4a 파일의 mvhd 헤더에서 생성 시각(UTC -> 로컬) 및 재생 길이(초) 추출
    실패 시 os.path.getmtime 및 duration=0 반환
    """
    mtime_dt = datetime.fromtimestamp(os.path.getmtime(file_path))
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.m4a':
        try:
            with open(file_path, 'rb') as f:
                while True:
                    header = f.read(8)
                    if len(header) < 8:
                        break
                    size, name = struct.unpack('>I4s', header)
                    if name == b'moov':
                        moov_data = f.read(size - 8)
                        idx = moov_data.find(b'mvhd')
                        if idx != -1:
                            mvhd = moov_data[idx+4:]
                            ver = mvhd[0]
                            if ver == 0:
                                c_time, _, timescale, duration = struct.unpack('>IIII', mvhd[4:20])
                            else:
                                c_time, _, timescale, duration = struct.unpack('>QQIQ', mvhd[4:28])
                            epoch = datetime(1904, 1, 1, tzinfo=timezone.utc)
                            dt = epoch + timedelta(seconds=c_time)
                            local_dt = dt.astimezone().replace(tzinfo=None)
                            dur_sec = duration / timescale if timescale else 0
                            return local_dt, dur_sec
                        break
                    elif size == 1:
                        ext_size, = struct.unpack('>Q', f.read(8))
                        f.seek(ext_size - 16, os.SEEK_CUR)
                    elif size == 0:
                        break
                    else:
                        f.seek(size - 8, os.SEEK_CUR)
        except Exception:
            pass
    return mtime_dt, 0

def natural_sort_key(file_path):
    """
    파일명의 자연스러운 순서 정렬 키
    '이문동.m4a' -> ('이문동', 1)
    '이문동 2.m4a' -> ('이문동', 2)
    '이문동 3.m4a' -> ('이문동', 3)
    """
    filename = os.path.basename(file_path)
    name, ext = os.path.splitext(filename)
    match = re.search(r'^(.*?)(?:\s+(\d+))?$', name)
    if match:
        base = match.group(1).strip()
        num = int(match.group(2)) if match.group(2) else 1
        return (base, num)
    return (name, 1)

def get_scheduled_classes_for_date(timetable_data, target_date):
    """특정 날짜의 수업 목록 반환 (calendar_sessions 우선, 없으면 주간 schedule)"""
    date_str = target_date.strftime("%Y-%m-%d")
    calendar_sessions = timetable_data.get("calendar_sessions", [])

    if calendar_sessions:
        matched = [s for s in calendar_sessions if s.get("date") == date_str and not s.get("is_holiday", False)]
        if matched:
            matched.sort(key=lambda x: x["start_time"])
            return matched
        # 공휴일 확인
        holidays = [s for s in calendar_sessions if s.get("date") == date_str and s.get("is_holiday", False)]
        if holidays:
            print(f"[Info] {date_str}은(는) 공휴일/휴강({holidays[0].get('note', '')})입니다.")
            return []

    # 기본 주간 시간표에서 요일 매칭
    schedule = timetable_data.get("schedule", [])
    weekday = target_date.weekday()
    day_classes = [c for c in schedule if weekday in c.get("days", c.get("day_of_week", []))]
    day_classes.sort(key=lambda x: x["start_time"])
    return day_classes

def is_course_already_organized(course, date_str, processed):
    """해당 날짜에 특정 과목의 녹음이 이미 정리되었는지 확인"""
    # 1. 처리 로그 확인
    for p_info in processed.values():
        if p_info.get("course") == course["course_name"] and p_info.get("date") == date_str:
            return True

    # 2. 실제 저장 디렉토리 파일 확인
    folder_name = course.get("folder_name", course["course_name"])
    course_dir = resolve_course_dir(folder_name)
    rec_dir = os.path.join(course_dir, "음성녹음")
    if os.path.exists(rec_dir):
        for fn in os.listdir(rec_dir):
            if fn.startswith(date_str) and fn.endswith(('.m4a', '.mp3', '.wav')):
                return True
    return False

def ensure_folders():
    os.makedirs(INBOX_DIR, exist_ok=True)
    timetable = load_timetable()
    for item in timetable:
        folder_name = item.get("folder_name", item["course_name"])
        course_dir = resolve_course_dir(folder_name)
        rec_folder = os.path.join(course_dir, "음성녹음")
        os.makedirs(rec_folder, exist_ok=True)

def scan_and_organize():
    ensure_folders()
    timetable_data = load_timetable_data()
    processed = load_processed_files()

    candidate_files = []

    # 1. 00_녹음_수신함 스캔
    for ext in ("*.m4a", "*.mp3", "*.wav"):
        candidate_files.extend(glob.glob(os.path.join(INBOX_DIR, ext)))

    # 2. Voice Memos 폴더 스캔
    if os.path.exists(VOICE_MEMOS_DIR):
        for ext in ("*.m4a", "*.mp3", "*.wav", "*.aac"):
            candidate_files.extend(glob.glob(os.path.join(VOICE_MEMOS_DIR, ext)))

    # 미처리 파일만 선별
    unprocessed_files = []
    for fp in candidate_files:
        fhash = f"{os.path.basename(fp)}_{os.path.getsize(fp)}"
        if fhash not in processed:
            unprocessed_files.append(fp)

    if not unprocessed_files:
        print("[Info] 처리할 새로운 음성 녹음 파일이 없습니다.")
        return []

    # 각 파일에 대해 (file_path, audio_dt, duration_sec) 정보 파싱
    file_info_list = []
    for fp in unprocessed_files:
        dt, dur = get_audio_info(fp)
        file_info_list.append((fp, dt, dur))

    # 날짜(YYYY-MM-DD)별 그룹화
    date_groups = {}
    for item in file_info_list:
        date_str = item[1].strftime("%Y-%m-%d")
        if date_str not in date_groups:
            date_groups[date_str] = []
        date_groups[date_str].append(item)

    newly_organized = []

    for date_str, items in sorted(date_groups.items()):
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        day_classes = get_scheduled_classes_for_date(timetable_data, target_date)
        available_classes = [c for c in day_classes if not is_course_already_organized(c, date_str, processed)]

        items.sort(key=lambda x: (natural_sort_key(x[0]), x[1]))
        print(f"\n[{date_str}] 감지된 녹음 파일: {len(items)}개 / 시간표 수업: {len(day_classes)}개")

        for file_path, record_dt, duration_sec in items:
            matched = None
            match_type = None
            file_hash = f"{os.path.basename(file_path)}_{os.path.getsize(file_path)}"
            rec_minutes = record_dt.hour * 60 + record_dt.minute

            # 수동 파일명 키워드/과목명 지정 매칭 (자동 추측 매칭 비활성화)
            fn_lower = os.path.basename(file_path).lower()
            settings = config_manager.load_settings()
            courses_list = settings.get("courses", []) or timetable_data.get("schedule", []) or timetable_data.get("weekly_rules", [])

            for c in courses_list:
                if not isinstance(c, dict):
                    continue
                cname = c.get("course_name", "").lower()
                fname = c.get("folder_name", cname).lower()
                tokens = [t for t in (cname.split() + fname.split() + [cname.replace(" ", ""), fname.replace(" ", "")]) if len(t) >= 2]
                if any(tok in fn_lower for tok in tokens):
                    matched = c
                    match_type = "수동 지정(파일명) 매칭"
                    break

            if not matched:
                print(f"ℹ️ [수신함 대기] '{os.path.basename(file_path)}' -> 과목 키워드 미지정 (파일명에 과목명을 적어주시면 이동됩니다)")
                continue

            if matched in available_classes:
                available_classes.remove(matched)

            course_name = matched["course_name"]
            folder_name = matched.get("folder_name", course_name)
            course_dir = resolve_course_dir(folder_name)
            target_dir = os.path.join(course_dir, "음성녹음")
            os.makedirs(target_dir, exist_ok=True)

            actual_folder_base = os.path.basename(course_dir)
            ext = os.path.splitext(file_path)[1]
            target_filename = f"{date_str}_{actual_folder_base}{ext}"
            target_path = os.path.join(target_dir, target_filename)

            # 중복 파일명 처리 (예: _2)
            counter = 2
            while os.path.exists(target_path):
                target_filename = f"{date_str}_{actual_folder_base}_{counter}{ext}"
                target_path = os.path.join(target_dir, target_filename)
                counter += 1

            dur_str = f"{round(duration_sec / 60, 1)}분" if duration_sec > 0 else "미확인"
            print(f"[{match_type}] {os.path.basename(file_path)} ({dur_str}) -> [{course_name} ({matched['start_time']}~{matched['end_time']})] {target_filename}")

            is_inbox = (
                os.path.realpath(file_path).startswith(os.path.realpath(INBOX_DIR)) or
                "00_녹음_수신함" in file_path or
                os.path.dirname(os.path.abspath(file_path)) == os.path.abspath(INBOX_DIR)
            )

            if is_inbox:
                shutil.move(file_path, target_path)
                print(f"  🚚 [수신함 파일 이동 완료] {os.path.basename(file_path)} -> {target_path}")
            else:
                shutil.copy2(file_path, target_path)
                print(f"  📋 [파일 복사 완료] {os.path.basename(file_path)} -> {target_path}")

            processed[file_hash] = {
                "source": file_path,
                "target": target_path,
                "course": course_name,
                "date": date_str,
                "match_type": match_type,
                "duration_seconds": duration_sec,
                "processed_at": datetime.now().isoformat()
            }
            newly_organized.append({
                "course": course_name,
                "target_path": target_path,
                "match_type": match_type,
                "date": date_str
            })

    save_processed_files(processed)
    print(f"\n[Done] 총 {len(newly_organized)}개의 녹음 파일이 과목별로 정리되었습니다.")
    return newly_organized

if __name__ == "__main__":
    scan_and_organize()
