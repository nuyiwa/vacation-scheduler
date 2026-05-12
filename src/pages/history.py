"""
이력 페이지
- 모든 방학 기록 조회
- 교사별 누적 통계
- 이전 방학과의 포인트 차이 보정 정보
"""

from datetime import date, timedelta
from typing import List, Optional
import streamlit as st
import pandas as pd

from src.config.settings import (
    Season, SEASON_NAMES, VacationStatus, VACATION_POINTS, SlotType
)
from src.db.models import (
    Vacation, VacationTeacher, Schedule, VacationRequest
)
from src.db.queries import (
    get_vacations, get_vacation,
    get_vacation_teachers, get_schedules, get_vacation_requests,
    get_vacation_stats
)
from src.ui.calendar import render_calendar_page


# ============================================================
# 이력 페이지 메인
# ============================================================
def render_history_page(mobile: bool = False):
    """이력 페이지 메인 렌더링"""

    if mobile:
        st.markdown("### 📚 이력")
    else:
        st.markdown("# 📚 방학 이력")
    
    # ============================================================
    # 모든 방학 목록
    # ============================================================
    vacations = get_vacations()
    
    if not vacations:
        st.info("📭 아직 저장된 방학 기록이 없습니다.")
        return
    
    # ============================================================
    # 전체 통계 요약
    # ============================================================
    st.markdown("## 📊 전체 통계")
    
    total_vacations = len(vacations)
    confirmed_vacations = len([v for v in vacations if v.status == "confirmed"])
    total_schedules = sum(len(get_schedules(v.id)) for v in vacations)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📅 총 방학", total_vacations)
    with col2:
        st.metric("✅ 확정 완료", confirmed_vacations)
    with col3:
        st.metric("📋 총 배정", total_schedules)
    
    # ============================================================
    # 방학별 상세
    # ============================================================
    st.markdown("---")
    st.markdown("## 📋 방학별 상세")
    
    # 방학 선택
    vacation_options = {v.title: v for v in reversed(vacations)}
    selected_title = st.selectbox(
        "방학 선택",
        list(vacation_options.keys()),
        key="history_vacation_select"
    )
    selected_vacation = vacation_options[selected_title]
    
    tab1, tab2, tab3 = st.tabs([
        "📅 스케줄 보기",
        "👨‍🏫 교사별 통계",
        "📊 포인트 분석"
    ])
    
    with tab1:
        _render_vacation_schedule(selected_vacation)
    
    with tab2:
        _render_teacher_stats(selected_vacation)
    
    with tab3:
        _render_point_analysis(selected_vacation)


