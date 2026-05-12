"""
Supabase 클라이언트 설정 모듈
- Supabase 클라이언트 초기화 및 관리
- 세션 관리 (로그인/로그아웃)
- 실시간 구독 설정
- 데모 모드 지원 (Supabase 없이도 실행 가능)
"""

import streamlit as st
from src.config.settings import SUPABASE_URL, SUPABASE_ANON_KEY, DEMO_MODE


# ============================================================
# 데모 모드 확인
# ============================================================
def is_demo_mode() -> bool:
    """
    현재 데모 모드인지 확인합니다.
    Supabase 설정이 없으면 자동으로 데모 모드로 전환됩니다.
    
    Returns:
        bool: 데모 모드 여부
    """
    return DEMO_MODE or not SUPABASE_URL or not SUPABASE_ANON_KEY


# ============================================================
# Supabase 클라이언트 생성 (싱글톤 패턴)
# ============================================================
@st.cache_resource
def get_supabase_client():
    """
    Supabase 클라이언트를 생성하거나 캐시된 인스턴스를 반환합니다.
    데모 모드에서는 None을 반환합니다.

    Returns:
        Client | None: 초기화된 Supabase 클라이언트 또는 None (데모 모드)
    """
    if is_demo_mode():
        return None

    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


@st.cache_resource
def get_service_client():
    """RLS를 우회하는 서비스 롤 클라이언트 (관리 작업용)"""
    from src.config.settings import SUPABASE_SERVICE_KEY as SVC_KEY
    if is_demo_mode() or not SVC_KEY:
        return None
    from supabase import create_client
    return create_client(SUPABASE_URL, SVC_KEY)


# ============================================================
# 데모 데이터 (Supabase 없이 테스트용)
# ============================================================
DEMO_USERS = {
    "admin@test.com": {
        "id": "demo-admin-001",
        "email": "admin@test.com",
        "password": "admin1234",
        "name": "김관리자",
        "role": "admin",
        "phone": "010-1234-5678",
        "is_active": True,
    },
    "teacher1@test.com": {
        "id": "demo-teacher-001",
        "email": "teacher1@test.com",
        "password": "teacher1234",
        "name": "이교사",
        "role": "teacher",
        "phone": "010-2345-6789",
        "is_active": True,
    },
    "teacher2@test.com": {
        "id": "demo-teacher-002",
        "email": "teacher2@test.com",
        "password": "teacher1234",
        "name": "박교사",
        "role": "teacher",
        "phone": "010-3456-7890",
        "is_active": True,
    },
    "teacher3@test.com": {
        "id": "demo-teacher-003",
        "email": "teacher3@test.com",
        "password": "teacher1234",
        "name": "최교사",
        "role": "teacher",
        "phone": "010-4567-8901",
        "is_active": True,
    },
}

DEMO_VACATIONS = [
    {
        "id": "demo-vacation-001",
        "title": "2026 겨울방학",
        "year": 2026,
        "season": "winter",
        "start_date": "2026-01-05",
        "end_date": "2026-02-28",
        "status": "planning",
        "admin_id": "demo-admin-001",
        "notes": "테스트 방학입니다",
    }
]

DEMO_TEACHERS_IN_VACATION = [
    {"id": "demo-vt-001", "vacation_id": "demo-vacation-001", "teacher_id": "demo-teacher-001", "target_count": 10, "carry_over_points": 0, "vacation_point_budget": 10, "admin_target_count": 3},
    {"id": "demo-vt-002", "vacation_id": "demo-vacation-001", "teacher_id": "demo-teacher-002", "target_count": 10, "carry_over_points": 0, "vacation_point_budget": 10, "admin_target_count": 3},
    {"id": "demo-vt-003", "vacation_id": "demo-vacation-001", "teacher_id": "demo-teacher-003", "target_count": 10, "carry_over_points": 0, "vacation_point_budget": 10, "admin_target_count": 3},
]


