"""
PuLP 최적화 엔진 (포인트 기반)
- Integer Linear Programming으로 교사 스케줄 최적화
- Hard Constraints: 돌봄/행정/휴가 포인트, 하루 최대 슬롯, 최소 인원
- Soft Constraints: 교사 선호도, 연속 업무 최소화
"""

from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional, Set
import streamlit as st
import pandas as pd

from src.config.settings import (
    SlotType, MAX_SLOTS_PER_DAY, VACATION_POINTS,
    VacationRequestType
)
from src.db.models import (
    Vacation, Schedule, VacationRequest, TeacherPreference,
    CareRequirement, FlashTeacher, ExcludedDate, MeetingWeek
)
from src.db.queries import (
    get_vacation_teachers_fresh,
    get_care_requirements, get_flash_teachers,
    get_excluded_dates, get_meeting_weeks, get_teacher_preferences,
    get_vacation_requests, get_admin_requests, save_schedules, calculate_and_save_stats
)
from src.utils.korean_holidays import (
    get_korean_holidays, is_weekend, get_working_days, is_meeting_week
)


# ============================================================
# 최적화 입력 데이터
# ============================================================
class OptimizationInput:
    """최적화에 필요한 모든 입력 데이터"""
    def __init__(self, vacation: Vacation):
        self.vacation = vacation
        self.teachers: List[dict] = []  # 교사 목록 [{id, name, care_points, admin_points, vacation_points, carry_over}]
        self.working_days: List[date] = []  # 근무 가능한 날짜
        self.care_requirements: Dict[Tuple[date, str], int] = {}  # (날짜, AM/PM) -> 필요 인원
        self.flash_teachers: Dict[Tuple[date, str], str] = {}  # (날짜, AM/PM) -> 교사ID
        self.vacation_requests: Dict[str, List[VacationRequest]] = {}  # 교사ID -> 휴가신청 목록
        self.preferences: Dict[str, TeacherPreference] = {}  # 교사ID -> 선호도
        self.meeting_weeks: Set[date] = set()  # 회의 주간 날짜
        self.excluded_dates: Dict[date, str] = {}  # 제외일: date -> time_scope ("ALL" | "AM" | "PM")
        self.excluded_dates_set: Set[date] = set()  # ALL 제외일만 모은 set (working_days 계산용)


# ============================================================
# 최적화 결과
# ============================================================
class OptimizationResult:
    """최적화 결과"""
    def __init__(self):
        self.success: bool = False
        self.schedules: List[Schedule] = []
        self.objective_value: float = 0.0
        self.solver_status: str = ""
        self.error_message: str = ""
        self.stats: Dict = {}


