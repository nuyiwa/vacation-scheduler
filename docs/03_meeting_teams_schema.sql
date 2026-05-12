-- ============================================================
-- 회의 팀 (Meeting Teams) - 추가 테이블
-- ============================================================

-- 2.12 meeting_teams (회의 팀)
CREATE TABLE meeting_teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    team_name TEXT NOT NULL,                          -- 팀 이름 (예: "1팀", "수학팀")
    member_ids UUID[] DEFAULT '{}',                   -- 팀 구성원 teacher_id 배열
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vacation_id, team_name)
);

ALTER TABLE meeting_teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY "meeting_teams_select_policy" ON meeting_teams
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "meeting_teams_insert_policy" ON meeting_teams
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "meeting_teams_update_policy" ON meeting_teams
    FOR UPDATE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "meeting_teams_delete_policy" ON meeting_teams
    FOR DELETE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );


-- 2.13 daily_meeting_assignments (일별 회의 팀 배정)
-- 날짜별로 여러 팀이 배정될 수 있도록 UNIQUE(vacation_id, date, team_id)
CREATE TABLE IF NOT EXISTS daily_meeting_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vacation_id UUID NOT NULL REFERENCES vacations(id) ON DELETE CASCADE,
    date DATE NOT NULL,                               -- 날짜
    team_id UUID NOT NULL REFERENCES meeting_teams(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(vacation_id, date, team_id)
);

ALTER TABLE daily_meeting_assignments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "daily_meeting_assignments_select_policy" ON daily_meeting_assignments
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "daily_meeting_assignments_insert_policy" ON daily_meeting_assignments
    FOR INSERT WITH CHECK (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "daily_meeting_assignments_update_policy" ON daily_meeting_assignments
    FOR UPDATE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );

CREATE POLICY "daily_meeting_assignments_delete_policy" ON daily_meeting_assignments
    FOR DELETE USING (
        auth.uid() IN (SELECT id FROM profiles WHERE role = 'admin')
    );