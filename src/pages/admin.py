"""
관리자 전용 페이지
- 방학 생성 및 관리
- 돌봄 필요 인원 설정
- 반짝선생님 등록
- 제외일/회의 주간 설정
- 교사 배정 및 목표 횟수 계산
"""

from datetime import date, timedelta, datetime
from typing import List, Optional
import streamlit as st
import pandas as pd

from src.config.settings import (
    Season, SEASON_NAMES, VacationStatus, VACATION_POINTS,
    SLOT_TYPE_NAMES, SlotType
)
from src.db.models import (
    Vacation, VacationTeacher, CareRequirement, FlashTeacher,
    ExcludedDate, MeetingWeek
)
from src.db.queries import (
    get_vacations, get_vacation, create_vacation, update_vacation,
    get_vacation_teachers, add_teacher_to_vacation, remove_teacher_from_vacation,
    update_teacher_points, update_all_teacher_admin_points, get_all_teachers,
    get_vacation_teacher_points,
    get_care_requirements, set_care_requirement,
    get_flash_teachers, add_flash_teacher, remove_flash_teacher,
    get_excluded_dates, add_excluded_date, remove_excluded_date,
    get_meeting_weeks, add_meeting_week, remove_meeting_week,
    get_meeting_teams, save_meeting_team, delete_meeting_team,
    get_daily_meeting_assignments, save_daily_meeting_assignment, delete_daily_meeting_assignment,
    get_schedules, save_schedules, calculate_and_save_stats,
    clear_vacation_cache,
    get_teachers_ready_status, is_all_teachers_ready,
    delete_teacher_account, reset_all_vacation_assignments,
    reset_vacation_assignments, delete_vacation
)
from src.db.models import MeetingTeam
from src.utils.korean_holidays import (
    get_korean_holidays, get_working_days
)
from src.optimizer.scheduler import run_random_assignment, render_optimization_preview


# ============================================================
# 관리자 페이지 메인
# ============================================================
def _cols(mobile: bool, ratios_pc: list, n_mobile: int = 1):
    """모바일이면 1열, PC면 지정 비율 다열 반환"""
    if mobile:
        return [st.container() for _ in range(n_mobile if n_mobile > 1 else len(ratios_pc))]
    return st.columns(ratios_pc)


def render_admin_page(mobile: bool = False):
    """관리자 페이지 메인 렌더링"""

    if not mobile:
        st.markdown("# 🔧 관리자 설정")
    
    # ============================================================
    # 탭 구성
    # ============================================================
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📅 방학 관리",
        "👶 돌봄 필요 인원",
        "⭐ 반짝선생님",
        "📋 제외일/회의",
        "⚡ 1차 최적화",
        "🎲 2차 랜덤 배정",
        "🔐 계정 관리"
    ])

    with tab1:
        _render_vacation_management()

    with tab2:
        _render_care_requirements()

    with tab3:
        _render_flash_teachers()

    with tab4:
        _render_excluded_dates()

    with tab5:
        _render_stage1_optimization()

    with tab6:
        _render_stage2_random_assignment()

    with tab7:
        _render_account_management()


# ============================================================
# 방학 관리 탭
# ============================================================
def _render_vacation_management():
    """방학 생성 및 관리"""
    
    st.markdown("## 📅 방학 관리")
    
    # 기존 방학 목록
    vacations = get_vacations()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if vacations:
            vacation_options = {v.title: v for v in vacations}
            selected_title = st.selectbox(
                "방학 선택",
                list(vacation_options.keys()),
                key="admin_vacation_select"
            )
            selected_vacation = vacation_options[selected_title]
            st.session_state["selected_vacation_id"] = selected_vacation.id
            
            # 방학 정보 표시
            status_display = {
                "planning": "📝 생성됨",
                "input": "✏️ 교사 입력 중",
                "optimized": "⚡ 최적화 완료",
                "confirmed": "✅ 승인됨",
                "completed": "🏁 종료"
            }.get(selected_vacation.status, selected_vacation.status)
            st.markdown(f"""
            **선택된 방학:** {selected_vacation.title}
            - 기간: {selected_vacation.start_date} ~ {selected_vacation.end_date}
            - 상태: {status_display}
            """)
            
            # 상태 변경
            new_status = st.selectbox(
                "상태 변경",
                [s.value for s in VacationStatus],
                index=[s.value for s in VacationStatus].index(selected_vacation.status)
                if selected_vacation.status in [s.value for s in VacationStatus] else 0,
                format_func=lambda x: {
                    "planning": "📝 생성됨 (관리자 설정 중)",
                    "input": "✏️ 교사 입력 중",
                    "optimized": "⚡ 최적화 완료",
                    "confirmed": "✅ 승인됨",
                    "completed": "🏁 종료"
                }.get(x, x)
            )
            if new_status != selected_vacation.status:
                if st.button("상태 업데이트", key="update_status"):
                    if update_vacation(selected_vacation.id, {"status": new_status}):
                        status_names = {
                            "planning": "📝 생성됨",
                            "input": "✏️ 교사 입력 중",
                            "optimized": "⚡ 최적화 완료",
                            "confirmed": "✅ 승인됨",
                            "completed": "🏁 종료"
                        }
                        st.success(f"✅ 상태가 '{status_names[new_status]}'(으)로 변경되었습니다.")
                        st.rerun()
        else:
            st.info("📭 아직 생성된 방학이 없습니다.")
    
    with col2:
        # 새 방학 생성
        st.markdown("### ➕ 새 방학 생성")
        with st.form("create_vacation_form"):
            year = st.number_input("년도", min_value=2024, max_value=2030, value=2026)
            season = st.selectbox("방학 종류", [s.value for s in Season], format_func=lambda x: SEASON_NAMES.get(Season(x), x))
            title = f"{year} {SEASON_NAMES.get(Season(season), season)}"
            
            start_date = st.date_input("시작일", value=date(year, 7, 1))
            end_date = st.date_input("종료일", value=date(year, 8, 31))
            
            notes = st.text_area("비고 (선택사항)")
            
            if st.form_submit_button("방학 생성", use_container_width=True):
                new_vacation = Vacation(
                    title=title,
                    year=year,
                    season=season,
                    start_date=start_date,
                    end_date=end_date,
                    admin_id=st.session_state.get("user_id", ""),
                    notes=notes if notes else None
                )
                result = create_vacation(new_vacation)
                if result:
                    st.success(f"✅ '{title}' 방학이 생성되었습니다!")
                    st.rerun()
                else:
                    st.error("❌ 방학 생성에 실패했습니다.")


