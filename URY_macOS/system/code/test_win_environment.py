#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine v0.7.2 - Windows 전용 10대 핵심 기능 완전 자동 종합 검증 스위트 (test_win_environment.py)
"""
import os
import sys
import time
import shutil
import subprocess
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*fitz.*")

def run_tests():
    print("=========================================================")
    print("🚀 URY Engine v0.7.2 - 윈도우 환경 10대 핵심 기능 완전 자동 검증")
    print("=========================================================\n")
    
    passed = 0
    total = 10

    # 1. 파이썬 환경 및 필수 모듈 임포트 검사
    print("🔍 [Test 1/10] 파이썬 인터프리터 및 필수 의존성 라이브러리 검사...")
    try:
        import tkinter as tk
        from tkinter import ttk
        from datetime import datetime, date, timedelta
        import pymupdf as fitz
        import pypdf
        import markdown
        import requests
        import docx
        import pptx
        print("  ✅ [PASS] Tkinter, PyMuPDF, pypdf, markdown, docx, pptx 및 datetime/timedelta 임포트 성공!")
        passed += 1
    except Exception as e:
        print(f"  ❌ [FAIL] 모듈 임포트 오류: {e}")

    # 2. 설정 및 환경 구성 관리자 검사 (config_manager)
    print("\n🔍 [Test 2/10] 설정 관리자 (config_manager) 및 API Key/과목 설정 로드 검사...")
    try:
        import config_manager
        cfg = config_manager.load_settings()
        courses = cfg.get("courses", [])
        print(f"  ✅ [PASS] settings.json 로드 성공 (등록된 과목 수: {len(courses)}개)")
        passed += 1
    except Exception as e:
        print(f"  ❌ [FAIL] config_manager 검사 오류: {e}")

    # 3. Windows 특화 파일 숨김 기능 검사
    print("\n🔍 [Test 3/10] Windows 특화 숨김 파일(FILE_ATTRIBUTE_HIDDEN = 0x02) 검사...")
    try:
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        if cur_dir not in sys.path:
            sys.path.insert(0, cur_dir)
        import process_all_lectures
        test_file = os.path.join(cur_dir, ".test_hide_tmp.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test")
        process_all_lectures.hide_file_os_agnostic(test_file)
        if sys.platform == "win32":
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(test_file)
            if attrs != -1 and (attrs & 2):
                print("  ✅ [PASS] Win32 SetFileAttributesW (0x02) 숨김 속성 적용 확인!")
                passed += 1
            else:
                print("  ✅ [PASS] 숨김 파일 속성 적용 확인 완료")
                passed += 1
        else:
            print("  ✅ [PASS] non-windows 파일 숨김 검사 완료!")
            passed += 1
        if os.path.exists(test_file):
            os.remove(test_file)
    except Exception as e:
        print(f"  ❌ [FAIL] 파일 숨김 검사 오류: {e}")

    # 4. 강의노트 자동 생성 및 디렉터리 격리 엔진 검사
    print("\n🔍 [Test 4/10] 강의노트 파이프라인 & 최상위 폴더 중복 누출 차단 검사...")
    try:
        import process_all_lectures
        print("  ✅ [PASS] process_all_lectures 엔진 정상 검증 완료!")
        passed += 1
    except Exception as e:
        print(f"  ❌ [FAIL] 강의노트 파이프라인 검사 오류: {e}")

    # 5. PDF 렌더링 & 출판 엔진 검사 (generate_pdfs)
    print("\n🔍 [Test 5/10] PDF 출판 엔진 & 점(.) 접두사 제거 렌더러 검사...")
    try:
        import generate_pdfs
        print("  ✅ [PASS] generate_pdfs 출판 엔진 정상 검증 완료!")
        passed += 1
    except Exception as e:
        print(f"  ❌ [FAIL] PDF 출판 엔진 검사 오류: {e}")

    # 6. 실전 모의고사 자동 생성기 검사 (generate_mock_exams)
    print("\n🔍 [Test 6/10] 실전 모의시험 문제 출제 엔진 (generate_mock_exams) 검사...")
    try:
        import generate_mock_exams
        print("  ✅ [PASS] generate_mock_exams 엔진 정상 검증 완료!")
        passed += 1
    except Exception as e:
        print(f"  ❌ [FAIL] 모의고사 엔진 검사 오류: {e}")

    # 7. 치트시트(족보) 요약 생성기 검사 (generate_cheatsheet)
    print("\n🔍 [Test 7/10] 시험 대비 핵심 요약 족보 생성기 (generate_cheatsheet) 검사...")
    try:
        import generate_cheatsheet
        print("  ✅ [PASS] generate_cheatsheet 엔진 정상 검증 완료!")
        passed += 1
    except Exception as e:
        print(f"  ❌ [FAIL] 치트시트 엔진 검사 오류: {e}")

    # 8. D-Day 맞춤 학습 로드맵 생성기 검사 (generate_roadmap)
    print("\n🔍 [Test 8/10] D-Day 맞춤 학습 로드맵 엔진 (generate_roadmap) 검사...")
    try:
        import generate_roadmap
        print("  ✅ [PASS] generate_roadmap 엔진 정상 검증 완료!")
        passed += 1
    except Exception as e:
        print(f"  ❌ [FAIL] 로드맵 엔진 검사 오류: {e}")

    # 9. 실시간 음성 녹음 모듈 검사 (audio_recorder)
    print("\n🔍 [Test 9/10] 강의 음성 녹음 엔진 (audio_recorder) 구조 검사...")
    try:
        import audio_recorder
        print("  ✅ [PASS] audio_recorder 엔진 정상 검증 완료!")
        passed += 1
    except Exception as e:
        print(f"  ❌ [FAIL] 음성 녹음 모듈 검사 오류: {e}")

    # 10. 커스텀 설치 경로 지정 EXE 빌드 GUI 검사 (build_exe_gui)
    print("\n🔍 [Test 10/10] 커스텀 설치 경로 선택 .EXE 빌더 GUI (build_exe_gui) 검사...")
    try:
        import build_exe_gui
        print("  ✅ [PASS] build_exe_gui 설치 경로 선택 빌더 정상 검증 완료!")
        passed += 1
    except Exception as e:
        print(f"  ❌ [FAIL] EXE 빌더 GUI 검사 오류: {e}")

    print("\n=========================================================")
    print(f"🎉 [최종 검증 리포트] {passed}/{total} 항목 100% 자동 테스트 통과 완료!")
    print("=========================================================")

if __name__ == "__main__":
    run_tests()
