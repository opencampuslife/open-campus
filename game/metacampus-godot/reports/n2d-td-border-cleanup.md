# N2D TD-1: PNG Border Transparency Report

## Method
Pure stdlib (struct+zlib) PNG parsing of 88 NPC PNGs. Extracts border ring (top/bottom rows + left/right cols) alpha channel per file.

## Per-NPC Results

### admissions_director

| File | Result |
|------|--------|
| admissions_director_walk_down.png | ⚠ 586/636 opaque (92.1%) |
| admissions_director_walk_left.png | ⚠ 596/636 opaque (93.7%) |
| admissions_director_walk_right.png | ⚠ 577/636 opaque (90.7%) |
| admissions_director_walk_up.png | ⚠ 563/636 opaque (88.5%) |
| portrait_happy.png | ⚠ 944/1020 opaque (92.5%) |
| portrait_neutral.png | ⚠ 858/1020 opaque (84.1%) |
| portrait_strict.png | ⚠ 926/1020 opaque (90.8%) |
| portrait_worried.png | ⚠ 878/1020 opaque (86.1%) |
| sprite_idle.png | ⚠ 210/252 opaque (83.3%) |

### compliance_officer

| File | Result |
|------|--------|
| compliance_officer_walk_down.png | ⚠ 605/636 opaque (95.1%) |
| compliance_officer_walk_left.png | ⚠ 605/636 opaque (95.1%) |
| compliance_officer_walk_right.png | ⚠ 605/636 opaque (95.1%) |
| compliance_officer_walk_up.png | ⚠ 605/636 opaque (95.1%) |
| portrait_happy.png | ⚠ 880/1020 opaque (86.3%) |
| portrait_neutral.png | ⚠ 902/1020 opaque (88.4%) |
| portrait_strict.png | ⚠ 917/1020 opaque (89.9%) |
| portrait_worried.png | ⚠ 926/1020 opaque (90.8%) |
| sprite_idle.png | ⚠ 235/252 opaque (93.3%) |

### homeroom_teacher

| File | Result |
|------|--------|
| homeroom_teacher_walk_down.png | ⚠ 606/636 opaque (95.3%) |
| homeroom_teacher_walk_left.png | ⚠ 606/636 opaque (95.3%) |
| homeroom_teacher_walk_right.png | ⚠ 606/636 opaque (95.3%) |
| homeroom_teacher_walk_up.png | ⚠ 606/636 opaque (95.3%) |
| portrait_happy.png | ⚠ 928/1020 opaque (91.0%) |
| portrait_neutral.png | ⚠ 880/1020 opaque (86.3%) |
| portrait_strict.png | ⚠ 889/1020 opaque (87.2%) |
| portrait_worried.png | ⚠ 934/1020 opaque (91.6%) |
| sprite_idle.png | ⚠ 237/252 opaque (94.0%) |

### it_operator

| File | Result |
|------|--------|
| it_operator_walk_down.png | ⚠ 580/636 opaque (91.2%) |
| it_operator_walk_left.png | ⚠ 580/636 opaque (91.2%) |
| it_operator_walk_right.png | ⚠ 580/636 opaque (91.2%) |
| it_operator_walk_up.png | ⚠ 580/636 opaque (91.2%) |
| portrait_happy.png | ⚠ 851/1020 opaque (83.4%) |
| portrait_neutral.png | ⚠ 895/1020 opaque (87.7%) |
| portrait_strict.png | ⚠ 904/1020 opaque (88.6%) |
| portrait_worried.png | ⚠ 817/1020 opaque (80.1%) |
| sprite_idle.png | ⚠ 235/252 opaque (93.3%) |

### logistics_manager

| File | Result |
|------|--------|
| logistics_manager_walk_down.png | ⚠ 594/636 opaque (93.4%) |
| logistics_manager_walk_left.png | ⚠ 594/636 opaque (93.4%) |
| logistics_manager_walk_right.png | ⚠ 594/636 opaque (93.4%) |
| logistics_manager_walk_up.png | ⚠ 594/636 opaque (93.4%) |
| portrait_happy.png | ⚠ 950/1020 opaque (93.1%) |
| portrait_neutral.png | ⚠ 949/1020 opaque (93.0%) |
| portrait_strict.png | ⚠ 898/1020 opaque (88.0%) |
| portrait_worried.png | ⚠ 836/1020 opaque (82.0%) |
| sprite_idle.png | ⚠ 242/252 opaque (96.0%) |

### parent_representative