# ============================================================
# 교사 배정 탭 (포인트 기반)
# ============================================================
# 1차 최적화 탭 (교사 선택 + 총량 자동 계산)
# ============================================================
def _render_stage1_optimization():
    """1차 최적화: 참여 교사 선택 후 총량(설정돌봄/설정행정/설정휴가) 자동 계산"""

    vacation_id = st.session_state.get("selected_vacation_id")
    if not vacation_id:
        st.warning("⚠️ 먼저 방학을 선택해주세요.")
        return

    vacation = get_vacation(vacation_id)
    if not vacation:
        st.error("❌ 방학 정보를 찾을 수 없습니다.")
        return

    st.markdown(f"## ⚡ 1차 최적화 - {vacation.title}")
    st.markdown("""
    방학 기간·돌봄 필요 인원·반짝선생님·제외일/회의 설정이 완료된 후 실행합니다.
    버튼을 누르면 각 교사에게 **설정돌봄 / 설정행정 / 설정휴가 총량**이 자동 배포됩니다.
    """)

    col_left, col_right = st.columns([3, 2])

    # ── 왼쪽: 참여 교사 목록 ──
    with col_left:
        st.markdown("### 참여 교사")

        teachers = get_vacation_teachers(vacation_id)

        if teachers:
            teacher_data = []
            for t in teachers:
                tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
                tname = t.get("teacher_name", "Unknown") if isinstance(t, dict) else "Unknown"
                cp = t.get("care_points", 0) if isinstance(t, dict) else t.care_points
                ap = t.get("admin_points", 0) if isinstance(t, dict) else t.admin_points
                vp = t.get("vacation_points", 0) if isinstance(t, dict) else t.vacation_points
                teacher_data.append({
                    "교사명": tname,
                    "설정돌봄": cp,
                    "설정행정": ap,
                    "설정휴가": vp,
                    "합계": cp + ap + vp,
                    "teacher_id": tid
                })

            st.dataframe(
                pd.DataFrame(teacher_data).drop(columns=["teacher_id"]),
                use_container_width=True, hide_index=True
            )

            teachers_to_remove = st.multiselect(
                "제거할 교사 선택",
                options=[t["교사명"] for t in teacher_data],
                key="remove_teachers"
            )
            if teachers_to_remove and st.button("선택 교사 제거", key="remove_teacher_btn"):
                for tname in teachers_to_remove:
                    t = next((t for t in teacher_data if t["교사명"] == tname), None)
                    if t:
                        remove_teacher_from_vacation(vacation_id, t["teacher_id"])
                st.success("✅ 제거 완료")
                st.rerun()
        else:
            st.info("📭 아직 배정된 교사가 없습니다. 아래에서 교사를 추가해주세요.")

        # 교사 추가
        st.markdown("**교사 추가**")
        assigned_ids = {
            (t.get("teacher_id") if isinstance(t, dict) else t.teacher_id)
            for t in teachers
        }
        all_teachers = get_all_teachers()
        available = [t for t in all_teachers if t.get("id") not in assigned_ids]

        if available:
            teacher_options = {t.get("id"): t.get("name", t.get("email", "Unknown")) for t in available}
            sel_id = st.selectbox(
                "추가할 교사 선택",
                options=list(teacher_options.keys()),
                format_func=lambda x: teacher_options[x],
                key="add_teacher_select"
            )
            if st.button("교사 추가", key="add_teacher_btn", use_container_width=True):
                if add_teacher_to_vacation(vacation_id, sel_id):
                    st.success(f"✅ '{teacher_options[sel_id]}' 추가 완료")
                    st.rerun()
                else:
                    st.error("❌ 추가 실패")
        else:
            st.info("✅ 모든 교사가 배정되었습니다." if all_teachers else "📭 등록된 교사 계정이 없습니다.")

    # ── 오른쪽: 현재 설정 요약 + 최적화 실행 ──
    with col_right:
        st.markdown("### 설정 요약 및 실행")

        care_reqs = get_care_requirements(vacation_id)
        flash = get_flash_teachers(vacation_id)
        excluded = get_excluded_dates(vacation_id)
        meetings = get_meeting_weeks(vacation_id)

        st.markdown(f"""
        - 👨‍🏫 교사: **{len(teachers)}명**
        - 👶 돌봄 설정: {len(care_reqs)}개
        - ⭐ 반짝선생님: {len(flash)}개 슬롯
        - 🚫 제외일: {len(excluded)}일
        - 📅 회의 주간: {len(meetings)}주
        """)

        admin_point_value = st.number_input(
            "행정 포인트 (모든 교사 동일)",
            min_value=0, max_value=100, value=5,
            help="방학 동안 각 교사에게 동일하게 부여할 행정 횟수",
            key="admin_point_input"
        )

        if st.button("⚡ 1차 최적화 실행", type="primary", use_container_width=True):
            with st.spinner("🔄 총량 계산 중..."):
                _run_stage1_total_calculation(vacation, vacation_id, admin_point_value)


