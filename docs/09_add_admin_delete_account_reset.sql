-- 관리자 계정 삭제 및 방학 배정 초기화 기능
-- 1. 선생님 계정 삭제 함수 (관련 데이터 모두 CASCADE 삭제)
-- 2. 모든 방학 배정 초기화 함수

-- =============================================
-- 1. 선생님 계정 삭제 함수
-- =============================================
CREATE OR REPLACE FUNCTION delete_teacher_account(p_teacher_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_count INT;
BEGIN
    -- teacher_preferences 삭제
    DELETE FROM teacher_preferences WHERE teacher_id = p_teacher_id;
    
    -- vacation_assignments 삭제
    DELETE FROM vacation_assignments WHERE teacher_id = p_teacher_id;
    
    -- daily_meeting_assignments 삭제
    DELETE FROM daily_meeting_assignments WHERE teacher_id = p_teacher_id;
    
    -- admin_requests 삭제
    DELETE FROM admin_requests WHERE teacher_id = p_teacher_id;
    
    -- teachers 테이블에서 삭제
    DELETE FROM teachers WHERE id = p_teacher_id;
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count > 0;
END;
$$;

-- =============================================
-- 2. 모든 방학 배정 초기화 함수
-- =============================================
CREATE OR REPLACE FUNCTION reset_all_vacation_assignments()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_count INT;
BEGIN
    -- vacation_assignments 모두 삭제
    DELETE FROM vacation_assignments;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    
    -- daily_meeting_assignments 모두 삭제
    DELETE FROM daily_meeting_assignments;
    
    -- teacher_preferences의 is_ready 초기화
    UPDATE teacher_preferences SET is_ready = FALSE;
    
    RETURN TRUE;
END;
$$;