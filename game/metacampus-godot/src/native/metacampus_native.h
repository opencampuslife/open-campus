#ifndef METACAMPUS_NATIVE_H
#define METACAMPUS_NATIVE_H

#include <godot_cpp/classes/node.hpp>

namespace godot {

class MetaCampusNative : public Node {
	GDCLASS(MetaCampusNative, Node)

protected:
	static void _bind_methods();

public:
	MetaCampusNative();
	~MetaCampusNative();

	String get_poc_message() const;
};

} // namespace godot

#endif // METACAMPUS_NATIVE_H
