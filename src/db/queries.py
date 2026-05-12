"""
Supabase DB 쿼리 함수 모음
- 각 테이블별 CRUD 함수
- 복잡한 조인 쿼리
- 데이터 변환 및 검증
- 데모 모드 지원 (Supabase 없이도 동작)
"""

from datetime import date, datetime
from typing import Optional, List
import streamlit as st
from src.config.supabase_client import (
    get_supabase_client, is_demo_mode,
    query_table, insert_record, upsert_record, update_record, delete_record
)

from src.db.models import (
    Vacation, VacationTeacher, CareRequirement, FlashTeacher,
    ExcludedDate, MeetingWeek, TeacherPreference, VacationRequest,
    Schedule, VacationStat, MeetingTeam, DailyMeetingAssignment, AdminRequest
)


def clear_vacation_cache():
    """쓰기 작업 후 캐시 전체 삭제"""
    st.cache_data.clear()


# ============================================================
# 헬퍼 함수
# ============================================================
def _handle_error(e: Exception, operation: str) -> None:
    """Supabase 에러를 Streamlit 에러 메시지로 변환"""
    error_msg = str(e)
    st.error(f"❌ {operation} 중 오류 발생: {error_msg}")


# ============================================================
# 방학 (Vacations)
# ============================================================
@st.cache_data(ttl=30)
def get_vacations() -> List[Vacation]:
    """모든 방학 목록 조회 (최신순)"""
    try:
        data = query_table("vacations")
        data.sort(key=lambda x: (x.get("year", 0), x.get("created_at", "")), reverse=True)
        return [Vacation(**item) for item in data]
    except Exception as e:
        _handle_error(e, "방학 목록 조회")
        return []


@st.cache_data(ttl=30)
def get_vacation(vacation_id: str) -> Optional[Vacation]:
    """특정 방학 정보 조회"""
    try:
        data = query_table("vacations", eq={"id": vacation_id})
        return Vacation(**data[0]) if data else None
    except Exception as e:
        _handle_error(e, "방학 정보 조회")
        return None


def create_vacation(vacation: Vacation) -> Optional[Vacation]:
    """새 방학 생성"""
    try:
        data = vacation.model_dump(
            exclude={"id", "created_at", "updated_at"},
            exclude_none=True,
            mode="json"
        )
        result = insert_record("vacations", data)
        return Vacation(**result) if result else None
    except Exception as e:
        _handle_error(e, "방학 생성")
        return None


def update_vacation(vacation_id: str, updates: dict) -> bool:
    """방학 정보 업데이트"""
    try:
        updates["updated_at"] = datetime.now().isoformat()
        result = update_record("vacations", updates, {"id": vacation_id})
        return result is not None
    except Exception as e:
        _handle_error(e, "방학 정보 업데이트")
        return False


# ============================================================
# 교사 프로필 (Profiles)
# ============================================================
@st.cache_data(ttl=30)
def get_all_teachers() -> List[dict]:
    """모든 교사(role='teacher') 목록 조회"""
    try:
        data = query_table("profiles", eq={"role": "teacher"})
        return data
    except Exception as e:
        _handle_error(e, "교사 목록 조회")
        return []


def delete_teacher_account(teacher_id: str) -> bool:
    """선생님 계정 및 관련 데이터 모두 삭제 (profiles, vacation_teachers, teacher_preferences, vacation_requests, admin_requests, schedules, flash_teachers 등)"""
    try:
        # 관련 테이블에서 해당 교사 데이터 삭제
        delete_record("teacher_preferences", {"teacher_id": teacher_id})
        delete_record("vacation_requests", {"teacher_id": teacher_id})
        delete_record("admin_requests", {"teacher_id": teacher_id})
        delete_record("flash_teachers", {"teacher_id": teacher_id})
        delete_record("schedules", {"teacher_id": teacher_id})
        delete_record("vacation_teachers", {"teacher_id": teacher_id})
        delete_record("vacation_stats", {"teacher_id": teacher_id})
        # 프로필 삭제
        result = delete_record("profiles", {"id": teacher_id})
        return result
    except Exception as e:
        _handle_error(e, "계정 삭제")
        return False


