#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine — 목표 학점 맞춤형 학습 로드맵 생성 엔진 (generate_roadmap.py)
- 목표 학점 (A+, A0, B+ 등) 및 학기 일자(개강~종강 16주) 기반
- 중간고사(8주차), 기말고사(16주차) D-Day별 일자 및 주차별 복습 체계 자동 산출
- 마크다운 및 PDF 학습 로드맵 생성
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR

def generate_course_roadmap(course, target_grade="A+"):
    """과목별 목표 학점 맞춤형 16주 학습 로드맵 마크다운 생성"""
    cname = course.get("course_name", "강의")
    prof = course.get("professor", "교수님")
    days = ", ".join(course.get("days", []))
    dur = course.get("duration", 75)
    
    settings = config_manager.load_settings()
    sem_name = settings.get("semester", "2026년 2학기")
    custom_start = settings.get("semester_start_date", "2026-09-01")
    custom_end = settings.get("semester_end_date", "2026-12-21")
    
    s_date, e_date, _ = config_manager.get_semester_period(sem_name, custom_start, custom_end)
    
    md_lines = []
    md_lines.append(f"# 🎯 [{cname}] 목표 학점({target_grade}) 맞춤형 학습 로드맵")
    md_lines.append(f"> **시스템**: URY Engine (Ultimate Result for You)")
    md_lines.append(f"> **수강 학기**: {sem_name} ({s_date} ~ {e_date})")
    md_lines.append(f"> **담당 교수**: {prof} | **강의 요일**: {days} ({dur}분)")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 📌 1. 목표 학점 달성 핵심 전략 메트릭스")
    md_lines.append("")
    md_lines.append("| 항목 | 목표 달성 가이드라인 | 비고 |")
    md_lines.append("| :--- | :--- | :--- |")
    md_lines.append("| **주차별 복습** | 매주 음성 요약 + PPT 슬라이드 100% 1회독 | 당일 24시간 내 복습 |")
    md_lines.append("| **예상문제 회독** | URY 주차별 모의고사 전문항 최소 2회독 | 오답 노트 정독 |")
    md_lines.append("| **과제 제출** | 출처 태그(`[출처: 슬라이드 p.X]`) 명시 답안 작성 | 기한 내 전원 제출 |")
    md_lines.append("| **시험 직전 D-Day** | D-7 전체 통합본 PDF 단권화 3회독 & Glossary 암기 | 시험 전날 최종 점검 |")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 📅 2. 16주차 주차별 세부 학습 로드맵")
    md_lines.append("")

    curr_monday = s_date - timedelta(days=s_date.weekday())
    for w in range(1, 17):
        w_start = curr_monday + timedelta(weeks=w-1)
        w_end = w_start + timedelta(days=6)
        
        md_lines.append(f"### 🗓️ {w}주차 ({w_start.strftime('%m/%d')} ~ {w_end.strftime('%m/%d')})")
        
        if w == 8:
            md_lines.append("> 🚨 **[중간고사 주차]** 1~7주차 전체 통합 PDF 및 예상문제 3회독 완독 달성!")
            md_lines.append("- [ ] 1~7주차 통합 강의노트 PDF 다독 및 오답 노트 가동")
            md_lines.append("- [ ] 용어 사전(Glossary) 핵심 개념 100% 암기 확인")
        elif w == 16:
            md_lines.append("> 🎓 **[기말고사 주차]** 9~15주차(또는 전범위) 최종 단권화 정리 완료!")
            md_lines.append("- [ ] 전 범위 통합 PDF 다이어그램 및 슬라이드 도표 총정리")
            md_lines.append("- [ ] 예상문제 실전 퀴즈 풀이 완료 및 A+ 최종 달성")
        else:
            md_lines.append(f"- [ ] **강의 수강**: 음성 녹음본 수신함 투입 & 파이프라인 구동")
            md_lines.append(f"- [ ] **강의노트 복습**: `{cname}_{w}주차_강의노트.pdf` 핵심 도표 체크")
            md_lines.append(f"- [ ] **예상문제 풀이**: `{cname}_{w}주차_예상문제.pdf` 정답 비공개 상태 풀이 후 해설 확인")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append("`URY Engine — Powered by Ultimate Result for You Engine`")
    
    content = "\n".join(md_lines)
    
    course_dir = config_manager.get_course_dir(cname)
    os.makedirs(course_dir, exist_ok=True)
    md_file = os.path.join(course_dir, f"{cname}_학습로드맵_{target_grade}.md")
    pdf_file = os.path.join(course_dir, f"{cname}_학습로드맵_{target_grade}.pdf")
    
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    # 출판용 PDF 렌더링
    import generate_mock_exams
    generate_mock_exams.compile_pdf(md_file, pdf_file, f"{cname} 16주 학습 로드맵 ({target_grade})")

    # 사용자의 명시적 요청: 마크다운 파일 자동 삭제 (오직 PDF 파일만 유지)
    if os.path.exists(md_file):
        try:
            os.remove(md_file)
        except Exception:
            pass

    print(f"  ✅ [{cname}] 학습 로드맵 PDF 생성 완료 (MD 삭제됨): {pdf_file}")
    return pdf_file

