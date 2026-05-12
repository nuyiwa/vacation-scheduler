-- ============================================================
-- vacation_teachers 테이블에 is_ready 컬럼 추가
-- 교사가 휴가/행정 설정을 완료했는지 표시
-- ============================================================
ALTER TABLE vacation_teachers ADD COLUMN IF NOT EXISTS is_ready BOOLEAN DEFAULT FALSE;

-- ============================================================
-- vacations 테이블 status 체크 제약조건 업데이트
-- (planning, input, optimized, teacher_input, confirmed, completed)
-- ============================================================
-- 기존 제약조건 삭제 후 재생성
ALTER TABLE vacations DROP CONSTRAINT IF EXISTS vacations_status_check;
ALTER TABLE vacations ADD CONSTRAINT vacations_status_check 
    CHECK (status IN ('planning', 'input', 'optimized', 'teacher_input', 'confirmed', 'completed'));