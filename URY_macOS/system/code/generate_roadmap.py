#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine — 목표 학점 맞춤형 학습 로드맵 생성 엔진 v0.7.7 (generate_roadmap.py)
- 과목별 강의자료 및 마크다운 파싱 기반 주차별/일자별 세부 학술 주제 산출
- 과목별 실제 세부 단원명, 핵심 개념, 정밀 공부 지침 기반 로드맵 생성
- 마크다운 및 출판용 PDF 학습 로드맵 생성
"""

import os
import sys
import json
import re
import glob
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import config_manager
WORKSPACE_DIR = config_manager.WORKSPACE_DIR

def extract_course_week_topics(cname):
    """과목별 저장된 강의자료 및 마크다운에서 주차별 실제 강의 주제 및 핵심 항목 추출"""
    topics_map = {}
    folder = cname
    settings = config_manager.load_settings()
    for c in settings.get("courses", []):
        if c.get("course_name") == cname or c.get("folder_name") == cname:
            folder = c.get("folder_name", cname)
            break

    course_dir = config_manager.get_course_dir(folder)
    cache_dir = os.path.join(WORKSPACE_DIR, ".markdown_cache", folder)
    notes_dir = os.path.join(course_dir, "강의노트")

    # 1. .markdown_cache 및 사용자 강의노트 탐색하여 실제 강의 주제 추출
    candidate_mds = []
    if os.path.exists(cache_dir):
        candidate_mds.extend(glob.glob(os.path.join(cache_dir, "*.md")))
    if os.path.exists(notes_dir):
        candidate_mds.extend(glob.glob(os.path.join(notes_dir, "**", "*.md"), recursive=True))

    for fp in candidate_mds:
        fname = os.path.basename(fp)
        w_match = re.search(r"(\d+)주차|week\s*(\d+)", fname, re.IGNORECASE)
        if w_match:
            wnum = int(w_match.group(1) or w_match.group(2))
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                    for line in file:
                        line_s = line.strip()
                        if line_s.startswith("## "):
                            parts = re.split(r"[:\-\—\|]", line_s.replace("## ", ""), maxsplit=1)
                            if len(parts) > 1:
                                sub_title = parts[1].strip()
                                sub_title = re.sub(r"^\[?수업의[^\]]+\]?", "", sub_title).strip()
                                if sub_title and len(sub_title) > 2:
                                    topics_map[wnum] = sub_title
                                    break
                            elif len(parts) == 1 and len(parts[0].strip()) > 3:
                                topics_map[wnum] = parts[0].strip()
                                break
            except Exception:
                pass

    # 2. 강의자료 슬라이드 파일명 탐색
    mat_dir = os.path.join(course_dir, "강의자료")
    if os.path.exists(mat_dir):
        for f in os.listdir(mat_dir):
            w_match = re.search(r"(\d+)주차|week\s*(\d+)", f, re.IGNORECASE)
            if w_match:
                wnum = int(w_match.group(1) or w_match.group(2))
                if wnum not in topics_map:
                    stem = os.path.splitext(f)[0]
                    clean_title = re.sub(r"^(\d+주차|week\s*\d+|_)+", "", stem, flags=re.IGNORECASE).replace("_", " ").strip()
                    if clean_title and len(clean_title) > 2:
                        topics_map[wnum] = clean_title

    return topics_map

def generate_course_roadmap(course, target_grade="A+"):
    """과목별 목표 학점 맞춤형 16주 세부 학습 로드맵 생성"""
    cname = course.get("course_name", "강의")
    prof = course.get("professor", "교수님")
    days = ", ".join(course.get("days", []))
    dur = course.get("duration", 75)

    settings = config_manager.load_settings()
    sem_name = settings.get("semester", "2026년 2학기")
    custom_start = settings.get("semester_start_date", "2026-09-01")
    custom_end = settings.get("semester_end_date", "2026-12-21")

    s_date, e_date, _ = config_manager.get_semester_period(sem_name, custom_start, custom_end)
    topics_map = extract_course_week_topics(cname)

    md_lines = []
    md_lines.append(f"# 🎯 [{cname}] 목표 학점({target_grade}) 세부 16주 학습 로드맵")
    md_lines.append(f"> **시스템**: URY Engine (Ultimate Result for You v0.7.7)")
    md_lines.append(f"> **수강 학기**: {sem_name} ({s_date} ~ {e_date})")
    md_lines.append(f"> **담당 교수**: {prof} | **강의 요일**: {days} ({dur}분)")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 📌 1. 목표 학점 달성 핵심 전략 메트릭스")
    md_lines.append("")
    md_lines.append("| 단계 | 학습 실행 가이드라인 | 상세 검증 기준 |")
    md_lines.append("| :--- | :--- | :--- |")
    md_lines.append("| **주차별 정독** | 해당 주차 핵심 학술 개념 및 슬라이드 다독 | 24시간 내 복습 완료 |")
    md_lines.append("| **예상문제 회독** | URY 주차별 모의고사 전문항 최소 2회독 | 오답 및 근거 정리 |")
    md_lines.append("| **용어 및 공식** | 핵심 용어 사전(Glossary) 및 주요 LaTeX 공식 암기 | 백지 인출 테스트 |")
    md_lines.append("| **시험 직전 D-Day** | 전체 통합 PDF 단권화 3회독 & 치트시트 회독 | 고득점 마감 정독 |")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 📅 2. 16주차 주차별 세부 학술 학습 로드맵")
    md_lines.append("")

    DEFAULT_PHASES = {
        1: "과목 개요 및 입문 핵심 개념 정립",
        2: "기초 학술 이론 체계 및 기본 모델 분석",
        3: "심화 개념 전개 및 주요 분석 방법론",
        4: "응용 사례 연구 및 정량/정성 평가 모델",
        5: "핵심 메커니즘 분석 및 도표/수식 정독",
        6: "중간 평가 대비 핵심 단원 총정리",
        7: "중간고사 집중 예상문제 퀴즈 및 풀이 연습",
        8: "🚨 [중간고사 주차] 1~7주차 전범위 통합 정복 및 오답 복습",
        9: "후반부 핵심 이론 개시 및 새로운 분석 프레임워크",
        10: "고급 이론 모델 및 시스템 심화 응용",
        11: "실전 비즈니스/학술 케이스 스터디 및 적용",
        12: "다변량 분석 및 종합 이론 메커니즘",
        13: "기말 평가 대비 핵심 이슈 및 요약 단원",
        14: "전범위 통합 PDF 마스터 및 약점 단원 보완",
        15: "실전 모의고사 3회독 및 치트시트 암기",
        16: "🎓 [기말고사 주차] 전범위 최종 단권화 정독 및 A+ 달성"
    }

    curr_monday = s_date - timedelta(days=s_date.weekday())
    for w in range(1, 17):
        w_start = curr_monday + timedelta(weeks=w-1)
        w_end = w_start + timedelta(days=6)
        topic_title = topics_map.get(w, DEFAULT_PHASES.get(w, f"{w}주차 핵심 강의 주제"))

        md_lines.append(f"### 🗓️ {w}주차 ({w_start.strftime('%m/%d')} ~ {w_end.strftime('%m/%d')}) : {topic_title}")

        if w == 8:
            md_lines.append("> 🚨 **[중간고사 주차]** 1~7주차 전체 통합 PDF 및 예상문제 3회독 완독 달성!")
            md_lines.append("- [ ] **통합본 다독**: 1~7주차 통합 강의노트 PDF 정독 및 오답 분석")
            md_lines.append("- [ ] **용어 암기**: 주요 키워드 사전(Glossary) 및 수식 100% 백지 암기")
            md_lines.append("- [ ] **모의고사**: 1~7주차 모의시험 10문항 정답 비공개 풀이 및 해설 확인")
        elif w == 16:
            md_lines.append("> 🎓 **[기말고사 주차]** 9~15주차(또는 전범위) 최종 단권화 정리 완료!")
            md_lines.append("- [ ] **전범위 단권화**: 전 범위 통합 PDF 다이어그램 및 슬라이드 도표 총정리")
            md_lines.append("- [ ] **치트시트**: 3분 완성 A4 치트시트 최종 암기 및 입실 전 점검")
            md_lines.append("- [ ] **최종 응시**: 모의고사 100점 달성 후 시험 입실하여 A+ 확정")
        else:
            md_lines.append(f"- [ ] **[핵심 개념 정복]**: `{topic_title}` 관련 주요 학술 이론 및 슬라이드 1회독")
            md_lines.append(f"- [ ] **[실전 문제 풀이]**: `{cname}` {w}주차 예상문제 풀이 및 오답 개념 보완")
            md_lines.append(f"- [ ] **[단권화 요약]**: 핵심 용어 사전 및 주요 수식/도표 노트 정리")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append("`URY Engine v0.7.7 — Powered by Ultimate Result for You`")

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

    if os.path.exists(md_file):
        try:
            os.remove(md_file)
        except Exception:
            pass

    print(f"  ✅ [{cname}] 학습 로드맵 PDF 생성 완료 (MD 삭제됨): {pdf_file}")
    return pdf_file

def generate_dday_custom_roadmap(cname, d_day=14, exam_type="중간고사", scope="1~7주차", target_grade="A+", daily_hours="3시간", log_func=print):
    """시험 D-Day 및 범위를 기반으로 일자별 세부 과제 및 단원 목표를 정교하게 산출하는 로드맵 생성기"""
    log_func(f"📅 [{cname}] {exam_type} D-{d_day} 맞춤 세부 학습 로드맵 일정 산출 시작...")
    today = datetime.now().date()
    exam_date = today + timedelta(days=d_day)

    topics_map = extract_course_week_topics(cname)

    md_lines = []
    md_lines.append(f"# 🎯 [{cname}] {exam_type} D-{d_day} 초집밀 세부 학습 로드맵")
    md_lines.append(f"> **시스템**: URY Engine (Ultimate Result for You v0.7.7)")
    md_lines.append(f"> **목표 학점**: {target_grade} | **시험 예정일**: {exam_date.strftime('%Y년 %m월 %d일')} (D-{d_day})")
    md_lines.append(f"> **시험 범위**: {scope} | **일일 목표 공부 시간**: {daily_hours}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 📌 1. 시험 D-Day 필승 공부 전략 메트릭스")
    md_lines.append("")
    md_lines.append("| D-Day 구간 | 주요 학습 목표 | 세부 실행 가이드 |")
    md_lines.append("| :--- | :--- | :--- |")
    md_lines.append(f"| **D-{d_day} ~ D-{max(1, d_day//2)}** | 범위 내 핵심 개념 100% 정독 & 슬라이드 분석 | 지정 범위(`{scope}`) 주요 단원 분석 |")
    md_lines.append(f"| **D-{max(1, d_day//2)-1} ~ D-3** | URY 주차별 예상문제 2회독 및 오답 분석 | 출제 오개념 바로잡기 |")
    md_lines.append(f"| **D-2 ~ D-1** | 전체 통합 PDF 3회독 & 용어 사전 백지 암기 | 직전 백지 인출 테스트 |")
    md_lines.append(f"| **D-Day (시험 당일)** | A4 1페이지 치트시트 3분 정독 & 입실 | 최상위 {target_grade} 확정 |")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append(f"## 📅 2. D-{d_day} 일자별 세부 단원 공부 스케줄표")
    md_lines.append("")

    log_func(f"🎯 일자별 복습 목표 및 시간 배분 계산 중 ({daily_hours}/일)...")

    # D-Day 기간에 맞춰 주차/단원 할당
    for i in range(d_day, 0, -1):
        target_day = today + timedelta(days=(d_day - i))
        day_name = ["월", "화", "수", "목", "금", "토", "일"][target_day.weekday()]
        day_idx = d_day - i + 1

        # 할당 단원 계산 (1~7주차 등 범위 내 주차 매핑)
        assigned_w = min(16, max(1, (day_idx * 7) // max(1, d_day)))
        w_topic = topics_map.get(assigned_w, f"{assigned_w}주차 핵심 개념 및 주요 도표 분석")

        if i == d_day:
            md_lines.append(f"### 🗓️ D-{i} ({target_day.strftime('%m/%d')} {day_name}) — [1단계] 범위 전체 조망 및 {w_topic}")
            md_lines.append(f"- [ ] **[전체 조망]**: 시험 범위 (`{scope}`) 내 전체 통합 PDF 목차 및 주요 다이어그램 훑어보기")
            md_lines.append(f"- [ ] **[단원 집중]**: `{w_topic}` 주요 슬라이드 및 개념 1회독 ({daily_hours} 집중)")
        elif i == 1:
            md_lines.append(f"### 🚨 D-1 ({target_day.strftime('%m/%d')} {day_name}) — [최종단계] 직전 백지 검증 & 치트시트 회독")
            md_lines.append(f"- [ ] **[백지 인출]**: 주요 수식, 정의, 교수님 강조 팁 백지 인출 확인")
            md_lines.append(f"- [ ] **[치트시트]**: A4 1페이지 초고밀도 치트시트 회독 및 오답 노트 최종 점검")
        elif i <= max(2, d_day // 3):
            md_lines.append(f"### 🎯 D-{i} ({target_day.strftime('%m/%d')} {day_name}) — [문제풀이 & 약점보완]")
            md_lines.append(f"- [ ] **[실전 모의고사]**: URY 맞춤 모의시험 10문항 정답 비공개 풀이")
            md_lines.append(f"- [ ] **[오답 피드백]**: 정답 및 해설 PDF를 참조하여 약점 개념 재정독")
        else:
            md_lines.append(f"### 🗓️ D-{i} ({target_day.strftime('%m/%d')} {day_name}) — [{assigned_w}주차 단원 정복] {w_topic}")
            md_lines.append(f"- [ ] **[개념 정복]**: `{w_topic}` 핵심 이론 및 주요 공식 정독 ({daily_hours})")
            md_lines.append(f"- [ ] **[키워드 암기]**: 필수 용어 사전(Glossary) 및 비교 표 암기")

        md_lines.append("")

    target_day = exam_date
    day_name = ["월", "화", "수", "목", "금", "토", "일"][target_day.weekday()]
    md_lines.append(f"### 🎓 D-Day ({exam_date.strftime('%m/%d')} {day_name}) — 시험 당일! 최고 성적 {target_grade} 달성!")
    md_lines.append("- [ ] **[입실 전 3분]**: URY A4 1페이지 치트시트 회독")
    md_lines.append("- [ ] **[시험 응시]**: 자신감 있게 최고 성적 달성!")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("`URY Engine v0.7.7 — Powered by Ultimate Result for You`")

    content = "\n".join(md_lines)

    course_dir = config_manager.get_course_dir(cname)
    os.makedirs(course_dir, exist_ok=True)
    md_file = os.path.join(course_dir, f"{cname}_D-{d_day}_맞춤학습로드맵.md")
    pdf_file = os.path.join(course_dir, f"{cname}_D-{d_day}_맞춤학습로드맵.pdf")

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(content)

    log_func("🖨️ 세부 학습 로드맵 출판용 PDF 컴파일 중...")
    import generate_mock_exams
    generate_mock_exams.compile_pdf(md_file, pdf_file, f"{cname} {exam_type} D-{d_day} 학습 로드맵")

    if os.path.exists(md_file):
        try:
            os.remove(md_file)
        except Exception:
            pass

    log_func(f"✅ [{cname}] D-{d_day} 세부 학습 로드맵 PDF 생성 완료 (MD 삭제됨): {os.path.basename(pdf_file)}")
    return pdf_file, content

def run_all_roadmaps(target_courses=None):
    """전 과목 학습 로드맵 일괄 생성"""
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

    print("\n✅ 세부 학습 로드맵 생성이 성공적으로 완료되었습니다!")

if __name__ == "__main__":
    run_all_roadmaps()