# ============================================================
# 돌봄 필요 인원 탭
# ============================================================
def _render_care_requirements():
    """날짜별·오전/오후별 돌봄 필요 인원 설정"""
    
    vacation_id = st.session_state.get("selected_vacation_id")
    if not vacation_id:
        st.warning("⚠️ 먼저 방학을 선택해주세요.")
        return
    
    vacation = get_vacation(vacation_id)
    if not vacation:
        st.error("❌ 방학 정보를 찾을 수 없습니다.")
        return
    
    st.markdown(f"## 👶 돌봄 필요 인원 - {vacation.title}")
    
    # 기존 설정 로드
    care_reqs = get_care_requirements(vacation_id)
    care_dict = {}
    for cr in care_reqs:
        care_dict[(cr.date.isoformat(), cr.slot_type)] = cr.required_count
    
    # 날짜 범위 선택
    date_range = pd.date_range(vacation.start_date, vacation.end_date, freq='D')
    
    # 주말/공휴일 제외 옵션
    exclude_weekends = st.checkbox("주말 제외", value=True)
    exclude_holidays = st.checkbox("공휴일 제외", value=True)
    
    # 공휴일 목록
    holidays = set()
    if exclude_holidays:
        for y in range(vacation.start_date.year, vacation.end_date.year + 1):
            for h in get_korean_holidays(y):
                if vacation.start_date <= h <= vacation.end_date:
                    holidays.add(h)
    
    # 일괄 설정
    st.markdown("### 일괄 설정")
    col1, col2, col3 = st.columns(3)
    with col1:
        default_am = st.number_input("기본 오전 인원", min_value=0, max_value=20, value=3)
    with col2:
        default_pm = st.number_input("기본 오후 인원", min_value=0, max_value=20, value=3)
    with col3:
        if st.button("일괄 적용", key="batch_apply"):
            success = True
            for d in date_range:
                d_date = d.date()
                if exclude_weekends and d_date.weekday() >= 5:
                    continue
                if d_date in holidays:
                    continue
                
                if not set_care_requirement(vacation_id, d_date, "AM", default_am):
                    success = False
                if not set_care_requirement(vacation_id, d_date, "PM", default_pm):
                    success = False
            
            if success:
                st.success(f"✅ 일괄 설정이 완료되었습니다.")
                st.rerun()
            else:
                st.error("❌ 일부 설정에 실패했습니다.")
    
    # 개별 설정 (날짜별)
    st.markdown("### 개별 설정")
    
    # 달력 형태로 표시
    for month_start in pd.date_range(vacation.start_date.replace(day=1), vacation.end_date, freq='MS'):
        month_end = month_start + pd.offsets.MonthEnd(1)
        month_dates = [d for d in date_range if month_start <= d <= month_end]
        
        with st.expander(f"{month_start.year}년 {month_start.month}월", expanded=False):
            data = []
            for d in month_dates:
                d_date = d.date()
                is_weekend = d_date.weekday() >= 5
                is_holiday = d_date in holidays
                
                if (exclude_weekends and is_weekend) or (exclude_holidays and is_holiday):
                    continue
                
                am_key = (d_date.isoformat(), "AM")
                pm_key = (d_date.isoformat(), "PM")
                
                data.append({
                    "날짜": d_date.strftime("%m/%d(%a)"),
                    "오전": care_dict.get(am_key, default_am),
                    "오후": care_dict.get(pm_key, default_pm),
                    "date": d_date,
                })
            
            if data:
                df = pd.DataFrame(data)
                edited = st.data_editor(
                    df,
                    column_config={
                        "날짜": st.column_config.TextColumn("날짜", disabled=True),
                        "오전": st.column_config.NumberColumn("오전 인원", min_value=0, max_value=20),
                        "오후": st.column_config.NumberColumn("오후 인원", min_value=0, max_value=20),
                        "date": None,
                    },
                    use_container_width=True,
                    hide_index=True,
                    key=f"care_editor_{month_start.month}"
                )
                
                if st.button(f"{month_start.month}월 저장", key=f"save_care_{month_start.month}"):
                    success = True
                    for _, row in edited.iterrows():
                        if not set_care_requirement(vacation_id, row["date"], "AM", row["오전"]):
                            success = False
                        if not set_care_requirement(vacation_id, row["date"], "PM", row["오후"]):
                            success = False
                    
                    if success:
                        st.success(f"✅ {month_start.month}월 설정이 저장되었습니다.")
                        st.rerun()
                    else:
                        st.error("❌ 일부 저장에 실패했습니다.")


# ============================================================
# 반짝선생님 탭
# ============================================================
def _render_flash_teachers():
    """반짝선생님 등록 및 관리"""
    
    vacation_id = st.session_state.get("selected_vacation_id")
    if not vacation_id:
        st.warning("⚠️ 먼저 방학을 선택해주세요.")
        return
    
    vacation = get_vacation(vacation_id)
    if not vacation:
        st.error("❌ 방학 정보를 찾을 수 없습니다.")
        return
    
    st.markdown(f"## ⭐ 반짝선생님 - {vacation.title}")
    st.markdown("""
    반짝선생님은 **부모님**이 특정 날짜·시간대(오전/오후)에 돌봄을 도와주는 것으로,
    해당 슬롯의 돌봄 필요 인원이 **정확히 1명 감소**합니다.
    """)

    # 등록된 반짝선생님 목록
    flash_teachers = get_flash_teachers(vacation_id)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### 등록된 반짝선생님")
        if flash_teachers:
            flash_data = []
            for f in flash_teachers:
                f_date = f.get("date") if isinstance(f, dict) else f.date
                f_slot = f.get("slot_type") if isinstance(f, dict) else f.slot_type
                f_id = f.get("id") if isinstance(f, dict) else f.id

                flash_data.append({
                    "날짜": f_date.strftime("%m/%d(%a)") if hasattr(f_date, 'strftime') else str(f_date),
                    "시간": "오전" if f_slot == "AM" else "오후",
                    "id": f_id
                })

            df = pd.DataFrame(flash_data)
            st.dataframe(df[["날짜", "시간"]], use_container_width=True, hide_index=True)

            # 삭제
            flash_to_remove = st.multiselect(
                "삭제할 항목 선택",
                options=[f"{r['날짜']} {r['시간']}" for r in flash_data],
                key="remove_flash"
            )
            if flash_to_remove and st.button("선택 삭제", key="remove_flash_btn"):
                for item in flash_to_remove:
                    idx = [f"{r['날짜']} {r['시간']}" for r in flash_data].index(item)
                    remove_flash_teacher(flash_data[idx]["id"])
                st.success("✅ 삭제 완료")
                st.rerun()
        else:
            st.info("📭 등록된 반짝선생님이 없습니다.")

    with col2:
        st.markdown("### ➕ 새로 등록")
        with st.form("add_flash_form"):
            flash_date = st.date_input("날짜", value=vacation.start_date,
                                       min_value=vacation.start_date, max_value=vacation.end_date)
            flash_slot = st.selectbox("시간대", ["AM", "PM"], format_func=lambda x: "오전" if x == "AM" else "오후")

            if st.form_submit_button("등록", use_container_width=True):
                admin_id = st.session_state.get("user_id", "")
                if add_flash_teacher(vacation_id, flash_date, flash_slot, admin_id):
                    st.success(f"✅ {flash_date} {('오전' if flash_slot == 'AM' else '오후')} 반짝선생님이 등록되었습니다.")
                    st.rerun()
                else:
                    st.error("❌ 등록에 실패했습니다.")