# ============================================================
# 인증 관련 함수 (데모 모드 지원)
# ============================================================
def sign_up(email: str, password: str, name: str, role: str = "teacher") -> dict:
    """
    새 사용자 회원가입
    데모 모드에서는 로컬 딕셔너리에 저장합니다.
    
    Args:
        email: 이메일 주소
        password: 비밀번호
        name: 사용자 이름
        role: 역할 (admin/teacher, 기본값: teacher)
    
    Returns:
        dict: 회원가입 결과
    """
    if is_demo_mode():
        # 데모 모드: 세션 상태에 사용자 추가
        if email in DEMO_USERS:
            return {"error": "이미 존재하는 이메일입니다."}
        
        new_id = f"demo-{email.split('@')[0]}-{len(DEMO_USERS) + 1}"
        DEMO_USERS[email] = {
            "id": new_id,
            "email": email,
            "password": password,
            "name": name,
            "role": role,
            "phone": "",
            "is_active": True,
        }
        return {
            "user": {
                "id": new_id,
                "email": email,
                "user_metadata": {"name": name, "role": role},
            },
            "session": {"access_token": "demo-token"},
        }
    
    supabase = get_supabase_client()
    response = supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "data": {
                "name": name,
                "role": role,
            }
        }
    })
    if hasattr(response, "user") and response.user:
        return {
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "user_metadata": response.user.user_metadata or {},
            },
            "session": {"access_token": response.session.access_token if response.session else None},
        }
    return {"error": "회원가입에 실패했습니다."}


def sign_in(email: str, password: str) -> dict:
    """
    이메일/비밀번호로 로그인
    데모 모드에서는 로컬 딕셔너리로 인증합니다.
    
    Args:
        email: 이메일 주소
        password: 비밀번호
    
    Returns:
        dict: 로그인 결과
    """
    if is_demo_mode():
        user = DEMO_USERS.get(email)
        if not user:
            return {"error": "존재하지 않는 이메일입니다."}
        if user["password"] != password:
            return {"error": "비밀번호가 일치하지 않습니다."}
        
        return {
            "user": {
                "id": user["id"],
                "email": user["email"],
                "user_metadata": {"name": user["name"], "role": user["role"]},
            },
            "session": {"access_token": "demo-token"},
        }
    
    supabase = get_supabase_client()
    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password,
    })
    if hasattr(response, "user") and response.user:
        return {
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "user_metadata": response.user.user_metadata or {},
            },
            "session": {"access_token": response.session.access_token if response.session else None},
        }
    return {"error": "이메일 또는 비밀번호가 올바르지 않습니다."}


def sign_out():
    """로그아웃 — 세션 상태만 초기화하고 rerun은 호출자가 담당"""
    if not is_demo_mode():
        supabase = get_supabase_client()
        supabase.auth.sign_out()

    # 모든 인증 관련 세션 키 초기화 (app.py 포함)
    clear_keys = [
        "user", "session", "user_profile", "page",
        "authenticated", "user_id", "user_email", "user_name", "user_role",
    ]
    for key in clear_keys:
        if key in st.session_state:
            del st.session_state[key]


def get_current_session() -> dict | None:
    """
    현재 로그인된 사용자의 세션 정보를 반환합니다.
    
    Returns:
        dict | None: 세션 정보 또는 None
    """
    if is_demo_mode():
        return st.session_state.get("session")
    
    supabase = get_supabase_client()
    try:
        session = supabase.auth.get_session()
        return session
    except Exception:
        return None


def get_current_user() -> dict | None:
    """
    현재 로그인된 사용자 정보를 반환합니다.
    
    Returns:
        dict | None: 사용자 정보 또는 None
    """
    if is_demo_mode():
        return st.session_state.get("user")
    
    session = get_current_session()
    if session:
        return session.user
    return None


# ============================================================
# 프로필 관련 함수 (데모 모드 지원)
# ============================================================
def get_user_profile(user_id: str) -> dict | None:
    """
    사용자 ID로 프로필 정보를 조회합니다.
    데모 모드에서는 로컬 데이터를 반환합니다.
    
    Args:
        user_id: 사용자 UUID
    
    Returns:
        dict | None: 프로필 정보 또는 None
    """
    if is_demo_mode():
        for user in DEMO_USERS.values():
            if user["id"] == user_id:
                return {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user["name"],
                    "role": user["role"],
                    "phone": user.get("phone", ""),
                    "is_active": user.get("is_active", True),
                }
        return None
    
    client = get_service_client() or get_supabase_client()
    if not client:
        return None
    response = client.table("profiles")\
        .select("*")\
        .eq("id", user_id)\
        .maybe_single()\
        .execute()

    if response and response.data:
        return response.data
    return None


