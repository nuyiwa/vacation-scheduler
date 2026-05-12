"""
홈화면 캘린더 UI 컴포넌트
- Streamlit으로 구현한 시각적 캘린더
- 색상 구분: 돌봄(파랑), 행정(초록), 휴가(회색), 반짝선생님(노랑)
- 필터 기능: 전체/본인/슬롯 타입별
- 모바일 반응형 지원
"""

from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Set
import streamlit as st
import pandas as pd

from src.config.settings import (
    SlotType, SLOT_TYPE_NAMES, SLOT_TYPE_COLORS,
    VACATION_COLOR, FLASH_TEACHER_COLOR, MAX_SLOTS_PER_DAY
)
from src.db.models import Schedule, Vacation, VacationRequest, AdminRequest
from src.db.queries import (
    get_schedules, get_vacation_requests, get_admin_requests,
    get_vacation_teachers, get_all_teachers
)


# ============================================================
# 캘린더 데이터 구조
# ============================================================
class CalendarDay:
    """캘린더의 하루 데이터"""
    def __init__(self, date: date):
        self.date = date
        self.is_weekend = date.weekday() >= 5
        self.is_excluded = False
        self.is_meeting_week = False
        self.schedules: List[Schedule] = []  # 배정된 스케줄
        self.vacation_requests: List[VacationRequest] = []  # 휴가 신청
        self.admin_requests: List[AdminRequest] = []  # 행정 신청
        self.flash_teachers: List[dict] = []  # 반짝선생님 정보
    
    @property
    def has_schedule(self) -> bool:
        """스케줄이 있는지 확인"""
        return len(self.schedules) > 0
    
    @property
    def slot_count(self) -> int:
        """배정된 슬롯 수"""
        return len(self.schedules)
    
    @property
    def is_full(self) -> bool:
        """하루 최대 슬롯에 도달했는지 확인"""
        return self.slot_count >= MAX_SLOTS_PER_DAY


