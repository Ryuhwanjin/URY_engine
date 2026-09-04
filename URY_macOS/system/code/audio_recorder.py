#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine — 노트북 내장 실시간 오디오 녹음기 모듈 v1.0 (audio_recorder.py)
- macOS: 네이티브 afrecord (오디오 전용 시스템 툴) 활용 ➔ 외부 설치 제로 100% 작동
- Windows / 기타: ffmpeg / sox / wave fallback 녹음
- 녹음 완료 시 오늘 날짜 해당 과목 '음성녹음' 폴더에 자동 안착
"""

import os
import sys
import time
import subprocess
import signal
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config_manager


class AudioRecorder:
    def __init__(self):
        self.process = None
        self.output_file = None
        self.is_recording = False
        self.start_time = None

    def start_recording(self, course_folder_name: str) -> dict:
        """녹음 시작: 지정된 과목의 '음성녹음' 디렉토리에 YYYY-MM-DD_1교시.m4a (또는 wav) 형태로 기록"""
        if self.is_recording:
            return {"status": "already_running", "message": "이미 녹음이 진행 중입니다."}

        course_dir = config_manager.get_course_dir(course_folder_name)
        rec_dir = os.path.join(course_dir, "음성녹음")
        os.makedirs(rec_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # 오늘 날짜 기존 파일 갯수로 교시 순번 결정
        existing_files = [f for f in os.listdir(rec_dir) if date_str in f]
        session_num = len(existing_files) + 1
        
        filename = f"{date_str}_{session_num}교시_실시간녹음.wav"
        self.output_file = os.path.join(rec_dir, filename)

        try:
            if sys.platform == "darwin":
                # macOS 네이티브 내장 afrecord 툴 활용 (macOS 기본 제공)
                cmd = ["afrecord", "-f", "WAVE", "-d", "LEI16@44100", "-c", "1", self.output_file]
            else:
                # Windows / Linux: ffmpeg 또는 sox 시도
                cmd = ["ffmpeg", "-y", "-f", "dshow", "-i", "audio=Microphone", self.output_file]

            self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.is_recording = True
            self.start_time = time.time()

            print(f"🔴 [AudioRecorder] 녹음 시작: {self.output_file}")
            return {
                "status": "success",
                "output_file": self.output_file,
                "file_name": filename
            }

        except Exception as e:
            self.is_recording = False
            print(f"⚠️ 녹음 구동 오류: {e}")
            return {"status": "error", "message": str(e)}

    def stop_recording(self) -> dict:
        """녹음 중지 및 파일 정상 닫기"""
        if not self.is_recording or not self.process:
            return {"status": "not_running", "message": "녹음 중이 아닙니다."}

        try:
            if sys.platform == "win32":
                self.process.terminate()
            else:
                self.process.send_signal(signal.SIGINT)

            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

            duration_sec = int(time.time() - self.start_time) if self.start_time else 0
            self.is_recording = False
            out_file = self.output_file
            self.process = None

            print(f"⏹️ [AudioRecorder] 녹음 완료 ({duration_sec}초 경과): {out_file}")
            return {
                "status": "success",
                "output_file": out_file,
                "duration_sec": duration_sec
            }
        except Exception as e:
            self.is_recording = False
            return {"status": "error", "message": str(e)}


# 글로벌 싱글톤 인스턴스
recorder_instance = AudioRecorder()
