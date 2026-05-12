-- ============================================================
-- daily_meeting_assignments 마이그레이션
-- UNIQUE(vacation_id, date) → UNIQUE(vacation_id, date, team_id)
-- 날짜별 여러 팀 배정 가능하도록 변경
-- ============================================================

-- 1. 기존 테이블이 있다면 UNIQUE 제약 조건 변경
-- (DROP 후 재생성, 데이터는 유지)
ALTER TABLE daily_meeting_assignments DROP CONSTRAINT IF EXISTS daily_meeting_assignments_vacation_id_date_key;

-- 2. 새 UNIQUE 제약 조건 추가 (vacation_id, date, team_id 조합)
ALTER TABLE daily_meeting_assignments ADD CONSTRAINT daily_meeting_assignments_vacation_id_date_team_id_key UNIQUE (vacation_id, date, team_id);

-- 3. 테이블이 아예 없다면 생성
CREATE TABLE IF NOT EXISTS daily_meeting_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    team_id UUID NOT NULL REFERENCES meeting_teams(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    
    CONSTRAINT daily_meeting_assignments_vacation_id_date_team_id_key UNIQUE(vacation_id, date, team_id)
);

-- 4. RLS 설정 (이미 설정되어 있으면 무시됨)
ALTER TABLE daily_meeting_assignments ENABLE ROW LEVEL SECURITY;

-- 5. 정책 생성 (이미 존재하면 무시)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'daily_meeting_assignments' AND policyname = 'daily_meeting_assignments_select_policy') THEN
        CREATE POLICY "daily_meeting_assignments_select_policy" ON daily_meeting_assignments
            FOR SELECT USING (auth.role() = 'authenticated');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'daily_meeting_assignments' AND policyname = 'daily_meeting_assignments_insert_policy') THEN
        CREATE POLICY "daily_meeting_assignments_insert_policy" ON daily_meeting_assignments
            FOR INSERT WITH CHECK (
                auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
            );
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'daily_meeting_assignments' AND policyname = 'daily_meeting_assignments_update_policy') THEN
        CREATE POLICY "daily_meeting_assignments_update_policy" ON daily_meeting_assignments
            FOR UPDATE USING (
                auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
            );
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'daily_meeting_assignments' AND policyname = 'daily_meeting_assignments_delete_policy') THEN
        CREATE POLICY "daily_meeting_assignments_delete_policy" ON daily_meeting_assignments
            FOR DELETE USING (
                auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
            );
    END IF;
END $$;