# ============================================================
# 캘린더 렌더링 함수
# ============================================================
def render_calendar(
    year: int,
    month: int,
    schedules: List[Schedule],
    vacation_requests: List[VacationRequest],
    admin_requests: List[AdminRequest],
    flash_teachers: List[dict],
    excluded_dates: Set[date],
    meeting_weeks: List[tuple[date, date]],
    current_teacher_id: Optional[str] = None,
    show_all: bool = True,
    filter_slot_type: Optional[str] = None,
    teacher_name_map: Optional[Dict[str, str]] = None,
):
    """
    월별 캘린더를 렌더링합니다.
    
    Args:
        year: 연도
        month: 월 (1~12)
        schedules: 해당 방학의 모든 스케줄
        vacation_requests: 해당 방학의 모든 휴가 신청
        admin_requests: 해당 방학의 모든 행정 신청
        flash_teachers: 반짝선생님 정보
        excluded_dates: 제외일 목록
        meeting_weeks: 회의 주간 목록
        current_teacher_id: 현재 로그인한 교사 ID
        show_all: 전체 스케줄 표시 여부
        filter_slot_type: 슬롯 타입 필터 (None=전체)
        teacher_name_map: 교사 ID -> 이름 매핑 (None이면 이름 미표시)
    """
    
    # ============================================================
    # 캘린더 데이터 준비
    # ============================================================
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    # 스케줄을 날짜별로 그룹화
    schedules_by_date: Dict[date, List[Schedule]] = {}
    for s in schedules:
        if s.date not in schedules_by_date:
            schedules_by_date[s.date] = []
        schedules_by_date[s.date].append(s)
    
    # 휴가 신청을 날짜별로 그룹화
    vacation_by_date: Dict[date, List[VacationRequest]] = {}
    for v in vacation_requests:
        if v.date not in vacation_by_date:
            vacation_by_date[v.date] = []
        vacation_by_date[v.date].append(v)
    
    # 행정 신청을 날짜별로 그룹화
    admin_by_date: Dict[date, List[AdminRequest]] = {}
    for a in admin_requests:
        a_date = a.date if hasattr(a, 'date') else a.get("date")
        if a_date not in admin_by_date:
            admin_by_date[a_date] = []
        admin_by_date[a_date].append(a)
    
    # 반짝선생님을 날짜별로 그룹화
    flash_by_date: Dict[date, List[dict]] = {}
    for f in flash_teachers:
        f_date = f.get("date") if isinstance(f, dict) else f.date
        if f_date not in flash_by_date:
            flash_by_date[f_date] = []
        flash_by_date[f_date].append(f)
    
    # ============================================================
    # CSS 스타일 (모바일 반응형)
    # ============================================================
    st.markdown("""
    <style>
    /* 캘린더 컨테이너 */
    .calendar-container {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 4px;
        margin: 10px 0;
    }
    
    /* 요일 헤더 */
    .calendar-header {
        text-align: center;
        font-weight: bold;
        padding: 8px 4px;
        font-size: 14px;
        color: #555;
    }
    .calendar-header.sunday { color: #E74C3C; }
    .calendar-header.saturday { color: #3498DB; }
    
    /* 날짜 셀 */
    .calendar-cell {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 6px;
        min-height: 80px;
        background: white;
        cursor: pointer;
        transition: all 0.2s;
        position: relative;
    }
    .calendar-cell:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        transform: translateY(-1px);
    }
    .calendar-cell.weekend {
        background: #F8F9FA;
    }
    .calendar-cell.excluded {
        background: #FDEDEC;
        opacity: 0.6;
    }
    .calendar-cell.other-month {
        opacity: 0.3;
    }
    
    /* 날짜 번호 */
    .calendar-day-number {
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 4px;
        color: #333;
    }
    .calendar-day-number.sunday { color: #E74C3C; }
    .calendar-day-number.saturday { color: #3498DB; }
    
    /* 슬롯 배지 */
    .slot-badge {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 500;
        margin: 1px 0;
        color: white;
        width: 100%;
        text-align: center;
        box-sizing: border-box;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .slot-badge.vacation {
        background: #95A5A6;
    }
    .slot-badge.flash {
        background: #F1C40F;
        color: #333;
    }
    
    /* 반응형 */
    @media (max-width: 768px) {
        .calendar-cell {
            min-height: 60px;
            padding: 4px;
        }
        .calendar-day-number {
            font-size: 11px;
        }
        .slot-badge {
            font-size: 8px;
            padding: 1px 3px;
        }
        .calendar-header {
            font-size: 11px;
            padding: 4px 2px;
        }
    }
    @media (max-width: 480px) {
        .calendar-cell {
            min-height: 50px;
            padding: 2px;
        }
        .slot-badge {
            font-size: 7px;
            padding: 1px 2px;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # ============================================================
    # 요일 헤더
    # ============================================================
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_classes = ["", "", "", "", "", "saturday", "sunday"]
    
    header_html = '<div class="calendar-container">'
    for i, day_name in enumerate(weekdays):
        header_html += f'<div class="calendar-header {weekday_classes[i]}">{day_name}</div>'
    
    # ============================================================
    # 빈 칸 채우기 (1일의 요일 위치)
    # ============================================================
    start_weekday = first_day.weekday()  # 월=0, 일=6
    # 월요일 시작으로 변환 (월=0, 일=6)
    empty_cells = start_weekday
    
    for _ in range(empty_cells):
        header_html += '<div class="calendar-cell other-month"></div>'
    
    # ============================================================
    # 각 날짜 렌더링
    # ============================================================
    current = first_day
    while current <= last_day:
        day_num = current.day
        is_weekend = current.weekday() >= 5
        is_excluded = current in excluded_dates
        is_today = current == date.today()
        
        # CSS 클래스
        cell_classes = ["calendar-cell"]
        if is_weekend:
            cell_classes.append("weekend")
        if is_excluded:
            cell_classes.append("excluded")
        if is_today:
            cell_classes.append("today")
        
        # 날짜 번호 CSS 클래스
        day_classes = ["calendar-day-number"]
        if current.weekday() == 6:  # 일요일
            day_classes.append("sunday")
        elif current.weekday() == 5:  # 토요일
            day_classes.append("saturday")
        
        # 셀 시작
        cell_html = f'<div class="{" ".join(cell_classes)}">'
        cell_html += f'<div class="{" ".join(day_classes)}">{day_num}</div>'
        
        # 제외일 표시
        if is_excluded:
            cell_html += '<div class="slot-badge" style="background:#E74C3C;">휴일</div>'
        else:
            # 해당 날짜의 스케줄 표시
            day_schedules = schedules_by_date.get(current, [])
            day_vacations = vacation_by_date.get(current, [])
            day_admin = admin_by_date.get(current, [])
            day_flash = flash_by_date.get(current, [])
            
            # 필터 적용
            if current_teacher_id and not show_all:
                day_schedules = [s for s in day_schedules if s.teacher_id == current_teacher_id]
                day_vacations = [v for v in day_vacations if v.teacher_id == current_teacher_id]
                day_admin = [a for a in day_admin if a.teacher_id == current_teacher_id]
            
            if filter_slot_type:
                day_schedules = [s for s in day_schedules if s.slot_type == filter_slot_type]
            
            # 스케줄 배지 표시
            for s in day_schedules:
                slot_name = SLOT_TYPE_NAMES.get(SlotType(s.slot_type), s.slot_type)
                color = SLOT_TYPE_COLORS.get(SlotType(s.slot_type), "#999")
                
                # 교사 이름 조회
                t_name = ""
                if teacher_name_map:
                    t_name = teacher_name_map.get(s.teacher_id, "")
                
                if s.is_flash_teacher:
                    cell_html += f'<div class="slot-badge flash">⭐ {slot_name}</div>'
                else:
                    display_text = f"{slot_name}({t_name})" if t_name else slot_name
                    cell_html += f'<div class="slot-badge" style="background:{color};">{display_text}</div>'
            
            # 반짝선생님 표시 (스케줄에 포함되지 않은 경우)
            for f in day_flash:
                f_teacher_name = f.get("profiles", {}).get("name", "선생님") if isinstance(f, dict) else "선생님"
                f_slot = f.get("slot_type", "AM") if isinstance(f, dict) else f.slot_type
                cell_html += f'<div class="slot-badge flash">⭐ {f_teacher_name}</div>'
            
            # 휴가 표시
            for v in day_vacations:
                v_type = v.request_type if hasattr(v, 'request_type') else v.get("request_type", "")
                v_label = {"full_day": "종일휴가", "am": "오전휴가", "pm": "오후휴가"}.get(v_type, "휴가")
                cell_html += f'<div class="slot-badge vacation">{v_label}</div>'
            
            # 행정 신청 표시 (스케줄에 포함되지 않은 경우)
            for a in day_admin:
                a_slot = a.slot_type if hasattr(a, 'slot_type') else a.get("slot_type", "AM")
                a_label = "오전행정(지정)" if a_slot == "AM" else "오후행정(지정)"
                a_color = SLOT_TYPE_COLORS.get(SlotType.AM_ADMIN if a_slot == "AM" else SlotType.PM_ADMIN, "#27AE60")
                cell_html += f'<div class="slot-badge" style="background:{a_color};">{a_label}</div>'
        
        cell_html += '</div>'
        header_html += cell_html
        
        current += timedelta(days=1)
    
    header_html += '</div>'
    
    # 캘린더 렌더링
    st.markdown(header_html, unsafe_allow_html=True)


# ============================================================
# 캘린더 페이지 (홈화면 / 교사 내스케줄)
# ============================================================
def render_calendar_page(
    vacation: Vacation,
    current_user_id: str,
    show_teacher_filter: bool = False,
    default_show_all: bool = True,
    mobile: bool = False,
):
    """
    캘린더 페이지를 렌더링합니다.
    
    Args:
        vacation: 현재 선택된 방학 정보
        current_user_id: 현재 로그인한 사용자 ID
        show_teacher_filter: 교사 선택 드롭다운 표시 여부 (홈화면용)
        default_show_all: 기본값으로 전체 스케줄 표시 여부
    """
    # ============================================================
    # 데이터 로드 (한 번에)
    # ============================================================
    schedules = get_schedules(vacation.id)
    
    # 모든 교사의 휴가 신청 및 행정 신청 로드 (한 번에)
    all_teachers = get_vacation_teachers(vacation.id)
    all_teacher_ids = [
        t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
        for t in all_teachers
    ]
    
    # 모든 vacation_requests를 한 번에 조회 (교사별 개별 쿼리 대신)
    from src.config.supabase_client import query_table
    all_vacation_requests_data = query_table("vacation_requests", eq={"vacation_id": vacation.id})
    vacation_requests = []
    for item in all_vacation_requests_data:
        try:
            from src.db.models import VacationRequest
            vacation_requests.append(VacationRequest(**item))
        except Exception:
            pass
    
    # 모든 admin_requests를 한 번에 조회
    all_admin_requests_data = query_table("admin_requests", eq={"vacation_id": vacation.id})
    admin_requests = []
    for item in all_admin_requests_data:
        try:
            from src.db.models import AdminRequest
            admin_requests.append(AdminRequest(**item))
        except Exception:
            pass
    
    # TODO: flash_teachers, excluded_dates, meeting_weeks 로드
    flash_teachers = []
    excluded_dates = set()
    meeting_weeks = []
    
    # ============================================================
    # 보기 모드 상태 (세션별로 유지)
    # ============================================================
    view_key = f"calendar_view_mode_{vacation.id}"
    if view_key not in st.session_state:
        st.session_state[view_key] = "calendar"  # "calendar" or "table"
    
    # ============================================================
    # 필터 옵션 (모바일: 2열 2행 / PC: 4열 1행)
    # ============================================================
    # 월 선택용 공통 데이터 먼저 계산
    today = date.today()
    months_in_range = []
    d = vacation.start_date
    while d <= vacation.end_date:
        if (d.year, d.month) not in months_in_range:
            months_in_range.append((d.year, d.month))
        d += timedelta(days=1)
    month_labels = [f"{y}년 {m}월" for y, m in months_in_range]
    default_idx = next(
        (i for i, (y, m) in enumerate(months_in_range)
         if y == today.year and m == today.month), 0
    )

    slot_filter_options = {
        "전체": None, "오전돌봄": "AM_Childcare", "오후돌봄": "PM_Childcare",
        "오전행정": "AM_Admin", "오후행정": "PM_Admin", "휴가": "vacation",
    }

    if mobile:
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        col1, col2, col3, col4 = r1c1, r1c2, r2c1, r2c2
    else:
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

    with col1:
        if show_teacher_filter:
            teachers = get_vacation_teachers(vacation.id)
            teacher_options = {"all": "📋 전체 스케줄"}
            for t in teachers:
                tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
                tname = t.get("teacher_name", "") if isinstance(t, dict) else getattr(t, "teacher_name", "")
                teacher_options[tid] = f"👤 {tname}"
            selected_teacher = st.selectbox(
                "교사 선택", options=list(teacher_options.keys()),
                format_func=lambda x: teacher_options[x],
                key=f"teacher_filter_{vacation.id}", label_visibility="collapsed"
            )
            show_all = selected_teacher == "all"
            filter_teacher_id = None if show_all else selected_teacher
        else:
            view_options = {"mine": "👤 내 스케줄만", "all": "📋 전체 스케줄"}
            default_view = "all" if default_show_all else "mine"
            selected_view = st.selectbox(
                "보기 모드", options=list(view_options.keys()),
                format_func=lambda x: view_options[x],
                index=0 if default_view == "all" else 1,
                key=f"view_mode_{vacation.id}", label_visibility="collapsed"
            )
            show_all = selected_view == "all"
            filter_teacher_id = None

    with col2:
        selected_filter = st.selectbox(
            "슬롯 필터", list(slot_filter_options.keys()),
            key=f"slot_filter_{vacation.id}", label_visibility="collapsed"
        )
        filter_slot_type = slot_filter_options[selected_filter]

    with col3:
        display_mode = st.segmented_control(
            "보기 방식", options=["calendar", "table"],
            format_func=lambda x: "📅 달력" if x == "calendar" else "📋 표",
            default=st.session_state[view_key],
            key=f"display_mode_{vacation.id}", label_visibility="collapsed",
        )
        if display_mode:
            st.session_state[view_key] = display_mode

    with col4:
        selected_month = st.selectbox(
            "월 선택", month_labels, index=default_idx,
            key=f"month_select_{vacation.id}", label_visibility="collapsed"
        )
        sel_year, sel_month = months_in_range[month_labels.index(selected_month)]
    
    # ============================================================
    # 통계 요약
    # ============================================================
    total_slots = len(schedules)
    
    # 필터링된 교사 ID에 따라 통계 계산
    if show_teacher_filter and not show_all and filter_teacher_id:
        my_schedules = [s for s in schedules if s.teacher_id == filter_teacher_id]
    else:
        my_schedules = [s for s in schedules if s.teacher_id == current_user_id]
    
    my_slot_count = len(my_schedules)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 전체 배정", total_slots)
    with col2:
        st.metric("👤 내 배정", my_slot_count)
    with col3:
        care_count = len([s for s in my_schedules if "Childcare" in s.slot_type])
        st.metric("👶 내 돌봄", care_count)
    with col4:
        admin_count = len([s for s in my_schedules if "Admin" in s.slot_type])
        st.metric("📋 내 행정", admin_count)
    
    # ============================================================
    # 범례
    # ============================================================
    st.markdown("""
    <div style="display:flex; gap:15px; flex-wrap:wrap; margin:10px 0; font-size:13px;">
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="display:inline-block; width:12px; height:12px; background:#4A90D9; border-radius:3px;"></span> 오전돌봄
        </span>
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="display:inline-block; width:12px; height:12px; background:#5BA3E6; border-radius:3px;"></span> 오후돌봄
        </span>
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="display:inline-block; width:12px; height:12px; background:#27AE60; border-radius:3px;"></span> 오전행정
        </span>
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="display:inline-block; width:12px; height:12px; background:#2ECC71; border-radius:3px;"></span> 오후행정
        </span>
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="display:inline-block; width:12px; height:12px; background:#95A5A6; border-radius:3px;"></span> 휴가
        </span>
        <span style="display:flex; align-items:center; gap:4px;">
            <span style="display:inline-block; width:12px; height:12px; background:#F1C40F; border-radius:3px;"></span> 반짝선생님
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    # ============================================================
    # 교사 이름 매핑 생성
    # ============================================================
    teacher_name_map: Dict[str, str] = {}
    for t in all_teachers:
        tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
        tname = t.get("teacher_name", "") if isinstance(t, dict) else getattr(t, "teacher_name", "")
        if tid:
            teacher_name_map[tid] = tname
    
    # ============================================================
    # 보기 모드: 달력 or 표
    # ============================================================
    if st.session_state[view_key] == "calendar":
        # ---- 달력 보기 ----
        render_calendar(
            year=sel_year,
            month=sel_month,
            schedules=schedules,
            vacation_requests=vacation_requests,
            admin_requests=admin_requests,
            flash_teachers=flash_teachers,
            excluded_dates=excluded_dates,
            meeting_weeks=meeting_weeks,
            current_teacher_id=filter_teacher_id if not show_all else None,
            show_all=show_all,
            filter_slot_type=filter_slot_type,
            teacher_name_map=teacher_name_map,
        )
    else:
        # ---- 표 보기 ----
        _render_schedule_table(
            schedules=schedules,
            vacation=vacation,
            sel_year=sel_year,
            sel_month=sel_month,
            show_all=show_all,
            filter_teacher_id=filter_teacher_id,
            filter_slot_type=filter_slot_type,
            current_user_id=current_user_id,
            teacher_name_map=teacher_name_map,
        )
    


# ============================================================
# 표 보기 모드
# ============================================================
def _render_schedule_table(
    schedules: List[Schedule],
    vacation: Vacation,
    sel_year: int,
    sel_month: int,
    show_all: bool,
    filter_teacher_id: Optional[str],
    filter_slot_type: Optional[str],
    current_user_id: str,
    teacher_name_map: Optional[Dict[str, str]] = None,
):
    """표 형태로 스케줄을 렌더링합니다."""
    
    # 해당 월의 스케줄 필터링
    month_schedules = [
        s for s in schedules
        if s.date.year == sel_year and s.date.month == sel_month
    ]
    
    if not show_all:
        if filter_teacher_id:
            month_schedules = [s for s in month_schedules if s.teacher_id == filter_teacher_id]
        else:
            month_schedules = [s for s in month_schedules if s.teacher_id == current_user_id]
    
    if filter_slot_type:
        month_schedules = [s for s in month_schedules if s.slot_type == filter_slot_type]
    
    if not month_schedules:
        st.info("📭 이번 달에 표시할 스케줄이 없습니다.")
        return
    
    # 날짜순 정렬
    month_schedules.sort(key=lambda s: (s.date, s.slot_type))
    
    # 데이터프레임 생성
    df_data = []
    for s in month_schedules:
        slot_name = SLOT_TYPE_NAMES.get(SlotType(s.slot_type), s.slot_type)
        # 교사 이름 조회
        t_name = ""
        if teacher_name_map:
            t_name = teacher_name_map.get(s.teacher_id, "")
        df_data.append({
            "날짜": s.date.strftime("%m/%d(%a)"),
            "슬롯": slot_name,
            "교사": t_name,
            "유형": "⭐ 반짝" if s.is_flash_teacher else "일반",
        })
    
    df = pd.DataFrame(df_data)
    
    # 날짜별로 그룹화하여 표시
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "날짜": st.column_config.TextColumn("날짜", width="small"),
            "슬롯": st.column_config.TextColumn("슬롯", width="medium"),
            "교사": st.column_config.TextColumn("교사", width="small"),
            "유형": st.column_config.TextColumn("유형", width="small"),
        }
    )
    
    # 요약 통계
    st.markdown("#### 📊 월간 요약")
    total_count = len(month_schedules)
    care_count = len([s for s in month_schedules if "Childcare" in s.slot_type])
    admin_count = len([s for s in month_schedules if "Admin" in s.slot_type])
    flash_count = len([s for s in month_schedules if s.is_flash_teacher])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 총 배정", total_count)
    with col2:
        st.metric("👶 돌봄", care_count)
    with col3:
        st.metric("📋 행정", admin_count)
    with col4:
        st.metric("⭐ 반짝", flash_count)