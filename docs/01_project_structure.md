# 🏗️ 방학 스케줄링 시스템 - 프로젝트 구조

## 1. 전체 폴더 구조

```
vacation/
├── .streamlit/                    # Streamlit 설정
│   ├── config.toml                # Streamlit 서버/테마 설정
│   ├── secrets.toml               # Supabase 인증 정보 (gitignore)
│   └── manifest.json              # PWA manifest (홈화면 추가용)
│
├── docs/                          # 문서
│   ├── 01_project_structure.md    # (현재 파일)
│   ├── 02_db_schema.md            # DB 스키마
│   └── 03_architecture.md         # 아키텍처 설명
│
├── src/                           # 소스 코드
│   ├── __init__.py
│   │
│   ├── config/                    # 설정 관련
│   │   ├── __init__.py
│   │   ├── settings.py            # 앱 설정 (상수, 환경변수)
│   │   └── supabase_client.py     # Supabase 클라이언트 초기화
│   │
│   ├── db/                        # 데이터베이스 관련
│   │   ├── __init__.py
│   │   ├── models.py              # 데이터 모델 (dataclass)
│   │   ├── queries.py             # Supabase 쿼리 함수
│   │   └── seed_data.py           # 초기 데이터 (공휴일 등)
│   │
│   ├── auth/                      # 인증 관련
│   │   ├── __init__.py
│   │   ├── login.py               # 로그인/회원가입 UI
│   │   └── permissions.py         # 권한 체크 (관리자/교사)
│   │
│   ├── models/                    # 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── vacation.py            # 방학 관리 로직
│   │   ├── schedule.py            # 스케줄 관리 로직
│   │   ├── teacher.py             # 교사 관리 로직
│   │   └── preferences.py         # 선호도 관리 로직
│   │
│   ├── optimizer/                 # PuLP 최적화
│   │   ├── __init__.py
│   │   ├── constraints.py         # 제약조건 정의
│   │   ├── objective.py           # 목적함수 정의
│   │   ├── solver.py              # 최적화 실행 엔진
│   │   └── validator.py           # 결과 검증
│   │
│   ├── ui/                        # Streamlit UI 컴포넌트
│   │   ├── __init__.py
│   │   ├── calendar.py            # 캘린더 UI 컴포넌트
│   │   ├── filters.py             # 필터 UI 컴포넌트
│   │   ├── tables.py              # 테이블 UI 컴포넌트
│   │   └── styles.py              # CSS 스타일 정의
│   │
│   ├── utils/                     # 유틸리티
│   │   ├── __init__.py
│   │   ├── date_utils.py          # 날짜 관련 유틸리티
│   │   ├── korean_holidays.py     # 한국 공휴일 데이터
│   │   └── helpers.py             # 기타 헬퍼 함수
│   │
│   └── pages/                     # Streamlit 멀티페이지
│       ├── __init__.py
│       ├── home.py                # 홈화면 (캘린더)
│       ├── admin_settings.py      # 관리자 설정 페이지
│       ├── teacher_input.py       # 교사 입력 페이지
│       ├── optimization.py        # 최적화 실행 페이지
│       └── history.py             # 이전 방학 기록 페이지
│
├── tests/                         # 테스트
│   ├── __init__.py
│   ├── test_optimizer.py
│   ├── test_queries.py
│   └── test_validator.py
│
├── app.py                         # Streamlit 메인 앱 (진입점)
├── requirements.txt               # Python 의존성
├── .env.example                   # 환경변수 예시
├── .gitignore
└── README.md
```

## 2. 주요 Streamlit 페이지 구조

### app.py (메인 진입점)
```python
# Streamlit 멀티페이지 앱 설정
# - 페이지 설정 (제목, 아이콘, 레이아웃)
# - Supabase 클라이언트 초기화
# - 인증 상태 확인
# - 네비게이션 사이드바
# - 각 페이지 라우팅
```

### pages/home.py (홈화면 - 캘린더)
```python
# 가장 중요한 페이지
# - 로그인한 교사 본인 스케줄 표시 (기본)
# - 전체 스케줄 보기 탭
# - 필터: 오전돌봄/오후돌봄/오전행정/오후행정/휴가
# - 색상 구분: 돌봄(파랑), 행정(초록), 휴가(회색), 반짝선생님(노랑)
# - 월별/주별 캘린더 뷰
```