def reset_vacation_assignments(vacation_id: str) -> bool:
    """특정 방학의 배정 초기화 (스케줄, 통계, 포인트, is_ready 상태 초기화)"""
    try:
        delete_record("schedules", {"vacation_id": vacation_id})
        delete_record("vacation_stats", {"vacation_id": vacation_id})
        # 해당 방학에 속한 모든 교사의 포인트 + is_ready 초기화
        vt_records = query_table("vacation_teachers", eq={"vacation_id": vacation_id})
        for vt in vt_records:
            tid = vt.get("teacher_id")
            if tid:
                update_record("vacation_teachers", {
                    "is_ready": False,
                    "care_points": 0,
                    "admin_points": 0,
                    "vacation_points": 0,
                    "carry_over_points": 0,
                }, {"vacation_id": vacation_id, "teacher_id": tid})
        return True
    except Exception as e:
        _handle_error(e, "방학 배정 초기화")
        return False


def reset_all_vacation_assignments() -> bool:
    """모든 방학 배정 초기화 (스케줄, 통계, 포인트, is_ready 상태 초기화)"""
    try:
        vacations = get_vacations()
        for v in vacations:
            reset_vacation_assignments(v.id)
        return True
    except Exception as e:
        _handle_error(e, "전체 방학 배정 초기화")
        return False


def delete_vacation(vacation_id: str) -> bool:
    """방학 및 관련 데이터 모두 삭제"""
    try:
        # 관련 데이터 먼저 삭제
        delete_record("schedules", {"vacation_id": vacation_id})
        delete_record("vacation_stats", {"vacation_id": vacation_id})
        delete_record("vacation_teachers", {"vacation_id": vacation_id})
        delete_record("teacher_preferences", {"vacation_id": vacation_id})
        delete_record("vacation_requests", {"vacation_id": vacation_id})
        delete_record("admin_requests", {"vacation_id": vacation_id})
        delete_record("care_requirements", {"vacation_id": vacation_id})
        delete_record("flash_teachers", {"vacation_id": vacation_id})
        delete_record("excluded_dates", {"vacation_id": vacation_id})
        delete_record("meeting_weeks", {"vacation_id": vacation_id})
        delete_record("meeting_teams", {"vacation_id": vacation_id})
        delete_record("daily_meeting_assignments", {"vacation_id": vacation_id})
        # 방학 자체 삭제
        result = delete_record("vacations", {"id": vacation_id})
        return result
    except Exception as e:
        _handle_error(e, "방학 삭제")
        return False


# ============================================================
# 방학별 교사 배정 (Vacation Teachers)
# ============================================================
@st.cache_data(ttl=30)
def get_vacation_teachers(vacation_id: str) -> List[VacationTeacher]:
    """특정 방학에 배정된 모든 교사 목록 조회"""
    try:
        data = query_table("vacation_teachers", eq={"vacation_id": vacation_id})
        if not data:
            return []

        # 교사 이름/이메일 조인 (한 번에 모든 프로필 조회)
        teacher_ids = [item.get("teacher_id") for item in data if item.get("teacher_id")]
        profiles = query_table("profiles")
        profile_map = {p["id"]: p for p in profiles if p.get("id") in teacher_ids}

        result = []
        for item in data:
            teacher_id = item.get("teacher_id")
            profile = profile_map.get(teacher_id)
            if profile:
                item["teacher_name"] = profile.get("name", "")
                item["teacher_email"] = profile.get("email", "")
            result.append(item)

        return result
    except Exception as e:
        _handle_error(e, "교사 목록 조회")
        return []


def add_teacher_to_vacation(vacation_id: str, teacher_id: str) -> bool:
    """방학에 교사 추가 (포인트 기반)"""
    try:
        data = {
            "vacation_id": vacation_id,
            "teacher_id": teacher_id,
            "care_points": 0,
            "admin_points": 0,
            "vacation_points": 0,
            "carry_over_points": 0
        }
        # upsert_record 사용 (조회 후 있으면 업데이트, 없으면 삽입)
        result = upsert_record("vacation_teachers", data, {
            "vacation_id": vacation_id,
            "teacher_id": teacher_id
        })
        if result:
            clear_vacation_cache()
        return result is not None
    except Exception as e:
        _handle_error(e, "교사 추가")
        return False