| File | Result |
|------|--------|
| parent_representative_walk_down.png | ⚠ 3/636 opaque (0.5%) |
| parent_representative_walk_left.png | ⚠ 3/636 opaque (0.5%) |
| parent_representative_walk_right.png | ⚠ 3/636 opaque (0.5%) |
| parent_representative_walk_up.png | ⚠ 3/636 opaque (0.5%) |
| portrait_happy.png | ⚠ 1020/1020 opaque (100.0%) |
| portrait_neutral.png | ERROR: not valid RGBA PNG |
| portrait_strict.png | ⚠ 1020/1020 opaque (100.0%) |
| portrait_worried.png | ⚠ 1020/1020 opaque (100.0%) |
| sprite_idle.png | ✓ |

### principal

| File | Result |
|------|--------|
| portrait_happy.png | ⚠ 1020/1020 opaque (100.0%) |
| portrait_neutral.png | ERROR: not valid RGBA PNG |
| portrait_strict.png | ⚠ 1020/1020 opaque (100.0%) |
| portrait_worried.png | ⚠ 1020/1020 opaque (100.0%) |
| principal_walk_down.png | ⚠ 4/636 opaque (0.6%) |
| principal_walk_left.png | ⚠ 4/636 opaque (0.6%) |
| principal_walk_right.png | ⚠ 4/636 opaque (0.6%) |
| principal_walk_up.png | ⚠ 4/636 opaque (0.6%) |
| sprite_idle.png | ⚠ 5/252 opaque (2.0%) |

### student_representative

| File | Result |
|------|--------|
| portrait_happy.png | ⚠ 944/1020 opaque (92.5%) |
| portrait_neutral.png | ⚠ 791/1020 opaque (77.5%) |
| portrait_strict.png | ⚠ 917/1020 opaque (89.9%) |
| portrait_worried.png | ✓ |
| sprite_idle.png | ⚠ 224/252 opaque (88.9%) |
| student_representative_walk_down.png | ⚠ 614/636 opaque (96.5%) |
| student_representative_walk_left.png | ⚠ 581/636 opaque (91.4%) |
| student_representative_walk_right.png | ⚠ 561/636 opaque (88.2%) |
| student_representative_walk_up.png | ⚠ 591/636 opaque (92.9%) |

## Summary

**Verdict: FAIL — opaque border pixels found**

PNGs with opaque borders:

- `admissions_director/portrait_neutral.png`: ⚠ 858/1020 opaque (84.1%)
- `admissions_director/portrait_happy.png`: ⚠ 944/1020 opaque (92.5%)
- `admissions_director/portrait_worried.png`: ⚠ 878/1020 opaque (86.1%)
- `admissions_director/portrait_strict.png`: ⚠ 926/1020 opaque (90.8%)
- `admissions_director/sprite_idle.png`: ⚠ 210/252 opaque (83.3%)
- `admissions_director/admissions_director_walk_down.png`: ⚠ 586/636 opaque (92.1%)
- `admissions_director/admissions_director_walk_left.png`: ⚠ 596/636 opaque (93.7%)
- `admissions_director/admissions_director_walk_right.png`: ⚠ 577/636 opaque (90.7%)
- `admissions_director/admissions_director_walk_up.png`: ⚠ 563/636 opaque (88.5%)
- `compliance_officer/portrait_neutral.png`: ⚠ 902/1020 opaque (88.4%)
- `compliance_officer/portrait_happy.png`: ⚠ 880/1020 opaque (86.3%)
- `compliance_officer/portrait_worried.png`: ⚠ 926/1020 opaque (90.8%)
- `compliance_officer/portrait_strict.png`: ⚠ 917/1020 opaque (89.9%)
- `compliance_officer/sprite_idle.png`: ⚠ 235/252 opaque (93.3%)
- `compliance_officer/compliance_officer_walk_down.png`: ⚠ 605/636 opaque (95.1%)
- `compliance_officer/compliance_officer_walk_left.png`: ⚠ 605/636 opaque (95.1%)
- `compliance_officer/compliance_officer_walk_right.png`: ⚠ 605/636 opaque (95.1%)
- `compliance_officer/compliance_officer_walk_up.png`: ⚠ 605/636 opaque (95.1%)
- `homeroom_teacher/portrait_neutral.png`: ⚠ 880/1020 opaque (86.3%)
- `homeroom_teacher/portrait_happy.png`: ⚠ 928/1020 opaque (91.0%)
- `homeroom_teacher/portrait_worried.png`: ⚠ 934/1020 opaque (91.6%)
- `homeroom_teacher/portrait_strict.png`: ⚠ 889/1020 opaque (87.2%)
- `homeroom_teacher/sprite_idle.png`: ⚠ 237/252 opaque (94.0%)
- `homeroom_teacher/homeroom_teacher_walk_down.png`: ⚠ 606/636 opaque (95.3%)
- `homeroom_teacher/homeroom_teacher_walk_left.png`: ⚠ 606/636 opaque (95.3%)
- `homeroom_teacher/homeroom_teacher_walk_right.png`: ⚠ 606/636 opaque (95.3%)
- `homeroom_teacher/homeroom_teacher_walk_up.png`: ⚠ 606/636 opaque (95.3%)
- `it_operator/portrait_neutral.png`: ⚠ 895/1020 opaque (87.7%)
- `it_operator/portrait_happy.png`: ⚠ 851/1020 opaque (83.4%)
- `it_operator/portrait_worried.png`: ⚠ 817/1020 opaque (80.1%)
- `it_operator/portrait_strict.png`: ⚠ 904/1020 opaque (88.6%)
- `it_operator/sprite_idle.png`: ⚠ 235/252 opaque (93.3%)
- `it_operator/it_operator_walk_down.png`: ⚠ 580/636 opaque (91.2%)
- `it_operator/it_operator_walk_left.png`: ⚠ 580/636 opaque (91.2%)
- `it_operator/it_operator_walk_right.png`: ⚠ 580/636 opaque (91.2%)
- `it_operator/it_operator_walk_up.png`: ⚠ 580/636 opaque (91.2%)
- `logistics_manager/portrait_neutral.png`: ⚠ 949/1020 opaque (93.0%)
- `logistics_manager/portrait_happy.png`: ⚠ 950/1020 opaque (93.1%)
- `logistics_manager/portrait_worried.png`: ⚠ 836/1020 opaque (82.0%)
- `logistics_manager/portrait_strict.png`: ⚠ 898/1020 opaque (88.0%)
- `logistics_manager/sprite_idle.png`: ⚠ 242/252 opaque (96.0%)
- `logistics_manager/logistics_manager_walk_down.png`: ⚠ 594/636 opaque (93.4%)
- `logistics_manager/logistics_manager_walk_left.png`: ⚠ 594/636 opaque (93.4%)
- `logistics_manager/logistics_manager_walk_right.png`: ⚠ 594/636 opaque (93.4%)
- `logistics_manager/logistics_manager_walk_up.png`: ⚠ 594/636 opaque (93.4%)
- `parent_representative/portrait_happy.png`: ⚠ 1020/1020 opaque (100.0%)
- `parent_representative/portrait_worried.png`: ⚠ 1020/1020 opaque (100.0%)
- `parent_representative/portrait_strict.png`: ⚠ 1020/1020 opaque (100.0%)
- `parent_representative/parent_representative_walk_down.png`: ⚠ 3/636 opaque (0.5%)
- `parent_representative/parent_representative_walk_left.png`: ⚠ 3/636 opaque (0.5%)
- `parent_representative/parent_representative_walk_right.png`: ⚠ 3/636 opaque (0.5%)
- `parent_representative/parent_representative_walk_up.png`: ⚠ 3/636 opaque (0.5%)
- `principal/portrait_happy.png`: ⚠ 1020/1020 opaque (100.0%)
- `principal/portrait_worried.png`: ⚠ 1020/1020 opaque (100.0%)
- `principal/portrait_strict.png`: ⚠ 1020/1020 opaque (100.0%)
- `principal/sprite_idle.png`: ⚠ 5/252 opaque (2.0%)
- `principal/principal_walk_down.png`: ⚠ 4/636 opaque (0.6%)
- `principal/principal_walk_left.png`: ⚠ 4/636 opaque (0.6%)
- `principal/principal_walk_right.png`: ⚠ 4/636 opaque (0.6%)
- `principal/principal_walk_up.png`: ⚠ 4/636 opaque (0.6%)
- `student_representative/portrait_neutral.png`: ⚠ 791/1020 opaque (77.5%)
- `student_representative/portrait_happy.png`: ⚠ 944/1020 opaque (92.5%)
- `student_representative/portrait_strict.png`: ⚠ 917/1020 opaque (89.9%)
- `student_representative/sprite_idle.png`: ⚠ 224/252 opaque (88.9%)
- `student_representative/student_representative_walk_down.png`: ⚠ 614/636 opaque (96.5%)
- `student_representative/student_representative_walk_left.png`: ⚠ 581/636 opaque (91.4%)
- `student_representative/student_representative_walk_right.png`: ⚠ 561/636 opaque (88.2%)
- `student_representative/student_representative_walk_up.png`: ⚠ 591/636 opaque (92.9%)
