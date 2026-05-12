# 🗄️ Supabase DB 스키마 (PostgreSQL)

## 1. 테이블 관계도 (ERD)

```
profiles (교사 프로필)
    ↑ 1:N
vacations (방학)
    ↑ 1:N
vacation_teachers (방학별 교사 배정)
    ↑ 1:N
care_requirements (돌봄 필요 인원)
flash_teachers (반짝선생님)
excluded_dates (제외일)
meeting_weeks (회의 주간)
teacher_preferences (교사 선호도)
vacation_requests (휴가 신청)
schedules (최종 스케줄)
vacation_stats (방학별 통계)
```

## 2. 전체 테이블 정의

---

### 2.1 profiles (교사 프로필)

```sql
-- 교사(사용자) 프로필 테이블
-- Supabase Auth.users와 1:1 연결
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,                          -- 교사 이름
    role TEXT NOT NULL CHECK (role IN ('admin', 'teacher')),  -- 관리자 or 교사
    phone TEXT,                                  -- 연락처 (선택)
    is_active BOOLEAN DEFAULT true,              -- 활성화 여부
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: 본인만 읽기/수정 가능, 관리자는 모든 프로필 읽기 가능
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- 모든 인증된 사용자는 프로필 읽기 가능 (관리자 포함)
CREATE POLICY "profiles_select_policy" ON profiles
    FOR SELECT USING (
        auth.uid() = id 
        OR auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

-- 본인만 수정 가능
CREATE POLICY "profiles_update_policy" ON profiles
    FOR UPDATE USING (auth.uid() = id);

-- 트리거: auth.users에 새 사용자 생성 시 자동으로 profiles 레코드 생성
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, name, role)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
        COALESCE(NEW.raw_user_meta_data->>'role', 'teacher')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
```

---

### 2.2 vacations (방학)

```sql
-- 방학 정보 테이블
CREATE TABLE vacations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,                          -- 예: "2026 겨울방학"
    year INTEGER NOT NULL,                        -- 년도 (예: 2026)
    season TEXT NOT NULL CHECK (season IN ('spring', 'summer', 'fall', 'winter')),  -- 봄/여름/가을/겨울
    start_date DATE NOT NULL,                     -- 방학 시작일
    end_date DATE NOT NULL,                       -- 방학 종료일
    status TEXT NOT NULL DEFAULT 'planning' 
        CHECK (status IN ('planning', 'input', 'optimized', 'confirmed', 'completed')),
    -- planning: 생성됨, input: 교사 입력 중, optimized: 최적화 완료, confirmed: 승인됨, completed: 종료
    admin_id UUID NOT NULL REFERENCES profiles(id),  -- 생성한 관리자
    notes TEXT,                                   -- 비고
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    -- 같은 시즌 중복 방학 방지
    UNIQUE(year, season)
);

-- RLS: 모든 인증된 사용자가 읽기 가능, 관리자만 쓰기 가능
ALTER TABLE vacations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "vacations_select_policy" ON vacations
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "vacations_insert_policy" ON vacations
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "vacations_update_policy" ON vacations
    FOR UPDATE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );
```

---

### 2.3 vacation_teachers (방학별 교사 배정)

```sql
-- 각 방학에 참여하는 교사 목록
CREATE TABLE vacation_teachers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    target_count INTEGER NOT NULL DEFAULT 0,      -- 목표 근무 횟수 (자동 계산)
    carry_over_points INTEGER NOT NULL DEFAULT 0, -- 이전 방학에서 이월된 포인트
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vacation_id, teacher_id)
);

ALTER TABLE vacation_teachers ENABLE ROW LEVEL SECURITY;

-- 본인 + 관리자만 읽기 가능
CREATE POLICY "vacation_teachers_select_policy" ON vacation_teachers
    FOR SELECT USING (
        auth.uid() = teacher_id 
        OR auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

-- 관리자만 쓰기 가능
CREATE POLICY "vacation_teachers_insert_policy" ON vacation_teachers
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "vacation_teachers_update_policy" ON vacation_teachers
    FOR UPDATE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );
```