# ============================================================
# PuLP 최적화 엔진
# ============================================================
def run_optimization(vacation: Vacation) -> OptimizationResult:
    """
    PuLP를 사용하여 스케줄 최적화를 실행합니다.
    
    Args:
        vacation: 최적화할 방학 정보
    
    Returns:
        OptimizationResult: 최적화 결과
    """
    result = OptimizationResult()
    
    try:
        # ============================================================
        # 1. 입력 데이터 수집
        # ============================================================
        input_data = _collect_input_data(vacation)
        
        if not input_data.teachers:
            result.error_message = "배정된 교사가 없습니다."
            return result
        
        if not input_data.working_days:
            result.error_message = "근무 가능한 날짜가 없습니다."
            return result
        
        # ============================================================
        # 2. PuLP 모델 생성
        # ============================================================
        import pulp
        
        # 문제 정의 (최대화: 선호도 만족도)
        prob = pulp.LpProblem(
            f"Vacation_Schedule_{vacation.title}",
            pulp.LpMaximize
        )
        
        teachers = input_data.teachers
        days = input_data.working_days
        slot_types = ["AM_Childcare", "PM_Childcare", "AM_Admin", "PM_Admin"]

        # teacher_id (실제 user ID) 목록 — vacation_teacher 행 ID와 구분
        def get_tid(t):
            return t.get("teacher_id") if isinstance(t, dict) else t.teacher_id

        def get_care_points(t):
            return t.get("care_points", 0) if isinstance(t, dict) else t.care_points

        def get_admin_points(t):
            return t.get("admin_points", 0) if isinstance(t, dict) else t.admin_points

        def get_vacation_points(t):
            return t.get("vacation_points", 0) if isinstance(t, dict) else t.vacation_points

        # ============================================================
        # 3. 결정 변수 생성
        # ============================================================
        # x[teacher_id][date][slot] = 1 if teacher works that slot
        x = {}
        for t in teachers:
            tid = get_tid(t)
            x[tid] = {}
            for d in days:
                x[tid][d] = {}
                for s in slot_types:
                    x[tid][d][s] = pulp.LpVariable(
                        f"x_{tid[:8]}_{d.strftime('%Y%m%d')}_{s}",
                        cat=pulp.LpBinary
                    )

        # ============================================================
        # 4. Hard Constraints (필수 제약조건)
        # ============================================================

        # 4-1. 각 교사는 하루 최대 2슬롯
        for t in teachers:
            tid = get_tid(t)
            for d in days:
                prob += pulp.lpSum([x[tid][d][s] for s in slot_types]) <= MAX_SLOTS_PER_DAY

        # 4-2. 각 교사의 포인트 기반 배정
        for t in teachers:
            tid = get_tid(t)
            care_pts = get_care_points(t)
            admin_pts = get_admin_points(t)
            vacation_pts = get_vacation_points(t)
            
            # 돌봄 포인트: AM_Childcare + PM_Childcare <= care_points
            # (돌봄 필요 인원이 부족하면 덜 배정될 수 있음)
            prob += pulp.lpSum([x[tid][d]["AM_Childcare"] + x[tid][d]["PM_Childcare"] for d in days]) <= care_pts
            
            # 행정 포인트: AM_Admin + PM_Admin == admin_points
            prob += pulp.lpSum([x[tid][d]["AM_Admin"] + x[tid][d]["PM_Admin"] for d in days]) == admin_pts
            
            # 휴가 포인트: 교사가 자유롭게 사용 (돌봄 또는 행정)
            # 총 배정 = care_points + admin_points + vacation_points
            total_pts = care_pts + admin_pts + vacation_pts
            prob += pulp.lpSum([x[tid][d][s] for d in days for s in slot_types]) == total_pts

        # 4-3. 오전/오후별 최대 1개 슬롯
        for t in teachers:
            tid = get_tid(t)
            for d in days:
                # 오전: AM_Childcare + AM_Admin <= 1
                prob += x[tid][d]["AM_Childcare"] + x[tid][d]["AM_Admin"] <= 1
                # 오후: PM_Childcare + PM_Admin <= 1
                prob += x[tid][d]["PM_Childcare"] + x[tid][d]["PM_Admin"] <= 1
        
        # 4-4. 돌봄 필요 인원 충족 (반짝선생님 적용)
        for (d, slot_am_pm), required in input_data.care_requirements.items():
            if d not in days:
                continue
            slot = f"{slot_am_pm}_Childcare"
            if slot not in slot_types:
                continue

            flash_key = (d, slot_am_pm)
            if flash_key in input_data.flash_teachers:
                required = max(0, required - 1)

            if required > 0:
                prob += pulp.lpSum([
                    x[get_tid(t)][d][slot] for t in teachers
                    if flash_key not in input_data.flash_teachers or get_tid(t) != input_data.flash_teachers.get(flash_key)
                ]) == required

        # 4-5. 반짝선생님은 해당 슬롯에 배정되지 않음
        for (d, slot_am_pm), flash_tid in input_data.flash_teachers.items():
            slot = f"{slot_am_pm}_Childcare"
            if slot in slot_types and d in days and flash_tid and flash_tid in x:
                prob += x[flash_tid][d][slot] == 0

        # 4-6. 휴가 신청한 날짜는 해당 슬롯 배정 불가
        for tid, requests in input_data.vacation_requests.items():
            if tid not in x:
                continue
            for req in requests:
                req_date = req.date if hasattr(req, 'date') else req.get("date")
                req_type = req.request_type if hasattr(req, 'request_type') else req.get("request_type")
                if req_date not in days:
                    continue
                if req_type in (VacationRequestType.FULL_DAY, "full_day"):
                    for s in slot_types:
                        prob += x[tid][req_date][s] == 0
                elif req_type in (VacationRequestType.AM, "am"):
                    prob += x[tid][req_date]["AM_Childcare"] == 0
                    prob += x[tid][req_date]["AM_Admin"] == 0
                elif req_type in (VacationRequestType.PM, "pm"):
                    prob += x[tid][req_date]["PM_Childcare"] == 0
                    prob += x[tid][req_date]["PM_Admin"] == 0

        # 4-7. 회의 주간: 오후 돌봄 슬롯 없음
        for d in input_data.meeting_weeks:
            if d in days:
                prob += pulp.lpSum([
                    x[get_tid(t)][d]["PM_Childcare"] for t in teachers
                ]) == 0

        # 4-8. 제외일: time_scope에 따라 해당 슬롯 배정 불가
        # (working_days에서 ALL 제외일은 이미 제외되지만, AM/PM 제외일은 여기서 처리)
        for d, scope in input_data.excluded_dates.items():
            if d not in days:
                continue
            if scope == "ALL":
                # ALL은 working_days에서 이미 제외됨 (안전장치)
                for t in teachers:
                    tid = get_tid(t)
                    for s in slot_types:
                        prob += x[tid][d][s] == 0
            elif scope == "AM":
                # 오전 슬롯만 제외
                for t in teachers:
                    tid = get_tid(t)
                    prob += x[tid][d]["AM_Childcare"] == 0
                    prob += x[tid][d]["AM_Admin"] == 0
            elif scope == "PM":
                # 오후 슬롯만 제외
                for t in teachers:
                    tid = get_tid(t)
                    prob += x[tid][d]["PM_Childcare"] == 0
                    prob += x[tid][d]["PM_Admin"] == 0
        
        # ============================================================
        # 5. Soft Constraints (목적 함수 - 선호도 최대화)
        # ============================================================
        
        # 선호도 가중치
        preference_weight = 1.0
        consecutive_penalty = 0.5
        vacation_balance_weight = 0.3
        
        objective_terms = []
        
        for t in teachers:
            tid = get_tid(t)
            prefs = input_data.preferences.get(tid)

            if prefs:
                objective_terms.append(
                    prefs.prefer_care_am / 100.0 *
                    pulp.lpSum([x[tid][d]["AM_Childcare"] for d in days])
                )
                objective_terms.append(
                    prefs.prefer_care_pm / 100.0 *
                    pulp.lpSum([x[tid][d]["PM_Childcare"] for d in days])
                )
                objective_terms.append(
                    prefs.prefer_admin_am / 100.0 *
                    pulp.lpSum([x[tid][d]["AM_Admin"] for d in days])
                )
                objective_terms.append(
                    prefs.prefer_admin_pm / 100.0 *
                    pulp.lpSum([x[tid][d]["PM_Admin"] for d in days])
                )

        # 연속 업무 페널티 (연속 근무 최소화)
        for t in teachers:
            tid = get_tid(t)
            for i in range(len(days) - 1):
                d1, d2 = days[i], days[i + 1]
                # 연속된 날짜에 모두 배정되면 페널티
                y = pulp.LpVariable(f"consec_{tid[:8]}_{d1.strftime('%Y%m%d')}", cat=pulp.LpBinary)
                prob += y >= pulp.lpSum([x[tid][d1][s] for s in slot_types]) + \
                        pulp.lpSum([x[tid][d2][s] for s in slot_types]) - 1
                objective_terms.append(-consecutive_penalty * y)
        
        # 목적 함수 설정
        prob += pulp.lpSum(objective_terms)
        
        # ============================================================
        # 6. 최적화 실행
        # ============================================================
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=120)  # 2분 제한
        prob.solve(solver)
        
        # ============================================================
        # 7. 결과 처리
        # ============================================================
        result.solver_status = pulp.LpStatus[prob.status]
        result.objective_value = pulp.value(prob.objective)
        
        if prob.status == pulp.constants.LpSolutionOptimal:
            schedules = []
            for t in teachers:
                tid = get_tid(t)
                for d in days:
                    for s in slot_types:
                        if pulp.value(x[tid][d][s]) == 1:
                            is_flash = (
                                (d, s.replace("_Childcare", "")) in input_data.flash_teachers and
                                input_data.flash_teachers[(d, s.replace("_Childcare", ""))] == tid
                            )
                            schedules.append(Schedule(
                                vacation_id=vacation.id,
                                teacher_id=tid,
                                date=d,
                                slot_type=s,
                                is_flash_teacher=is_flash
                            ))
            
            result.schedules = schedules
            result.success = True
            
            # 통계 계산
            result.stats = _calculate_stats(schedules, teachers)
        else:
            # 실패 원인 분석
            total_points = sum(
                get_care_points(t) + get_admin_points(t) + get_vacation_points(t)
                for t in teachers
            )
            total_slots_available = len(days) * 2 * len(teachers)  # 하루 최대 2슬롯
            total_care_needed = sum(input_data.care_requirements.values())
            
            # 교사별 포인트 합계
            teacher_point_details = []
            for t in teachers:
                tid = get_tid(t)
                tname = t.get("teacher_name", "Unknown") if isinstance(t, dict) else "Unknown"
                cp = get_care_points(t)
                ap = get_admin_points(t)
                vp = get_vacation_points(t)
                teacher_point_details.append(f"  - {tname}: 돌봄={cp}, 행정={ap}, 휴가={vp}, 합계={cp+ap+vp}")
            
            # 휴가 신청으로 인한 제약 분석
            vacation_days = set()
            for tid, requests in input_data.vacation_requests.items():
                for req in requests:
                    req_date = req.date if hasattr(req, 'date') else req.get("date")
                    vacation_days.add(req_date)
            
            # 회의 주간 분석
            meeting_days_count = len(input_data.meeting_weeks)
            
            error_parts = [f"PuLP 상태: {result.solver_status}"]
            error_parts.append(f"총 포인트 합계: {total_points}")
            error_parts.append(f"최대 가능 슬롯: {total_slots_available}")
            error_parts.append(f"돌봄 필요 슬롯 합계: {total_care_needed}")
            error_parts.append(f"휴가 신청 건수: {len(vacation_days)}일")
            error_parts.append(f"회의 주간: {meeting_days_count}일")
            error_parts.append(f"\n📋 교사별 포인트:")
            error_parts.extend(teacher_point_details)
            
            if total_points > total_slots_available:
                error_parts.append(f"\n⚠️ 총 포인트 합계({total_points})가 최대 가능 슬롯({total_slots_available})보다 큽니다!")
                error_parts.append("👉 교사별 포인트를 줄이거나, 근무 가능한 날짜를 늘리세요.")
            
            result.error_message = "\n".join(error_parts)
        
        return result
        
    except Exception as e:
        result.error_message = str(e)
        result.success = False
        return result


