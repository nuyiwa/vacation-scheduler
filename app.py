"""
# 🏫 방학 스케줄링 시스템 (Vacation Scheduling System)
# 
# 유치원/초등 방학 스케줄링을 위한 Streamlit 웹 애플리케이션
# - Supabase: 데이터베이스, 인증, Realtime
# - PuLP: Integer Linear Programming 최적화
# - Streamlit: 웹 UI
#
# 실행 방법:
#   streamlit run app.py
#
# 개발 환경:
#   Python 3.11+, Visual Studio Code
#
# 데모 모드:
#   Supabase 설정 없이도 로컬 메모리로 실행 가능합니다.
#   .env 파일에 DEMO_MODE=true 로 설정하거나, SUPABASE_URL이 없으면 자동 데모 모드
#   데모 계정:
#     관리자: admin@test.com / admin1234
#     교사1:  teacher1@test.com / teacher1234
#     교사2:  teacher2@test.com / teacher1234
#     교사3:  teacher3@test.com / teacher1234
"""

import streamlit as st
import sys

from pathlib import Path

# ============================================================
# 프로젝트 루트를 Python 경로에 추가
# ============================================================
sys.path.insert(0, str(Path(__file__).parent))

# ============================================================
# 페이지 설정 (가장 먼저 실행되어야 함)
# ============================================================
st.set_page_config(
    page_title="🏫 방학 스케줄링 시스템",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-org/vacation-scheduler',
        'Report a bug': 'https://github.com/your-org/vacation-scheduler/issues',
        'About': '# 🏫 방학 스케줄링 시스템\n\n유치원/초등 방학 스케줄링을 위한 최적화 시스템입니다.'
    }
)