def remove_teacher_from_vacation(vacation_id: str, teacher_id: str) -> bool:
    """방학에서 교사 제거"""
    try:
        return delete_record("vacation_teachers", {
            "vacation_id": vacation_id,
            "teacher_id": teacher_id
        })
    except Exception as e:
        _handle_error(e, "교사 제거")
        return False


@st.cache_data(ttl=30)
def get_vacation_teacher_points(vacation_id: str, teacher_id: str) -> Optional[dict]:
    """특정 교사의 포인트 정보 조회"""
    try:
        data = query_table("vacation_teachers", eq={
            "vacation_id": vacation_id,
            "teacher_id": teacher_id
        })
        if data:
            return data[0]
        return None
    except Exception as e:
        _handle_error(e, "교사 포인트 조회")
        return None


def update_teacher_points(vacation_id: str, teacher_id: str,
                          care_points: Optional[int] = None,
                          admin_points: Optional[int] = None,
                          vacation_points: Optional[int] = None,
                          carry_over_points: Optional[int] = None) -> bool:
    """교사별 포인트 업데이트"""
    try:
        updates = {}
        if care_points is not None:
            updates["care_points"] = care_points
        if admin_points is not None:
            updates["admin_points"] = admin_points
        if vacation_points is not None:
            updates["vacation_points"] = vacation_points
        if carry_over_points is not None:
            updates["carry_over_points"] = carry_over_points

        if not updates:
            return True

        result = update_record("vacation_teachers", updates, {
            "vacation_id": vacation_id,
            "teacher_id": teacher_id
        })
        return result is not None
    except Exception as e:
        _handle_error(e, "포인트 업데이트")
        return False


def update_teacher_ready_status(vacation_id: str, teacher_id: str, is_ready: bool) -> bool:
    """교사의 설정 완료 상태 업데이트"""
    try:
        result = update_record("vacation_teachers", {"is_ready": is_ready}, {
            "vacation_id": vacation_id,
            "teacher_id": teacher_id
        })
        return result is not None
    except Exception as e:
        _handle_error(e, "교사 완료 상태 업데이트")
        return False


@st.cache_data(ttl=30)
def get_teachers_ready_status(vacation_id: str) -> List[dict]:
    """모든 교사의 완료 상태 조회 (교사명 포함)"""
    try:
        data = query_table("vacation_teachers", eq={"vacation_id": vacation_id})
        if not data:
            return []

        # 한 번에 모든 프로필 조회
        teacher_ids = [item.get("teacher_id") for item in data if item.get("teacher_id")]
        profiles = query_table("profiles")
        profile_map = {p["id"]: p["name"] for p in profiles if p.get("id") in teacher_ids}

        result = []
        for item in data:
            teacher_id = item.get("teacher_id")
            teacher_name = profile_map.get(teacher_id, "")
            result.append({
                "teacher_id": teacher_id,
                "teacher_name": teacher_name,
                "is_ready": item.get("is_ready", False)
            })
        return result
    except Exception as e:
        _handle_error(e, "교사 완료 상태 조회")
        return []


def is_all_teachers_ready(vacation_id: str) -> bool:
    """모든 교사가 설정을 완료했는지 확인"""
    try:
        status_list = get_teachers_ready_status(vacation_id)
        if not status_list:
            return False
        return all(item.get("is_ready", False) for item in status_list)
    except Exception as e:
        _handle_error(e, "전체 완료 확인")
        return False


def update_all_teacher_admin_points(vacation_id: str, admin_points: int) -> bool:
    """모든 교사의 행정 포인트를 동일하게 설정"""
    try:
        teachers = get_vacation_teachers(vacation_id)
        success = True
        for t in teachers:
            tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
            if not update_teacher_points(vacation_id, tid, admin_points=admin_points):
                success = False
        return success
    except Exception as e:
        _handle_error(e, "전체 행정 포인트 설정")
        return False


