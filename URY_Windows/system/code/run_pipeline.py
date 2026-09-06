#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
🎓 URY Engine — Ultimate Result for You Master Pipeline (v0.6.7)
=============================================================================
0단계: generate_roadmap.py          -> 목표 학점(A+) 맞춤형 16주 학습 로드맵 마크다운 생성
1단계: auto_organize.py             -> 수신함 새 녹음 파일만 시간표 기반 자동 분류 및 이동
2단계: process_all_lectures.py      -> 새로운 강의만 자동 감지하여 Gemini AI 음성 분석 및 한/영 노트 누적 적재
3단계: dynamic_slide_integrator.py  -> 강의자료 업데이트 시 슬라이드 도표 자동 추출 & 마크다운 임베드
4단계: generate_pdfs.py            -> 문장 중간 잘림 방지 CSS 적용, 최종 업데이트 일자 PDF 생성 & 구버전 삭제
5단계: generate_mock_exams.py      -> 과목별 AI 모의시험 PDF 생성 (정답 및 해설은 무조건 마지막 페이지 배치)
6단계: sync_markdown_vault.py      -> 모든 마크다운 파일을 하나의 중앙 보관함('마크다운_강의노트/')에 자동 집결
=============================================================================
"""

import os
import sys
import time
import glob
from datetime import datetime

# 파이프라인 모듈 임포트
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.join(SCRIPT_DIR, "code") if os.path.isdir(os.path.join(SCRIPT_DIR, "code")) else SCRIPT_DIR
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR

class TeeLogger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        try:
            self.log = open(filepath, "w", encoding="utf-8")
        except Exception:
            self.log = None

    def write(self, message):
        self.terminal.write(message)
        if self.log:
            try:
                self.log.write(message)
                self.log.flush()
            except Exception:
                pass

    def flush(self):
        self.terminal.flush()
        if self.log:
            try:
                self.log.flush()
            except Exception:
                pass

import config_manager
log_file_path = config_manager.get_log_file_path()
sys.stdout = TeeLogger(log_file_path)
import generate_roadmap
import auto_organize
import process_all_lectures
import dynamic_slide_integrator
import generate_pdfs
import generate_mock_exams
import sync_markdown_vault

TOTAL_STAGES = 6

def print_stage(stage_num, title, pipeline_start_time):
    pct = int((stage_num / TOTAL_STAGES) * 100)
    elapsed = time.time() - pipeline_start_time
    if stage_num > 0:
        avg_per_stage = elapsed / stage_num
        rem_stages = TOTAL_STAGES - stage_num
        eta_sec = int(avg_per_stage * rem_stages)
        eta_str = f"{eta_sec // 60:02d}분 {eta_sec % 60:02d}초 남음"
    else:
        eta_str = "계산 중..."
    
    bar_len = 20
    filled = int(bar_len * (pct / 100))
    bar = "█" * filled + "░" * (bar_len - filled)
    
    print("\n" + "=" * 65)
    print(f"📊 [{pct:3d}%] [{bar}] Stage {stage_num}/{TOTAL_STAGES} | ETA: {eta_str}")
    print(f"🚀 {title}")
    print("=" * 65)

def main():
    start_time = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    target_courses = None
    target_audio_files = None
    target_slide_files = None

    import argparse
    parser = argparse.ArgumentParser(description="URY Engine Master Pipeline")
    parser.add_argument("--courses", nargs="*", help="선택 과목 목록 (공백으로 구분)")
    parser.add_argument("--audio-files", nargs="*", help="선택 음성 파일 목록")
    parser.add_argument("--slide-files", nargs="*", help="선택 슬라이드 파일 목록")
    args, _ = parser.parse_known_args()

    if args.courses:
        target_courses = args.courses
        print(f"🎯 [선택적 파이프라인 구동] 타겟 과목: {target_courses}")
    if args.audio_files:
        target_audio_files = args.audio_files
    if args.slide_files:
        target_slide_files = args.slide_files

    print("=" * 65)
    print(f"🎓 URY Engine — Ultimate Result for You Engine v0.6.7")
    print(f"⏰ 실행 시각: {today_str}")
    print("=" * 65)

    # [0단계] 목표 학점 맞춤형 16주 학습 로드맵 생성/업데이트
    print_stage(0, "[0단계] 과목별 세부 16주 학습 로드맵 생성 및 동기화", start_time)
    try:
        settings = config_manager.load_settings()
        courses = settings.get("courses", [])
        for c in courses:
            cname = c.get("course_name") or c.get("folder_name")
            if target_courses and cname not in target_courses and c.get("folder_name") not in target_courses:
                continue
            try:
                generate_roadmap.generate_course_roadmap(c, target_grade="A+")
            except Exception as e_rm:
                print(f"⚠️ [{cname}] 로드맵 생성 알림: {e_rm}")
    except Exception as e:
        print(f"❌ [0단계 오류] 로드맵 생성 중 문제 발생: {e}")

    # [1단계] 새 녹음 파일만 자동 감지 및 시간표 매칭
    print_stage(1, "[1단계] 음성 녹음 파일 자동 감지 및 시간표 매칭 (신규 파일만)", start_time)
    try:
        organized_files = auto_organize.scan_and_organize()
        if organized_files:
            print(f"✅ 총 {len(organized_files)}개의 새로운 녹음 파일이 해당 과목 폴더로 이동되었습니다.")
        else:
            print("ℹ️ 새로 이동할 녹음 파일이 없습니다. (기존 파일 건너뜀)")
    except Exception as e:
        print(f"❌ [1단계 오류] 녹음 파일 분류 중 문제 발생: {e}")

    # [2단계] Gemini AI 음성 분석 & 통합 강의노트 적재
    print_stage(2, "[2단계] Gemini AI 음성 분석 및 통합 강의노트 적재 (신규 강의만)", start_time)
    try:
        process_all_lectures.scan_and_process_all_lectures(target_courses=target_courses, target_audio_files=target_audio_files)
    except Exception as e:
        print(f"❌ [2단계 오류] 강의노트 생성 중 문제 발생: {e}")

    # [3단계] PPT 슬라이드 핵심 도표/사진 자동 추출
    print_stage(3, "[3단계] PPT 슬라이드 핵심 도표/사진 자동 추출 및 임베드 (동적 감지)", start_time)
    try:
        dynamic_slide_integrator.sync_and_embed_all_slides_dynamically(target_courses=target_courses)
    except Exception as e:
        print(f"❌ [3단계 오류] 슬라이드 이미지 추출 중 문제 발생: {e}")

    # [4단계] 가독성 극대화 출판용 PDF 렌더링
    print_stage(4, "[4단계] 출판용 PDF 렌더링 (문장 잘림 방지 & 구버전 자동 삭제)", start_time)
    try:
        generate_pdfs.generate_all_pdfs(target_courses=target_courses)
    except Exception as e:
        print(f"❌ [4단계 오류] PDF 렌더링 중 문제 발생: {e}")

    # [5단계] 과목별 AI 모의시험 PDF 생성
    print_stage(5, "[5단계] 과목별 AI 모의시험 PDF 생성 (정답은 가장 마지막 페이지)", start_time)
    try:
        generate_mock_exams.generate_all_mock_exams(target_courses=target_courses)
    except Exception as e:
        print(f"❌ [5단계 오류] 모의시험 생성 중 문제 발생: {e}")

    # [6단계] 마크다운 파일 중앙 보관함 집결
    print_stage(6, "[6단계] 모든 마크다운 파일 중앙 보관함 집결 ('.마크다운_강의노트/')", start_time)
    try:
        sync_markdown_vault.sync_markdown_files()
    except Exception as e:
        print(f"❌ [6단계 오류] 마크다운 보관함 동기화 중 문제 발생: {e}")

    # 완료 시 100% 출력
    print_stage(6, "[완료] 파이프라인 전체 완료 및 수강 학기 리포트 발행", start_time)

    # -------------------------------------------------------------
    # 최종 결과 리포트 출력
    # -------------------------------------------------------------
    elapsed = round(time.time() - start_time, 1)
    print("\n" + "=" * 65)
    print(f"🎉 URY Engine 마스터 파이프라인 구동 완료! (총 소요시간: {elapsed}초)")
    print("=" * 65)

    settings = config_manager.load_settings()
    courses = [c.get("course_name") for c in settings.get("courses", [])]

    semester = config_manager.get_current_semester()
    print(f"📄 [{semester}] 최신 과목별 강의노트 PDF (주차별 + 전체통합):")
    for cdir in courses:
        c_path = config_manager.get_course_dir(cdir)
        for p in sorted(glob.glob(os.path.join(c_path, "강의노트", "**", "*.pdf"), recursive=True)):
            sz = round(os.path.getsize(p) / 1024 / 1024, 2)
            rel_p = os.path.relpath(p, c_path)
            print(f"  • [{sz}MB] {cdir} > {rel_p}")

    print(f"\n📝 [{semester}] 과목별 실전 예상문제 PDF (정답은 마지막 페이지 배치):")
    for cdir in courses:
        c_path = config_manager.get_course_dir(cdir)
        for ep in sorted(glob.glob(os.path.join(c_path, "예상문제", "**", "*.pdf"), recursive=True)):
            sz = round(os.path.getsize(ep) / 1024, 1)
            rel_ep = os.path.relpath(ep, c_path)
            print(f"  • [{sz}KB] {cdir} > {rel_ep}")

    print("\n📁 마크다운 통합 보관함:")
    print(f"  • 위치: {os.path.join(WORKSPACE_DIR, '.마크다운_강의노트')}")
    print("=" * 65)

    # macOS 상단 알림센터 팝업 알림
    config_manager.send_system_notification(
        title="🎓 URY Engine 파이프라인 완료",
        message=f"{semester} 전 과정 PDF 및 시험 산출물 생성이 완료되었습니다! (소요: {elapsed}초)",
        subtitle=f"등록 과목 {len(courses)}개 처리 완료"
    )

if __name__ == "__main__":
    main()
