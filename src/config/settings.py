"""
앱 설정 모듈
- 환경변수 로드
- 앱 전체에서 사용하는 상수 정의
- 슬롯 타입, 색상, 시즌 등 공통 설정
"""

import os
from enum import Enum
from typing import Dict, Tuple
from dotenv import load_dotenv

# .env 파일 로드 (개발 환경)
load_dotenv()


# ============================================================
# 데모 모드 설정
# ============================================================
# Supabase 설정이 없으면 자동으로 데모 모드로 실행됩니다.
# 데모 모드에서는 로컬 메모리(Streamlit session_state)에 데이터를 저장합니다.
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"


# ============================================================
# Supabase 설정
# ============================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


# ============================================================
# 슬롯 타입 정의 (하루 4개 슬롯)
# ============================================================
class SlotType(str, Enum):
    """하루 4개 슬롯 타입"""
    AM_CHILDCARE = "AM_Childcare"      # 오전돌봄
    PM_CHILDCARE = "PM_Childcare"      # 오후돌봄
    AM_ADMIN = "AM_Admin"              # 오전행정
    PM_ADMIN = "PM_Admin"              # 오후행정


# 슬롯 타입별 표시 이름 (한국어)
SLOT_TYPE_NAMES: Dict[SlotType, str] = {
    SlotType.AM_CHILDCARE: "오전돌봄",
    SlotType.PM_CHILDCARE: "오후돌봄",
    SlotType.AM_ADMIN: "오전행정",
    SlotType.PM_ADMIN: "오후행정",
}

# 슬롯 타입별 색상 (캘린더 표시용)
SLOT_TYPE_COLORS: Dict[SlotType, str] = {
    SlotType.AM_CHILDCARE: "#4A90D9",   # 돌봄 - 파랑
    SlotType.PM_CHILDCARE: "#5BA3E6",   # 돌봄 - 연파랑
    SlotType.AM_ADMIN: "#27AE60",       # 행정 - 초록
    SlotType.PM_ADMIN: "#2ECC71",       # 행정 - 연초록
}

# 휴가 색상
VACATION_COLOR = "#95A5A6"             # 휴가 - 회색
FLASH_TEACHER_COLOR = "#F1C40F"        # 반짝선생님 - 노랑


# ============================================================
# 방학 시즌
# ============================================================
class Season(str, Enum):
    """방학 시즌"""
    SPRING = "spring"     # 봄방학
    SUMMER = "summer"     # 여름방학
    FALL = "fall"         # 가을방학
    WINTER = "winter"     # 겨울방학


# 시즌별 표시 이름 (한국어)
SEASON_NAMES: Dict[Season, str] = {
    Season.SPRING: "봄방학",
    Season.SUMMER: "여름방학",
    Season.FALL: "가을방학",
    Season.WINTER: "겨울방학",
}


# ============================================================
# 방학 상태
# ============================================================
class VacationStatus(str, Enum):
    """방학 진행 상태"""
    PLANNING = "planning"       # 생성됨 (관리자 설정 중)
    INPUT = "input"             # 교사 입력 중
    OPTIMIZED = "optimized"     # 최적화 완료
    CONFIRMED = "confirmed"     # 승인됨
    COMPLETED = "completed"     # 종료


# ============================================================
# 휴가 유형
# ============================================================
class VacationRequestType(str, Enum):
    """휴가 신청 유형"""
    FULL_DAY = "full_day"       # 종일휴가 (2포인트)
    AM = "am"                   # 오전휴가 (1포인트)
    PM = "pm"                   # 오후휴가 (1포인트)


# 휴가 유형별 포인트
VACATION_POINTS = {
    VacationRequestType.FULL_DAY: 2,
    VacationRequestType.AM: 1,
    VacationRequestType.PM: 1,
}


# ============================================================
# 역할
# ============================================================
class UserRole(str, Enum):
    """사용자 역할"""
    ADMIN = "admin"             # 관리자
    TEACHER = "teacher"         # 교사


# ============================================================
# 앱 설정 상수
# ============================================================
APP_NAME = "방학 스케줄링 시스템"
APP_ICON = "📅"
APP_DESCRIPTION = "유치원/초등 방학 중 교사 스케줄 관리 시스템"

# 하루 최대 슬롯 수
MAX_SLOTS_PER_DAY = 2

# 선호도 가중치 범위
PREFERENCE_MIN = 0
PREFERENCE_MAX = 100
PREFERENCE_DEFAULT = 50

# 휴가 우선순위 범위
VACATION_PRIORITY_MIN = 1
VACATION_PRIORITY_MAX = 5