### pages/admin_settings.py (관리자 설정)
```python
# 관리자 전용 페이지
# - 방학 생성/수정
# - 돌봄 필요 인원 설정
# - 반짝선생님 기간 등록
# - 행정 총량 설정
# - 제외일 등록 (공휴일 + 추가 휴일)
# - 회의 주간 설정
```

### pages/teacher_input.py (교사 입력)
```python
# 교사용 페이지
# - 휴가 날짜 등록 (종일/오전/오후)
# - 선호도 설정 (가중치 0~100%)
# - 본인 입력 현황 확인
```

### pages/optimization.py (최적화)
```python
# 관리자 전용
# - 모든 입력 확인 대시보드
# - PuLP 최적화 실행 버튼
# - 결과 미리보기
# - 승인/저장
```

### pages/history.py (이력)
```python
# 모든 사용자 접근 가능
# - 이전 방학 기록 조회
# - 방학별 통계
# - 교사별 누적 포인트
```

## 3. 주요 함수 구조

### Supabase 클라이언트 (src/config/supabase_client.py)
```python
# create_supabase_client() -> Client
#   - URL과 Key로 Supabase 클라이언트 생성
#   - 세션 관리 (로그인 상태 유지)
# get_current_user() -> dict | None
#   - 현재 로그인한 사용자 정보
# sign_out() -> None
```

### DB 쿼리 (src/db/queries.py)
```python
# 방학 관련
#   get_vacations() -> list[Vacation]
#   create_vacation(data) -> Vacation
#   update_vacation(id, data) -> Vacation
#
# 교사 관련
#   get_teachers(vacation_id) -> list[Teacher]
#   create_teacher(data) -> Teacher
#
# 스케줄 관련
#   get_schedules(vacation_id, teacher_id) -> list[Schedule]
#   save_schedules(schedules) -> list[Schedule]
#   get_schedules_by_date(vacation_id, date) -> list[Schedule]
#
# 돌봄 필요 인원 관련
#   get_care_requirements(vacation_id) -> list[CareRequirement]
#   set_care_requirements(data) -> list[CareRequirement]
#
# 반짝선생님 관련
#   get_flash_teachers(vacation_id) -> list[FlashTeacher]
#   set_flash_teachers(data) -> list[FlashTeacher]
#
# 선호도 관련
#   get_preferences(teacher_id, vacation_id) -> Preferences
#   save_preferences(data) -> Preferences
#
# 휴가 관련
#   get_vacation_requests(teacher_id, vacation_id) -> list[VacationRequest]
#   save_vacation_requests(data) -> list[VacationRequest]
```

### 최적화 엔진 (src/optimizer/solver.py)
```python
# run_optimization(vacation_id) -> OptimizationResult
#   1. 모든 입력 데이터 로드
#   2. PuLP 문제 정의
#   3. Hard Constraints 적용
#   4. Soft Constraints + 가중치 적용
#   5. 최적화 실행 (CBC Solver)
#   6. 결과 검증
#   7. 결과 반환
```

### 캘린더 UI (src/ui/calendar.py)
```python
# render_calendar(schedules, filters) -> None
#   - 월별 캘린더 그리드 생성
#   - 각 날짜별 스케줄 표시
#   - 색상 코딩 적용
#   - 클릭 시 상세 정보 표시
# render_weekly_view(schedules, week_start) -> None
#   - 주별 상세 뷰
```

## 4. 데이터 흐름

```
[관리자] → 방학 생성 → 돌봄 필요인원 설정 → 반짝선생님 등록
    ↓
[교사] → 휴가 신청 → 선호도 입력
    ↓
[관리자] → 최적화 실행 (PuLP)
    ↓
[시스템] → 결과 검증 → Supabase 저장
    ↓
[모든 교사] → 캘린더에서 확인
```

## 5. 기술 스택 상세

### Python 패키지
```
streamlit==1.35.0
supabase==2.5.0
pulp==2.8.0
pandas==2.2.0
numpy==1.26.0
python-dotenv==1.0.0
gspread==6.1.0  # 선택사항
pydantic==2.6.0  # 데이터 검증
python-dateutil==2.9.0  # 날짜 처리
holidays==0.53  # 한국 공휴일
```

### Supabase 서비스
- **Database**: PostgreSQL (모든 데이터 저장)
- **Auth**: 이메일/비밀번호 인증 + Magic Link
- **Realtime**: 스케줄 변경 실시간 반영 (선택)
- **Storage**: 프로필 이미지 등 (선택)
- **Row Level Security (RLS)**: 테이블별 접근 제어