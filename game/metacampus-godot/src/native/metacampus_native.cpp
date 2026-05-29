#include "metacampus_native.h"

#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/variant/utility_functions.hpp>

using namespace godot;

void MetaCampusNative::_bind_methods() {
	ClassDB::bind_method(D_METHOD("get_poc_message"), &MetaCampusNative::get_poc_message);
}

MetaCampusNative::MetaCampusNative() {
}

MetaCampusNative::~MetaCampusNative() {
}

String MetaCampusNative::get_poc_message() const {
	return "Native PoC OK";
}