def generate_dday_custom_roadmap(cname, d_day=14, exam_type="중간고사", scope="1~7주차", target_grade="A+", daily_hours="3시간", log_func=print):
    """시험 D-Day 및 범위를 기반으로 일자별 스케줄을 자동으로 계산하는 D-Day 맞춤 로드맵 생성기"""
    log_func(f"📅 [{cname}] {exam_type} D-{d_day} 맞춤 학습 로드맵 일정 산출 시작...")
    today = datetime.now().date()
    exam_date = today + timedelta(days=d_day)
    
    md_lines = []
    md_lines.append(f"# 🎯 [{cname}] {exam_type} D-{d_day} 초집밀 학습 로드맵")
    md_lines.append(f"> **시스템**: URY Engine (Ultimate Result for You)")
    md_lines.append(f"> **목표 학점**: {target_grade} | **시험 예정일**: {exam_date.strftime('%Y년 %m월 %d일')} (D-{d_day})")
    md_lines.append(f"> **시험 범위**: {scope} | **일일 목표 공부 시간**: {daily_hours}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 📌 1. 시험 D-Day 필승 공부 전략")
    md_lines.append("")
    md_lines.append("| D-Day 구간 | 주요 학습 목표 | 실행 행동 가이드 |")
    md_lines.append("| :--- | :--- | :--- |")
    md_lines.append(f"| **D-{d_day} ~ D-{max(1, d_day//2)}** | 범위 내 핵심 슬라이드 100% 다독 & URY 강의노트 정독 | 지정 범위(`{scope}`) 개념 정복 |")
    md_lines.append(f"| **D-{max(1, d_day//2)-1} ~ D-3** | URY 주차별 예상문제 2회독 및 오답 노트 작성 | 개념 간 연결고리 완성 |")
    md_lines.append(f"| **D-2 ~ D-1** | 전체 통합 PDF 3회독 & 주요 용어/수식 최종 백지 암기 | 직전 마무리 다독 |")
    md_lines.append(f"| **D-Day (시험 당일)** | 핵심 요약본 직전 정독 & 시험 응시 | 최상위 {target_grade} 달성 |")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append(f"## 📅 2. D-{d_day} 일자별 세부 공부 스케줄표")
    md_lines.append("")

    log_func(f"🎯 일자별 복습 목표 및 시간 배분 계산 중 ({daily_hours}/일)...")
    for i in range(d_day, 0, -1):
        target_day = today + timedelta(days=(d_day - i))
        day_name = ["월", "화", "수", "목", "금", "토", "일"][target_day.weekday()]
        
        if i == d_day:
            md_lines.append(f"### 🗓️ D-{i} ({target_day.strftime('%m/%d')} {day_name}) — 로드맵 가동 및 범위 전체 조망")
            md_lines.append(f"- [ ] 시험 범위 (`{scope}`) 내 전체 통합 PDF 목차 및 도표 전체 1회 훑어보기")
            md_lines.append(f"- [ ] 오늘 할당 공부 시간 ({daily_hours}) 확보 및 URY 핵심 요약 노트 개시")
        elif i == 1:
            md_lines.append(f"### 🚨 D-1 ({target_day.strftime('%m/%d')} {day_name}) — 시험 직전 최종 마무리 백지 검증")
            md_lines.append(f"- [ ] 전체 통합 PDF 내 핵심 다이어그램 및 주요 개념 공식 백지 인출")
            md_lines.append(f"- [ ] 오답 노트 및 헷갈렸던 예상문제 100% 재확인")
        else:
            md_lines.append(f"### 🗓️ D-{i} ({target_day.strftime('%m/%d')} {day_name})")
            md_lines.append(f"- [ ] **개념 정복**: 지정 범위 내 강의노트 PDF 정독 ({daily_hours} 집중)")
            md_lines.append(f"- [ ] **문제 풀이**: URY 주차별 예상문제 풀이 및 해설 확인")

        md_lines.append("")

    target_day = exam_date
    day_name = ["월", "화", "수", "목", "금", "토", "일"][target_day.weekday()]
    md_lines.append(f"### 🎓 D-Day ({exam_date.strftime('%m/%d')} {day_name}) — 시험 당일! 최고 성적 {target_grade} 달성!")
    md_lines.append("- [ ] 시험 입실 전 URY 요약본 다독")
    md_lines.append("- [ ] 자신감 있게 시험 응시!")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("`URY Engine — Powered by Ultimate Result for You`")

    content = "\n".join(md_lines)
    
    course_dir = config_manager.get_course_dir(cname)
    os.makedirs(course_dir, exist_ok=True)
    md_file = os.path.join(course_dir, f"{cname}_D-{d_day}_맞춤학습로드맵.md")
    pdf_file = os.path.join(course_dir, f"{cname}_D-{d_day}_맞춤학습로드맵.pdf")
    
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(content)

    log_func("🖨️ 학습 로드맵 출판용 PDF 컴파일 중...")
    # 출판용 PDF 렌더링
    import generate_mock_exams
    generate_mock_exams.compile_pdf(md_file, pdf_file, f"{cname} {exam_type} D-{d_day} 학습 로드맵")

    # 사용자의 명시적 요청: 마크다운 파일 자동 삭제 (오직 PDF 파일만 유지)
    if os.path.exists(md_file):
        try:
            os.remove(md_file)
        except Exception:
            pass

    log_func(f"✅ [{cname}] D-{d_day} 학습 로드맵 PDF 생성 완료 (MD 삭제됨): {os.path.basename(pdf_file)}")
    return pdf_file, content

def run_all_roadmaps(target_courses=None):
    """전 과목 학습 로드맵 일괄 생성 (target_courses 지정 시 해당 과목만)"""
    print("\n" + "=" * 60)
    print("🎯 URY Engine — 목표 학점 맞춤형 학습 로드맵 생성 중...")
    print("=" * 60)
    
    settings = config_manager.load_settings()
    courses = settings.get("courses", [])
    
    if not courses:
        print("[Warn] 등록된 과목이 없습니다. settings.json을 확인하세요.")
        return
        
    for c in courses:
        cname = c.get("course_name")
        fname = c.get("folder_name", cname)
        if target_courses and cname not in target_courses and fname not in target_courses:
            continue
        generate_course_roadmap(c, target_grade="A+")
        
    print("\n✅ 학습 로드맵 생성이 성공적으로 완료되었습니다!")

if __name__ == "__main__":
    run_all_roadmaps()