---

### 2.4 care_requirements (돌봄 필요 인원)

```sql
-- 날짜별·오전/오후별 돌봄 필요 인원
CREATE TABLE care_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    date DATE NOT NULL,                           -- 날짜
    slot_type TEXT NOT NULL CHECK (slot_type IN ('AM', 'PM')),  -- 오전/오후
    required_count INTEGER NOT NULL CHECK (required_count >= 0),  -- 필요 인원
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vacation_id, date, slot_type)
);

ALTER TABLE care_requirements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "care_requirements_select_policy" ON care_requirements
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "care_requirements_insert_policy" ON care_requirements
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "care_requirements_update_policy" ON care_requirements
    FOR UPDATE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );
```

---

### 2.5 flash_teachers (반짝선생님)

```sql
-- 반짝선생님: 특정 날짜·시간대에 돌봄 필요 인원 1명 감소
CREATE TABLE flash_teachers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    date DATE NOT NULL,                           -- 날짜
    slot_type TEXT NOT NULL CHECK (slot_type IN ('AM', 'PM')),  -- 오전/오후
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vacation_id, teacher_id, date, slot_type)
);

ALTER TABLE flash_teachers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "flash_teachers_select_policy" ON flash_teachers
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "flash_teachers_insert_policy" ON flash_teachers
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "flash_teachers_delete_policy" ON flash_teachers
    FOR DELETE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );
```

---

### 2.6 excluded_dates (제외일)

```sql
-- 휴일/제외일: 해당 날짜 전체 슬롯 제외
CREATE TABLE excluded_dates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    date DATE NOT NULL,                           -- 제외 날짜
    reason TEXT NOT NULL,                         -- 사유 (예: "설날", "대체공휴일", "학교장 재량휴일")
    is_holiday BOOLEAN DEFAULT true,              -- 공휴일 여부
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vacation_id, date)
);

ALTER TABLE excluded_dates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "excluded_dates_select_policy" ON excluded_dates
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "excluded_dates_insert_policy" ON excluded_dates
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "excluded_dates_delete_policy" ON excluded_dates
    FOR DELETE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );
```

---

### 2.7 meeting_weeks (회의 주간)

```sql
-- 회의 주간: 오후 전체 회의 → 오후 돌봄 슬롯 없음
CREATE TABLE meeting_weeks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    week_start DATE NOT NULL,                     -- 해당 주 월요일
    week_end DATE NOT NULL,                       -- 해당 주 금요일
    description TEXT DEFAULT '전체 회의',          -- 설명
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vacation_id, week_start)
);

ALTER TABLE meeting_weeks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "meeting_weeks_select_policy" ON meeting_weeks
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "meeting_weeks_insert_policy" ON meeting_weeks
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "meeting_weeks_delete_policy" ON meeting_weeks
    FOR DELETE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );
```

---

### 2.8 teacher_preferences (교사 선호도)

