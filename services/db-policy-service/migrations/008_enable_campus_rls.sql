ALTER TABLE schools ENABLE ROW LEVEL SECURITY;
ALTER TABLE schools FORCE ROW LEVEL SECURITY;
ALTER TABLE campus_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE campus_users FORCE ROW LEVEL SECURITY;
ALTER TABLE classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE classes FORCE ROW LEVEL SECURITY;
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE students FORCE ROW LEVEL SECURITY;
ALTER TABLE leave_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE leave_requests FORCE ROW LEVEL SECURITY;
ALTER TABLE meal_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE meal_orders FORCE ROW LEVEL SECURITY;
ALTER TABLE delivery_confirmations ENABLE ROW LEVEL SECURITY;
ALTER TABLE delivery_confirmations FORCE ROW LEVEL SECURITY;
ALTER TABLE repair_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE repair_tickets FORCE ROW LEVEL SECURITY;
ALTER TABLE reminder_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminder_tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE operation_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE operation_logs FORCE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION campus_is_admin(role_name TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT role_name IN ('admin', 'super_admin', 'school_admin');
$$;

CREATE OR REPLACE FUNCTION campus_school_match(target_school TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT current_setting('app.school_id', true) IS NOT NULL
           AND current_setting('app.school_id', true) = target_school;
$$;

CREATE OR REPLACE FUNCTION campus_class_match(target_class TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT current_setting('app.class_id', true) IS NOT NULL
           AND current_setting('app.class_id', true) = target_class;
$$;

DROP POLICY IF EXISTS p_schools_select ON schools;
CREATE POLICY p_schools_select ON schools
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR campus_school_match(school_id)
);

DROP POLICY IF EXISTS p_campus_users_select ON campus_users;
CREATE POLICY p_campus_users_select ON campus_users
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR campus_school_match(school_id)
);

DROP POLICY IF EXISTS p_classes_select ON classes;
CREATE POLICY p_classes_select ON classes
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR campus_school_match(school_id)
);

DROP POLICY IF EXISTS p_students_select ON students;
CREATE POLICY p_students_select ON students
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR current_setting('app.role', true) = 'head_teacher' AND campus_class_match(class_id)
    OR current_setting('app.role', true) = 'parent_or_student_h5' AND current_setting('app.student_id', true) = student_id
);

DROP POLICY IF EXISTS p_leave_requests_select ON leave_requests;
CREATE POLICY p_leave_requests_select ON leave_requests
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR current_setting('app.role', true) = 'head_teacher' AND campus_class_match(class_id)
    OR current_setting('app.role', true) = 'academic_staff' AND campus_school_match(school_id)
    OR current_setting('app.role', true) = 'parent_or_student_h5' AND current_setting('app.student_id', true) = student_id
);

DROP POLICY IF EXISTS p_meal_orders_select ON meal_orders;
CREATE POLICY p_meal_orders_select ON meal_orders
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR current_setting('app.role', true) IN ('head_teacher', 'academic_staff', 'logistics_staff') AND campus_school_match(school_id)
    OR current_setting('app.role', true) = 'parent_or_student_h5' AND current_setting('app.student_id', true) = student_id
);

DROP POLICY IF EXISTS p_delivery_confirmations_select ON delivery_confirmations;
CREATE POLICY p_delivery_confirmations_select ON delivery_confirmations
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR current_setting('app.role', true) = 'logistics_staff' AND campus_school_match(school_id)
    OR current_setting('app.role', true) = 'vendor_link_user'
       AND current_setting('app.vendor_token_hash', true) IS NOT NULL
       AND current_setting('app.vendor_token_hash', true) = token_hash
);

DROP POLICY IF EXISTS p_repair_tickets_select ON repair_tickets;
CREATE POLICY p_repair_tickets_select ON repair_tickets
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR current_setting('app.role', true) IN ('logistics_staff', 'repair_assignee') AND campus_school_match(school_id)
    OR current_setting('app.role', true) = 'head_teacher' AND campus_class_match(class_id)
);

DROP POLICY IF EXISTS p_reminder_tasks_select ON reminder_tasks;
CREATE POLICY p_reminder_tasks_select ON reminder_tasks
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR campus_school_match(school_id)
);

DROP POLICY IF EXISTS p_operation_logs_select ON operation_logs;
CREATE POLICY p_operation_logs_select ON operation_logs
FOR SELECT
USING (
    campus_is_admin(current_setting('app.role', true))
    OR campus_school_match(school_id)
);

DROP POLICY IF EXISTS p_campus_admin_all_schools ON schools;
CREATE POLICY p_campus_admin_all_schools ON schools
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_campus_admin_all_users ON campus_users;
CREATE POLICY p_campus_admin_all_users ON campus_users
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_campus_admin_all_classes ON classes;
CREATE POLICY p_campus_admin_all_classes ON classes
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_campus_admin_all_students ON students;
CREATE POLICY p_campus_admin_all_students ON students
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_campus_admin_all_leaves ON leave_requests;
CREATE POLICY p_campus_admin_all_leaves ON leave_requests
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_campus_admin_all_meals ON meal_orders;
CREATE POLICY p_campus_admin_all_meals ON meal_orders
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_campus_admin_all_delivery ON delivery_confirmations;
CREATE POLICY p_campus_admin_all_delivery ON delivery_confirmations
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_campus_admin_all_repairs ON repair_tickets;
CREATE POLICY p_campus_admin_all_repairs ON repair_tickets
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_campus_admin_all_reminders ON reminder_tasks;
CREATE POLICY p_campus_admin_all_reminders ON reminder_tasks
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS p_campus_admin_all_logs ON operation_logs;
CREATE POLICY p_campus_admin_all_logs ON operation_logs
FOR ALL TO gaokao_api_admin
USING (true)
WITH CHECK (true);

GRANT SELECT ON schools, campus_users, classes, students, leave_requests, meal_orders, delivery_confirmations, repair_tickets, reminder_tasks, operation_logs TO gaokao_api_public;
GRANT SELECT ON schools, campus_users, classes, students, leave_requests, meal_orders, delivery_confirmations, repair_tickets, reminder_tasks, operation_logs TO gaokao_api_staff;
GRANT SELECT, INSERT, UPDATE, DELETE ON schools, campus_users, classes, students, leave_requests, meal_orders, delivery_confirmations, repair_tickets, reminder_tasks, operation_logs TO gaokao_api_admin;