# ============================================================
# 헬퍼 함수
# ============================================================
def _collect_input_data(vacation: Vacation) -> OptimizationInput:
    """최적화에 필요한 모든 입력 데이터를 수집합니다."""
    input_data = OptimizationInput(vacation)
    
    # 교사 목록 — 캐시 없이 최신 DB 값 조회 (1차 최적화 직후 admin_points 반영 보장)
    teachers_data = get_vacation_teachers_fresh(vacation.id)
    input_data.teachers = teachers_data
    
    # 제외일 (공휴일 + 학교 휴일) - time_scope 정보 포함
    excluded = get_excluded_dates(vacation.id)
    for e in excluded:
        e_date = e.date if hasattr(e, 'date') else e.get("date")
        e_scope = e.time_scope if hasattr(e, 'time_scope') else e.get("time_scope", "ALL")
        input_data.excluded_dates[e_date] = e_scope
    
    # 한국 공휴일 추가 (ALL로 간주)
    for y in range(vacation.start_date.year, vacation.end_date.year + 1):
        for h in get_korean_holidays(y):
            if vacation.start_date <= h <= vacation.end_date:
                input_data.excluded_dates[h] = "ALL"
    
    # 근무 가능한 날짜: time_scope="ALL"인 날짜만 제외
    all_excluded = {d for d, scope in input_data.excluded_dates.items() if scope == "ALL"}
    input_data.excluded_dates_set = all_excluded
    input_data.working_days = get_working_days(
        vacation.start_date,
        vacation.end_date,
        all_excluded
    )
    
    # 돌봄 필요 인원
    care_reqs = get_care_requirements(vacation.id)
    for cr in care_reqs:
        input_data.care_requirements[(cr.date, cr.slot_type)] = cr.required_count
    
    # 반짝선생님
    # get_flash_teachers()는 raw dict 반환 → date가 문자열일 수 있으므로 변환
    flash_data = get_flash_teachers(vacation.id)
    for f in flash_data:
        f_date = f.get("date") if isinstance(f, dict) else f.date
        f_slot = f.get("slot_type") if isinstance(f, dict) else f.slot_type
        f_teacher = f.get("teacher_id") if isinstance(f, dict) else f.teacher_id
        if isinstance(f_date, str):
            f_date = date.fromisoformat(f_date)
        input_data.flash_teachers[(f_date, f_slot)] = f_teacher
    
    # 교사 선호도
    for t in teachers_data:
        tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
        prefs = get_teacher_preferences(tid, vacation.id)
        if prefs:
            input_data.preferences[tid] = prefs
    
    # 휴가 신청
    for t in teachers_data:
        tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
        requests = get_vacation_requests(tid, vacation.id)
        if requests:
            input_data.vacation_requests[tid] = requests
    
    # 회의 주간
    meetings = get_meeting_weeks(vacation.id)
    for m in meetings:
        m_start = m.week_start if hasattr(m, 'week_start') else m.get("week_start")
        m_end = m.week_end if hasattr(m, 'week_end') else m.get("week_end")
        d = m_start
        while d <= m_end:
            input_data.meeting_weeks.add(d)
            d += timedelta(days=1)
    
    return input_data