# ============================================================
# 돌봄 필요 인원 (Care Requirements)
# ============================================================
@st.cache_data(ttl=30)
def get_care_requirements(vacation_id: str) -> List[CareRequirement]:
    """특정 방학의 모든 돌봄 필요 인원 조회"""
    try:
        data = query_table("care_requirements", eq={"vacation_id": vacation_id})
        data.sort(key=lambda x: x.get("date", ""))
        return [CareRequirement(**item) for item in data]
    except Exception as e:
        _handle_error(e, "돌봄 필요 인원 조회")
        return []


def set_care_requirement(vacation_id: str, date_val: date, slot_type: str, count: int) -> bool:
    """특정 날짜·시간대의 돌봄 필요 인원 설정 (UPSERT)"""
    try:
        date_str = date_val.isoformat() if hasattr(date_val, 'isoformat') else date_val
        data = {
            "vacation_id": vacation_id,
            "date": date_str,
            "slot_type": slot_type,
            "required_count": count
        }
        # 먼저 기존 레코드 조회
        existing = query_table("care_requirements", eq={
            "vacation_id": vacation_id,
            "date": date_str,
            "slot_type": slot_type
        })
        if existing:
            # 있으면 업데이트
            result = update_record("care_requirements", data, {
                "vacation_id": vacation_id,
                "date": date_str,
                "slot_type": slot_type
            })
        else:
            # 없으면 삽입
            result = insert_record("care_requirements", data)
        return result is not None
    except Exception as e:
        _handle_error(e, "돌봄 필요 인원 설정")
        return False


# ============================================================
# 반짝선생님 (Flash Teachers)
# ============================================================
@st.cache_data(ttl=30)
def get_flash_teachers(vacation_id: str) -> List[FlashTeacher]:
    """특정 방학의 모든 반짝선생님 정보 조회"""
    try:
        data = query_table("flash_teachers", eq={"vacation_id": vacation_id})
        if not data:
            return []
        data.sort(key=lambda x: x.get("date", ""))

        # 한 번에 모든 프로필 조회
        teacher_ids = [item.get("teacher_id") for item in data if item.get("teacher_id")]
        profiles = query_table("profiles")
        profile_map = {p["id"]: p["name"] for p in profiles if p.get("id") in teacher_ids}

        result = []
        for item in data:
            teacher_id = item.get("teacher_id")
            if teacher_id and teacher_id in profile_map:
                item["teacher_name"] = profile_map[teacher_id]
            result.append(item)

        return result
    except Exception as e:
        _handle_error(e, "반짝선생님 조회")
        return []


def add_flash_teacher(vacation_id: str, date_val: date, slot_type: str, teacher_id: str) -> bool:
    """반짝선생님 등록 (UPSERT)"""
    try:
        data = {
            "vacation_id": vacation_id,
            "teacher_id": teacher_id,
            "date": date_val.isoformat(),
            "slot_type": slot_type
        }
        result = upsert_record("flash_teachers", data, {
            "vacation_id": vacation_id,
            "teacher_id": teacher_id,
            "date": date_val.isoformat(),
            "slot_type": slot_type
        }, on_conflict="vacation_id,teacher_id,date,slot_type")
        return result is not None
    except Exception as e:
        _handle_error(e, "반짝선생님 등록")
        return False


def remove_flash_teacher(flash_id: str) -> bool:
    """반짝선생님 삭제"""
    try:
        return delete_record("flash_teachers", {"id": flash_id})
    except Exception as e:
        _handle_error(e, "반짝선생님 삭제")
        return False


# ============================================================
# 제외일 (Excluded Dates)
# ============================================================
@st.cache_data(ttl=30)
def get_excluded_dates(vacation_id: str) -> List[ExcludedDate]:
    """특정 방학의 모든 제외일 조회"""
    try:
        data = query_table("excluded_dates", eq={"vacation_id": vacation_id})
        data.sort(key=lambda x: x.get("date", ""))
        return [ExcludedDate(**item) for item in data]
    except Exception as e:
        _handle_error(e, "제외일 조회")
        return []