# ============================================================
# 제외일/회의 주간 탭
# ============================================================
def _render_excluded_dates():
    """제외일 및 회의 주간 설정"""
    
    vacation_id = st.session_state.get("selected_vacation_id")
    if not vacation_id:
        st.warning("⚠️ 먼저 방학을 선택해주세요.")
        return
    
    vacation = get_vacation(vacation_id)
    if not vacation:
        st.error("❌ 방학 정보를 찾을 수 없습니다.")
        return
    
    st.markdown(f"## 📋 제외일 및 회의 주간 - {vacation.title}")
    
    tab1, tab2 = st.tabs(["🚫 제외일", "📅 회의 주간"])
    
    with tab1:
        _render_excluded_dates_tab(vacation)
    
    with tab2:
        _render_meeting_weeks_tab(vacation)


def _render_excluded_dates_tab(vacation: Vacation):
    """제외일 관리"""

    excluded = get_excluded_dates(vacation.id)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### 등록된 제외일")
        if excluded:
            excluded_data = []
            for e in excluded:
                time_scope_display = {
                    "ALL": "종일",
                    "AM": "오전",
                    "PM": "오후"
                }.get(e.time_scope, e.time_scope)
                excluded_data.append({
                    "날짜": e.date.strftime("%m/%d(%a)"),
                    "사유": e.reason,
                    "유형": "공휴일" if e.is_holiday else "학교 휴일",
                    "적용 시간": time_scope_display,
                    "id": e.id
                })

            df = pd.DataFrame(excluded_data)
            st.dataframe(df[["날짜", "사유", "유형", "적용 시간"]], use_container_width=True, hide_index=True)

            # 삭제
            exclude_to_remove = st.multiselect(
                "삭제할 제외일 선택",
                options=[f"{r['날짜']} - {r['사유']}" for r in excluded_data],
                key="remove_excluded"
            )
            if exclude_to_remove and st.button("선택 삭제", key="remove_excluded_btn"):
                for item in exclude_to_remove:
                    idx = [f"{r['날짜']} - {r['사유']}" for r in excluded_data].index(item)
                    remove_excluded_date(excluded_data[idx]["id"])
                st.success("✅ 삭제 완료")
                st.rerun()
        else:
            st.info("📭 등록된 제외일이 없습니다.")

    with col2:
        st.markdown("### ➕ 제외일 추가")
        with st.form("add_excluded_form"):
            ex_date = st.date_input("날짜", value=vacation.start_date,
                                    min_value=vacation.start_date, max_value=vacation.end_date)
            ex_reason = st.text_input("사유", placeholder="개교기념일")
            ex_is_holiday = st.checkbox("공휴일", value=True)
            ex_time_scope = st.selectbox(
                "적용 시간",
                options=["ALL", "AM", "PM"],
                format_func=lambda x: {"ALL": "종일", "AM": "오전", "PM": "오후"}[x],
                index=0
            )

            if st.form_submit_button("추가", use_container_width=True):
                if add_excluded_date(vacation.id, ex_date, ex_reason, ex_is_holiday, ex_time_scope):
                    st.success(f"✅ {ex_date} 제외일이 추가되었습니다.")
                    st.rerun()
                else:
                    st.error("❌ 추가에 실패했습니다.")


def _render_meeting_weeks_tab(vacation: Vacation):
    """회의 주간 관리 - 주간 설정 + 팀 설정 + 일별 배정"""

    sub1, sub2, sub3 = st.tabs(["📅 회의 주간 등록", "👥 팀 설정", "📋 일별 팀 배정"])

    with sub1:
        _render_meeting_week_list(vacation)

    with sub2:
        _render_meeting_team_settings(vacation)

    with sub3:
        _render_daily_team_assignments(vacation)