def _calculate_stats(schedules: List[Schedule], teachers: List[dict]) -> Dict:
    """최적화 결과 통계를 계산합니다."""
    stats = {
        "total_schedules": len(schedules),
        "teacher_stats": {}
    }

    for t in teachers:
        tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
        tname = t.get("teacher_name", "Unknown") if isinstance(t, dict) else "Unknown"
        
        teacher_schedules = [s for s in schedules if s.teacher_id == tid]
        am_care_count = len([s for s in teacher_schedules if s.slot_type == "AM_Childcare"])
        pm_care_count = len([s for s in teacher_schedules if s.slot_type == "PM_Childcare"])
        am_admin_count = len([s for s in teacher_schedules if s.slot_type == "AM_Admin"])
        pm_admin_count = len([s for s in teacher_schedules if s.slot_type == "PM_Admin"])
        
        stats["teacher_stats"][tid] = {
            "name": tname,
            "total": len(teacher_schedules),
            "care": am_care_count + pm_care_count,
            "admin": am_admin_count + pm_admin_count,
            "am_care": am_care_count,
            "pm_care": pm_care_count,
            "am_admin": am_admin_count,
            "pm_admin": pm_admin_count,
        }
    
    return stats


# ============================================================
# 최적화 결과 미리보기
# ============================================================
# ============================================================
# 규칙 기반 랜덤 배정 (교사 입력 기반)
# ============================================================
def run_random_assignment(vacation: Vacation) -> OptimizationResult:
    """
    2차 랜덤 배정:
    - _collect_input_data 로 모든 입력 데이터 수집 (teachers는 캐시 없이 최신값)
    - Phase 1: 행정 신청 → 해당 날짜·슬롯 고정
    - Phase 2: 돌봄 배정 → 슬롯별 필요 인원 충족 (care_points 소진)
    - Phase 3: 나머지 행정 랜덤 배정 → admin_points 소진
    """
    import random
    result = OptimizationResult()

    try:
        # _collect_input_data 안에서 get_vacation_teachers_fresh 사용 → 최신 포인트 보장
        inp = _collect_input_data(vacation)

        teachers = inp.teachers
        if not teachers:
            result.error_message = "배정된 교사가 없습니다."
            return result
        if not inp.working_days:
            result.error_message = "근무 가능한 날짜가 없습니다."
            return result

        def get_tid(t):
            return t.get("teacher_id", "") if isinstance(t, dict) else t.teacher_id

        def _valid(d, half):
            scope = inp.excluded_dates.get(d)
            if scope == "ALL":                 return False
            if scope == "AM" and half == "AM": return False
            if scope == "PM" and half == "PM": return False
            if half == "PM" and d in inp.meeting_weeks: return False
            return True

        all_slots = [(d, h) for d in inp.working_days
                     for h in ("AM", "PM") if _valid(d, h)]

        # ── 교사별 사전 데이터 수집 ─────────────────────────────────
        t_care  = {}   # tid -> 설정 돌봄 횟수
        t_admin = {}   # tid -> 남은 행정 횟수
        t_blocked = {} # tid -> 휴가로 차단된 (date, half) set
        t_used    = {} # tid -> 이미 배정된 (date, half) set

        for t in teachers:
            tid = get_tid(t)
            t_care[tid]    = int(t.get("care_points",  0) if isinstance(t, dict) else t.care_points)
            t_admin[tid]   = int(t.get("admin_points", 0) if isinstance(t, dict) else t.admin_points)
            t_blocked[tid] = set()
            t_used[tid]    = set()

            # 휴가 신청 → 차단
            for r in inp.vacation_requests.get(tid, []):
                r_date = r.date if hasattr(r, "date") else r.get("date")
                r_type = (r.request_type if hasattr(r, "request_type")
                          else r.get("request_type", ""))
                if r_type in ("full_day", VacationRequestType.FULL_DAY):
                    t_blocked[tid].add((r_date, "AM"))
                    t_blocked[tid].add((r_date, "PM"))
                elif r_type in ("am", VacationRequestType.AM):
                    t_blocked[tid].add((r_date, "AM"))
                elif r_type in ("pm", VacationRequestType.PM):
                    t_blocked[tid].add((r_date, "PM"))

        schedules: List[Schedule] = []

        # ── Phase 1: 행정 신청 고정 배정 ────────────────────────────
        for t in teachers:
            tid = get_tid(t)
            adm_reqs = get_admin_requests(tid, vacation.id)
            for r in adm_reqs:
                r_date = r.date if hasattr(r, "date") else r.get("date")
                r_slot = (r.slot_type if hasattr(r, "slot_type")
                           else r.get("slot_type", "AM"))
                key = (r_date, r_slot)
                if not _valid(r_date, r_slot): continue
                if key in t_blocked[tid]: continue
                if key in t_used[tid]: continue
                schedules.append(Schedule(
                    vacation_id=vacation.id, teacher_id=tid,
                    date=r_date, slot_type=f"{r_slot}_Admin",
                    is_flash_teacher=False
                ))
                t_used[tid].add(key)
                t_admin[tid] = max(0, t_admin[tid] - 1)

        # ── Phase 2: 돌봄 배정 (슬롯별 필요 인원 충족, care_points 소진) ──
        # 각 슬롯의 남은 필요 인원
        slot_need: Dict = {}
        for (d, half), req in inp.care_requirements.items():
            if not _valid(d, half): continue
            flash_key = (d, half)
            n = req - (1 if flash_key in inp.flash_teachers else 0)
            if n > 0:
                slot_need[(d, half)] = n

        for d in inp.working_days:
            for half in ("AM", "PM"):
                if not _valid(d, half): continue
                needed = slot_need.get((d, half), 0)
                if needed <= 0: continue

                flash_tid = inp.flash_teachers.get((d, half))
                slot_key  = f"{half}_Childcare"

                # 이미 배정된 수 차감
                already = sum(1 for s in schedules
                              if s.date == d and s.slot_type == slot_key)
                needed -= already
                if needed <= 0: continue

                # 배정 가능 교사: care 남음 + 반짝선생님 아님 + 차단 없음 + 미배정
                candidates = [
                    t for t in teachers
                    if t_care[get_tid(t)] > 0
                    and get_tid(t) != flash_tid
                    and (d, half) not in t_blocked[get_tid(t)]
                    and (d, half) not in t_used[get_tid(t)]
                ]
                random.shuffle(candidates)

                for t in candidates[:needed]:
                    tid = get_tid(t)
                    schedules.append(Schedule(
                        vacation_id=vacation.id, teacher_id=tid,
                        date=d, slot_type=slot_key,
                        is_flash_teacher=False
                    ))
                    t_used[tid].add((d, half))
                    t_care[tid] -= 1

        # ── Phase 3: 나머지 행정 랜덤 배정 (admin_points 소진) ─────
        for t in teachers:
            tid   = get_tid(t)
            need  = t_admin[tid]
            if need <= 0: continue

            avail = [(d, h) for (d, h) in all_slots
                     if (d, h) not in t_blocked[tid]
                     and (d, h) not in t_used[tid]]
            random.shuffle(avail)

            for d, h in avail:
                if need <= 0: break
                schedules.append(Schedule(
                    vacation_id=vacation.id, teacher_id=tid,
                    date=d, slot_type=f"{h}_Admin",
                    is_flash_teacher=False
                ))
                t_used[tid].add((d, h))
                need -= 1

        result.schedules     = schedules
        result.success       = True
        result.solver_status = "랜덤 배정 완료"
        result.stats         = _calculate_stats(schedules, teachers)
        return result

    except Exception as e:
        result.error_message = str(e)
        result.success       = False
        return result


