"""
교사 전용 페이지
- 휴가 신청 (종일/오전/오후)
- 선호도 설정 (돌봄/행정 선호, 연속 휴가 선호 등)
- 본인 스케줄 확인
"""

from datetime import date, timedelta
from typing import List, Optional
import streamlit as st
import pandas as pd

from src.config.settings import (
    VacationRequestType, SLOT_TYPE_NAMES, SlotType,
    VACATION_POINTS
)
from src.db.models import (
    Vacation, VacationRequest, TeacherPreference, Schedule
)
from src.db.queries import (
    get_vacations, get_vacation,
    get_vacation_requests, save_vacation_request, delete_vacation_request,
    get_teacher_preferences, save_teacher_preferences,
    get_schedules, get_vacation_teachers,
    get_admin_requests, save_admin_request, delete_admin_request,
    update_teacher_ready_status, get_vacation_teacher_points
)
from src.db.models import AdminRequest
from src.ui.calendar import render_calendar_page


# ============================================================
# 교사 페이지 메인
# ============================================================
def render_teacher_page(mobile: bool = False):
    """교사 페이지 메인 렌더링"""

    user_id = st.session_state.get("user_id", "")
    user_name = st.session_state.get("user_name", "선생님")

    if mobile:
        st.markdown(f"### 👋 {user_name}님")
    else:
        st.markdown(f"# 👋 안녕하세요, {user_name}님")
    
    # ============================================================
    # 현재 활성화된 방학 선택
    # ============================================================
    vacations = get_vacations()
    active_vacations = [v for v in vacations if v.status in ["planning", "input", "optimized", "confirmed"]]
    
    if not active_vacations:
        st.info("📭 현재 진행 중인 방학이 없습니다. 관리자가 방학을 생성할 때까지 기다려주세요.")
        return
    
    # 방학 선택
    vacation_options = {v.title: v for v in active_vacations}
    selected_title = st.selectbox(
        "방학 선택",
        list(vacation_options.keys()),
        key="teacher_vacation_select"
    )
    selected_vacation = vacation_options[selected_title]
    vacation_id = selected_vacation.id
    
    # ============================================================
    # 탭 구성
    # ============================================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 내 스케줄",
        "🏖️ 휴가 신청",
        "📋 행정 신청",
        "⚙️ 선호도 설정"
    ])

    with tab1:
        _render_my_schedule(selected_vacation, user_id)

    with tab2:
        _render_vacation_request(selected_vacation, user_id)

    with tab3:
        _render_admin_request(selected_vacation, user_id)

    with tab4:
        _render_preferences(selected_vacation, user_id)


# ============================================================
# 내 스케줄 탭
# ============================================================
def _render_my_schedule(vacation: Vacation, user_id: str):
    """본인 스케줄 확인"""
    
    st.markdown(f"## 📅 {vacation.title} 스케줄")
    
    # 캘린더 표시 (기본값: 내 스케줄만)
    render_calendar_page(vacation, user_id, default_show_all=False)
    
    # ============================================================
    # 내 통계
    # ============================================================
    st.markdown("---")
    st.markdown("### 📊 내 통계")
    
    schedules = get_schedules(vacation.id)
    my_schedules = [s for s in schedules if s.teacher_id == user_id]
    
    # 휴가 신청
    my_vacations = get_vacation_requests(user_id, vacation.id)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📋 총 배정", len(my_schedules))
    with col2:
        care_count = len([s for s in my_schedules if "Childcare" in s.slot_type])
        st.metric("👶 돌봄", care_count)
    with col3:
        admin_count = len([s for s in my_schedules if "Admin" in s.slot_type])
        st.metric("📋 행정", admin_count)
    with col4:
        # 휴가 포인트 계산
        vacation_points = sum(
            VACATION_POINTS.get(v.request_type, 0) for v in my_vacations
        )
        st.metric("🏖️ 휴가 포인트", vacation_points)
    with col5:
        # 포인트 대비 진행률
        teachers = get_vacation_teachers(vacation.id)
        my_info = next((t for t in teachers if t.get("teacher_id") == user_id), None)
        total_points = (my_info.get("care_points", 0) + my_info.get("admin_points", 0) + my_info.get("vacation_points", 0)) if my_info else 0
        progress = len(my_schedules)
        st.metric("🎯 포인트 진행", f"{progress}/{total_points}")