def add_excluded_date(vacation_id: str, date_val: date, reason: str, is_holiday: bool = True) -> bool:
    """제외일 추가"""
    try:
        date_str = date_val.isoformat() if hasattr(date_val, 'isoformat') else date_val
        data = {
            "vacation_id": vacation_id,
            "date": date_str,
            "reason": reason,
            "is_holiday": is_holiday,
        }
        # upsert_record 사용 (조회 후 있으면 업데이트, 없으면 삽입)
        result = upsert_record("excluded_dates", data, {
            "vacation_id": vacation_id,
            "date": date_str
        })
        if result:
            clear_vacation_cache()
        return result is not None
    except Exception as e:
        _handle_error(e, "제외일 추가")
        return False


def remove_excluded_date(excluded_id: str) -> bool:
    """제외일 삭제"""
    try:
        result = delete_record("excluded_dates", {"id": excluded_id})
        if result:
            clear_vacation_cache()
        return result
    except Exception as e:
        _handle_error(e, "제외일 삭제")
        return False


# ============================================================
# 회의 주간 (Meeting Weeks)
# ============================================================
@st.cache_data(ttl=30)
def get_meeting_weeks(vacation_id: str) -> List[MeetingWeek]:
    """특정 방학의 모든 회의 주간 조회"""
    try:
        data = query_table("meeting_weeks", eq={"vacation_id": vacation_id})
        data.sort(key=lambda x: x.get("week_start", ""))
        return [MeetingWeek(**item) for item in data]
    except Exception as e:
        _handle_error(e, "회의 주간 조회")
        return []


def add_meeting_week(vacation_id: str, week_start: date, week_end: date) -> bool:
    """회의 주간 추가 (UPSERT)"""
    try:
        data = {
            "vacation_id": vacation_id,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat()
        }
        result = upsert_record("meeting_weeks", data, {
            "vacation_id": vacation_id,
            "week_start": week_start.isoformat()
        }, on_conflict="vacation_id,week_start")
        return result is not None
    except Exception as e:
        _handle_error(e, "회의 주간 추가")
        return False


def remove_meeting_week(meeting_id: str) -> bool:
    """회의 주간 삭제"""
    try:
        return delete_record("meeting_weeks", {"id": meeting_id})
    except Exception as e:
        _handle_error(e, "회의 주간 삭제")
        return False


# ============================================================
# 교사 선호도 (Teacher Preferences)
# ============================================================
@st.cache_data(ttl=30)
def get_teacher_preferences(teacher_id: str, vacation_id: str) -> Optional[TeacherPreference]:
    """특정 교사의 방학별 선호도 조회"""
    try:
        data = query_table("teacher_preferences", eq={
            "teacher_id": teacher_id,
            "vacation_id": vacation_id
        })
        return TeacherPreference(**data[0]) if data else None
    except Exception as e:
        return None  # 선호도가 없으면 None 반환 (에러 아님)


def save_teacher_preferences(prefs: TeacherPreference) -> bool:
    """교사 선호도 저장 (UPSERT)"""
    try:
        data = prefs.model_dump(exclude={"id", "created_at", "updated_at"}, exclude_none=True)
        result = upsert_record("teacher_preferences", data, {
            "teacher_id": prefs.teacher_id,
            "vacation_id": prefs.vacation_id
        })
        return result is not None
    except Exception as e:
        _handle_error(e, "선호도 저장")
        return False


# ============================================================
# 휴가 신청 (Vacation Requests)
# ============================================================
@st.cache_data(ttl=30)
def get_vacation_requests(teacher_id: str, vacation_id: str) -> List[VacationRequest]:
    """특정 교사의 방학별 휴가 신청 목록 조회"""
    try:
        data = query_table("vacation_requests", eq={
            "teacher_id": teacher_id,
            "vacation_id": vacation_id
        })
        data.sort(key=lambda x: x.get("date", ""))
        return [VacationRequest(**item) for item in data]
    except Exception as e:
        _handle_error(e, "휴가 신청 조회")
        return []


def save_vacation_request(request: VacationRequest) -> bool:
    """휴가 신청 저장 (UPSERT)"""
    try:
        data = request.model_dump(exclude={"id", "created_at", "updated_at"}, exclude_none=True, mode="json")
        date_str = data["date"]
        result = upsert_record("vacation_requests", data, {
            "teacher_id": request.teacher_id,
            "vacation_id": request.vacation_id,
            "date": date_str
        })
        return result is not None
    except Exception as e:
        _handle_error(e, "휴가 신청 저장")
        return False