```sql
-- 교사별 선호도 설정 (방학별)
CREATE TABLE teacher_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    -- 선호도 가중치 (0~100)
    prefer_care_am INTEGER DEFAULT 50 CHECK (prefer_care_am BETWEEN 0 AND 100),     -- 오전돌봄 선호
    prefer_care_pm INTEGER DEFAULT 50 CHECK (prefer_care_pm BETWEEN 0 AND 100),     -- 오후돌봄 선호
    prefer_admin_am INTEGER DEFAULT 50 CHECK (prefer_admin_am BETWEEN 0 AND 100),   -- 오전행정 선호
    prefer_admin_pm INTEGER DEFAULT 50 CHECK (prefer_admin_pm BETWEEN 0 AND 100),   -- 오후행정 선호
    prefer_consecutive_vacation INTEGER DEFAULT 50 CHECK (prefer_consecutive_vacation BETWEEN 0 AND 100),  -- 연속 휴가 선호
    prefer_vacation_am_ratio INTEGER DEFAULT 34 CHECK (prefer_vacation_am_ratio BETWEEN 0 AND 100),   -- 오전휴가 비율
    prefer_vacation_pm_ratio INTEGER DEFAULT 33 CHECK (prefer_vacation_pm_ratio BETWEEN 0 AND 100),   -- 오후휴가 비율
    prefer_vacation_full_ratio INTEGER DEFAULT 33 CHECK (prefer_vacation_full_ratio BETWEEN 0 AND 100),  -- 종일휴가 비율
    notes TEXT,                                  -- 추가 요청사항
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(teacher_id, vacation_id)
);

ALTER TABLE teacher_preferences ENABLE ROW LEVEL SECURITY;

-- 본인만 읽기/쓰기 가능, 관리자는 모두 읽기 가능
CREATE POLICY "teacher_preferences_select_policy" ON teacher_preferences
    FOR SELECT USING (
        auth.uid() = teacher_id 
        OR auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

-- 본인만 입력/수정 가능
CREATE POLICY "teacher_preferences_insert_policy" ON teacher_preferences
    FOR INSERT WITH CHECK (auth.uid() = teacher_id);

CREATE POLICY "teacher_preferences_update_policy" ON teacher_preferences
    FOR UPDATE USING (auth.uid() = teacher_id);
```

---

### 2.9 vacation_requests (휴가 신청)

```sql
-- 교사별 휴가 신청 (원하는 휴가 날짜)
CREATE TABLE vacation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    date DATE NOT NULL,                           -- 휴가 희망일
    request_type TEXT NOT NULL CHECK (request_type IN ('full_day', 'am', 'pm')),  -- 종일/오전/오후
    priority INTEGER DEFAULT 1 CHECK (priority BETWEEN 1 AND 5),  -- 우선순위 (1: 가장 원함, 5: 덜 원함)
    reason TEXT,                                  -- 사유 (선택)
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(teacher_id, vacation_id, date)
);

ALTER TABLE vacation_requests ENABLE ROW LEVEL SECURITY;

-- 본인만 읽기/쓰기 가능, 관리자는 모두 읽기 가능
CREATE POLICY "vacation_requests_select_policy" ON vacation_requests
    FOR SELECT USING (
        auth.uid() = teacher_id 
        OR auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "vacation_requests_insert_policy" ON vacation_requests
    FOR INSERT WITH CHECK (auth.uid() = teacher_id);

CREATE POLICY "vacation_requests_update_policy" ON vacation_requests
    FOR UPDATE USING (auth.uid() = teacher_id);

CREATE POLICY "vacation_requests_delete_policy" ON vacation_requests
    FOR DELETE USING (auth.uid() = teacher_id);
```

---

### 2.10 schedules (최종 스케줄)

```sql
-- 최종 배정된 스케줄 (최적화 결과)
CREATE TABLE schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    date DATE NOT NULL,                           -- 날짜
    slot_type TEXT NOT NULL CHECK (slot_type IN ('AM_Childcare', 'PM_Childcare', 'AM_Admin', 'PM_Admin')),  -- 슬롯 유형
    is_flash_teacher BOOLEAN DEFAULT false,       -- 반짝선생님 여부
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    -- 같은 교사가 같은 날짜에 같은 슬롯 중복 배정 방지
    UNIQUE(vacation_id, teacher_id, date, slot_type)
);

-- 인덱스: 빠른 조회를 위해
CREATE INDEX idx_schedules_vacation_teacher ON schedules(vacation_id, teacher_id);
CREATE INDEX idx_schedules_vacation_date ON schedules(vacation_id, date);

ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;

-- 본인 스케줄 + 관리자는 모두 읽기 가능
CREATE POLICY "schedules_select_policy" ON schedules
    FOR SELECT USING (
        auth.uid() = teacher_id 
        OR auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

-- 관리자만 쓰기 가능 (최적화 결과 저장)
CREATE POLICY "schedules_insert_policy" ON schedules
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "schedules_update_policy" ON schedules
    FOR UPDATE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "schedules_delete_policy" ON schedules
    FOR DELETE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );
```

