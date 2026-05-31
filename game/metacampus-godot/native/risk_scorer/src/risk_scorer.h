#ifndef RISK_SCORER_H
#define RISK_SCORER_H

#include <godot_cpp/core/class_db.hpp>

namespace godot {

class RiskScorer : public Object {
    GDCLASS(RiskScorer, Object)

private:
    // Internal rule storage - using godot::Vector
    struct Rule {
        String pattern;
        int risk_score;        // 0-100
        String risk_level;     // "low", "medium", "high", "critical"
        String action;         // "allow", "revise", "escalate", "block"
        String category;
    };

    Vector<Rule> rules;

    void init_rules() {
        Rule r;
        
        r = Rule{"保证录取", 80, "high", "block", "admissions"};
        rules.append(r);
        r = Rule{"保证能上", 80, "high", "block", "admissions"};
        rules.append(r);
        r = Rule{"保证入学", 80, "high", "block", "admissions"};
        rules.append(r);
        r = Rule{"保证进来", 80, "high", "block", "admissions"};
        rules.append(r);
        r = Rule{"走关系", 95, "critical", "block", "compliance"};
        rules.append(r);
        r = Rule{"找人疏通", 95, "critical", "block", "compliance"};
        rules.append(r);
        r = Rule{"有关系", 90, "critical", "block", "compliance"};
        rules.append(r);
        r = Rule{"找找人", 90, "critical", "block", "compliance"};
        rules.append(r);
        r = Rule{"身份证", 75, "high", "escalate", "privacy"};
        rules.append(r);
        r = Rule{"手机号", 75, "high", "escalate", "privacy"};
        rules.append(r);
        r = Rule{"家庭住址", 75, "high", "escalate", "privacy"};
        rules.append(r);
        r = Rule{"户口本", 75, "high", "escalate", "privacy"};
        rules.append(r);
        r = Rule{"高考成绩", 60, "medium", "revise", "privacy"};
        rules.append(r);
        r = Rule{"获奖证书", 60, "medium", "revise", "privacy"};
        rules.append(r);
    }

    int evaluate_rule(const String& text, const Rule& rule) const {
        // Convert both strings to UTF-8 std::string for reliable comparison
        std::string text_utf8(text.utf8().ptr());
        std::string pattern_utf8(rule.pattern.utf8().ptr());
        
        // Use std::string::find for substring search
        if (text_utf8.find(pattern_utf8) != std::string::npos) {
            return rule.risk_score;
        }
        return 0;
    }

public:
    RiskScorer() {
        init_rules();
    }

    ~RiskScorer() {}

    Dictionary evaluate_text(const String& question, const String& answer,
                             const Dictionary& context);

    static void _bind_methods() {
        ClassDB::bind_method(D_METHOD("evaluate_text", "question", "answer", "context"),
                            &RiskScorer::evaluate_text);
    }
};

} // namespace godot

#endif // RISK_SCORER_H