# ============================================================
# CSS 스타일 (모바일 대응, PWA 스타일)
# ============================================================
st.markdown("""
<link rel="manifest" href="/app/static/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="방학스케줄">
<meta name="theme-color" content="#4A90D9">
<meta name="mobile-web-app-capable" content="yes">
<style>
    /* ===== Streamlit 기본 UI 완전 제거 ===== */
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stSidebar"] {display: none !important;}

    /* ===== 전체 배경 ===== */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #F0F4F8 !important;
    }
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 1100px !important;
    }

    /* ===== 버튼 ===== */
    .stButton > button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        transition: transform 0.15s, box-shadow 0.15s !important;
        border: none !important;
        padding: 0.6rem 1.2rem !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4A90D9, #2c72b8) !important;
        box-shadow: 0 4px 14px rgba(74,144,217,0.4) !important;
        color: white !important;
    }
    .stButton > button[kind="secondary"] {
        background: white !important;
        border: 1.5px solid #e0e8f0 !important;
        color: #2C3E50 !important;
    }
    .stButton > button:active {
        transform: scale(0.97) !important;
    }

    /* ===== 입력 필드 ===== */
    [data-testid="stTextInput"] input {
        border-radius: 10px !important;
        border: 1.5px solid #e0e8f0 !important;
        font-size: 1rem !important;
        padding: 0.6rem 0.9rem !important;
        background: white !important;
    }
    [data-testid="stTextInput"] input:focus {
        border-color: #4A90D9 !important;
        box-shadow: 0 0 0 3px rgba(74,144,217,0.15) !important;
    }

    /* ===== 탭 ===== */
    .stTabs [data-baseweb="tab-list"] {
        background: #e8edf2 !important;
        border-radius: 12px !important;
        padding: 4px !important;
        gap: 4px !important;
        border-bottom: none !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 9px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        color: #666 !important;
        padding: 0.5rem 1.2rem !important;
    }
    .stTabs [aria-selected="true"] {
        background: white !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.12) !important;
        color: #2C3E50 !important;
    }
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 1rem !important;
    }

    /* ===== 사이드바 ===== */
    [data-testid="stSidebar"] {
        background: white !important;
        border-right: 1px solid #e8ecf0 !important;
    }
    [data-testid="stSidebar"] .block-container {
        padding: 1.5rem 1rem !important;
    }

    /* ===== 카드 ===== */
    .app-card {
        background: white;
        border-radius: 16px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 6px rgba(0,0,0,0.07);
    }

    /* ===== 사이드바 유저 정보 ===== */
    .sidebar-user-info {
        background: linear-gradient(135deg, #EBF5FB, #D6EAF8);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    /* ===== 메트릭 카드 ===== */
    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 1.25rem;
        box-shadow: 0 1px 6px rgba(0,0,0,0.07);
        text-align: center;
    }

    /* ===== 슬롯 배지 ===== */
    .slot-badge {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 6px;
        font-size: 0.68rem;
        margin: 1px;
        color: white;
        font-weight: 600;
    }
    .slot-badge.care  { background: #4A90D9; }
    .slot-badge.admin { background: #27AE60; }
    .slot-badge.vacation { background: #95A5A6; }
    .slot-badge.flash { background: #F1C40F; color: #333; }

    /* ===== 캘린더 ===== */
    .calendar-container {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 3px;
        margin: 1rem 0;
    }
    .calendar-header {
        text-align: center;
        font-weight: 700;
        padding: 0.4rem 0;
        font-size: 0.72rem;
        color: #888;
    }
    .calendar-day {
        text-align: center;
        padding: 0.4rem 0.2rem;
        min-height: 64px;
        border: 1px solid #eef1f5;
        border-radius: 10px;
        background: white;
    }
    .calendar-day.weekend  { background: #fafbfc; }
    .calendar-day.holiday  { background: #fff5f5; }
    .calendar-day.today    { border: 2px solid #4A90D9; background: #EBF5FB; }
    .calendar-day-number {
        font-size: 0.75rem;
        font-weight: 600;
        color: #555;
        margin-bottom: 0.2rem;
    }

    /* ===== 데모 배너 ===== */
    .demo-banner {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 0.6rem 1rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 1rem;
        font-size: 0.85rem;
    }

    /* ===== 로딩 ===== */
    .stSpinner > div { border-color: #4A90D9 !important; }

    /* ===== 모바일 최적화 ===== */
    @media (max-width: 768px) {
        .block-container {
            padding: 0.75rem 0.75rem 2rem !important;
            max-width: 100% !important;
        }
        .stButton > button {
            padding: 0.4rem 0.6rem !important;
            font-size: 0.85rem !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .stTabs [data-baseweb="tab"] {
            white-space: nowrap;
        }
        [data-testid="stTextInput"] input {
            font-size: 16px !important;
        }
        [data-testid="stSidebar"] {
            display: none !important;
        }
        /* 컬럼이 좁을 때 줄바꿈 허용 (세로 강제 스택 제거) */
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        /* 상단 탭바 숨기고 하단 탭바만 */
        .topnav-desktop { display: none !important; }
        .bottomnav-mobile {
            display: flex !important;
            position: fixed;
            bottom: 0; left: 0; right: 0;
            background: white;
            border-top: 1px solid #e8ecf0;
            z-index: 9999;
            padding: 0.4rem 0;
            padding-bottom: env(safe-area-inset-bottom, 0.4rem);
            box-shadow: 0 -2px 10px rgba(0,0,0,0.07);
        }
    }
    @media (min-width: 769px) {
        .topnav-desktop { display: flex !important; }
        .bottomnav-mobile { display: none !important; }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 쿠키 매니저 (자동 로그인용)
# ============================================================
import extra_streamlit_components as stx
from datetime import datetime, timedelta

@st.cache_resource
def _get_cookie_manager():
    return stx.CookieManager(key="vac_cookie_mgr")

_cm = _get_cookie_manager()

# 쿠키에서 세션 복원
if not st.session_state.get("authenticated"):
    _uid = _cm.get("v_uid")
    if _uid:
        st.session_state.update({
            "authenticated": True,
            "user_id":    _uid,
            "user_email": _cm.get("v_ue") or "",
            "user_name":  _cm.get("v_un") or "",
            "user_role":  _cm.get("v_ur") or "teacher",
            "current_page": "home",
        })

# ============================================================
# 세션 상태 초기화
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_id" not in st.session_state:
    st.session_state["user_id"] = ""
if "user_email" not in st.session_state:
    st.session_state["user_email"] = ""
if "user_name" not in st.session_state:
    st.session_state["user_name"] = ""
if "user_role" not in st.session_state:
    st.session_state["user_role"] = ""
if "selected_vacation_id" not in st.session_state:
    st.session_state["selected_vacation_id"] = None
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "home"


# ============================================================
# 데모 모드 확인
# ============================================================
def is_demo_mode() -> bool:
    """현재 데모 모드인지 확인"""
    from src.config.supabase_client import is_demo_mode as check_demo
    return check_demo()


# ============================================================
# 인증 관련 함수 (데모 모드 지원)
# ============================================================
def check_authentication():
    """사용자 인증 상태 확인"""
    return st.session_state.get("authenticated", False)


def _to_email(username: str) -> str:
    """아이디를 Supabase용 이메일 형식으로 변환"""
    if "@" in username:
        return username
    return f"{username}@vacation.school"


def login_user(email: str, password: str) -> bool:
    """
    로그인 (데모 모드 지원)

    Args:
        email: 사용자 이메일 또는 아이디
        password: 비밀번호

    Returns:
        bool: 로그인 성공 여부
    """
    try:
        from src.config.supabase_client import sign_in

        response = sign_in(_to_email(email), password)
        
        if response and "user" in response and not response.get("error"):
            user = response["user"]
            st.session_state["authenticated"] = True
            st.session_state["user_id"] = user["id"]
            st.session_state["user_email"] = user["email"]

            from src.config.supabase_client import get_user_profile, get_service_client
            profile = get_user_profile(user["id"])

            # profile이 없거나 role이 틀리면 upsert로 동기화
            meta = user.get("user_metadata") or {}
            meta_role = meta.get("role", "teacher")
            if not profile or (meta_role == "admin" and profile.get("role") != "admin"):
                username = user["email"].replace("@vacation.school", "")
                svc = get_service_client()
                if svc:
                    svc.table("profiles").upsert({
                        "id": user["id"],
                        "email": user["email"],
                        "name": meta.get("name", username),
                        "role": meta_role,
                    }).execute()
                profile = get_user_profile(user["id"])

            if profile:
                st.session_state["user_name"] = profile.get("name", email)
                st.session_state["user_role"] = profile.get("role", "teacher")

            # 쿠키에 저장 (30일 유지)
            _exp = datetime.now() + timedelta(days=30)
            _cm.set("v_uid", st.session_state["user_id"],    expires_at=_exp)
            _cm.set("v_ue",  st.session_state["user_email"], expires_at=_exp)
            _cm.set("v_un",  st.session_state["user_name"],  expires_at=_exp)
            _cm.set("v_ur",  st.session_state["user_role"],  expires_at=_exp)
            return True
        else:
            error_msg = response.get("error", "로그인에 실패했습니다.")
            st.error(f"❌ {error_msg}")
            return False
    except Exception as e:
        st.error(f"❌ 로그인 실패: {str(e)}")
        return False


def logout_user():
    """로그아웃"""
    from src.config.supabase_client import sign_out
    sign_out()

    # 쿠키 삭제
    for _k in ["v_uid", "v_ue", "v_un", "v_ur"]:
        _cm.delete(_k)

    for key in ["authenticated", "user_id", "user_email", "user_name", "user_role"]:
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()


def register_user(email: str, password: str, name: str, role: str = "teacher") -> bool:
    """
    새 사용자 등록 (데모 모드 지원)

    Args:
        email: 사용자 이메일 또는 아이디
        password: 비밀번호
        name: 사용자 이름
        role: 역할 (admin/teacher)

    Returns:
        bool: 등록 성공 여부
    """
    try:
        from src.config.supabase_client import sign_up

        response = sign_up(_to_email(email), password, name, role)
        
        if response and "user" in response and not response.get("error"):
            return True
        else:
            error_msg = response.get("error", "회원가입에 실패했습니다.")
            st.error(f"❌ {error_msg}")
            return False
    except Exception as e:
        st.error(f"❌ 회원가입 실패: {str(e)}")
        return False


# ============================================================
# 로그인 페이지
# ============================================================
def render_login_page():
    """로그인 페이지 렌더링"""

    st.markdown("""
    <div style="text-align:center; padding: 2.5rem 0 1.5rem;">
        <div style="font-size:3.5rem; margin-bottom:0.5rem;">🏫</div>
        <div style="font-size:1.6rem; font-weight:800; color:#1a2e45; letter-spacing:-0.5px;">방학 스케줄러</div>
        <div style="font-size:0.9rem; color:#7f8c9a; margin-top:0.3rem;">교사 방학 스케줄 관리 시스템</div>
    </div>
    """, unsafe_allow_html=True)

    if is_demo_mode():
        st.markdown("""
        <div class="demo-banner">
            🧪 <b>데모 모드</b> — Supabase 없이 실행 중<br>
            <small>관리자: admin@test.com / admin1234</small>
        </div>
        """, unsafe_allow_html=True)

    _, col2, _ = st.columns([1, 2, 1])

    with col2:
        if is_demo_mode():
            tab_login, = st.tabs(["🔐 로그인"])
        else:
            tab_login, tab_signup = st.tabs(["🔐 로그인", "📝 회원가입"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("아이디", placeholder="아이디 입력")
                password = st.text_input("비밀번호", type="password", placeholder="••••••••")

                if st.form_submit_button("로그인", use_container_width=True, type="primary"):
                    if username and password:
                        if login_user(username, password):
                            st.rerun()
                    else:
                        st.warning("⚠️ 아이디와 비밀번호를 입력해주세요.")

        if not is_demo_mode():
            with tab_signup:
                with st.form("signup_form"):
                    su_username = st.text_input("아이디", placeholder="영문/숫자 조합")
                    su_name = st.text_input("이름", placeholder="홍길동")
                    su_password = st.text_input("비밀번호", type="password", placeholder="6자 이상")
                    su_password2 = st.text_input("비밀번호 확인", type="password", placeholder="••••••••")
                    su_role = st.selectbox("역할", ["teacher", "admin"], format_func=lambda x: "👨‍🏫 교사" if x == "teacher" else "👑 관리자")

                    if st.form_submit_button("회원가입", use_container_width=True, type="primary"):
                        if not (su_username and su_name and su_password):
                            st.warning("⚠️ 모든 항목을 입력해주세요.")
                        elif su_password != su_password2:
                            st.error("❌ 비밀번호가 일치하지 않습니다.")
                        elif len(su_password) < 6:
                            st.error("❌ 비밀번호는 6자 이상이어야 합니다.")
                        else:
                            if register_user(su_username, su_password, su_name, su_role):
                                st.success("✅ 회원가입 완료! 바로 로그인하세요.")

        # 데모 모드: 빠른 로그인 버튼
        if is_demo_mode():
            st.markdown("---")
            st.markdown("### 🚀 데모 모드 빠른 로그인")
            st.markdown("아래 버튼을 클릭하여 바로 로그인할 수 있습니다.")

            demo_col1, demo_col2 = st.columns(2)

            with demo_col1:
                if st.button("👑 관리자 로그인", use_container_width=True):
                    if login_user("admin@test.com", "admin1234"):
                        st.rerun()

            with demo_col2:
                if st.button("👨‍🏫 교사 로그인", use_container_width=True):
                    if login_user("teacher1@test.com", "teacher1234"):
                        st.rerun()

            st.markdown("""
            <small>
            <b>데모 계정 목록:</b><br>
            👑 관리자: admin@test.com / admin1234<br>
            👨‍🏫 이교사: teacher1@test.com / teacher1234<br>
            👨‍🏫 박교사: teacher2@test.com / teacher1234<br>
            👨‍🏫 최교사: teacher3@test.com / teacher1234
            </small>
            """, unsafe_allow_html=True)


# ============================================================
# 사이드바
# ============================================================
def render_sidebar():
    """사이드바 렌더링"""
    
    with st.sidebar:
        # 앱 로고 + 유저 정보
        role = st.session_state.get("user_role", "teacher")
        role_badge = "👑 관리자" if role == "admin" else "👨‍🏫 교사"
        st.markdown(f"""
        <div style="text-align:center; padding:0.5rem 0 1rem;">
            <div style="font-size:2rem;">🏫</div>
            <div style="font-weight:800; font-size:1rem; color:#1a2e45;">방학 스케줄러</div>
        </div>
        <div class="sidebar-user-info">
            <div style="font-weight:700; font-size:1rem;">{st.session_state.get('user_name', '사용자')}</div>
            <div style="font-size:0.78rem; color:#5a7a9a; margin-top:2px;">{role_badge}</div>
        </div>
        """, unsafe_allow_html=True)

        if is_demo_mode():
            st.markdown("""<div style="background:#e8f5e9;padding:0.4rem;border-radius:8px;text-align:center;font-size:0.78rem;margin-bottom:0.75rem;">🧪 데모 모드</div>""", unsafe_allow_html=True)

        st.markdown("---")

        # 메뉴 아이템
        menu_items = {"home": "🏠  홈", "history": "📚  이력"}
        if role == "admin":
            menu_items["admin"] = "🔧  관리자 설정"
        if role == "teacher":
            menu_items["teacher"] = "👨‍🏫  내 페이지"

        for page_key, page_label in menu_items.items():
            active = st.session_state["current_page"] == page_key
            if st.button(
                page_label,
                use_container_width=True,
                type="primary" if active else "secondary",
                key=f"nav_{page_key}"
            ):
                st.session_state["current_page"] = page_key
                st.rerun()

        st.markdown("---")
        if st.button("🚪  로그아웃", use_container_width=True):
            logout_user()

        mode_text = "🧪 데모" if is_demo_mode() else "☁️ Supabase"
        st.markdown(f"<div style='font-size:0.75rem;color:#aaa;text-align:center;margin-top:1rem;'>v1.0 · {mode_text}</div>", unsafe_allow_html=True)


# ============================================================
# 네비게이션
# ============================================================
def _nav_pages() -> list:
    role = st.session_state.get("user_role", "teacher")
    pages = [("🏠", "홈", "home"), ("📚", "이력", "history")]
    if role == "admin":
        pages.append(("🔧", "관리자", "admin"))
    else:
        pages.append(("👨‍🏫", "내 페이지", "teacher"))
    return pages


def render_topnav():
    """상단 내비게이션 — 라디오 버튼 한 줄"""
    current = st.session_state.get("current_page", "home")
    role = st.session_state.get("user_role", "teacher")

    page_map = {"🏠 홈": "home", "📚 이력": "history"}
    if role == "admin":
        page_map["🔧 관리자"] = "admin"
    else:
        page_map["👨‍🏫 내 페이지"] = "teacher"

    labels = list(page_map.keys())
    keys = list(page_map.values())
    current_idx = keys.index(current) if current in keys else 0

    selected = st.radio(
        "nav",
        labels,
        index=current_idx,
        horizontal=True,
        label_visibility="collapsed",
    )

    selected_page = page_map[selected]
    if selected_page != current:
        st.session_state["current_page"] = selected_page
        st.rerun()

    st.markdown("<hr style='margin:0.25rem 0 1rem;border:none;border-top:1px solid #e8ecf0;'>", unsafe_allow_html=True)


def render_bottomnav():
    """모바일 전용 하단 탭바"""
    current = st.session_state.get("current_page", "home")
    pages = _nav_pages()
    all_items = pages + [("🚪", "로그아웃", "__logout__")]

    # CSS fixed 하단 바 안에 버튼 배치
    st.markdown('<div class="bottomnav-mobile">', unsafe_allow_html=True)
    cols = st.columns(len(all_items))
    for i, (icon, label, page_key) in enumerate(all_items):
        with cols[i]:
            active = current == page_key
            btn_style = "primary" if active else "secondary"
            if st.button(
                f"{icon}\n{label}",
                key=f"bottomnav_{page_key}",
                use_container_width=True,
                type=btn_style,
            ):
                if page_key == "__logout__":
                    logout_user()
                else:
                    st.session_state["current_page"] = page_key
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# 메인 앱
# ============================================================
def main():
    """메인 애플리케이션"""
    
    # ============================================================
    # 인증 확인
    # ============================================================
    if not check_authentication():
        render_login_page()
        return
    
    # 상단 내비게이션 버튼 (모바일/PC 공통)
    render_topnav()

    # ============================================================
    # 페이지 라우팅
    # ============================================================
    current_page = st.session_state.get("current_page", "home")

    if current_page == "home":
        from src.ui.calendar import render_calendar_page
        from src.db.queries import get_vacations

        vacations = get_vacations()
        if vacations:
            active = [v for v in vacations if v.status in ["planning", "input", "optimized", "confirmed"]]
            selected = active[-1] if active else vacations[-1]
            render_calendar_page(
                selected,
                st.session_state.get("user_id", ""),
                show_teacher_filter=True,
            )
        else:
            st.info("📭 아직 생성된 방학이 없습니다. 관리자 설정에서 방학을 생성해주세요.")

    elif current_page == "admin":
        from src.pages.admin import render_admin_page
        render_admin_page()

    elif current_page == "teacher":
        from src.pages.teacher import render_teacher_page
        render_teacher_page()

    elif current_page == "history":
        from src.pages.history import render_history_page
        render_history_page()

    # 하단 로그아웃
    st.markdown("<hr style='margin:2rem 0 0.5rem;border:none;border-top:1px solid #e8ecf0;'>", unsafe_allow_html=True)
    if st.button("🚪 로그아웃", key="bottom_logout"):
        logout_user()


# ============================================================
# 앱 실행
# ============================================================
if __name__ == "__main__":
    main()