def _render_meeting_week_list(vacation: Vacation):
    """회의 주간 목록 및 추가"""

    meetings = get_meeting_weeks(vacation.id)

    st.markdown("""
    회의 주간에는 **오전에 돌봄이 운영**되며, 팀별로 순서대로 오전 회의를 합니다.
    회의 중인 팀원은 해당 오전 돌봄에서 제외됩니다.
    """)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### 등록된 회의 주간")
        if meetings:
            meeting_data = [
                {
                    "시작일": m.week_start.strftime("%m/%d(%a)"),
                    "종료일": m.week_end.strftime("%m/%d(%a)"),
                    "설명": m.description,
                    "id": m.id
                }
                for m in meetings
            ]
            st.dataframe(pd.DataFrame(meeting_data)[["시작일", "종료일", "설명"]], use_container_width=True, hide_index=True)

            # 삭제
            meeting_to_remove = st.multiselect(
                "삭제할 회의 주간 선택",
                options=[f"{r['시작일']} ~ {r['종료일']} ({r['설명']})" for r in meeting_data],
                key="remove_meeting"
            )
            if meeting_to_remove and st.button("선택 삭제", key="remove_meeting_btn"):
                for item in meeting_to_remove:
                    idx = [f"{r['시작일']} ~ {r['종료일']} ({r['설명']})" for r in meeting_data].index(item)
                    remove_meeting_week(meeting_data[idx]["id"])
                st.success("✅ 삭제 완료")
                st.rerun()
        else:
            st.info("📭 등록된 회의 주간이 없습니다.")

    with col2:
        st.markdown("### ➕ 회의 주간 추가")
        with st.form("add_meeting_form"):
            m_start = st.date_input("시작일 (월요일)", value=vacation.start_date,
                                    min_value=vacation.start_date, max_value=vacation.end_date)
            m_end = st.date_input("종료일 (금요일)", value=min(m_start + timedelta(days=4), vacation.end_date),
                                  min_value=vacation.start_date, max_value=vacation.end_date)

            if st.form_submit_button("추가", use_container_width=True):
                if add_meeting_week(vacation.id, m_start, m_end):
                    st.success(f"✅ {m_start} ~ {m_end} 회의 주간이 추가되었습니다.")
                    st.rerun()
                else:
                    st.error("❌ 추가에 실패했습니다.")


def _render_meeting_team_settings(vacation: Vacation):
    """회의 팀 생성 및 구성원 설정"""

    teams = get_meeting_teams(vacation.id)
    teachers = get_vacation_teachers(vacation.id)

    teacher_map = {}
    for t in teachers:
        tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
        tname = t.get("teacher_name", tid) if isinstance(t, dict) else getattr(t, "teacher_name", tid)
        teacher_map[tid] = tname

    st.markdown("### 등록된 팀")

    if teams:
        for team in teams:
            member_names = [teacher_map.get(mid, mid) for mid in (team.member_ids or [])]
            with st.expander(f"👥 {team.team_name} ({len(team.member_ids)}명: {', '.join(member_names) or '없음'})"):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    new_members = st.multiselect(
                        "구성원",
                        options=list(teacher_map.keys()),
                        default=[m for m in (team.member_ids or []) if m in teacher_map],
                        format_func=lambda x: teacher_map.get(x, x),
                        key=f"team_members_{team.id}"
                    )
                with col_b:
                    if st.button("저장", key=f"save_team_{team.id}"):
                        updated = MeetingTeam(
                            id=team.id,
                            vacation_id=vacation.id,
                            team_name=team.team_name,
                            member_ids=new_members
                        )
                        if save_meeting_team(updated):
                            st.success("✅ 저장됨")
                            st.rerun()
                    if st.button("🗑️ 팀 삭제", key=f"del_team_{team.id}"):
                        if delete_meeting_team(team.id):
                            st.success("✅ 삭제됨")
                            st.rerun()
    else:
        st.info("📭 등록된 팀이 없습니다.")

    st.markdown("---")
    st.markdown("### ➕ 새 팀 추가")
    with st.form("add_team_form"):
        new_team_name = st.text_input("팀 이름", placeholder="예: 1팀, 수학팀")
        new_members = st.multiselect(
            "구성원",
            options=list(teacher_map.keys()),
            format_func=lambda x: teacher_map.get(x, x)
        )
        if st.form_submit_button("팀 추가", use_container_width=True):
            if new_team_name:
                new_team = MeetingTeam(
                    vacation_id=vacation.id,
                    team_name=new_team_name,
                    member_ids=new_members
                )
                if save_meeting_team(new_team):
                    st.success(f"✅ '{new_team_name}' 팀이 추가되었습니다.")
                    st.rerun()
                else:
                    st.error("❌ 추가에 실패했습니다.")
            else:
                st.warning("⚠️ 팀 이름을 입력해주세요.")


def _render_daily_team_assignments(vacation: Vacation):
    """회의 주간 날짜별로 어느 팀이 오전 회의를 하는지 배정 (여러 팀 가능)"""

    meetings = get_meeting_weeks(vacation.id)
    if not meetings:
        st.info("⚠️ 먼저 회의 주간을 등록해주세요.")
        return

    teams = get_meeting_teams(vacation.id)
    if not teams:
        st.info("⚠️ 먼저 팀을 설정해주세요.")
        return

    assignments = get_daily_meeting_assignments(vacation.id)
    # 날짜별 배정된 팀 목록
    assignment_map = {}
    for a in assignments:
        d = a.date.isoformat() if hasattr(a.date, 'isoformat') else str(a.date)
        if d not in assignment_map:
            assignment_map[d] = []
        assignment_map[d].append(a.team_id)

    team_options = {t.id: t.team_name for t in teams}

    st.markdown("""
    회의 주간의 각 날짜에 오전 회의를 진행하는 팀을 배정합니다.
    **날짜별로 여러 팀이 돌아가며 회의할 수 있습니다.**
    배정된 팀의 구성원은 해당 날 오전 돌봄에서 제외됩니다.
    """)

    for meeting in meetings:
        week_start = meeting.week_start
        week_end = meeting.week_end
        st.markdown(f"#### 📅 {week_start.strftime('%m/%d')} ~ {week_end.strftime('%m/%d')} 주간")

        date_range = pd.date_range(week_start, week_end, freq='D')
        for d in date_range:
            d_date = d.date()
            if d_date.weekday() >= 5:
                continue
            d_str = d_date.isoformat()
            current_team_ids = assignment_map.get(d_str, [])

            st.markdown(f"**{d_date.strftime('%m/%d (%a)')}**")

            # 현재 배정된 팀 표시
            if current_team_ids:
                assigned_names = [team_options.get(tid, tid) for tid in current_team_ids]
                st.markdown(f"현재 배정: {', '.join(assigned_names)}")

            # 새 팀 추가
            col_add, col_btn = st.columns([3, 1])
            with col_add:
                team_to_add = st.selectbox(
                    "팀 추가",
                    options=list(team_options.keys()),
                    format_func=lambda x: team_options.get(x, x),
                    key=f"add_team_{d_str}",
                    label_visibility="collapsed",
                    placeholder="추가할 팀 선택"
                )
            with col_btn:
                if st.button("➕ 추가", key=f"add_daily_{d_str}"):
                    if team_to_add and team_to_add not in current_team_ids:
                        save_daily_meeting_assignment(vacation.id, d_date, team_to_add)
                        st.success(f"✅ {team_options[team_to_add]} 추가됨")
                        st.rerun()

            # 배정된 팀 삭제
            if current_team_ids:
                team_to_remove = st.multiselect(
                    "삭제할 팀 선택",
                    options=current_team_ids,
                    format_func=lambda x: team_options.get(x, x),
                    key=f"remove_team_{d_str}"
                )
                if team_to_remove and st.button("🗑️ 삭제", key=f"del_daily_{d_str}"):
                    for tid in team_to_remove:
                        delete_daily_meeting_assignment(vacation.id, d_date, tid)
                    st.success("✅ 삭제 완료")
                    st.rerun()

            st.divider()