---

### 2.11 vacation_stats (방학별 통계)

```sql
-- 방학별 교사 통계 (누적 관리용)
CREATE TABLE vacation_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    total_care_count INTEGER DEFAULT 0,           -- 총 돌봄 횟수
    total_admin_count INTEGER DEFAULT 0,          -- 총 행정 횟수
    total_work_count INTEGER DEFAULT 0,           -- 총 근무 횟수 (돌봄+행정)
    vacation_am_points INTEGER DEFAULT 0,         -- 오전휴가 포인트
    vacation_pm_points INTEGER DEFAULT 0,         -- 오후휴가 포인트
    vacation_full_points INTEGER DEFAULT 0,       -- 종일휴가 포인트 (2포인트)
    total_vacation_points INTEGER DEFAULT 0,      -- 총 휴가 포인트
    flash_teacher_count INTEGER DEFAULT 0,        -- 반짝선생님 횟수
    carry_over_to_next INTEGER DEFAULT 0,         -- 다음 방학으로 이월할 포인트
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vacation_id, teacher_id)
);

ALTER TABLE vacation_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "vacation_stats_select_policy" ON vacation_stats
    FOR SELECT USING (
        auth.uid() = teacher_id 
        OR auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "vacation_stats_insert_policy" ON vacation_stats
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "vacation_stats_update_policy" ON vacation_stats
    FOR UPDATE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );
```

---

## 3. 인덱스 요약

```sql
-- 성능 최적화를 위한 추가 인덱스
CREATE INDEX idx_schedules_date ON schedules(date);
CREATE INDEX idx_care_requirements_date ON care_requirements(vacation_id, date);
CREATE INDEX idx_vacation_requests_teacher ON vacation_requests(teacher_id, vacation_id);
CREATE INDEX idx_flash_teachers_date ON flash_teachers(vacation_id, date);
CREATE INDEX idx_excluded_dates_date ON excluded_dates(vacation_id, date);
```

## 4. 실시간 구독 (Realtime)

```sql
-- Supabase Realtime: 스케줄 변경 시 실시간 업데이트
-- (선택사항, 필요시 활성화)
ALTER PUBLICATION supabase_realtime ADD TABLE schedules;
ALTER PUBLICATION supabase_realtime ADD TABLE vacations;
```

## 5. 시드 데이터 (초기 공휴일)

```sql
-- 한국 공휴일 데이터 (2026년 기준, 매년 업데이트 필요)
-- src/db/seed_data.py에서 관리
```

## 6. 테이블 관계 요약

| 테이블 | 부모 테이블 | 관계 | 설명 |
|--------|------------|------|------|
| profiles | auth.users | 1:1 | Supabase Auth와 연결 |
| vacations | profiles(admin_id) | N:1 | 관리자가 생성 |
| vacation_teachers | vacations, profiles | N:1 | 방학별 교사 배정 |
| care_requirements | vacations | N:1 | 날짜별 필요 인원 |
| flash_teachers | vacations, profiles | N:1 | 반짝선생님 |
| excluded_dates | vacations | N:1 | 제외일 |
| meeting_weeks | vacations | N:1 | 회의 주간 |
| teacher_preferences | profiles, vacations | N:1 | 교사 선호도 |
| vacation_requests | profiles, vacations | N:1 | 휴가 신청 |
| schedules | vacations, profiles | N:1 | 최종 스케줄 |
| vacation_stats | vacations, profiles | N:1 | 방학별 통계 |