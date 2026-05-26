from __future__ import annotations

from typing import Any


SYNONYMS: dict[str, list[str]] = {
    "学费": ["费用", "收费", "价格", "多少钱", "一年多少钱"],
    "报名": ["报名流程", "入学流程", "怎么报名", "报名条件", "报名材料", "入学测试", "预约测评"],
    "复读": ["高考复读", "全日制复读", "复读学校", "复读班", "复读课程"],
    "班型": ["课程类型", "全日制冲刺", "基础巩固", "个性化小班", "班型对比"],
    "手机": ["手机管理", "电子设备", "管理制度", "手机使用"],
    "住宿": ["宿舍", "寝室", "生活管理", "住校", "住宿条件", "几个人一间"],
    "老师": ["师资", "教师", "教研", "教学团队", "教学经验"],
    "食堂": ["餐饮", "饭菜", "伙食", "吃饭", "营养"],
    "管理": ["管理制度", "全日制管理", "封闭管理", "学生管理", "日常管理"],
    "提分": ["学习规划", "薄弱科目", "阶段测评", "补习", "进步", "成绩提升", "效果"],
    "退费": ["退费政策", "费用退还", "休学", "退款", "不读了"],
    "测评": ["评估", "学情诊断", "入学测试", "摸底考试", "评估流程"],
    "课程": ["全日制复读班", "教学安排", "课时", "课程体系", "上课"],
    "请假": ["请假制度", "请假流程", "怎么请假", "休学"],
    "安全": ["安全管理", "门禁", "校园安全", "封闭管理", "24小时"],
    "家长": ["家长会", "学情沟通", "学情反馈", "家校沟通"],
    "案例": ["学生案例", "复读案例", "成功案例", "往年情况"],
    "优惠": ["优惠价格", "折扣", "减免", "团报", "优惠活动"],
    "名额": ["学位", "招生名额", "满员", "还能报名"],
    "艺考": ["艺考生", "艺术生", "文化课", "艺术类"],
    "体育": ["体育生", "体育类", "体考"],
    "志愿": ["志愿填报", "高考报名", "录取"],
    "学籍": ["学籍问题", "高考报名资格", "报名条件"],
    "纪律": ["校规", "违纪", "处分", "管理制度"],
}

INTENT_KEYWORDS: dict[str, list[str]] = {
    "pricing_consulting": ["价格", "费用", "收费", "学费", "优惠"],
    "class_recommendation": ["班型", "课程", "班级", "适合", "推荐"],
    "enrollment_flow": ["报名", "流程", "办理", "入学"],
    "faq": ["说明", "介绍", "指南", "常见问题", "怎么样", "如何"],
}


def expand_query(query: str, intent: str = "faq") -> str:
    expanded = [query]

    for keyword, synonyms in SYNONYMS.items():
        if keyword in query:
            for syn in synonyms:
                if syn not in query:
                    expanded.append(syn)

    if intent in INTENT_KEYWORDS:
        for kw in INTENT_KEYWORDS[intent]:
            if kw not in " ".join(expanded):
                expanded.append(kw)

    return " ".join(expanded)


def expand_with_tags(query: str, business_tags: list[str]) -> str:
    parts = [query]
    parts.extend(business_tags)
    return " ".join(parts)