# ============================================================
# 2차 랜덤 배정 탭
# ============================================================
def _render_stage2_random_assignment():
    """2차 랜덤 배정: 교사 입력 완료 후 최종 날짜·슬롯 배치"""

    vacation_id = st.session_state.get("selected_vacation_id")
    if not vacation_id:
        st.warning("⚠️ 먼저 방학을 선택해주세요.")
        return

    vacation = get_vacation(vacation_id)
    if not vacation:
        st.error("❌ 방학 정보를 찾을 수 없습니다.")
        return

    st.markdown(f"## 🎲 2차 랜덤 배정 - {vacation.title}")
    st.markdown("모든 교사가 **휴가 신청 / 행정 신청 / 선호도 설정**을 완료한 후 실행합니다.")

    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.markdown("### 교사 입력 완료 현황")

        ready_status = get_teachers_ready_status(vacation_id)
        all_ready = bool(ready_status) and all(item.get("is_ready", False) for item in ready_status)

        if ready_status:
            ready_data = [{
                "교사명": item.get("teacher_name", "Unknown"),
                "상태": "✅ 완료" if item.get("is_ready", False) else "⏳ 미완료"
            } for item in ready_status]
            st.dataframe(pd.DataFrame(ready_data), use_container_width=True, hide_index=True)

            if all_ready:
                st.success("✅ 모든 교사 입력 완료!")
            else:
                st.warning("⏳ 미완료 교사가 있습니다.")
        else:
            st.info("📭 배정된 교사가 없습니다.")

        if st.button("🎲 2차 랜덤 배정 실행", type="primary", use_container_width=True,
                     disabled=not all_ready):
            with st.spinner("🔄 랜덤 배정 실행 중..."):
                try:
                    result = run_random_assignment(vacation)
                    if result.success:
                        st.session_state["optimization_result"] = result
                        st.success("✅ 배정 완료! 오른쪽에서 결과를 확인하고 저장하세요.")
                    else:
                        st.error(f"❌ 배정 실패: {result.error_message}")
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc(), language="python")

    with col_right:
        if "optimization_result" in st.session_state:
            result = st.session_state["optimization_result"]
            st.markdown("### 📊 배정 결과")
            render_optimization_preview(result)

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                if st.button("💾 결과 저장", type="primary", use_container_width=True):
                    if save_schedules(result.schedules):
                        calculate_and_save_stats(vacation_id)
                        update_vacation(vacation_id, {"status": "confirmed"})
                        st.success("✅ 스케줄 저장 완료!")
                        st.session_state.pop("optimization_result", None)
                        st.rerun()
                    else:
                        st.error("❌ 저장 실패")
            with col_s2:
                if st.button("🔄 결과 초기화", use_container_width=True):
                    st.session_state.pop("optimization_result", None)
                    st.rerun()
        else:
            st.info("왼쪽에서 2차 랜덤 배정을 실행하면 결과가 여기에 표시됩니다.")