def delete_vacation_request(request_id: str) -> bool:
    """휴가 신청 삭제"""
    try:
        return delete_record("vacation_requests", {"id": request_id})
    except Exception as e:
        _handle_error(e, "휴가 신청 삭제")
        return False


# ============================================================
# 최종 스케줄 (Schedules)
# ============================================================
@st.cache_data(ttl=30)
def get_schedules(vacation_id: str, teacher_id: Optional[str] = None) -> List[Schedule]:
    """
    특정 방학의 스케줄 조회

    Args:
        vacation_id: 방학 UUID
        teacher_id: 특정 교사만 조회 (None이면 전체)
    """
    try:
        if teacher_id:
            data = query_table("schedules", eq={
                "vacation_id": vacation_id,
                "teacher_id": teacher_id
            })
        else:
            data = query_table("schedules", eq={"vacation_id": vacation_id})

        data.sort(key=lambda x: x.get("date", ""))
        return [Schedule(**item) for item in data]
    except Exception as e:
        _handle_error(e, "스케줄 조회")
        return []


def save_schedules(schedules: List[Schedule]) -> bool:
    """
    최적화된 스케줄 일괄 저장

    기존 스케줄을 모두 삭제하고 새로 저장합니다.
    """
    try:
        if not schedules:
            return False

        vacation_id = schedules[0].vacation_id

        # 기존 스케줄 삭제
        delete_record("schedules", {"vacation_id": vacation_id})

        # 새 스케줄 저장
        for s in schedules:
            data = s.model_dump(
                exclude={"id", "created_at", "updated_at"},
                exclude_none=True,
                mode="json"
            )
            insert_record("schedules", data)

        return True
    except Exception as e:
        _handle_error(e, "스케줄 저장")
        return False


# ============================================================
# 방학별 통계 (Vacation Stats)
# ============================================================
@st.cache_data(ttl=30)
def get_vacation_stats(vacation_id: str) -> List[VacationStat]:
    """특정 방학의 모든 교사 통계 조회"""
    try:
        data = query_table("vacation_stats", eq={"vacation_id": vacation_id})
        return [VacationStat(**item) for item in data]
    except Exception as e:
        _handle_error(e, "통계 조회")
        return []


# ============================================================
# 회의 팀 (Meeting Teams)
# ============================================================
@st.cache_data(ttl=30)
def get_meeting_teams(vacation_id: str) -> List[MeetingTeam]:
    """특정 방학의 회의 팀 목록 조회"""
    try:
        data = query_table("meeting_teams", eq={"vacation_id": vacation_id})
        return [MeetingTeam(**item) for item in data]
    except Exception as e:
        _handle_error(e, "회의 팀 조회")
        return []


def save_meeting_team(team: MeetingTeam) -> Optional[MeetingTeam]:
    """회의 팀 저장 (신규 또는 수정)"""
    try:
        data = team.model_dump(exclude={"id", "created_at"}, exclude_none=True)
        if team.id:
            result = update_record("meeting_teams", data, {"id": team.id})
        else:
            result = insert_record("meeting_teams", data)
        return MeetingTeam(**result) if result else None
    except Exception as e:
        _handle_error(e, "회의 팀 저장")
        return None


def delete_meeting_team(team_id: str) -> bool:
    """회의 팀 삭제"""
    try:
        delete_record("daily_meeting_assignments", {"team_id": team_id})
        return delete_record("meeting_teams", {"id": team_id})
    except Exception as e:
        _handle_error(e, "회의 팀 삭제")
        return False


# ============================================================
# 일별 회의 팀 배정 (Daily Meeting Assignments)
# ============================================================
@st.cache_data(ttl=30)
def get_daily_meeting_assignments(vacation_id: str) -> List[DailyMeetingAssignment]:
    """특정 방학의 일별 회의 팀 배정 조회"""
    try:
        data = query_table("daily_meeting_assignments", eq={"vacation_id": vacation_id})
        data.sort(key=lambda x: x.get("date", ""))
        return [DailyMeetingAssignment(**item) for item in data]
    except Exception as e:
        _handle_error(e, "일별 회의 배정 조회")
        return []