def render_optimization_preview(result: OptimizationResult):
    """최적화 결과를 미리보기로 표시합니다."""
    
    if not result.success:
        st.error(f"❌ 최적화 실패: {result.error_message}")
        return
    
    st.success(f"✅ 최적화 완료! (상태: {result.solver_status})")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 총 배정", result.stats.get("total_schedules", 0))
    with col2:
        st.metric("🎯 목적 함수", f"{result.objective_value:.2f}")
    with col3:
        st.metric("👨‍🏫 교사 수", len(result.stats.get("teacher_stats", {})))
    
    # 교사별 통계
    st.markdown("### 👨‍🏫 교사별 배정 현황")
    
    stats_data = []
    for tid, tstat in result.stats.get("teacher_stats", {}).items():
        stats_data.append({
            "교사": tstat["name"],
            "총 배정": tstat["total"],
            "오전돌봄": tstat["am_care"],
            "오후돌봄": tstat["pm_care"],
            "오전행정": tstat["am_admin"],
            "오후행정": tstat["pm_admin"],
        })
    
    if stats_data:
        df = pd.DataFrame(stats_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 날짜별 배정 현황
    st.markdown("### 📅 날짜별 배정 현황")
    
    date_stats = {}
    for s in result.schedules:
        if s.date not in date_stats:
            date_stats[s.date] = {
                "AM_Childcare": 0, "PM_Childcare": 0,
                "AM_Admin": 0, "PM_Admin": 0,
                "total": 0
            }
        date_stats[s.date]["total"] += 1
        if s.slot_type in date_stats[s.date]:
            date_stats[s.date][s.slot_type] += 1
    
    date_data = []
    for d in sorted(date_stats.keys()):
        ds = date_stats[d]
        date_data.append({
            "날짜": d.strftime("%m/%d(%a)"),
            "오전돌봄": ds["AM_Childcare"],
            "오후돌봄": ds["PM_Childcare"],
            "오전행정": ds["AM_Admin"],
            "오후행정": ds["PM_Admin"],
            "합계": ds["total"],
        })
    
    if date_data:
        df = pd.DataFrame(date_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