def _run_stage1_total_calculation(vacation, vacation_id: str, admin_point_value: int):
    """1단계: 교사별 총량(설정돌봄/설정행정/설정휴가) 계산 후 DB 저장 및 상태를 'input'으로 변경"""
    try:
        teachers = get_vacation_teachers(vacation_id)
        care_reqs = get_care_requirements(vacation_id)
        flash = get_flash_teachers(vacation_id)
        excluded = get_excluded_dates(vacation_id)
        meetings = get_meeting_weeks(vacation_id)

        if not teachers:
            st.error("❌ 배정된 교사가 없습니다. 먼저 교사를 배정해주세요.")
            return
        if not care_reqs:
            st.error("❌ 돌봄 필요 인원이 설정되지 않았습니다. 먼저 설정해주세요.")
            return

        # 행정 포인트 일괄 설정
        update_all_teacher_admin_points(vacation_id, admin_point_value)

        # 제외일/공휴일 scope 맵 구성 (date → "ALL" | "AM" | "PM")
        excluded_scope_map = {e.date: e.time_scope for e in excluded}
        for y in range(vacation.start_date.year, vacation.end_date.year + 1):
            for h in get_korean_holidays(y):
                if vacation.start_date <= h <= vacation.end_date:
                    excluded_scope_map[h] = "ALL"

        # 유효한 (날짜, 슬롯) 조합 결정: 제외일·공휴일 슬롯은 처음부터 제외
        care_reqs_map = {(cr.date, cr.slot_type): cr.required_count for cr in care_reqs}
        valid_slots = set()
        for cr in care_reqs:
            scope = excluded_scope_map.get(cr.date)
            if scope == "ALL":
                continue          # 하루 전체 배정 불가
            if scope == "AM" and cr.slot_type == "AM":
                continue          # 오전 배정 불가
            if scope == "PM" and cr.slot_type == "PM":
                continue          # 오후 배정 불가
            valid_slots.add((cr.date, cr.slot_type))

        # 회의 주간: PM 슬롯 추가 제외
        meeting_teams = get_meeting_teams(vacation_id)
        daily_assignments = get_daily_meeting_assignments(vacation_id)

        for m in meetings:
            week_dates = pd.date_range(m.week_start, m.week_end, freq='D')
            for d in week_dates:
                d_date = d.date()
                if d_date.weekday() >= 5:
                    continue
                valid_slots.discard((d_date, "PM"))

        # 유효 슬롯 기준 총 돌봄 필요 슬롯 수
        total_care_slots = sum(care_reqs_map.get(slot, 0) for slot in valid_slots)

        # 반짝선생님: 유효한 슬롯에서만 1 감소 (제외된 날짜는 이미 valid_slots에 없음)
        # get_flash_teachers()는 raw dict를 반환하므로 date가 문자열일 수 있음 → date 타입 변환
        from datetime import date as _date
        for f in flash:
            f_date = f.get("date") if isinstance(f, dict) else f.date
            f_slot = f.get("slot_type") if isinstance(f, dict) else f.slot_type
            if isinstance(f_date, str):
                f_date = _date.fromisoformat(f_date)
            if (f_date, f_slot) in valid_slots:
                total_care_slots -= 1

        total_care_slots = max(0, total_care_slots)

        # 근무 가능 날짜: ALL 제외일/공휴일만 통째로 제외 (excluded_scope_map 재활용)
        all_excluded = {d for d, scope in excluded_scope_map.items() if scope == "ALL"}
        working_days = get_working_days(vacation.start_date, vacation.end_date, all_excluded)
        total_available_slots = len(working_days) * 2  # 오전+오후

        # carry_over_points가 적은 교사에게 우선 배정 (공평한 누적 관리)
        num_teachers = len(teachers)
        sorted_teachers = sorted(
            teachers,
            key=lambda t: t.get("carry_over_points", 0) if isinstance(t, dict) else t.carry_over_points
        )

        care_base = total_care_slots // num_teachers
        care_remainder = total_care_slots % num_teachers

        results = []
        for i, t in enumerate(sorted_teachers):
            tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
            tname = t.get("teacher_name", "Unknown") if isinstance(t, dict) else "Unknown"
            carry = t.get("carry_over_points", 0) if isinstance(t, dict) else t.carry_over_points

            cp = care_base + (1 if i < care_remainder else 0)
            cp = max(1, cp - carry)
            vp = max(0, total_available_slots - cp - admin_point_value)

            update_teacher_points(vacation_id, tid,
                                  care_points=cp,
                                  admin_points=admin_point_value,
                                  vacation_points=vp)
            results.append({
                "교사명": tname,
                "설정돌봄": cp,
                "설정행정": admin_point_value,
                "설정휴가": vp,
                "합계": cp + admin_point_value + vp
            })

        # 방학 상태를 "input"으로 변경 → 교사들이 신청 입력 가능
        update_vacation(vacation_id, {"status": "input"})
        clear_vacation_cache()  # DB에 저장된 최신 포인트를 2차 배정에서 바로 읽도록 캐시 초기화

        st.success("✅ 총량 계산 완료! 방학 상태가 '교사 입력 중'으로 변경되었습니다.")
        st.info(
            f"- 총 돌봄 슬롯: **{total_care_slots}개** ÷ {num_teachers}명 → 1인당 **{care_base}~{care_base + 1}회**\n"
            f"- 행정: **{admin_point_value}회** (모든 교사 동일)\n"
            f"- 근무 가능: {len(working_days)}일 × 2슬롯 = **{total_available_slots}슬롯**"
        )
        st.markdown("**📋 교사별 배포 결과:**")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        st.info("💡 교사들이 자신의 총량(설정돌봄/설정행정/설정휴가)을 확인하고 휴가·행정 신청을 입력할 수 있습니다.")

    except Exception as e:
        st.error(f"❌ 총량 계산 중 오류 발생: {str(e)}")
        import traceback
        st.code(traceback.format_exc(), language="python")


# ============================================================
# 계정 관리 탭
# ============================================================
def _render_account_management():
    """계정 관리 - 교사 계정 삭제 및 방학 배정 초기화"""
    
    st.markdown("## 🔐 계정 관리")
    st.warning("⚠️ 이 페이지의 작업은 되돌릴 수 없습니다. 신중하게 진행해주세요.")
    
    tab_del, tab_reset = st.tabs(["🗑️ 교사 계정 삭제", "🔄 방학 배정 초기화"])
    
    with tab_del:
        _render_delete_teacher_account()
    
    with tab_reset:
        _render_reset_vacation_assignments()


def _render_delete_teacher_account():
    """교사 계정 삭제 UI"""
    
    st.markdown("### 🗑️ 교사 계정 삭제")
    st.markdown("""
    선택한 교사의 계정을 **완전히 삭제**합니다.
    삭제 시 다음 데이터가 모두 함께 제거됩니다:
    - 교사 프로필 정보
    - 방학 배정 정보
    - 교사 선호도 설정
    - 휴가/행정 신청 내역
    - 배정된 스케줄
    - 반짝선생님 등록
    - 통계 데이터
    """)
    
    # 모든 교사 목록 조회
    all_teachers = get_all_teachers()
    
    if not all_teachers:
        st.info("📭 등록된 교사 계정이 없습니다.")
        return
    
    # 교사 선택
    teacher_options = {t.get("id"): f"{t.get('name', 'Unknown')} ({t.get('email', '')})" for t in all_teachers}
    
    selected_teacher_id = st.selectbox(
        "삭제할 교사 선택",
        options=list(teacher_options.keys()),
        format_func=lambda x: teacher_options[x],
        key="delete_teacher_select"
    )
    
    selected_teacher_name = teacher_options[selected_teacher_id]
    
    # 확인 체크박스
    st.markdown("---")
    st.error(f"🚨 정말로 **{selected_teacher_name}** 교사의 계정을 삭제하시겠습니까?")
    st.markdown("이 작업은 **되돌릴 수 없습니다.**")
    
    confirm_text = st.text_input(
        f'삭제를 확인하려면 "{selected_teacher_name.split("(")[0].strip()}"을(를) 입력하세요:',
        key="delete_confirm_input"
    )
    
    teacher_name_only = selected_teacher_name.split("(")[0].strip()
    
    if st.button("🗑️ 계정 영구 삭제", type="primary", use_container_width=True, disabled=(confirm_text != teacher_name_only)):
        if confirm_text == teacher_name_only:
            with st.spinner("🔄 계정을 삭제 중입니다..."):
                success = delete_teacher_account(selected_teacher_id)
                if success:
                    st.success(f"✅ '{teacher_name_only}' 교사의 계정이 성공적으로 삭제되었습니다.")
                    st.rerun()
                else:
                    st.error("❌ 계정 삭제에 실패했습니다.")
        else:
            st.warning("⚠️ 교사 이름을 정확히 입력해주세요.")