# ============================================================
# 휴가 신청 탭
# ============================================================
def _render_vacation_request(vacation: Vacation, user_id: str):
    """지정 휴가 신청 및 관리"""

    st.markdown(f"## 🏖️ 휴가 신청 - {vacation.title}")

    # 포인트 예산 확인
    teachers = get_vacation_teachers(vacation.id)
    my_info = next((t for t in teachers if (t.get("teacher_id") if isinstance(t, dict) else t.teacher_id) == user_id), None)
    budget = my_info.get("vacation_points", 0) if my_info else 0

    my_vacations = get_vacation_requests(user_id, vacation.id)
    used_points = sum(VACATION_POINTS.get(
        v.request_type if hasattr(v, 'request_type') else v.get("request_type", ""), 0
    ) for v in my_vacations)
    remaining = budget - used_points

    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        st.metric("📊 총 휴가 포인트", budget)
    with col_b2:
        st.metric("✅ 사용한 포인트", used_points)
    with col_b3:
        st.metric("🎯 남은 포인트", remaining, delta=None)

    st.markdown("""
    ### 지정 휴가 안내
    - **지정 휴가**를 신청하면 해당 날짜는 반드시 휴가로 처리됩니다.
    - 나머지 휴가는 최적화 엔진이 자동으로 배정합니다.
    - **오전휴가**: 1포인트 | **오후휴가**: 1포인트 | **종일휴가**: 2포인트
    """)
    
    col1, col2 = st.columns([2, 3])

    with col1:
        st.markdown("### ➕ 지정 휴가 신청")

        with st.form("vacation_request_form"):
            req_date = st.date_input(
                "날짜",
                value=vacation.start_date,
                min_value=vacation.start_date,
                max_value=vacation.end_date
            )

            req_type = st.selectbox(
                "휴가 유형",
                options=list(VacationRequestType),
                format_func=lambda x: {
                    VacationRequestType.FULL_DAY: "종일휴가 (2포인트)",
                    VacationRequestType.AM: "오전휴가 (1포인트)",
                    VacationRequestType.PM: "오후휴가 (1포인트)",
                }.get(x, str(x))
            )

            reason = st.text_area("사유 (선택사항)", placeholder="개인 사정")

            submitted = st.form_submit_button("신청", use_container_width=True)
            if submitted:
                cost = VACATION_POINTS.get(req_type.value if hasattr(req_type, 'value') else req_type, 0)
                if used_points + cost > budget:
                    st.error(f"❌ 포인트 초과! 남은 포인트: {remaining}, 필요 포인트: {cost}")
                else:
                    new_request = VacationRequest(
                        teacher_id=user_id,
                        vacation_id=vacation.id,
                        date=req_date,
                        request_type=req_type.value if hasattr(req_type, 'value') else req_type,
                        reason=reason if reason else None
                    )
                    result = save_vacation_request(new_request)
                    if result:
                        st.success(f"✅ 휴가가 신청되었습니다! (포인트: {cost})")
                        st.rerun()
                    else:
                        st.error("❌ 휴가 신청에 실패했습니다. 이미 신청한 날짜인지 확인해주세요.")

    with col2:
        st.markdown("### 📋 내 지정 휴가 목록")

        if my_vacations:
            vacation_data = []
            for v in my_vacations:
                v_type = v.request_type if hasattr(v, 'request_type') else v.get("request_type", "")
                v_label = {
                    "full_day": "종일휴가",
                    "am": "오전휴가",
                    "pm": "오후휴가"
                }.get(v_type, v_type)
                v_points = VACATION_POINTS.get(v_type, 0)

                vacation_data.append({
                    "날짜": v.date.strftime("%m/%d(%a)") if hasattr(v.date, 'strftime') else str(v.date),
                    "유형": v_label,
                    "포인트": v_points,
                    "사유": v.reason if hasattr(v, 'reason') and v.reason else "-",
                    "id": v.id if hasattr(v, 'id') else v.get("id")
                })

            df = pd.DataFrame(vacation_data)
            st.dataframe(df[["날짜", "유형", "포인트", "사유"]], use_container_width=True, hide_index=True)

            # 휴가 취소
            vacation_to_cancel = st.multiselect(
                "취소할 휴가 선택",
                options=[f"{r['날짜']} - {r['유형']}" for r in vacation_data],
                key="cancel_vacation"
            )
            if vacation_to_cancel and st.button("선택 휴가 취소", key="cancel_vacation_btn"):
                for item in vacation_to_cancel:
                    idx = [f"{r['날짜']} - {r['유형']}" for r in vacation_data].index(item)
                    delete_vacation_request(vacation_data[idx]["id"])
                st.success("✅ 선택한 휴가가 취소되었습니다.")
                st.rerun()
        else:
            st.info("📭 아직 신청한 지정 휴가가 없습니다.")