def is_admin(user_id: str) -> bool:
    """
    사용자가 관리자 권한을 가지고 있는지 확인합니다.
    
    Args:
        user_id: 사용자 UUID
    
    Returns:
        bool: 관리자 여부
    """
    profile = get_user_profile(user_id)
    if profile:
        return profile.get("role") == "admin"
    return False


# ============================================================
# DB 쿼리 헬퍼 (데이터 조회/저장)
# ============================================================
def query_table(table_name: str, select: str = "*", eq: dict = None, order: str = None, limit: int = None) -> list:
    """
    Supabase 테이블 조회 (데모 모드 지원)
    
    Args:
        table_name: 테이블명
        select: 선택할 컬럼
        eq: 필터 조건 딕셔너리
        order: 정렬 컬럼
        limit: 최대 개수
    
    Returns:
        list: 조회 결과 리스트
    """
    if is_demo_mode():
        return _demo_query(table_name, eq)
    
    supabase = get_supabase_client()
    query = supabase.table(table_name).select(select)
    
    if eq:
        for key, value in eq.items():
            query = query.eq(key, value)
    
    if order:
        query = query.order(order)
    
    if limit:
        query = query.limit(limit)
    
    response = query.execute()
    return response.data if response.data else []


def insert_record(table_name: str, data: dict) -> dict | None:
    """
    Supabase 테이블에 레코드 삽입 (데모 모드 지원)
    
    Args:
        table_name: 테이블명
        data: 삽입할 데이터
    
    Returns:
        dict | None: 삽입된 레코드 또는 None
    """
    if is_demo_mode():
        return _demo_insert(table_name, data)
    
    supabase = get_supabase_client()
    response = supabase.table(table_name).insert(data).execute()
    return response.data[0] if response.data else None


def upsert_record(table_name: str, data: dict, eq: dict = None) -> dict | None:
    """
    Supabase 테이블에 UPSERT (있으면 업데이트, 없으면 삽입)
    데모 모드 지원
    
    Args:
        table_name: 테이블명
        data: 저장할 데이터
        eq: 업데이트 조건 (데모 모드에서 사용)
    
    Returns:
        dict | None: 저장된 레코드 또는 None
    """
    if is_demo_mode():
        # 데모 모드: 조회 후 있으면 업데이트, 없으면 삽입
        if eq:
            existing = _demo_query(table_name, eq)
            if existing:
                return _demo_update(table_name, data, eq)
        return _demo_insert(table_name, data)
    
    supabase = get_supabase_client()
    response = supabase.table(table_name).upsert(data).execute()
    return response.data[0] if response.data else None


def update_record(table_name: str, data: dict, eq: dict) -> dict | None:
    """
    Supabase 테이블 레코드 업데이트 (데모 모드 지원)
    
    Args:
        table_name: 테이블명
        data: 업데이트할 데이터
        eq: 필터 조건
    
    Returns:
        dict | None: 업데이트된 레코드 또는 None
    """
    if is_demo_mode():
        return _demo_update(table_name, data, eq)
    
    supabase = get_supabase_client()
    query = supabase.table(table_name).update(data)
    
    for key, value in eq.items():
        query = query.eq(key, value)
    
    response = query.execute()
    return response.data[0] if response.data else None


def delete_record(table_name: str, eq: dict) -> bool:
    """
    Supabase 테이블 레코드 삭제 (데모 모드 지원)
    
    Args:
        table_name: 테이블명
        eq: 필터 조건
    
    Returns:
        bool: 삭제 성공 여부
    """
    if is_demo_mode():
        return _demo_delete(table_name, eq)
    
    supabase = get_supabase_client()
    query = supabase.table(table_name).delete()
    
    for key, value in eq.items():
        query = query.eq(key, value)
    
    response = query.execute()
    return len(response.data) > 0 if response.data else False


# ============================================================
# 데모 모드 내부 데이터 저장소
# ============================================================
if "demo_db" not in st.session_state:
    # profiles 테이블: DEMO_USERS에서 자동 생성
    _demo_profiles = [
        {
            "id": u["id"],
            "email": u["email"],
            "name": u["name"],
            "role": u["role"],
            "phone": u.get("phone", ""),
            "is_active": u.get("is_active", True),
        }
        for u in DEMO_USERS.values()
    ]
    st.session_state.demo_db = {
        "vacations": DEMO_VACATIONS.copy(),
        "vacation_teachers": DEMO_TEACHERS_IN_VACATION.copy(),
        "profiles": _demo_profiles,
        "care_requirements": [],
        "flash_teachers": [],
        "excluded_dates": [],
        "meeting_weeks": [],
        "meeting_teams": [],
        "daily_meeting_assignments": [],
        "teacher_preferences": [],
        "vacation_requests": [],
        "admin_requests": [],
        "schedules": [],
        "vacation_stats": [],
    }