def _render_reset_vacation_assignments():
    """방학 배정 초기화 및 방학 삭제 UI"""
    
    vacations = get_vacations()
    if not vacations:
        st.info("📭 등록된 방학이 없습니다.")
        return
    
    # ============================================================
    # 방학별 배정 초기화
    # ============================================================
    st.markdown("### 🔄 방학별 배정 초기화")
    st.markdown("""
    특정 방학의 **배정된 스케줄과 통계를 초기화**합니다.
    초기화 시 다음 데이터가 제거됩니다:
    - 해당 방학의 최종 스케줄
    - 해당 방학의 통계 데이터
    - 해당 방학 교사들의 `is_ready` 상태 (미완료로 초기화)
    - 해당 방학 교사들의 포인트 (0으로 초기화)
    
    **유지되는 데이터:**
    - 방학 정보 자체
    - 교사 배정 정보
    - 돌봄 필요 인원 설정
    - 반짝선생님 등록
    - 제외일/회의 주간 설정
    - 교사 선호도/휴가 신청
    """)
    
    # 방학 선택
    vacation_options = {v.title: v for v in vacations}
    selected_title = st.selectbox(
        "초기화할 방학 선택",
        list(vacation_options.keys()),
        key="reset_vacation_select"
    )
    selected_vacation = vacation_options[selected_title]
    
    col1, col2 = st.columns([1, 1])
    with col1:
        confirm_reset_single = st.checkbox(
            f"'{selected_vacation.title}' 방학 배정을 초기화하는 것에 동의합니다",
            key="reset_single_confirm"
        )
    with col2:
        if st.button("🔄 선택 방학 배정 초기화", type="primary", use_container_width=True, disabled=not confirm_reset_single):
            if confirm_reset_single:
                with st.spinner(f"🔄 '{selected_vacation.title}' 방학 배정을 초기화 중입니다..."):
                    success = reset_vacation_assignments(selected_vacation.id)
                    if success:
                        st.success(f"✅ '{selected_vacation.title}' 방학 배정이 초기화되었습니다.")
                        st.rerun()
                    else:
                        st.error("❌ 초기화에 실패했습니다.")
    
    st.markdown("---")
    
    # ============================================================
    # 전체 방학 배정 초기화
    # ============================================================
    st.markdown("### 🔄 전체 방학 배정 초기화")
    st.error("🚨 이 작업은 **모든 방학**의 최적화 결과를 초기화합니다. 되돌릴 수 없습니다.")
    
    confirm_reset_all = st.checkbox(
        "모든 방학 배정을 초기화하는 것에 동의합니다",
        key="reset_all_confirm"
    )
    
    if st.button("🔄 방학 배정 전체 초기화", type="primary", use_container_width=True, disabled=not confirm_reset_all):
        if confirm_reset_all:
            with st.spinner("🔄 모든 방학 배정을 초기화 중입니다..."):
                success = reset_all_vacation_assignments()
                if success:
                    st.success("✅ 모든 방학 배정이 초기화되었습니다. (스케줄/통계 삭제, is_ready 초기화)")
                    st.rerun()
                else:
                    st.error("❌ 초기화에 실패했습니다.")
    
    st.markdown("---")
    
    # ============================================================
    # 방학 삭제
    # ============================================================
    st.markdown("### 🗑️ 방학 삭제")
    st.markdown("""
    선택한 **방학 자체를 완전히 삭제**합니다.
    삭제 시 다음 데이터가 모두 함께 제거됩니다:
    - 방학 정보
    - 최종 스케줄 및 통계
    - 교사 배정 정보
    - 교사 선호도 및 휴가/행정 신청
    - 돌봄 필요 인원 설정
    - 반짝선생님 등록
    - 제외일/회의 주간 설정
    - 회의 팀 및 일별 배정
    """)
    
    # 방학 선택 (삭제용)
    delete_vacation_options = {v.title: v for v in vacations}
    delete_selected_title = st.selectbox(
        "삭제할 방학 선택",
        list(delete_vacation_options.keys()),
        key="delete_vacation_select"
    )
    delete_selected_vacation = delete_vacation_options[delete_selected_title]
    
    st.error(f"🚨 정말로 **'{delete_selected_vacation.title}'** 방학을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
    
    confirm_delete_text = st.text_input(
        f'삭제를 확인하려면 "{delete_selected_vacation.title}"을(를) 정확히 입력하세요:',
        key="delete_vacation_confirm_input"
    )
    
    if st.button("🗑️ 방학 영구 삭제", type="primary", use_container_width=True, disabled=(confirm_delete_text != delete_selected_vacation.title)):
        if confirm_delete_text == delete_selected_vacation.title:
            with st.spinner(f"🔄 '{delete_selected_vacation.title}' 방학을 삭제 중입니다..."):
                success = delete_vacation(delete_selected_vacation.id)
                if success:
                    st.success(f"✅ '{delete_selected_vacation.title}' 방학이 성공적으로 삭제되었습니다.")
                    st.rerun()
                else:
                    st.error("❌ 방학 삭제에 실패했습니다.")
        else:
            st.warning("⚠️ 방학 이름을 정확히 입력해주세요.")
