"""
한국 공휴일 데이터
- 음력/양력 공휴일 포함
- 연도별 공휴일 목록 제공
- 대체공휴일 자동 계산
"""

from datetime import date, timedelta
from typing import List, Set
import holidays


# ============================================================
# 한국 공휴일 계산
# ============================================================
def get_korean_holidays(year: int) -> List[date]:
    """
    특정 연도의 한국 공휴일 목록을 반환합니다.
    
    Args:
        year: 연도 (예: 2026)
    
    Returns:
        List[date]: 공휴일 날짜 목록
    
    사용 예시:
        holidays = get_korean_holidays(2026)
        # [2026-01-01, 2026-02-16, 2026-02-17, ...]
    """
    try:
        # holidays 라이브러리 사용 (한국 공휴일)
        kr_holidays = holidays.KR(years=year)
        return sorted([d for d in kr_holidays.keys()])
    except Exception:
        # holidays 라이브러리가 없거나 오류 시 기본 공휴일 반환
        return _get_default_holidays(year)


def _get_default_holidays(year: int) -> List[date]:
    """
    holidays 라이브러리 없이 기본 공휴일을 반환합니다.
    (참고: 실제 사용 시 holidays 라이브러리 설치 권장)
    
    주요 공휴일 (양력 기준):
    - 1월 1일: 신정
    - 3월 1일: 삼일절
    - 5월 5일: 어린이날
    - 6월 6일: 현충일
    - 8월 15일: 광복절
    - 10월 3일: 개천절
    - 10월 9일: 한글날
    - 12월 25일: 크리스마스
    
    음력 공휴일은 연도별로 다르므로 별도 계산 필요
    """
    fixed_holidays = [
        date(year, 1, 1),    # 신정
        date(year, 3, 1),    # 삼일절
        date(year, 5, 5),    # 어린이날
        date(year, 6, 6),    # 현충일
        date(year, 8, 15),   # 광복절
        date(year, 10, 3),   # 개천절
        date(year, 10, 9),   # 한글날
        date(year, 12, 25),  # 크리스마스
    ]
    
    # 대체공휴일 처리 (토/일요일인 경우 다음 월요일)
    result = []
    for h in fixed_holidays:
        result.append(h)
        if h.weekday() == 5:  # 토요일
            result.append(h + timedelta(days=2))  # 다음 월요일
        elif h.weekday() == 6:  # 일요일
            result.append(h + timedelta(days=1))  # 다음 월요일
    
    return sorted(set(result))


def is_weekend(d: date) -> bool:
    """주말(토/일) 여부 확인"""
    return d.weekday() >= 5  # 5=토, 6=일


def get_working_days(start_date: date, end_date: date, 
                     excluded_dates: Set[date] = None) -> List[date]:
    """
    방학 기간 중 실제 근무 가능한 날짜 목록을 반환합니다.
    주말과 제외일을 제외합니다.
    
    Args:
        start_date: 방학 시작일
        end_date: 방학 종료일
        excluded_dates: 추가 제외일 목록 (공휴일 등)
    
    Returns:
        List[date]: 근무 가능한 날짜 목록
    """
    if excluded_dates is None:
        excluded_dates = set()
    
    working_days = []
    current = start_date
    while current <= end_date:
        if not is_weekend(current) and current not in excluded_dates:
            working_days.append(current)
        current += timedelta(days=1)
    
    return working_days


def get_week_range(d: date) -> tuple[date, date]:
    """
    특정 날짜가 속한 주의 월요일과 금요일을 반환합니다.
    
    Args:
        d: 기준 날짜
    
    Returns:
        tuple[date, date]: (월요일, 금요일)
    """
    monday = d - timedelta(days=d.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def is_meeting_week(d: date, meeting_weeks: List[tuple[date, date]]) -> bool:
    """
    특정 날짜가 회의 주간에 포함되는지 확인합니다.
    
    Args:
        d: 확인할 날짜
        meeting_weeks: 회의 주간 목록 [(시작일, 종료일), ...]
    
    Returns:
        bool: 회의 주간 여부
    """
    for start, end in meeting_weeks:
        if start <= d <= end:
            return True
    return False