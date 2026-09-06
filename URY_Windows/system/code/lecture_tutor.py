#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine — "교수님 말씀 Q&A" 대화형 AI 강의 전용 튜터 (RAG 챗봇) v5.5
- 선택된 과목의 주차별 강의노트, 통합본, 3분 치트시트, 공지사항을 지식 베이스로 활용
- 교수님 실제 육성 발언 시점([🎙️ 음성 (MM:SS)])과 시험 팁을 정확히 인용
- 대화 기록(Multi-turn History)을 유지하며 맞춤형 질의응답 및 친절한 개념 해설 제공
"""

import os
import sys
import glob
import json
import re
import urllib.request
import urllib.error
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config_manager

WORKSPACE_DIR = config_manager.WORKSPACE_DIR

TUTOR_SYSTEM_PROMPT = """당신의 이름은 '{tutor_name}'이며, [{cname}] 과목의 1:1 전담 수석 조교이자 학술 Q&A 전담 튜터입니다.
학생이 시험 복습, 과제 해결, 개념 이해를 완벽히 할 수 있도록 성심성의껏 답변하십시오.

[답변 핵심 원칙 및 이원화 구조 (Dual-Source Architecture)]
1. 🎓 [수업 자료 기반 설명 vs 📚 원론적 기초 개념 구분]:
   - [Case A: 수업 자료에 있는 내용]:
     학생이 질문한 내용이 제공된 강의노트, 슬라이드, 강의계획서에 존재하는 경우, 반드시 제공된 자료를 최우선 근거로 답변하고 교수님 발언 타임스탬프([🎙️ 음성 (MM:SS)]) 및 슬라이드 출처를 명시하십시오.
   - [Case B: 수업 자료에 없는 원론적/기초 지식 질문 (자격증/독학/선수지식)]:
     강의 슬라이드에 직접 정의되지는 않았으나 수업 이해에 필요한 전공 표준 기초 이론(예: 수학적 공식 유도, 원론적 학술 정의 등)을 물어본 경우, 절대로 답변을 거부하지 마십시오!
     대신 다음과 같이 명확히 구분하여 답변하십시오:
     "💡 [전공 기초 개념 보충]: 본 강의 자료에 직접적인 정의는 포함되어 있지 않으나, 해당 단원 이해를 돕기 위해 전공 표준 기본 원리를 설명해 드립니다."라고 전제를 밝힌 후, 가장 쉽고 명쾌하게 기초 이론을 설명하십시오. (절대로 수업에서 교수님이 하신 말씀인 것처럼 꾸며내지 마십시오.)

2. 📑 [강의계획서 (Syllabus) 연동 가이드라인]:
{syllabus_instruction}

3. 🎙️ [교수님 발언 타임스탬프 인용 필수]:
   - 제공된 학습 자료에 교수님의 실제 육성 언급([🎙️ 음성 (MM:SS)])이나 시험/과제 팁이 있다면, 반드시 해당 주차와 시간(MM:SS)을 정확히 인용하십시오. (예: "교수님께서 1주차 강의 [🎙️ 음성 (24:10)]에서...")
   - 🚨 주의: 제공된 수업 자료에 없는 시간(MM:SS)이나 발언을 임의로 상상하여 지어내지 마십시오.

4. 📖 [실제 참조 원문 스니펫 (Reference Source Quotation) 필수]:
   - 모든 답변의 마지막에는 반드시 아래 서식에 맞춰 실제로 참조한 원문 문장을 1~2줄 직접 인용하십시오:
     ---
     📌 **[참조 원문 근거]**:
     • 출처: [참고한 강의노트, 강의계획서, 또는 슬라이드 파일명/주차] (원론적 질문일 경우: '전공 표준 기초 이론')
     • 원문 발췌: "실제 강의노트 또는 교재에서 발췌한 핵심 문장..."

5. 💡 [친절하고 명쾌한 눈높이 설명]:
   - 어려운 학술 용어와 공식은 학생이 직관적으로 이해할 수 있도록 일상생활 비유, 실무 예시, 단계별 요약을 곁들여 설명하십시오.

6. 🚨 [할루시네이션 방지 및 솔직한 고지]:
   - 제공된 수업 자료에 전혀 언급되지 않은 교수님의 개인 공지나 시험 일정은 자의적으로 꾸며내지 말고, "현재 강의노트에는 언급되어 있지 않습니다. e-캠퍼스 공식 공지사항을 확인하세요"라고 솔직하게 안내하십시오.

7. 📐 [수식 및 기호 표기 가이드]:
   - 데스크톱 대화창 가독성을 위해 웹 브라우저용 복잡한 LaTeX 원시 문법 대신, 직관적인 유니코드 수식 기호(예: ℝ, ℝ², ℝ³, u, c, ≠, ∈, ≤, ≥, ±, ∞, → 등)와 읽기 쉬운 텍스트 수식(예: [ c·u | c ∈ ℝ ])을 우선 사용하십시오.