# ============================================================
# 행정 신청 탭 (지정 행정)
# ============================================================
def _render_admin_request(vacation: Vacation, user_id: str):
    """지정 행정 신청 및 관리"""

    st.markdown(f"## 📋 행정 신청 - {vacation.title}")

    # 행정 포인트 확인
    teachers = get_vacation_teachers(vacation.id)
    my_info = next((t for t in teachers if (t.get("teacher_id") if isinstance(t, dict) else t.teacher_id) == user_id), None)
    admin_target = my_info.get("admin_points", 0) if my_info else 0

    my_admin_requests = get_admin_requests(user_id, vacation.id)
    used_admin = len(my_admin_requests)
    remaining_admin = admin_target - used_admin

    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        st.metric("📋 지정 행정 목표", admin_target)
    with col_b2:
        st.metric("✅ 신청한 행정", used_admin)
    with col_b3:
        st.metric("🎯 남은 지정 횟수", remaining_admin)

    st.markdown("""
    ### 지정 행정 안내
    - **지정 행정**을 신청하면 해당 날짜·시간에 행정 업무가 배정됩니다.
    - 나머지 행정 슬롯은 최적화 엔진이 자동으로 배정합니다.
    """)

    col1, col2 = st.columns([2, 3])

    with col1:
        st.markdown("### ➕ 지정 행정 신청")

        with st.form("admin_request_form"):
            req_date = st.date_input(
                "날짜",
                value=vacation.start_date,
                min_value=vacation.start_date,
                max_value=vacation.end_date
            )
            req_slot = st.selectbox(
                "시간대",
                options=["AM", "PM"],
                format_func=lambda x: "오전" if x == "AM" else "오후"
            )
            reason = st.text_area("사유 (선택사항)", placeholder="업무 일정")

            submitted = st.form_submit_button("신청", use_container_width=True)
            if submitted:
                new_req = AdminRequest(
                    teacher_id=user_id,
                    vacation_id=vacation.id,
                    date=req_date,
                    slot_type=req_slot,
                    reason=reason if reason else None
                )
                if save_admin_request(new_req):
                    st.success(f"✅ {req_date} {'오전' if req_slot == 'AM' else '오후'} 행정이 신청되었습니다!")
                    st.rerun()
                else:
                    st.error("❌ 신청에 실패했습니다. 이미 신청한 날짜·시간인지 확인해주세요.")

    with col2:
        st.markdown("### 📋 내 지정 행정 목록")

        if my_admin_requests:
            admin_data = []
            for r in my_admin_requests:
                r_date = r.date if hasattr(r, 'date') else r.get("date")
                r_slot = r.slot_type if hasattr(r, 'slot_type') else r.get("slot_type", "")
                r_reason = r.reason if hasattr(r, 'reason') else r.get("reason", "")
                r_id = r.id if hasattr(r, 'id') else r.get("id")

                admin_data.append({
                    "날짜": r_date.strftime("%m/%d(%a)") if hasattr(r_date, 'strftime') else str(r_date),
                    "시간": "오전" if r_slot == "AM" else "오후",
                    "사유": r_reason if r_reason else "-",
                    "id": r_id
                })

            df = pd.DataFrame(admin_data)
            st.dataframe(df[["날짜", "시간", "사유"]], use_container_width=True, hide_index=True)

            admin_to_cancel = st.multiselect(
                "취소할 행정 신청 선택",
                options=[f"{r['날짜']} {r['시간']}" for r in admin_data],
                key="cancel_admin"
            )
            if admin_to_cancel and st.button("선택 행정 취소", key="cancel_admin_btn"):
                for item in admin_to_cancel:
                    idx = [f"{r['날짜']} {r['시간']}" for r in admin_data].index(item)
                    delete_admin_request(admin_data[idx]["id"])
                st.success("✅ 선택한 행정 신청이 취소되었습니다.")
                st.rerun()
        else:
            st.info("📭 아직 신청한 지정 행정이 없습니다.")


