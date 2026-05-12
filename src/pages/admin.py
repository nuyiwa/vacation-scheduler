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
    get_teachers_ready_status, is_all_teachers_ready,
    delete_teacher_account, reset_all_vacation_assignments,
    reset_vacation_assignments, delete_vacation
)
from src.db.models import MeetingTeam
from src.utils.korean_holidays import (
    get_korean_holidays, get_working_days
)
from src.optimizer.scheduler import run_optimization, run_random_assignment, render_optimization_preview


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
        "👨‍🏫 교사 배정",
        "👶 돌봄 필요 인원",
        "⭐ 반짝선생님",
        "📋 제외일/회의",
        "⚡ 최적화 실행",
        "🔐 계정 관리"
    ])
    
    with tab1:
        _render_vacation_management()
    
    with tab2:
        _render_teacher_assignment()
    
    with tab3:
        _render_care_requirements()
    
    with tab4:
        _render_flash_teachers()
    
    with tab5:
        _render_excluded_dates()
    
    with tab6:
        _render_optimization()
    
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
def _render_teacher_assignment():
    """방학별 교사 배정 및 포인트 설정"""
    
    vacation_id = st.session_state.get("selected_vacation_id")
    if not vacation_id:
        st.warning("⚠️ 먼저 방학을 선택해주세요.")
        return
    
    vacation = get_vacation(vacation_id)
    if not vacation:
        st.error("❌ 방학 정보를 찾을 수 없습니다.")
        return
    
    st.markdown(f"## 👨‍🏫 교사 배정 - {vacation.title}")
    st.markdown("""
    **포인트 시스템 안내**
    - **돌봄 포인트**: 돌봄 필요 인원 기반 자동 계산 (오전/오후 각 1포인트)
    - **행정 포인트**: 관리자가 설정한 값 (모든 교사 동일)
    - **휴가 포인트**: 총 근무 가능 포인트 - 돌봄 포인트 - 행정 포인트 (자동 계산)
    """)
    
    # 현재 배정된 교사 목록
    teachers = get_vacation_teachers(vacation_id)
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("### 현재 배정된 교사")
        
        if teachers:
            teacher_data = []
            for t in teachers:
                t_name = t.get("teacher_name", "Unknown") if isinstance(t, dict) else "Unknown"
                t_care = t.get("care_points", 0) if isinstance(t, dict) else t.care_points
                t_admin = t.get("admin_points", 0) if isinstance(t, dict) else t.admin_points
                t_vacation = t.get("vacation_points", 0) if isinstance(t, dict) else t.vacation_points
                t_carry = t.get("carry_over_points", 0) if isinstance(t, dict) else t.carry_over_points

                teacher_data.append({
                    "교사명": t_name,
                    "돌봄 포인트": t_care,
                    "행정 포인트": t_admin,
                    "휴가 포인트": t_vacation,
                    "이월 포인트": t_carry,
                    "teacher_id": t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
                })

            df = pd.DataFrame(teacher_data)

            # 포인트 편집
            edited_df = st.data_editor(
                df,
                column_config={
                    "교사명": st.column_config.TextColumn("교사명", disabled=True),
                    "돌봄 포인트": st.column_config.NumberColumn("돌봄 포인트", min_value=0, max_value=200, help="돌봄 필요 인원 기반 자동 계산"),
                    "행정 포인트": st.column_config.NumberColumn("행정 포인트", min_value=0, max_value=100, help="관리자가 설정 (모든 교사 동일)"),
                    "휴가 포인트": st.column_config.NumberColumn("휴가 포인트", min_value=0, max_value=200, help="총 근무 가능 - 돌봄 - 행정 (자동 계산)"),
                    "이월 포인트": st.column_config.NumberColumn("이월 포인트", disabled=True),
                    "teacher_id": None  # 숨김
                },
                use_container_width=True,
                hide_index=True,
                key="teacher_point_editor"
            )

            # 변경사항 저장
            if st.button("설정 저장", key="save_points"):
                success = True
                for _, row in edited_df.iterrows():
                    if not update_teacher_points(
                        vacation_id, row["teacher_id"],
                        care_points=row["돌봄 포인트"],
                        admin_points=row["행정 포인트"],
                        vacation_points=row["휴가 포인트"]
                    ):
                        success = False

                if success:
                    st.success("✅ 교사 포인트 설정이 저장되었습니다.")
                    st.rerun()
                else:
                    st.error("❌ 일부 저장에 실패했습니다.")
            
            # 교사 제거
            teachers_to_remove = st.multiselect(
                "제거할 교사 선택",
                options=[t["교사명"] for t in teacher_data],
                key="remove_teachers"
            )
            if teachers_to_remove and st.button("선택 교사 제거", key="remove_teacher_btn"):
                for t_name in teachers_to_remove:
                    t = next((t for t in teacher_data if t["교사명"] == t_name), None)
                    if t:
                        remove_teacher_from_vacation(vacation_id, t["teacher_id"])
                st.success("✅ 선택한 교사가 제거되었습니다.")
                st.rerun()
        else:
            st.info("📭 아직 배정된 교사가 없습니다.")
    
    with col2:
        st.markdown("### ➕ 교사 추가")
        
        # 현재 배정된 교사 ID 목록
        assigned_teacher_ids = set()
        for t in teachers:
            tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
            assigned_teacher_ids.add(tid)
        
        # 모든 교사 목록 조회
        all_teachers = get_all_teachers()
        
        # 아직 배정되지 않은 교사만 필터링
        available_teachers = [t for t in all_teachers if t.get("id") not in assigned_teacher_ids]
        
        if available_teachers:
            teacher_options = {t.get("id"): t.get("name", t.get("email", "Unknown")) for t in available_teachers}
            selected_teacher_id = st.selectbox(
                "추가할 교사 선택",
                options=list(teacher_options.keys()),
                format_func=lambda x: teacher_options[x],
                key="add_teacher_select"
            )
            
            if st.button("교사 추가", key="add_teacher_btn", use_container_width=True):
                if add_teacher_to_vacation(vacation_id, selected_teacher_id):
                    st.success(f"✅ '{teacher_options[selected_teacher_id]}' 교사가 배정되었습니다.")
                    st.rerun()
                else:
                    st.error("❌ 교사 추가에 실패했습니다.")
        else:
            if all_teachers:
                st.info("✅ 모든 교사가 이미 배정되었습니다.")
            else:
                st.info("📭 등록된 교사 계정이 없습니다. 먼저 회원가입으로 교사 계정을 만들어주세요.")


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
                excluded_data.append({
                    "날짜": e.date.strftime("%m/%d(%a)"),
                    "사유": e.reason,
                    "유형": "공휴일" if e.is_holiday else "학교 휴일",
                    "id": e.id
                })

            df = pd.DataFrame(excluded_data)
            st.dataframe(df[["날짜", "사유", "유형"]], use_container_width=True, hide_index=True)

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

            if st.form_submit_button("추가", use_container_width=True):
                if add_excluded_date(vacation.id, ex_date, ex_reason, ex_is_holiday):
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
# 최적화 실행 탭
# ============================================================
def _render_optimization():
    """PuLP 최적화 실행 및 결과 저장"""
    
    vacation_id = st.session_state.get("selected_vacation_id")
    if not vacation_id:
        st.warning("⚠️ 먼저 방학을 선택해주세요.")
        return
    
    vacation = get_vacation(vacation_id)
    if not vacation:
        st.error("❌ 방학 정보를 찾을 수 없습니다.")
        return
    
    st.markdown(f"## ⚡ 최적화 실행 - {vacation.title}")
    
    st.markdown("""
    ### 최적화 전 확인사항
    1. ✅ 교사 배정 및 목표 횟수 설정 완료
    2. ✅ 돌봄 필요 인원 설정 완료
    3. ✅ 반짝선생님 등록 완료
    4. ✅ 제외일/회의 주간 설정 완료
    5. ✅ 교사 선호도 입력 완료
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 현재 설정 요약")
        
        teachers = get_vacation_teachers(vacation_id)
        care_reqs = get_care_requirements(vacation_id)
        flash = get_flash_teachers(vacation_id)
        excluded = get_excluded_dates(vacation_id)
        meetings = get_meeting_weeks(vacation_id)
        
        st.markdown(f"""
        - 👨‍🏫 교사 수: {len(teachers)}명
        - 👶 돌봄 설정: {len(care_reqs)}개
        - ⭐ 반짝선생님: {len(flash)}명
        - 🚫 제외일: {len(excluded)}일
        - 📅 회의 주간: {len(meetings)}주
        """)
    
    with col2:
        st.markdown("### 👨‍🏫 교사 설정 완료 현황")
        
        # 교사 완료 현황 표시
        ready_status = get_teachers_ready_status(vacation_id)
        if ready_status:
            ready_data = []
            all_ready = True
            for item in ready_status:
                is_ready = item.get("is_ready", False)
                if not is_ready:
                    all_ready = False
                ready_data.append({
                    "교사명": item.get("teacher_name", "Unknown"),
                    "상태": "✅ 완료" if is_ready else "⏳ 미완료"
                })
            
            df = pd.DataFrame(ready_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            if all_ready:
                st.success("✅ 모든 교사가 설정을 완료했습니다!")
            else:
                st.warning("⏳ 아직 설정을 완료하지 않은 교사가 있습니다.")
        else:
            st.info("📭 교사 정보를 불러올 수 없습니다.")
        
        st.markdown("---")
        st.markdown("### 🚀 최적화 실행")
        
        # 행정 포인트 입력
        st.markdown("**행정 포인트 설정**")
        admin_point_value = st.number_input(
            "모든 교사에게 동일하게 부여할 행정 포인트",
            min_value=0, max_value=100, value=5,
            help="모든 교사가 동일한 행정 포인트를 갖습니다. (예: 5)",
            key="admin_point_input"
        )
        
        col_opt1, col_opt2 = st.columns(2)
        
        with col_opt1:
            if st.button("🎲 랜덤 배정 실행", use_container_width=True):
                with st.spinner("🔄 랜덤 배정을 실행 중입니다..."):
                    try:
                        result = run_random_assignment(vacation)
                        if result.success:
                            st.session_state["optimization_result"] = result
                            st.session_state["optimization_type"] = "random"
                            st.success("✅ 랜덤 배정이 완료되었습니다! 아래에서 결과를 확인하고 저장하세요.")
                        else:
                            st.error(f"❌ 랜덤 배정 실패: {result.error_message}")
                    except Exception as e:
                        st.error(f"❌ 랜덤 배정 중 오류 발생: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc(), language="python")
        
        with col_opt2:
            if st.button("⚡ PuLP 최적화 실행", type="primary", use_container_width=True):
                with st.spinner("🔄 최적화를 실행 중입니다..."):
                    try:
                        # 1. 먼저 모든 교사의 행정 포인트를 설정
                        update_all_teacher_admin_points(vacation_id, admin_point_value)
                        
                        # 2. 돌봄 포인트 자동 계산
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
                        
                        # 총 돌봄 필요 포인트 계산
                        total_care_points = 0
                        for cr in care_reqs:
                            total_care_points += cr.required_count
                        
                        # 반짝선생님이 있는 슬롯은 돌봄 필요 인원 1 감소
                        for f in flash:
                            total_care_points -= 1
                        
                        # 회의 주간: 오후 돌봄 없음, 회의 팀원 오전 돌봄 제외
                        meeting_teams = get_meeting_teams(vacation_id)
                        daily_assignments = get_daily_meeting_assignments(vacation_id)
                        
                        for m in meetings:
                            week_dates = pd.date_range(m.week_start, m.week_end, freq='D')
                            for d in week_dates:
                                d_date = d.date()
                                if d_date.weekday() >= 5:
                                    continue
                                d_str = d_date.isoformat()
                                
                                # 오후 돌봄 없음
                                for cr in care_reqs:
                                    if cr.date == d_date and cr.slot_type == "PM":
                                        total_care_points -= cr.required_count
                                
                                # 회의 팀원 오전 돌봄 제외
                                assigned_teams = [a for a in daily_assignments if a.date == d_date]
                                for at in assigned_teams:
                                    team = next((t for t in meeting_teams if t.id == at.team_id), None)
                                    if team and team.member_ids:
                                        total_care_points -= len(team.member_ids)
                        
                        # 교사당 목표 돌봄 포인트 계산
                        num_teachers = len(teachers)
                        
                        # 총 근무 가능 포인트 계산 (1인당)
                        # 제외일 + 공휴일을 합쳐서 전달
                        all_excluded = set()
                        for e in excluded:
                            all_excluded.add(e.date)
                        for y in range(vacation.start_date.year, vacation.end_date.year + 1):
                            for h in get_korean_holidays(y):
                                if vacation.start_date <= h <= vacation.end_date:
                                    all_excluded.add(h)
                        
                        working_days = get_working_days(
                            vacation.start_date, vacation.end_date,
                            all_excluded
                        )
                        total_available_points = len(working_days) * 2  # 오전+오후
                        
                        # carry_over_points가 가장 적은 순으로 정렬 (누적치가 적은 교사가 우선)
                        sorted_teachers = sorted(
                            teachers,
                            key=lambda t: t.get("carry_over_points", 0) if isinstance(t, dict) else t.carry_over_points
                        )
                        
                        # 각 교사의 포인트 저장
                        # total_care_points를 교사 수로 나누되, 나머지는 carry_over_points가 적은 교사에게 우선 배정
                        care_points_base = total_care_points // num_teachers  # 기본 몫
                        care_points_remainder = total_care_points % num_teachers  # 나머지
                        
                        assigned_care_total = 0  # 실제 배정된 돌봄 포인트 합계
                        for i, t in enumerate(sorted_teachers):
                            tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
                            
                            # 나머지 1포인트를 carry_over_points가 적은 교사에게 배정
                            extra = 1 if i < care_points_remainder else 0
                            cp = care_points_base + extra
                            
                            # carry_over_points 반영 (양수면 덜 배정, 음수면 더 배정)
                            carry = t.get("carry_over_points", 0) if isinstance(t, dict) else t.carry_over_points
                            cp = max(1, cp - carry)  # 최소 1포인트는 보장
                            
                            vacation_points = max(0, total_available_points - cp - admin_point_value)
                            
                            update_teacher_points(
                                vacation_id, tid,
                                care_points=cp,
                                admin_points=admin_point_value,
                                vacation_points=vacation_points
                            )
                            assigned_care_total += cp
                        
                        # 만약 나머지 처리 + carry 반영으로 인해 total_care_points보다 부족하면,
                        # carry_over_points가 가장 적은 교사에게 추가 배정
                        deficit = total_care_points - assigned_care_total
                        if deficit > 0:
                            for i in range(deficit):
                                idx = i % num_teachers
                                t = sorted_teachers[idx]
                                tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
                                # 현재 DB에 저장된 값을 다시 읽어서 +1
                                current = get_vacation_teacher_points(vacation_id, tid)
                                if current:
                                    update_teacher_points(
                                        vacation_id, tid,
                                        care_points=current["care_points"] + 1,
                                        admin_points=admin_point_value,
                                        vacation_points=max(0, total_available_points - (current["care_points"] + 1) - admin_point_value)
                                    )
                                    assigned_care_total += 1
                        
                        st.success(f"✅ 포인트 자동 계산 완료! (총 돌봄 {total_care_points}포인트, 1인당 {care_points_base}~{care_points_base + 1}포인트)")
                        st.info(f"""
                        - **돌봄 포인트**: {care_points_base}~{care_points_base + 1} (총 {total_care_points}포인트 ÷ {num_teachers}명, 나머지 {care_points_remainder}포인트는 carry_over_points가 적은 교사에게 우선 배정)
                        - **행정 포인트**: {admin_point_value} (관리자 설정)
                        - **총 근무 가능**: {total_available_points}포인트 ({len(working_days)}일 × 2)
                        - **실제 배정 합계**: {assigned_care_total}포인트 (목표: {total_care_points})
                        """)
                        
                        # 3. 최적화 실행
                        result = run_optimization(vacation)
                        
                        if result.success:
                            st.session_state["optimization_result"] = result
                            st.session_state["optimization_type"] = "pulp"
                            st.success("✅ PuLP 최적화가 완료되었습니다! 아래에서 결과를 확인하고 저장하세요.")
                        else:
                            st.error(f"❌ 최적화 실패: {result.error_message}")
                            st.info("💡 문제 해결 팁:")
                            st.markdown("""
                            1. 각 교사의 **포인트**가 너무 높거나 낮은지 확인하세요.
                            2. **돌봄 필요 인원**이 전체 기간에 걸쳐 적절히 설정되었는지 확인하세요.
                            3. **휴가 신청**이 너무 많아서 배정이 불가능한 날짜가 없는지 확인하세요.
                            4. **회의 주간** 설정이 올바른지 확인하세요.
                            5. 교사 수에 비해 **총 포인트 합계**가 너무 큰지 확인하세요.
                            """)
                    except Exception as e:
                        st.error(f"❌ 최적화 중 오류 발생: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc(), language="python")
    
    # 최적화 결과 표시 (session_state에 저장된 결과)
    if "optimization_result" in st.session_state:
        st.markdown("---")
        result = st.session_state["optimization_result"]
        opt_type = st.session_state.get("optimization_type", "unknown")
        opt_label = "🎲 랜덤 배정" if opt_type == "random" else "⚡ PuLP 최적화"
        st.markdown(f"### 📊 {opt_label} 결과")
        
        render_optimization_preview(result)
        
        # 저장 버튼 (항상 표시)
        col_save1, col_save2 = st.columns([1, 1])
        with col_save1:
            if st.button("💾 결과 저장", type="primary", use_container_width=True):
                if save_schedules(result.schedules):
                    calculate_and_save_stats(vacation_id)
                    update_vacation(vacation_id, {"status": "confirmed"})
                    st.success("✅ 스케줄이 저장되었습니다! 모든 교사가 확인할 수 있습니다.")
                    st.session_state.pop("optimization_result", None)
                    st.session_state.pop("optimization_type", None)
                    st.rerun()
                else:
                    st.error("❌ 저장에 실패했습니다.")
        with col_save2:
            if st.button("🔄 결과 초기화", use_container_width=True):
                st.session_state.pop("optimization_result", None)
                st.session_state.pop("optimization_type", None)
                st.rerun()


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