def _demo_query(table_name: str, eq: dict = None) -> list:
    """데모 모드: 로컬 데이터 조회 (인덱스 최적화)"""
    db = st.session_state.demo_db
    data = db.get(table_name, [])
    
    if not eq:
        return data
    
    # 단일 키 조건이면 인덱스 활용
    if len(eq) == 1:
        key, value = next(iter(eq.items()))
        # 인덱스가 있으면 사용
        index_key = f"_idx_{table_name}_{key}"
        if index_key in db:
            return db[index_key].get(value, [])
        # 인덱스가 없으면 생성
        idx = {}
        for item in data:
            v = item.get(key)
            if v is not None:
                idx.setdefault(v, []).append(item)
        db[index_key] = idx
        return idx.get(value, [])
    
    # 다중 조건: 첫 번째 키로 인덱스 조회 후 필터링
    first_key, first_value = next(iter(eq.items()))
    index_key = f"_idx_{table_name}_{first_key}"
    if index_key in db:
        candidates = db[index_key].get(first_value, [])
    else:
        candidates = [item for item in data if item.get(first_key) == first_value]
    
    if not candidates:
        return []
    
    result = []
    for item in candidates:
        match = True
        for key, value in eq.items():
            if item.get(key) != value:
                match = False
                break
        if match:
            result.append(item)
    return result


def _demo_insert(table_name: str, data: dict) -> dict:
    """데모 모드: 로컬 데이터 삽입"""
    import uuid
    db = st.session_state.demo_db
    
    if table_name not in db:
        db[table_name] = []
    
    record = data.copy()
    if "id" not in record:
        record["id"] = f"demo-{uuid.uuid4().hex[:8]}"
    
    db[table_name].append(record)
    return record


def _demo_update(table_name: str, data: dict, eq: dict) -> dict | None:
    """데모 모드: 로컬 데이터 업데이트"""
    db = st.session_state.demo_db
    records = db.get(table_name, [])
    
    for i, record in enumerate(records):
        match = True
        for key, value in eq.items():
            if record.get(key) != value:
                match = False
                break
        if match:
            records[i].update(data)
            return records[i]
    
    return None


def _demo_delete(table_name: str, eq: dict) -> bool:
    """데모 모드: 로컬 데이터 삭제"""
    db = st.session_state.demo_db
    records = db.get(table_name, [])
    
    before = len(records)
    db[table_name] = [
        r for r in records
        if not all(r.get(k) == v for k, v in eq.items())
    ]
    
    return len(db[table_name]) < before


# ============================================================
# 실시간 구독 (Realtime) - 데모 모드에서는 사용 불가
# ============================================================
def subscribe_to_schedules(vacation_id: str, callback):
    """
    특정 방학의 스케줄 변경을 실시간으로 구독합니다.
    데모 모드에서는 지원하지 않습니다.
    """
    if is_demo_mode():
        st.info("🔔 데모 모드에서는 실시간 구독을 지원하지 않습니다.")
        return None
    
    supabase = get_supabase_client()
    channel = supabase.channel(f"schedules-{vacation_id}")
    
    channel.on_postgres_changes(
        event="*",
        schema="public",
        table="schedules",
        filter=f"vacation_id=eq.{vacation_id}",
        callback=callback
    ).subscribe()
    
    return channel


def subscribe_to_vacation_updates(vacation_id: str, callback):
    """
    방학 정보 변경을 실시간으로 구독합니다.
    데모 모드에서는 지원하지 않습니다.
    """
    if is_demo_mode():
        return None
    
    supabase = get_supabase_client()
    channel = supabase.channel(f"vacation-{vacation_id}")
    
    channel.on_postgres_changes(
        event="*",
        schema="public",
        table="vacations",
        filter=f"id=eq.{vacation_id}",
        callback=callback
    ).subscribe()
    
    return channel