# ============================================================
# 선호도 설정 탭
# ============================================================
def _render_preferences(vacation: Vacation, user_id: str):
    """교사 선호도 설정 - 비율형 슬라이더"""

    st.markdown(f"## ⚙️ 선호도 설정 - {vacation.title}")
    st.markdown("""
    선호도는 최적화 알고리즘에 반영됩니다. 오전/오후 비율은 합이 자동으로 100%가 됩니다.
    """)

    existing_prefs = get_teacher_preferences(user_id, vacation.id)

    # ── 돌봄 선호도 (오전 슬라이더 하나, 오후 자동 계산) ──────────────────
    st.markdown("### 👶 돌봄 선호도")
    care_am_default = existing_prefs.prefer_care_am if existing_prefs else 50
    prefer_care_am = st.slider(
        "오전 돌봄 선호 (%)",
        min_value=0, max_value=100, value=care_am_default,
        help="오전 돌봄 선호 비율. 오후는 (100 - 오전)으로 자동 계산됩니다."
    )
    prefer_care_pm = 100 - prefer_care_am
    st.caption(f"→ 오후 돌봄 선호: **{prefer_care_pm}%** (자동 계산)")

    # ── 행정 선호도 ──────────────────────────────────────────────────────
    st.markdown("### 📋 행정 선호도")
    admin_am_default = existing_prefs.prefer_admin_am if existing_prefs else 50
    prefer_admin_am = st.slider(
        "오전 행정 선호 (%)",
        min_value=0, max_value=100, value=admin_am_default,
        help="오전 행정 선호 비율. 오후는 (100 - 오전)으로 자동 계산됩니다."
    )
    prefer_admin_pm = 100 - prefer_admin_am
    st.caption(f"→ 오후 행정 선호: **{prefer_admin_pm}%** (자동 계산)")

    # ── 휴가 선호도 ──────────────────────────────────────────────────────
    st.markdown("### 🏖️ 휴가 선호도")

    prefer_consecutive_vacation = st.slider(
        "연속 휴가 선호 (%)",
        min_value=0, max_value=100,
        value=existing_prefs.prefer_consecutive_vacation if existing_prefs else 50,
        help="0% = 분산 선호, 100% = 연속 선호"
    )

    st.markdown("**휴가 종류 비율** (오전 + 오후 + 종일 = 100%)")

    vac_am_default = getattr(existing_prefs, "prefer_vacation_am_ratio", 34) if existing_prefs else 34
    vac_pm_default = getattr(existing_prefs, "prefer_vacation_pm_ratio", 33) if existing_prefs else 33

    col1, col2 = st.columns(2)
    with col1:
        prefer_vacation_am_ratio = st.slider(
            "오전 휴가 비율 (%)", 0, 100, vac_am_default,
            help="오전 휴가를 전체 휴가 중 얼마나 원하시나요?"
        )
    with col2:
        max_pm = 100 - prefer_vacation_am_ratio
        prefer_vacation_pm_ratio = st.slider(
            "오후 휴가 비율 (%)", 0, max_pm,
            min(vac_pm_default, max_pm),
            help="오후 휴가 비율. 종일 휴가는 자동 계산됩니다."
        )
    prefer_vacation_full_ratio = 100 - prefer_vacation_am_ratio - prefer_vacation_pm_ratio
    st.caption(
        f"→ 종일 휴가 비율: **{prefer_vacation_full_ratio}%** (자동 계산) "
        f"| 합계: {prefer_vacation_am_ratio + prefer_vacation_pm_ratio + prefer_vacation_full_ratio}%"
    )

    # ── 추가 의견 ─────────────────────────────────────────────────────────
    st.markdown("### 📝 추가 의견")
    notes = st.text_area(
        "기타 의견 (선택사항)",
        value=existing_prefs.notes if existing_prefs and getattr(existing_prefs, 'notes', None) else "",
        placeholder="최적화 시 고려해주었으면 하는 사항을 적어주세요."
    )

    if st.button("💾 선호도 저장", use_container_width=True, type="primary"):
        prefs = TeacherPreference(
            teacher_id=user_id,
            vacation_id=vacation.id,
            prefer_care_am=prefer_care_am,
            prefer_care_pm=prefer_care_pm,
            prefer_admin_am=prefer_admin_am,
            prefer_admin_pm=prefer_admin_pm,
            prefer_consecutive_vacation=prefer_consecutive_vacation,
            prefer_vacation_am_ratio=prefer_vacation_am_ratio,
            prefer_vacation_pm_ratio=prefer_vacation_pm_ratio,
            prefer_vacation_full_ratio=prefer_vacation_full_ratio,
            notes=notes if notes else None
        )
        if save_teacher_preferences(prefs):
            st.success("✅ 선호도가 저장되었습니다! 최적화 시 반영됩니다.")
            st.rerun()
        else:
            st.error("❌ 저장에 실패했습니다.")

    # 현재 선호도 요약
    if existing_prefs:
        st.markdown("---")
        st.markdown("### 📊 현재 저장된 선호도")

        _care_am = existing_prefs.prefer_care_am
        _care_pm = 100 - _care_am
        _admin_am = existing_prefs.prefer_admin_am
        _admin_pm = 100 - _admin_am
        _vac_am = getattr(existing_prefs, "prefer_vacation_am_ratio", 34)
        _vac_pm = getattr(existing_prefs, "prefer_vacation_pm_ratio", 33)
        _vac_full = getattr(existing_prefs, "prefer_vacation_full_ratio", 33)
        _consec = existing_prefs.prefer_consecutive_vacation

        items = [
            ("오전 돌봄", _care_am), ("오후 돌봄", _care_pm),
            ("오전 행정", _admin_am), ("오후 행정", _admin_pm),
            ("연속 휴가 선호", _consec),
        ]
        for label, val in items:
            st.markdown(f"**{label}**: {val}%")
            st.progress(val / 100.0)

        st.markdown(
            f"**휴가 종류 비율** — 오전: {_vac_am}% / 오후: {_vac_pm}% / 종일: {_vac_full}%"
        )

    # ============================================================
    # 설정 완료 버튼
    # ============================================================
    st.markdown("---")
    st.markdown("### ✅ 설정 완료")

    # 현재 완료 상태 확인
    my_info = get_vacation_teacher_points(vacation.id, user_id)
    is_ready = my_info.get("is_ready", False) if my_info else False

    if is_ready:
        st.success("✅ 설정이 완료되었습니다. 관리자가 최적화를 실행할 때까지 기다려주세요.")
        if st.button("🔄 설정 다시 열기", use_container_width=True):
            update_teacher_ready_status(vacation.id, user_id, False)
            st.rerun()
    else:
        st.info("""
        모든 설정을 마치셨다면 아래 **설정 완료** 버튼을 눌러주세요.
        - 휴가 신청, 행정 신청, 선호도 설정을 모두 마친 후 눌러주세요.
        - 관리자가 모든 교사의 설정이 완료된 것을 확인한 후 최적화를 실행합니다.
        """)
        if st.button("✅ 설정 완료", use_container_width=True, type="primary"):
            # 먼저 선호도가 저장되어 있는지 확인
            prefs = get_teacher_preferences(user_id, vacation.id)
            if not prefs:
                st.warning("⚠️ 선호도 설정을 먼저 저장해주세요.")
            else:
                if update_teacher_ready_status(vacation.id, user_id, True):
                    st.success("✅ 설정이 완료되었습니다! 관리자가 최적화를 실행할 때까지 기다려주세요.")
                    st.rerun()
                else:
                    st.error("❌ 설정 완료 처리 중 오류가 발생했습니다.")