"""

def extract_text_from_file(file_path):
    if not os.path.exists(file_path):
        return ""
    try:
        import doc_parser
        parsed = doc_parser.parse_document(file_path)
        return parsed.get("full_text", "")
    except Exception:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".md", ".txt"):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return ""
        return ""


def get_course_knowledge_base(cname, max_chars=40000):
    """선택 과목의 강의계획서, 마크다운 강의노트 및 시험자료를 지식 베이스로 수집"""
    folder_name = cname
    for c in config_manager.load_settings().get("courses", []):
        if c.get("course_name") == cname:
            folder_name = c.get("folder_name", cname)
            break

    cdir = config_manager.get_course_dir(folder_name)
    collected_chunks = []
    total_len = 0

    # 0. 강의계획서(Syllabus) 최우선 수집 (다중 파일 지원)
    syllabus_files = config_manager.get_course_syllabi(folder_name)
    has_syllabus = False
    for idx, s_file in enumerate(syllabus_files):
        if s_file and os.path.exists(s_file):
            s_txt = extract_text_from_file(s_file)
            if s_txt:
                has_syllabus = True
                fname = os.path.basename(s_file)
                tag = f" #{idx+1}" if len(syllabus_files) > 1 else ""
                chunk = f"\n\n=== 📑 [공식 강의계획서{tag} (Syllabus: {fname}) — 마스터 기준] ===\n{s_txt[:15000]}\n"
                collected_chunks.append(chunk)
                total_len += len(chunk)

    # 1. .markdown_cache 수집 (가장 고품질 마크다운 노트)
    cache_dirs = [
        os.path.join(WORKSPACE_DIR, ".markdown_cache", folder_name),
        os.path.join(WORKSPACE_DIR, ".markdown_cache", cname)
    ]
    for c_dir in cache_dirs:
        if os.path.exists(c_dir):
            for mdf in sorted(glob.glob(os.path.join(c_dir, "*.md"))):
                fname = os.path.basename(mdf)
                txt = extract_text_from_file(mdf)
                if txt and total_len < max_chars:
                    chunk = f"\n\n=== [참고 자료: {fname}] ===\n" + txt[:15000]
                    collected_chunks.append(chunk)
                    total_len += len(chunk)

    # 2. 강의노트 폴더 내 자료
    notes_dir = os.path.join(cdir, "강의노트")
    if os.path.exists(notes_dir) and total_len < max_chars:
        for mdf in sorted(glob.glob(os.path.join(notes_dir, "**", "*.md"), recursive=True)):
            fname = os.path.basename(mdf)
            txt = extract_text_from_file(mdf)
            if txt and total_len < max_chars:
                chunk = f"\n\n=== [강의노트: {fname}] ===\n" + txt[:15000]
                collected_chunks.append(chunk)
                total_len += len(chunk)

    # 3. 예상문제 및 치트시트 폴더
    exam_dir = os.path.join(cdir, "예상문제")
    if os.path.exists(exam_dir) and total_len < max_chars:
        for mdf in sorted(glob.glob(os.path.join(exam_dir, "*.md"))):
            fname = os.path.basename(mdf)
            txt = extract_text_from_file(mdf)
            if txt and total_len < max_chars:
                chunk = f"\n\n=== [시험/치트시트 자료: {fname}] ===\n" + txt[:10000]
                collected_chunks.append(chunk)
                total_len += len(chunk)

    full_kb = "".join(collected_chunks)
    if len(full_kb) > max_chars:
        full_kb = full_kb[:max_chars] + "\n...(일부 내용 생략)..."
    return full_kb, has_syllabus

def verify_and_guard_answer(answer, kb):
    """
    2단계 사실 검증 가드레일 (Fact-Checking Guardrail):
    1. 답변 내 [🎙️ 음성 (MM:SS)] 타임스탬프가 지식 베이스(KB)에 실제로 존재하는지 대조
    2. 지식 베이스에 없는 임의 타임스탬프 감지 시 경고 주석 부착
    3. 참조 원문 근거 섹션 유무 확인 및 보정
    """
    if not answer:
        return answer

    annotated = answer

    # 타임스탬프 유효성 검증
    pattern = r'\[🎙️\s*음성\s*\(([0-9]{1,2}:[0-9]{2})\)\]'
    matches = re.findall(pattern, annotated)
    for ts in matches:
        if kb and ts not in kb:
            annotated = annotated.replace(f"({ts})", f"({ts} ⚠️ 원본음성 확인필요)")

    # 참조 원문 근거 섹션 유무 확인 및 보정
    if "📌" not in annotated and "참조 원문" not in annotated:
        if kb and any(k in annotated for k in ["강의", "교수님", "수업"]):
            annotated += "\n\n---\n📌 **[참조 원문 근거]**: 수업 강의노트 및 슬라이드 교재 참조"
        else:
            annotated += "\n\n---\n📌 **[참조 원문 근거]**: 전공 표준 기초 이론 (강의노트 내 직접 언급 없음)"

    return annotated

def ask_lecture_tutor(cname, user_query, conversation_history=None, tutor_name=None, log_func=print):
    """AI 강의 튜터 질의응답 (Gemini API 호출 및 지수 백오프 적용)"""
    api_key = config_manager.get_api_key() or os.environ.get("GEMINI_API_KEY", "")
    if not api_key or len(api_key) < 10:
        return "⚠️ Google Gemini API 키가 설정되지 않았습니다. [⚙️ 과목 및 시스템 설정] 탭에서 API 키를 등록해주세요."

    kb, has_syllabus = get_course_knowledge_base(cname)

    if not tutor_name:
        for c in config_manager.load_settings().get("courses", []):
            if c.get("course_name") == cname:
                tutor_name = c.get("tutor_name")
                break
    if not tutor_name:
        tutor_name = f"{cname} 수석 조교"

    if has_syllabus:
        syllabus_inst = """   - 🟢 [강의계획서 등록됨]: 본 과목에는 공식 [강의계획서(Syllabus)]가 1순위 마스터 기준으로 등록되어 있습니다.
     시험 일정, 시험 범위, 평가 배점(중간/기말/과제/출석 %), 주교재, 주차별 진도 계획에 관한 질문을 받으면 반드시 등록된 강의계획서 원문을 최우선 인용하여 100% 정확하게 안내하십시오."""
    else:
        syllabus_inst = """   - 🟡 [강의계획서 미등록 (자율 학습 모드)]: 본 과목은 강의계획서가 아직 등록되지 않은 자율 학습 과목입니다.
     만약 학생이 시험 배점 비율이나 공식 학사 일정을 물어볼 경우, "현재 이 과목은 강의계획서가 등록되어 있지 않아 공식 배점은 확인할 수 없습니다. (언제든 [강의계획서 업로드]를 하시면 자동 연동됩니다!)"라고 솔직히 안내하고, 업로드된 슬라이드 본문 및 전공 표준 지식을 기반으로 시험 대비를 지원하십시오."""

    system_prompt = TUTOR_SYSTEM_PROMPT.format(
        cname=cname,
        tutor_name=tutor_name,
        syllabus_instruction=syllabus_inst
    )

    prompt = system_prompt + "\n\n"
    if kb.strip():
        prompt += f"[현재까지 누적된 {cname} 수업 강의노트 및 자료 발췌]\n{kb}\n\n"
    else:
        prompt += f"(안내: 아직 {cname} 과목의 강의노트가 생성되지 않았습니다. {cname} 전공 기본 지식을 토대로 답변하십시오.)\n\n"

    if conversation_history:
        prompt += "[이전 대화 기록]\n"
        for turn in conversation_history[-6:]:
            role = "학생" if turn.get("role") == "user" else "AI 조교"
            prompt += f"{role}: {turn.get('text', '')}\n"
        prompt += "\n"

    prompt += f"[학생의 새로운 질문]\n{user_query}\n\n[AI 조교 답변]:"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3}
    }

    # 초고속 실시간 대화형 공식 정식 모델 우선순위 (1~2초 이내 안정적 응답)
    fast_priority_models = [
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
    ]
    supported = config_manager.get_supported_gemini_models(api_key)
    ordered_models = []
    for m in fast_priority_models:
        if m not in ordered_models:
            ordered_models.append(m)
    for m in supported:
        if m not in ordered_models:
            ordered_models.append(m)

    last_error_msg = ""
    for model in ordered_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                candidates = res.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    if parts and "text" in parts[0]:
                        raw_answer = parts[0]["text"].strip()
                        return verify_and_guard_answer(raw_answer, kb)
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            if e.code in (400, 403):
                if "API_KEY_INVALID" in err_body or "API key not valid" in err_body:
                    return "⚠️ 등록된 Gemini API 키가 유효하지 않습니다. [설정] 탭에서 올바른 API 키를 등록해주세요."
                if "QUOTA_EXCEEDED" in err_body or "RESOURCE_EXHAUSTED" in err_body:
                    last_error_msg = "Google Gemini API 무료 할당량이 일시적으로 소진되었습니다."
                    continue
            last_error_msg = f"HTTP {e.code} ({model})"
            continue
        except (urllib.error.URLError, TimeoutError) as e:
            last_error_msg = f"네트워크 타임아웃 ({model})"
            continue
        except Exception as e:
            last_error_msg = str(e)
            continue

    if last_error_msg:
        return f"❌ 답변 생성에 실패했습니다 ({last_error_msg}). 잠시 후 다시 질문하시거나 [설정] 탭의 API 키를 확인해주세요."
    return "❌ 답변 생성에 실패했습니다. 인터넷 연결 및 [설정] 탭의 API 키를 확인해주세요."

if __name__ == "__main__":
    print("lecture_tutor module loaded successfully!")
