INSERT INTO schools (school_id, name, wecom_corp_id, wecom_agent_id, encrypted_app_secret, status)
VALUES ('school_demo', '演示校园', 'demo-corp', '1000001', 'encrypted-demo', 'active')
ON CONFLICT (school_id) DO NOTHING;

INSERT INTO classes (class_id, school_id, grade, name, head_teacher_id)
VALUES ('class_g7_1', 'school_demo', '七年级', '七年级1班', 'user_teacher_001')
ON CONFLICT (class_id) DO NOTHING;

INSERT INTO campus_users (user_id, school_id, wecom_userid, name, role, class_id, status)
VALUES
    ('user_teacher_001', 'school_demo', 'teacher_001', '班主任李老师', 'head_teacher', 'class_g7_1', 'active'),
    ('user_academic_001', 'school_demo', 'academic_001', '教务王老师', 'academic_staff', NULL, 'active'),
    ('user_logistics_001', 'school_demo', 'logistics_001', '后勤张老师', 'logistics_staff', NULL, 'active'),
    ('user_repair_001', 'school_demo', 'repair_001', '维修陈师傅', 'repair_assignee', NULL, 'active')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO students (student_id, school_id, class_id, name, student_no, parent_name, parent_mobile_hash, parent_userid, status)
VALUES ('student_demo_001', 'school_demo', 'class_g7_1', '张小明', '2026001', '张家长', 'hashed', 'parent_demo_001', 'active')
ON CONFLICT (student_id) DO NOTHING;

INSERT INTO leave_requests (leave_id, school_id, student_id, class_id, type, start_time, end_time, reason, status)
VALUES ('leave_demo_001', 'school_demo', 'student_demo_001', 'class_g7_1', 'sick', now(), now() + interval '8 hours', '发烧请假', 'pending')
ON CONFLICT (leave_id) DO NOTHING;

INSERT INTO delivery_confirmations (delivery_id, school_id, meal_date, meal_type, vendor_id, total_count, special_count, status, token_hash)
VALUES ('delivery_20260525', 'school_demo', DATE '2026-05-25', 'lunch', 'vendor_demo', 10, 1, 'locked', 'vendor_token_hash_demo')
ON CONFLICT (delivery_id) DO NOTHING;
