# 🏫 방학 스케줄링 시스템 (Vacation Scheduling System)

유치원/초등학교 방학 기간 동안 교사들의 돌봄, 행정 업무를 **자동으로 최적 배정**하는 웹 애플리케이션입니다.

## ✨ 주요 기능

### 📅 스케줄 관리
- **방학별 스케줄링**: 봄방학, 여름방학, 가을방학, 겨울방학 각각 관리
- **4개 슬롯 시스템**: 오전돌봄, 오후돌봄, 오전행정, 오후행정
- **시각적 캘린더**: 색상 구분으로 한눈에 파악 (돌봄=파랑, 행정=초록, 휴가=회색, 반짝선생님=노랑)

### 🤖 PuLP 최적화 엔진
- **Integer Linear Programming**으로 최적 스케줄 자동 생성
- **Hard Constraints**: 목표 횟수 정확히 달성, 하루 최대 2슬롯, 최소 인원 보장
- **Soft Constraints**: 교사 선호도 최대 반영, 연속 업무 최소화, 휴가 포인트 공평 분배

### 👨‍🏫 사용자 워크플로
1. **관리자 설정**: 방학 생성 → 교사 배정 → 돌봄 필요 인원 설정 → 반짝선생님 등록
2. **교사 입력**: 휴가 신청 → 선호도 설정 (돌봄/행정 선호도 0~100%)
3. **자동 배정**: PuLP 최적화 실행 → 결과 미리보기 → 승인 및 저장
4. **누적 관리**: 모든 방학 기록 영구 저장, 포인트 차이 자동 보정

### 🔐 인증 및 권한
- **Supabase Auth** 기반 로그인
- **역할 구분**: 관리자(admin) / 교사(teacher)
- **RLS(Row Level Security)** 로 데이터 보호

## 🛠️ 기술 스택

| 기술 | 용도 |
|------|------|
| **Python 3.11+** | 백엔드 언어 |
| **Streamlit** | 웹 UI 프레임워크 |
| **Supabase** | 데이터베이스 + 인증 + Realtime |
| **PuLP** | Integer Linear Programming 최적화 |
| **pandas** | 데이터 처리 |
| **gspread** | Google Sheets 연동 (선택사항) |

## 📁 프로젝트 구조

```
vacation/
├── app.py                          # 메인 Streamlit 앱 (진입점)
├── requirements.txt                # Python 의존성
├── .env.example                    # 환경변수 템플릿
├── .gitignore                      # Git 제외 파일
├── README.md                       # 이 파일
│
├── .streamlit/
│   ├── config.toml                 # Streamlit 설정
│   └── manifest.json               # PWA manifest
│
├── docs/
│   ├── 01_project_structure.md     # 프로젝트 구조 문서
│   └── 02_db_schema.md             # DB 스키마 문서
│
└── src/
    ├── __init__.py
    │
    ├── config/
    │   ├── __init__.py
    │   ├── settings.py             # 설정값, 상수, Enum
    │   └── supabase_client.py      # Supabase 클라이언트 설정
    │
    ├── db/
    │   ├── __init__.py
    │   ├── models.py               # 데이터 모델 (dataclass)
    │   └── queries.py              # DB 쿼리 함수
    │
    ├── utils/
    │   ├── __init__.py
    │   └── korean_holidays.py      # 한국 공휴일 계산
    │
    ├── ui/
    │   ├── __init__.py
    │   └── calendar.py             # 캘린더 UI 컴포넌트
    │
    ├── optimizer/
    │   ├── __init__.py
    │   └── scheduler.py            # PuLP 최적화 엔진
    │
    └── pages/
        ├── __init__.py
        ├── admin.py                # 관리자 페이지
        ├── teacher.py              # 교사 페이지
        └── history.py              # 이력 페이지
```

## 🚀 설치 및 실행

### 1. 저장소 클론

```bash
git clone https://github.com/your-org/vacation-scheduler.git
cd vacation
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate     # Windows
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. Supabase 설정

1. [Supabase](https://supabase.com)에서 새 프로젝트 생성
2. SQL Editor에서 `docs/02_db_schema.md`의 SQL 실행하여 테이블 생성
3. Authentication > Settings에서 이메일 인증 활성화
4. `.env.example`을 `.env`로 복사하고 Supabase URL과 anon key 입력

```bash
cp .env.example .env
# .env 파일 편집:
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-anon-key
```

### 5. 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501`으로 접속합니다.

## 📱 모바일 사용

### PWA처럼 사용하기
1. Chrome/Safari에서 앱 접속
2. 브라우저 메뉴 > "홈 화면에 추가"
3. 홈 화면의 아이콘으로 앱처럼 실행 가능

### 모바일 최적화
- 반응형 디자인으로 모바일에서도 최적화된 UI
- 터치 친화적인 버튼과 입력 필드
- 스크롤 가능한 탭 메뉴

## 🗄️ Supabase DB 스키마

주요 테이블:
- **vacations**: 방학 정보
- **profiles**: 사용자 프로필
- **vacation_teachers**: 방학별 교사 배정
- **care_requirements**: 돌봄 필요 인원
- **flash_teachers**: 반짝선생님
- **schedules**: 최종 스케줄
- **vacation_requests**: 휴가 신청
- **teacher_preferences**: 교사 선호도
- **excluded_dates**: 제외일
- **meeting_weeks**: 회의 주간
- **vacation_stats**: 방학 통계

자세한 스키마는 `docs/02_db_schema.md` 참조

## 🔧 개발 가이드

### 코드 스타일
- 모든 코드에 한국어 주석 포함
- 함수/클래스에 docstring 작성
- 타입 힌트 사용

### 테스트
```bash
pytest tests/
```

### 배포
```bash
# Streamlit Cloud 배포
# 1. GitHub에 푸시
# 2. Streamlit Cloud에서 New App
# 3. 레포지토리 연결
# 4. 환경변수 설정 (Supabase URL, Key)
```

## 📄 라이선스

MIT License

## 👥 기여

버그 리포트, 기능 제안은 GitHub Issues를 이용해주세요.