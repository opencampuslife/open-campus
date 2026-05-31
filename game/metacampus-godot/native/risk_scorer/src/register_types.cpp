#include "register_types.h"
#include "risk_scorer.h"

namespace godot {

void initialize_risk_scorer_module(ModuleInitializationLevel p_level) {
    if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) {
        return;
    }

    ClassDB::register_class<RiskScorer>();
}

void uninitialize_risk_scorer_module(ModuleInitializationLevel p_level) {
    if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) {
        return;
    }
    // Nothing to unregister for simple Object-derived classes
}

} // namespace godot