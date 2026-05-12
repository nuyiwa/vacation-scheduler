--
-- excluded_dates 테이블에 time_scope 컬럼 추가
-- 오전/오후 선택적 제외를 지원하기 위함
--

-- =============================================
-- 1. time_scope 컬럼 추가 (NULL 허용, 기존 데이터 호환)
-- =============================================
ALTER TABLE excluded_dates
ADD COLUMN time_scope TEXT CHECK (time_scope IN ('AM', 'PM', 'ALL')) DEFAULT 'ALL';

-- =============================================
-- 2. 기존 데이터는 ALL로 업데이트
-- =============================================
UPDATE excluded_dates SET time_scope = 'ALL' WHERE time_scope IS NULL;

-- =============================================
-- 3. NOT NULL 제약 조건 추가
-- =============================================
ALTER TABLE excluded_dates
ALTER COLUMN time_scope SET NOT NULL;

-- =============================================
-- 4. UNIQUE 제약 조건 변경 (vacation_id, date, time_scope)
-- =============================================
-- 기존 UNIQUE 제약 삭제
ALTER TABLE excluded_dates
DROP CONSTRAINT excluded_dates_vacation_id_date_key;

-- 새로운 UNIQUE 제약 추가
ALTER TABLE excluded_dates
ADD CONSTRAINT excluded_dates_vacation_id_date_time_scope_key
UNIQUE (vacation_id, date, time_scope);