def save_daily_meeting_assignment(vacation_id: str, date_val: date, team_id: str) -> bool:
    """일별 회의 팀 배정 저장 (날짜+팀 조합으로 UPSERT)"""
    try:
        date_str = date_val.isoformat() if hasattr(date_val, 'isoformat') else date_val
        data = {
            "vacation_id": vacation_id,
            "date": date_str,
            "team_id": team_id
        }
        result = upsert_record("daily_meeting_assignments", data, {
            "vacation_id": vacation_id,
            "date": date_str,
            "team_id": team_id
        })
        return result is not None
    except Exception as e:
        _handle_error(e, "일별 회의 배정 저장")
        return False


def delete_daily_meeting_assignment(vacation_id: str, date_val: date, team_id: str) -> bool:
    """일별 회의 팀 배정 삭제 (날짜+팀 조합)"""
    try:
        date_str = date_val.isoformat() if hasattr(date_val, 'isoformat') else date_val
        return delete_record("daily_meeting_assignments", {
            "vacation_id": vacation_id,
            "date": date_str,
            "team_id": team_id
        })
    except Exception as e:
        _handle_error(e, "일별 회의 배정 삭제")
        return False


# ============================================================
# 교사 행정 신청 (Admin Requests) - admin_requests 테이블 사용
# ============================================================
@st.cache_data(ttl=30)
def get_admin_requests(teacher_id: str, vacation_id: str) -> List[AdminRequest]:
    """특정 교사의 행정 신청 목록 조회"""
    try:
        data = query_table("admin_requests", eq={
            "teacher_id": teacher_id,
            "vacation_id": vacation_id
        })
        data.sort(key=lambda x: x.get("date", ""))
        return [AdminRequest(**item) for item in data]
    except Exception as e:
        _handle_error(e, "행정 신청 조회")
        return []


def save_admin_request(request: AdminRequest) -> bool:
    """행정 신청 저장 (UPSERT)"""
    try:
        data = request.model_dump(exclude={"id", "created_at", "updated_at"}, exclude_none=True, mode="json")
        date_str = data["date"]
        result = upsert_record("admin_requests", data, {
            "teacher_id": request.teacher_id,
            "vacation_id": request.vacation_id,
            "date": date_str,
            "slot_type": request.slot_type
        })
        return result is not None
    except Exception as e:
        _handle_error(e, "행정 신청 저장")
        return False


def delete_admin_request(request_id: str) -> bool:
    """행정 신청 삭제"""
    try:
        return delete_record("admin_requests", {"id": request_id})
    except Exception as e:
        _handle_error(e, "행정 신청 삭제")
        return False


def calculate_and_save_stats(vacation_id: str) -> bool:
    """
    스케줄을 기반으로 통계를 계산하고 저장합니다.
    최적화 완료 후 호출됩니다.
    """
    try:
        # 모든 스케줄 조회
        schedules = get_schedules(vacation_id)

        # 교사별 통계 집계
        stats_map = {}
        for s in schedules:
            tid = s.teacher_id
            if tid not in stats_map:
                stats_map[tid] = {
                    "vacation_id": vacation_id,
                    "teacher_id": tid,
                    "total_care_count": 0,
                    "total_admin_count": 0,
                    "total_work_count": 0,
                    "vacation_am_points": 0,
                    "vacation_pm_points": 0,
                    "vacation_full_points": 0,
                    "total_vacation_points": 0,
                    "flash_teacher_count": 0,
                    "carry_over_to_next": 0,
                }

            stats = stats_map[tid]
            if "Childcare" in s.slot_type:
                stats["total_care_count"] += 1
            elif "Admin" in s.slot_type:
                stats["total_admin_count"] += 1
            stats["total_work_count"] += 1

            if s.is_flash_teacher:
                stats["flash_teacher_count"] += 1

        # 기존 통계 삭제 후 저장
        delete_record("vacation_stats", {"vacation_id": vacation_id})

        for stats in stats_map.values():
            insert_record("vacation_stats", stats)

        return True
    except Exception as e:
        _handle_error(e, "통계 계산")
        return False