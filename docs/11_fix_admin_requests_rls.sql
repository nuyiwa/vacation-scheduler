-- ============================================================
-- admin_requests RLS 정책 수정
-- 행정 신청은 같은 날짜/시간에 여러 교사가 신청 가능
-- RLS 정책을 제거하고, 대신 애플리케이션 레벨에서 권한 관리
-- ============================================================

-- 기존 RLS 정책 삭제
DROP POLICY IF EXISTS "admin_requests_select_policy" ON admin_requests;
DROP POLICY IF EXISTS "admin_requests_insert_policy" ON admin_requests;
DROP POLICY IF EXISTS "admin_requests_update_policy" ON admin_requests;
DROP POLICY IF EXISTS "admin_requests_delete_policy" ON admin_requests;

-- RLS 비활성화 (애플리케이션 레벨에서 권한 관리)
ALTER TABLE admin_requests DISABLE ROW LEVEL SECURITY;