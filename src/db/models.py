"""
데이터 모델 정의
- Pydantic을 사용한 데이터 검증
- Supabase 테이블과 1:1 매핑
- 직렬화/역직렬화 지원
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


# ============================================================
# 프로필 (교사/관리자)
# ============================================================
class Profile(BaseModel):
    """교사/관리자 프로필 모델"""
    id: str
    email: str
    name: str
    role: str = "teacher"  # "admin" | "teacher"
    phone: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# 방학
# ============================================================
class Vacation(BaseModel):
    """방학 정보 모델"""
    id: Optional[str] = None
    title: str  # 예: "2026 겨울방학"
    year: int
    season: str  # "spring" | "summer" | "fall" | "winter"
    start_date: date
    end_date: date
    status: str = "planning"  # planning | input | optimized | confirmed | completed
    admin_id: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# 방학별 교사 배정
# ============================================================
class VacationTeacher(BaseModel):
    """방학에 참여하는 교사 정보 (포인트 기반)"""
    id: Optional[str] = None
    vacation_id: str
    teacher_id: str
    care_points: int = 0       # 목표 돌봄 포인트 (자동 계산)
    admin_points: int = 0      # 목표 행정 포인트 (관리자 설정)
    vacation_points: int = 0   # 사용 가능 휴가 포인트 (자동 계산 = 총가능 - 돌봄 - 행정)
    carry_over_points: int = 0  # 이전 방학에서 이월된 포인트
    is_ready: bool = False     # 교사 설정 완료 여부
    created_at: Optional[datetime] = None


# ============================================================
# 돌봄 필요 인원
# ============================================================
class CareRequirement(BaseModel):
    """날짜별·오전/오후별 돌봄 필요 인원"""
    id: Optional[str] = None
    vacation_id: str
    date: date
    slot_type: str  # "AM" | "PM"
    required_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# 반짝선생님
# ============================================================
class FlashTeacher(BaseModel):
    """반짝선생님: 특정 날짜·시간대 돌봄 인원 1명 감소 (부모님 - 이름 불필요)"""
    id: Optional[str] = None
    vacation_id: str
    teacher_id: Optional[str] = None  # 부모님이므로 교사 ID 불필요
    date: date
    slot_type: str  # "AM" | "PM"
    created_at: Optional[datetime] = None


# ============================================================
# 제외일
# ============================================================
class ExcludedDate(BaseModel):
    """휴일/제외일: 해당 날짜 전체 슬롯 제외"""
    id: Optional[str] = None
    vacation_id: str
    date: date
    reason: str
    is_holiday: bool = True
    created_at: Optional[datetime] = None


# ============================================================
# 회의 주간
# ============================================================
class MeetingWeek(BaseModel):
    """회의 주간: 오후 전체 회의 → 오후 돌봄 슬롯 없음"""
    id: Optional[str] = None
    vacation_id: str
    week_start: date  # 월요일
    week_end: date    # 금요일
    description: str = "전체 회의"
    created_at: Optional[datetime] = None


# ============================================================
# 교사 선호도
# ============================================================
class TeacherPreference(BaseModel):
    """교사별 선호도 설정"""
    id: Optional[str] = None
    teacher_id: str
    vacation_id: str
    prefer_care_am: int = 50   # 오전 돌봄 선호 (0~100), 오후 = 100 - 오전
    prefer_care_pm: int = 50   # 오후 돌봄 선호 (자동 계산)
    prefer_admin_am: int = 50  # 오전 행정 선호 (0~100), 오후 = 100 - 오전
    prefer_admin_pm: int = 50  # 오후 행정 선호 (자동 계산)
    prefer_consecutive_vacation: int = 50  # 연속 휴가 선호 (0~100)
    prefer_vacation_am_ratio: int = 34   # 오전휴가 비율 (세 값의 합 = 100)
    prefer_vacation_pm_ratio: int = 33   # 오후휴가 비율
    prefer_vacation_full_ratio: int = 33  # 종일휴가 비율
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# 휴가 신청
# ============================================================
class VacationRequest(BaseModel):
    """교사별 휴가 신청"""
    id: Optional[str] = None
    teacher_id: str
    vacation_id: str
    date: date
    request_type: str  # "full_day" | "am" | "pm"
    priority: int = 1  # 1~5 (1: 가장 원함)
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# 최종 스케줄
# ============================================================
class Schedule(BaseModel):
    """최종 배정된 스케줄 (최적화 결과)"""
    id: Optional[str] = None
    vacation_id: str
    teacher_id: str
    date: date
    slot_type: str  # AM_Childcare | PM_Childcare | AM_Admin | PM_Admin
    is_flash_teacher: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# 방학별 통계
# ============================================================
class VacationStat(BaseModel):
    """방학별 교사 통계 (누적 관리용)"""
    id: Optional[str] = None
    vacation_id: str
    teacher_id: str
    total_care_count: int = 0
    total_admin_count: int = 0
    total_work_count: int = 0
    vacation_am_points: int = 0
    vacation_pm_points: int = 0
    vacation_full_points: int = 0
    total_vacation_points: int = 0
    flash_teacher_count: int = 0
    carry_over_to_next: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# 회의 팀
# ============================================================
class MeetingTeam(BaseModel):
    """회의 주간 팀 설정 (오전 회의 팀별 구성)"""
    id: Optional[str] = None
    vacation_id: str
    team_name: str
    member_ids: List[str] = []  # 팀 구성원 teacher_id 목록
    created_at: Optional[datetime] = None


# ============================================================
# 일별 회의 팀 배정
# ============================================================
class DailyMeetingAssignment(BaseModel):
    """회의 주간 중 특정 날짜에 오전 회의하는 팀"""
    id: Optional[str] = None
    vacation_id: str
    date: date
    team_id: str
    created_at: Optional[datetime] = None


# ============================================================
# 교사 행정 신청 (지정 행정)
# ============================================================
class AdminRequest(BaseModel):
    """교사가 지정 신청하는 행정 업무 슬롯"""
    id: Optional[str] = None
    teacher_id: str
    vacation_id: str
    date: date
    slot_type: str  # "AM" | "PM"
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None