-- ============================================================
-- admin_requests 테이블 생성
-- 교사가 지정 신청하는 행정 업무 슬롯
-- vacation_requests와 별도로 관리 (유니크 제약조건 충돌 방지)
-- ============================================================

CREATE TABLE IF NOT EXISTS admin_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    slot_type TEXT NOT NULL CHECK (slot_type IN ('AM', 'PM')),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(teacher_id, vacation_id, date, slot_type)
);

ALTER TABLE admin_requests ENABLE ROW LEVEL SECURITY;

-- 본인만 읽기/쓰기 가능, 관리자는 모두 읽기 가능
CREATE POLICY "admin_requests_select_policy" ON admin_requests
    FOR SELECT USING (
        auth.uid() = teacher_id 
        OR auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "admin_requests_insert_policy" ON admin_requests
    FOR INSERT WITH CHECK (auth.uid() = teacher_id);

CREATE POLICY "admin_requests_update_policy" ON admin_requests
    FOR UPDATE USING (auth.uid() = teacher_id);

CREATE POLICY "admin_requests_delete_policy" ON admin_requests
    FOR DELETE USING (auth.uid() = teacher_id);