# ============================================================
# 방학 스케줄 보기
# ============================================================
def _render_vacation_schedule(vacation: Vacation):
    """선택한 방학의 전체 스케줄을 표시"""
    
    st.markdown(f"## 📅 {vacation.title} 스케줄")
    
    status_display = {
        "planning": "📝 생성됨",
        "input": "✏️ 교사 입력 중",
        "optimized": "⚡ 최적화 완료",
        "confirmed": "✅ 승인됨",
        "completed": "🏁 종료"
    }.get(vacation.status, vacation.status)
    st.markdown(f"""
    - **기간:** {vacation.start_date} ~ {vacation.end_date}
    - **상태:** {status_display}
    """)
    
    # 전체 스케줄 조회
    schedules = get_schedules(vacation.id)
    
    if not schedules:
        st.info("📭 이 방학의 스케줄이 없습니다.")
        return
    
    # ============================================================
    # 날짜별/슬롯별 요약
    # ============================================================
    st.markdown("### 📊 날짜별 배정 현황")
    
    # 데이터프레임 생성
    date_summary = {}
    for s in schedules:
        if s.date not in date_summary:
            date_summary[s.date] = {
                "AM_Childcare": [], "PM_Childcare": [],
                "AM_Admin": [], "PM_Admin": []
            }
        
        slot_key = s.slot_type
        if slot_key in date_summary[s.date]:
            date_summary[s.date][slot_key].append(s.teacher_id)
    
    summary_data = []
    for d in sorted(date_summary.keys()):
        ds = date_summary[d]
        summary_data.append({
            "날짜": d.strftime("%m/%d(%a)"),
            "오전돌봄": len(ds["AM_Childcare"]),
            "오후돌봄": len(ds["PM_Childcare"]),
            "오전행정": len(ds["AM_Admin"]),
            "오후행정": len(ds["PM_Admin"]),
            "합계": sum(len(v) for v in ds.values()),
        })
    
    if summary_data:
        df = pd.DataFrame(summary_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # ============================================================
    # 교사별 스케줄 표
    # ============================================================
    st.markdown("### 👨‍🏫 교사별 스케줄")
    
    teachers = get_vacation_teachers(vacation.id)
    
    # 교사별 스케줄 집계
    teacher_schedules = {}
    for t in teachers:
        tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
        t_name = t.get("teacher_name", "Unknown") if isinstance(t, dict) else "Unknown"

        t_schedules = [s for s in schedules if s.teacher_id == tid]
        teacher_schedules[tid] = {
            "name": t_name,
            "schedules": t_schedules,
            "care_count": len([s for s in t_schedules if "Childcare" in s.slot_type]),
            "admin_count": len([s for s in t_schedules if "Admin" in s.slot_type]),
            "total": len(t_schedules),
        }
    
    # 교사별 통계 테이블
    teacher_data = []
    for tid, ts in teacher_schedules.items():
        teacher_data.append({
            "교사": ts["name"],
            "총 배정": ts["total"],
            "돌봄": ts["care_count"],
            "행정": ts["admin_count"],
        })
    
    if teacher_data:
        df = pd.DataFrame(teacher_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # ============================================================
    # 캘린더로 보기
    # ============================================================
    with st.expander("📅 캘린더로 보기", expanded=False):
        # 모든 교사의 스케줄을 캘린더로 표시
        user_id = st.session_state.get("user_id", "")
        render_calendar_page(vacation, user_id)


# ============================================================
# 교사별 통계
# ============================================================
def _render_teacher_stats(vacation: Vacation):
    """교사별 상세 통계"""
    
    st.markdown(f"## 👨‍🏫 교사별 통계 - {vacation.title}")
    
    schedules = get_schedules(vacation.id)
    teachers = get_vacation_teachers(vacation.id)
    vacation_stats = get_vacation_stats(vacation.id)
    
    if not teachers:
        st.info("📭 배정된 교사가 없습니다.")
        return
    
    # vacation_stats를 teacher_id 기준 맵으로 변환
    stats_map = {}
    for vs in vacation_stats:
        tid = vs.get("teacher_id") if isinstance(vs, dict) else vs.teacher_id
        stats_map[tid] = vs
    
    # 교사별 상세 통계
    stats_data = []
    for t in teachers:
        tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
        t_name = t.get("teacher_name", "Unknown") if isinstance(t, dict) else "Unknown"
        t_care = t.get("care_points", 0) if isinstance(t, dict) else t.care_points
        t_admin = t.get("admin_points", 0) if isinstance(t, dict) else t.admin_points
        t_vacation = t.get("vacation_points", 0) if isinstance(t, dict) else t.vacation_points
        t_carry = t.get("carry_over_points", 0) if isinstance(t, dict) else t.carry_over_points
        t_total_points = t_care + t_admin + t_vacation

        t_schedules = [s for s in schedules if s.teacher_id == tid]

        # 휴가 신청
        t_vacations = get_vacation_requests(tid, vacation.id)
        vacation_points = sum(
            VACATION_POINTS.get(v.request_type if hasattr(v, 'request_type') else v.get("request_type", ""), 0)
            for v in t_vacations
        )
        
        # vacation_stats에서 실제 저장된 통계 정보 가져오기
        vs = stats_map.get(tid)
        stat_care_count = vs.get("total_care_count", 0) if vs else 0
        stat_admin_count = vs.get("total_admin_count", 0) if vs else 0
        stat_work_count = vs.get("total_work_count", 0) if vs else 0
        
        stats_data.append({
            "교사": t_name,
            "총 포인트": t_total_points,
            "돌봄 포인트": t_care,
            "행정 포인트": t_admin,
            "휴가 포인트": t_vacation,
            "실제 배정": len(t_schedules),
            "달성률": f"{len(t_schedules) / t_total_points * 100:.1f}%" if t_total_points > 0 else "N/A",
            "돌봄": len([s for s in t_schedules if "Childcare" in s.slot_type]),
            "행정": len([s for s in t_schedules if "Admin" in s.slot_type]),
            "신청 휴가 포인트": vacation_points,
            "이월 포인트": t_carry,
        })
    
    if stats_data:
        df = pd.DataFrame(stats_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 차트
        st.markdown("### 📊 교사별 배정 차트")
        
        chart_data = pd.DataFrame(stats_data)
        chart_data = chart_data.set_index("교사")
        
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(chart_data[["돌봄", "행정"]])
        with col2:
            st.bar_chart(chart_data[["총 포인트", "실제 배정"]])
    
    # 초기화 상태 표시
    if not schedules and not vacation_stats:
        st.info("📭 이 방학은 배정이 초기화된 상태입니다. (스케줄/통계 없음)")
    
    # ============================================================
    # 슬롯 타입별 분포
    # ============================================================
    st.markdown("### 📊 슬롯 타입별 분포")
    
    slot_counts = {
        "오전돌봄": len([s for s in schedules if s.slot_type == "AM_Childcare"]),
        "오후돌봄": len([s for s in schedules if s.slot_type == "PM_Childcare"]),
        "오전행정": len([s for s in schedules if s.slot_type == "AM_Admin"]),
        "오후행정": len([s for s in schedules if s.slot_type == "PM_Admin"]),
    }
    
    slot_df = pd.DataFrame({
        "슬롯": list(slot_counts.keys()),
        "횟수": list(slot_counts.values()),
    })
    
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(slot_df, use_container_width=True, hide_index=True)
    with col2:
        st.bar_chart(slot_df.set_index("슬롯"))


# ============================================================
# 포인트 분석
# ============================================================
def _render_point_analysis(vacation: Vacation):
    """휴가 포인트 및 이월 분석"""
    
    st.markdown(f"## 📊 포인트 분석 - {vacation.title}")
    
    st.markdown("""
    ### 포인트 시스템
    - **오전휴가**: 1포인트
    - **오후휴가**: 1포인트
    - **종일휴가**: 2포인트
    - 배정되지 않은 슬롯은 자동으로 휴가 처리
    - 이전 방학에서 미사용 포인트는 이월 가능
    """)
    
    schedules = get_schedules(vacation.id)
    teachers = get_vacation_teachers(vacation.id)
    
    if not teachers:
        st.info("📭 데이터가 없습니다.")
        return
    
    # 교사별 포인트 분석
    point_data = []
    for t in teachers:
        tid = t.get("teacher_id") if isinstance(t, dict) else t.teacher_id
        t_name = t.get("teacher_name", "Unknown") if isinstance(t, dict) else "Unknown"
        t_care = t.get("care_points", 0) if isinstance(t, dict) else t.care_points
        t_admin = t.get("admin_points", 0) if isinstance(t, dict) else t.admin_points
        t_vacation = t.get("vacation_points", 0) if isinstance(t, dict) else t.vacation_points
        t_carry = t.get("carry_over_points", 0) if isinstance(t, dict) else t.carry_over_points
        t_total_points = t_care + t_admin + t_vacation
        
        t_schedules = [s for s in schedules if s.teacher_id == tid]
        t_vacations = get_vacation_requests(tid, vacation.id)
        
        # 휴가 포인트 계산
        vacation_points = sum(
            VACATION_POINTS.get(v.request_type if hasattr(v, 'request_type') else v.get("request_type", ""), 0)
            for v in t_vacations
        )
        
        # 배정되지 않은 슬롯 = 자동 휴가
        # (총 포인트 - 실제 배정) = 미배정 슬롯
        unassigned = max(0, t_total_points - len(t_schedules))
        
        point_data.append({
            "교사": t_name,
            "총 포인트": t_total_points,
            "돌봄 포인트": t_care,
            "행정 포인트": t_admin,
            "휴가 포인트": t_vacation,
            "실제 배정": len(t_schedules),
            "미배정": unassigned,
            "신청 휴가 포인트": vacation_points,
            "이월 포인트": t_carry,
            "총 휴가 포인트": vacation_points + unassigned + t_carry,
        })
    
    if point_data:
        df = pd.DataFrame(point_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 포인트 분포 차트
        st.markdown("### 📊 포인트 분포")
        
        chart_df = pd.DataFrame(point_data).set_index("교사")
        st.bar_chart(chart_df[["신청 휴가 포인트", "미배정", "이월 포인트"]])
        
        # 공평성 분석
        st.markdown("### ⚖️ 공평성 분석")
        
        total_points = [d["총 휴가 포인트"] for d in point_data]
        if total_points:
            avg_points = sum(total_points) / len(total_points)
            max_points = max(total_points)
            min_points = min(total_points)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("평균 포인트", f"{avg_points:.1f}")
            with col2:
                st.metric("최대 포인트", max_points)
            with col3:
                st.metric("최소 포인트", min_points)
            
            # 표준편차
            variance = sum((p - avg_points) ** 2 for p in total_points) / len(total_points)
            std_dev = variance ** 0.5
            st.metric("표준편차", f"{std_dev:.2f}", 
                     delta="낮을수록 공평" if std_dev < 2 else "개선 필요",
                     delta_color="inverse" if std_dev < 2 else "off")
    
    # ============================================================
    # 이전 방학과 비교
    # ============================================================
    st.markdown("---")
    st.markdown("### 🔄 이전 방학과 비교")
    
    all_vacations = get_vacations()
    vacation_idx = next(
        (i for i, v in enumerate(all_vacations) if v.id == vacation.id),
        -1
    )
    
    if vacation_idx > 0:
        prev_vacation = all_vacations[vacation_idx - 1]
        st.markdown(f"**이전 방학:** {prev_vacation.title}")
        
        prev_schedules = get_schedules(prev_vacation.id)
        prev_teachers = get_vacation_teachers(prev_vacation.id)
        
        # 간단한 비교
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                f"{prev_vacation.title} 총 배정",
                len(prev_schedules)
            )
        with col2:
            st.metric(
                f"{vacation.title} 총 배정",
                len(schedules),
                delta=len(schedules) - len(prev_schedules)
            )
    else:
        st.info("📭 이전 방학이 없습니다.")