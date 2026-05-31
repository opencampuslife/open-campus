#include "risk_scorer.h"
#include <godot_cpp/core/method_bind.hpp>

namespace godot {

using namespace godot;

Dictionary RiskScorer::evaluate_text(const String& p_question,
                                       const String& p_answer,
                                       const Dictionary& p_context) {
    Dictionary result;

    // Debug: log rules size
    int rules_count = rules.size();
    print_line("RiskScorer: rules.size() = %d", rules_count);
    
    // Combine question + answer for evaluation
    String space = " ";
    String combined_text = p_question + space + p_answer;
    
    // Debug: check answer length and content
    print_line("RiskScorer: answer length = %d", p_answer.length());
    print_line("RiskScorer: combined length = %d", combined_text.length());
    
    // Debug: check if the pattern "保证录取" exists in combined_text
    String test_pattern = "保证录取";
    std::string test_pattern_utf8(test_pattern.utf8().ptr());
    std::string combined_utf8(combined_text.utf8().ptr());
    print_line("RiskScorer: test_pattern_utf8 size=%d", (int)test_pattern_utf8.size());
    print_line("RiskScorer: combined_utf8 size=%d", (int)combined_utf8.size());
    bool has_pattern = combined_utf8.find(test_pattern_utf8) != std::string::npos;
    print_line("RiskScorer: has_pattern=%d", has_pattern ? 1 : 0);
    
    int max_score = 0;
    String matched_level = "low";
    String recommended_action = "allow";
    Vector<String> triggered_rules;
    int compliance_delta = 0;
    int parent_trust_delta = 0;
    int stability_delta = 0;

    // Evaluate against rules
    bool rules_triggered = false;
    for (int i = 0; i < rules.size(); i++) {
        const Rule& rule = rules[i];
        int score = evaluate_rule(combined_text, rule);
        if (score > max_score) {
            max_score = score;
            matched_level = rule.risk_level;
            recommended_action = rule.action;
            rules_triggered = true;
            
            // Build triggered rule string
            String paren_open = " (";
            String paren_close = ")";
            String rule_desc = rule.pattern + paren_open + rule.risk_level + paren_close;
            triggered_rules.append(rule_desc);

            // Calculate metric deltas based on risk level and action
            if (rule.action == "block") {
                compliance_delta -= 15;
                parent_trust_delta -= 5;
                stability_delta -= 10;
            } else if (rule.action == "escalate") {
                compliance_delta -= 5;
                parent_trust_delta += 0;
                stability_delta -= 3;
            } else if (rule.action == "revise") {
                compliance_delta -= 2;
                parent_trust_delta += 1;
                stability_delta -= 1;
            }
        }
    }

    print_line("RiskScorer: after rules loop, max_score = %d, rules_triggered = %s", 
               max_score, rules_triggered ? "true" : "false");
    print_line("RiskScorer: triggered_rules count = %d", triggered_rules.size());

    // Check for empty/short answers - only if no rules triggered
    if (!rules_triggered && (p_answer.is_empty() || p_answer.length() < 10)) {
        max_score = 50;
        matched_level = "medium";
        recommended_action = "revise";
        triggered_rules.append("回答过短或为空");
    }

    // Check citation requirement from context - only if no rules triggered
    if (!rules_triggered) {
        String scenario = p_context.get("scenario", String("general"));
        int citation_count = p_context.get("citation_count", -1);  // -1 means not provided

        if (scenario.find("admissions") != -1 && citation_count == 0) {
            if (max_score < 40) {
                max_score = 40;
                matched_level = "medium";
                recommended_action = "revise";
                triggered_rules.append("招生场景无引用来源");
            }
        }
    }

    // Build result dictionary
    result["risk_score"] = max_score;
    result["risk_level"] = matched_level;
    
    // Convert Vector<String> to PackedStringArray
    PackedStringArray rules_array;
    for (int i = 0; i < triggered_rules.size(); i++) {
        rules_array.append(triggered_rules[i]);
    }
    result["triggered_rules"] = rules_array;
    
    result["recommended_action"] = recommended_action;
    result["compliance_delta"] = compliance_delta;
    result["parent_trust_delta"] = parent_trust_delta;
    result["stability_delta"] = stability_delta;

    return result;
}

} // namespace godot