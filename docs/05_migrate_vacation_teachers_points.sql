-- ============================================================
-- 마이그레이션: vacation_teachers 테이블에 포인트 컬럼 추가
-- 
-- 기존: target_count (목표 횟수) + carry_over_points (이월 포인트)
-- 변경: care_points + admin_points + vacation_points + carry_over_points
-- ============================================================

-- 1. 새 컬럼 추가 (기존 데이터 유지)
ALTER TABLE vacation_teachers
    ADD COLUMN IF NOT EXISTS care_points INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS admin_points INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS vacation_points INTEGER NOT NULL DEFAULT 0;

-- 2. 기존 데이터 마이그레이션 (target_count 값을 care_points로 변환)
--    기존 로직: target_count = 총 근무 가능 횟수
--    새 로직: care_points + admin_points + vacation_points = 총 포인트
--    기본 분배: care_points = target_count, admin_points = 0, vacation_points = 0
UPDATE vacation_teachers
SET 
    care_points = target_count,
    admin_points = 0,
    vacation_points = 0
WHERE care_points = 0 AND admin_points = 0 AND vacation_points = 0;

-- 3. (선택) 더 이상 사용하지 않는 target_count 컬럼 제거
--    주의: 다른 코드에서 참조하지 않는지 확인 후 실행
-- ALTER TABLE vacation_teachers DROP COLUMN IF EXISTS target_count;

-- 4. 변경 확인
SELECT 
    id, 
    vacation_id, 
    teacher_id, 
    care_points, 
    admin_points, 
    vacation_points, 
    carry_over_points,
    (care_points + admin_points + vacation_points + carry_over_points) AS total_points
FROM vacation_teachers
LIMIT 20;