-- ============================================================
-- 마이그레이션: teacher_preferences 테이블
-- prefer_vacation_type (TEXT) → prefer_vacation_am/pm/full_ratio (INTEGER)
-- ============================================================
-- 실행일: 2026-05-11
-- 설명: 단일 텍스트 필드(prefer_vacation_type)를 3개 비율 컬럼으로 교체
--       (오전/오후/종일 휴가 비율을 각각 0~100으로 설정, 합 = 100)
-- ============================================================

-- 1. 기존 prefer_vacation_type 컬럼 삭제
ALTER TABLE teacher_preferences DROP COLUMN IF EXISTS prefer_vacation_type;

-- 2. 새 비율 컬럼 추가
ALTER TABLE teacher_preferences ADD COLUMN prefer_vacation_am_ratio INTEGER DEFAULT 34 CHECK (prefer_vacation_am_ratio BETWEEN 0 AND 100);
ALTER TABLE teacher_preferences ADD COLUMN prefer_vacation_pm_ratio INTEGER DEFAULT 33 CHECK (prefer_vacation_pm_ratio BETWEEN 0 AND 100);
ALTER TABLE teacher_preferences ADD COLUMN prefer_vacation_full_ratio INTEGER DEFAULT 33 CHECK (prefer_vacation_full_ratio BETWEEN 0 AND 100);

-- 3. (선택) 기존 데이터가 있다면 기본값으로 변환
--    prefer_vacation_type 값에 따라 비율 설정
--    'am_only'   → (100, 0, 0)
--    'pm_only'   → (0, 100, 0)
--    'full_day'  → (0, 0, 100)
--    'balanced'  → (34, 33, 33)  -- 기본값
-- UPDATE teacher_preferences SET
--     prefer_vacation_am_ratio = CASE
--         WHEN prefer_vacation_type = 'am_only' THEN 100
--         WHEN prefer_vacation_type = 'pm_only' THEN 0
--         WHEN prefer_vacation_type = 'full_day' THEN 0
--         ELSE 34
--     END,
--     prefer_vacation_pm_ratio = CASE
--         WHEN prefer_vacation_type = 'am_only' THEN 0
--         WHEN prefer_vacation_type = 'pm_only' THEN 100
--         WHEN prefer_vacation_type = 'full_day' THEN 0
--         ELSE 33
--     END,
--     prefer_vacation_full_ratio = CASE
--         WHEN prefer_vacation_type = 'am_only' THEN 0
--         WHEN prefer_vacation_type = 'pm_only' THEN 0
--         WHEN prefer_vacation_type = 'full_day' THEN 100
--         ELSE 33
--     END
-- WHERE prefer_vacation_type IS NOT NULL;