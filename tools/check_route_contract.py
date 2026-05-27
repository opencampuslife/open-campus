from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_ROUTE_FIELDS = {
    "method",
    "path",
    "owner",
    "surface",
    "visibility",
    "auth",
    "csrf",
    "rate_limit",
    "audit",
    "backend",
    "request_schema",
    "response_schema",
    "migration_wave",
    "legacy_flags",
    "openapi",
    "openapi_ref",
}
ADMIN_LEGACY_GAP_FLAGS = {"legacy_policy_gap", "state_changing_get", "deprecated_compatibility_alias"}
MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SCHEMA_TYPES = {
    "array": list,
    "boolean": bool,
    "integer": int,
    "object": dict,
    "string": str,
}


def load_json_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            raise ValueError(f"invalid JSON/YAML {path}: install PyYAML or use JSON format") from None
        except Exception as exc:
            raise ValueError(f"invalid YAML {path}: {exc}") from exc


def validate_schema_node(value: Any, schema: dict[str, Any], location: str) -> list[str]:
    errors: list[str] = []
    schema_type = schema.get("type")
    if schema_type:
        expected_type = SCHEMA_TYPES.get(str(schema_type))
        if expected_type and not isinstance(value, expected_type):
            return [f"{location} must be {schema_type}"]
    if isinstance(value, str):
        if schema.get("minLength") and len(value) < int(schema["minLength"]):
            errors.append(f"{location} must not be empty")
        if "pattern" in schema and not re.search(str(schema["pattern"]), value):
            errors.append(f"{location} does not match {schema['pattern']}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location} must be one of {', '.join(map(str, schema['enum']))}")
    if isinstance(value, dict):
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"{location} missing required field {field}")
        properties = schema.get("properties", {})
        for field, field_value in value.items():
            if field in properties:
                errors.extend(validate_schema_node(field_value, properties[field], f"{location}.{field}"))
    if isinstance(value, list):
        item_schema = schema.get("items")
        if schema.get("minItems") and len(value) < int(schema["minItems"]):
            errors.append(f"{location} must have at least {schema['minItems']} item(s)")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate_schema_node(item, item_schema, f"{location}[{index}]"))
    return errors


def validate_route_schema(root: Path, contract: dict[str, Any]) -> list[str]:
    schema = load_json_yaml(root / "contracts" / "schemas" / "routes.schema.json")
    return validate_schema_node(contract, schema, "routes.yaml")


def normalize_template(path: str) -> str:
    # Convert {expression} style (Python f-string in server.py) to {param}.
    path = re.sub(r"\{[^{}]+\}", "{param}", path)
    if "{param}" not in path:
        return path
    # Has {param}: extract the catch-all prefix (everything before {param}).
    # This allows /api/knowledge/{param} and /api/knowledge/session-context
    # to both normalize to /api/knowledge/ and match each other.
    m = re.match(r"^(.+)/\{param\}.*$", path)
    if m:
        return m.group(1) + "/"
    return path


def openapi_parameter_names(parameters: list[dict[str, Any]], document: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    components = document.get("components", {}).get("parameters", {})
    for parameter in parameters:
        if "$ref" in parameter:
            referenced_name = str(parameter["$ref"]).rsplit("/", 1)[-1]
            parameter = components.get(referenced_name, {})
        if parameter.get("in") == "path" and parameter.get("name"):
            names.add(str(parameter["name"]))
    return names


def check_openapi_document(document_path: str, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("openapi") != "3.1.0" or not document.get("info"):
        errors.append(f"invalid OpenAPI header in {document_path}")
    for path, path_item in document.get("paths", {}).items():
        expected = set(re.findall(r"\{([^{}]+)\}", path))
        if not expected:
            continue
        path_parameters = openapi_parameter_names(path_item.get("parameters", []), document)
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            declared = path_parameters | openapi_parameter_names(operation.get("parameters", []), document)
            missing = expected - declared
            if missing:
                errors.append(
                    f"OpenAPI path parameters missing in {document_path} {method.upper()} {path}: "
                    f"{', '.join(sorted(missing))}"
                )
    return errors


def expression_value(node: ast.expr, constants: dict[str, object]) -> object | None:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return constants.get(node.attr)
    return None


def class_constants(class_node: ast.ClassDef) -> dict[str, object]:
    values: dict[str, object] = {}
    for statement in class_node.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            values[target.id] = statement.value.value
        elif isinstance(statement.value, ast.Set):
            entries = {
                item.value
                for item in statement.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            }
            values[target.id] = entries
    return values


def is_path_node(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "path"


def path_equals_or_membership(node: ast.expr, constants: dict[str, object]) -> list[str]:
    if not isinstance(node, ast.Compare) or not is_path_node(node.left) or len(node.ops) != 1 or len(node.comparators) != 1:
        return []
    value = expression_value(node.comparators[0], constants)
    if isinstance(node.ops[0], ast.Eq) and isinstance(value, str):
        return [value] if value else []
    if isinstance(node.ops[0], ast.In) and isinstance(value, set):
        return sorted(item for item in value if isinstance(item, str) and item)
    return []


def path_call_value(node: ast.expr, method_name: str) -> str | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr != method_name or not is_path_node(node.func.value) or len(node.args) != 1:
        return None
    value = node.args[0]
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def extract_condition_paths(node: ast.expr, constants: dict[str, object]) -> list[str]:
    exact = path_equals_or_membership(node, constants)
    if exact:
        return exact
    prefix = path_call_value(node, "startswith")
    if prefix is not None:
        return [f"{prefix}{{param}}"]
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        paths: list[str] = []
        for value in node.values:
            paths.extend(extract_condition_paths(value, constants))
        return paths
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        exact_paths: list[str] = []
        prefix_value: str | None = None
        suffix_value: str | None = None
        for value in node.values:
            exact_paths.extend(path_equals_or_membership(value, constants))
            prefix_value = prefix_value or path_call_value(value, "startswith")
            suffix_value = suffix_value or path_call_value(value, "endswith")
        if exact_paths:
            return exact_paths
        if prefix_value:
            return [f"{prefix_value}{{param}}{suffix_value or ''}"]
    return []


def extract_legacy_routes(server_path: Path) -> set[tuple[str, str]]:
    tree = ast.parse(server_path.read_text(encoding="utf-8"), filename=str(server_path))
    handler = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "GaokaoHandler"
    )
    constants = class_constants(handler)
    routes: set[tuple[str, str]] = set()
    for function in handler.body:
        if not isinstance(function, ast.FunctionDef) or not function.name.startswith("do_"):
            continue
        method = function.name.removeprefix("do_")
        for node in ast.walk(function):
            if not isinstance(node, ast.If):
                continue
            for path in extract_condition_paths(node.test, constants):
                routes.add((method, normalize_template(path)))
    return routes


def check_route_contract(root: Path) -> list[str]:
    errors: list[str] = []
    contract = load_json_yaml(root / "contracts" / "routes.yaml")
    errors.extend(validate_route_schema(root, contract))
    entries = contract.get("routes", [])
    contract_routes: set[tuple[str, str]] = set()
    documents: dict[str, dict[str, Any]] = {}
    entries_by_key: dict[tuple[str, str], dict[str, Any]] = {
        (str(entry["method"]).upper(), normalize_template(str(entry["path"]))): entry
        for entry in entries
        if {"method", "path"} <= set(entry)
    }
    for index, entry in enumerate(entries, start=1):
        missing = REQUIRED_ROUTE_FIELDS - set(entry)
        if missing:
            errors.append(f"route entry {index} missing fields: {', '.join(sorted(missing))}")
            continue
        key = (str(entry["method"]).upper(), normalize_template(str(entry["path"])))
        if key in contract_routes:
            errors.append(f"duplicate route entry: {key[0]} {entry['path']}")
        contract_routes.add(key)
        mutation = bool(entry.get("mutation")) or key[0] in MUTATION_METHODS
        legacy_flags = set(entry.get("legacy_flags", []))
        if mutation and entry["audit"] is not True:
            errors.append(f"mutation route must set audit=true: {key[0]} {entry['path']}")
        if (
            mutation
            and str(entry["path"]).startswith("/api/admin/")
            and entry["csrf"] != "required"
            and not (key[0] == "GET" and "state_changing_get" in legacy_flags)
        ):
            errors.append(f"admin mutation must set csrf=required: {key[0]} {entry['path']}")
        if legacy_flags & ADMIN_LEGACY_GAP_FLAGS:
            errors.extend(validate_admin_legacy_gap(entry, key, entries_by_key))
        if entry["surface"] != entry["visibility"]:
            errors.append(f"surface/visibility mismatch: {key[0]} {entry['path']}")
        if entry["openapi_ref"] != entry["openapi"]:
            errors.append(f"openapi_ref/openapi mismatch: {key[0]} {entry['path']}")
        document_path = str(entry["openapi_ref"])
        if document_path not in documents:
            documents[document_path] = load_json_yaml(root / document_path)
        paths = documents[document_path].get("paths", {})
        if entry["path"] not in paths or str(entry["method"]).lower() not in paths.get(entry["path"], {}):
            errors.append(f"OpenAPI operation missing for {key[0]} {entry['path']} in {document_path}")

    for document_path, document in documents.items():
        errors.extend(check_openapi_document(document_path, document))

    actual_routes = extract_legacy_routes(root / "services" / "api-gateway" / "src" / "server.py")
    for method, path in sorted(actual_routes - contract_routes):
        errors.append(f"unregistered legacy gateway route branch: {method} {path}")
    for method, path in sorted(contract_routes - actual_routes):
        errors.append(f"route inventory does not map to a legacy gateway branch: {method} {path}")
    return errors


def validate_admin_legacy_gap(
    entry: dict[str, Any],
    key: tuple[str, str],
    entries_by_key: dict[tuple[str, str], dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    path = str(entry["path"])
    method = str(entry["method"]).upper()
    legacy_flags = set(entry.get("legacy_flags", []))
    legacy_exit = entry.get("legacy_exit")
    replacement = entry.get("replacement")
    deprecation = entry.get("deprecation")
    legacy_exit_obj = legacy_exit if isinstance(legacy_exit, dict) else None
    replacement_obj = replacement if isinstance(replacement, dict) else None
    deprecation_obj = deprecation if isinstance(deprecation, dict) else None
    if "legacy_policy_gap" in legacy_flags and not legacy_exit:
        errors.append(f"legacy policy gap must define legacy_exit: {key[0]} {path}")
    if legacy_exit is not None and not isinstance(legacy_exit, dict):
        errors.append(f"legacy_exit must be an object: {key[0]} {path}")
    if "state_changing_get" in legacy_flags:
        if method != "GET":
            errors.append(f"state_changing_get must remain a GET route: {key[0]} {path}")
        if not bool(entry.get("mutation")):
            errors.append(f"state_changing_get must be marked mutation=true: {key[0]} {path}")
        if entry.get("csrf") != "none":
            errors.append(f"state_changing_get legacy alias must set csrf=none: {key[0]} {path}")
        if legacy_exit_obj is None:
            errors.append(f"state_changing_get must define legacy_exit: {key[0]} {path}")
        else:
            if legacy_exit_obj.get("cutover_blocker") is not True:
                errors.append(f"state_changing_get legacy_exit must set cutover_blocker=true: {key[0]} {path}")
        if replacement_obj is None:
            errors.append(f"state_changing_get must define replacement: {key[0]} {path}")
        else:
            if str(replacement_obj.get("method", "")).upper() != "POST":
                errors.append(f"state_changing_get replacement must use POST: {key[0]} {path}")
            if normalize_template(str(replacement_obj.get("path", ""))) != normalize_template(path):
                errors.append(f"state_changing_get replacement path must match GET path: {key[0]} {path}")
            if replacement_obj.get("target_phase") not in {"PR-3B", "PR-3"}:
                errors.append(f"state_changing_get replacement must target PR-3B or PR-3: {key[0]} {path}")
            status = replacement_obj.get("status")
            if status not in {"planned", "implemented"}:
                errors.append(f"state_changing_get replacement must be planned or implemented: {key[0]} {path}")
            if replacement_obj.get("csrf") != "required":
                errors.append(f"state_changing_get replacement must require csrf: {key[0]} {path}")
            if replacement_obj.get("audit") is not True:
                errors.append(f"state_changing_get replacement must require audit=true: {key[0]} {path}")
            if replacement_obj.get("idempotency") not in {None, "recommended", "required"}:
                errors.append(f"state_changing_get replacement idempotency must be recommended or required: {key[0]} {path}")
            if status == "implemented":
                replacement_key = (str(replacement_obj.get("method", "")).upper(), normalize_template(str(replacement_obj.get("path", ""))))
                replacement_entry = entries_by_key.get(replacement_key)
                if replacement_entry is None:
                    errors.append(f"implemented replacement must exist in routes.yaml: {key[0]} {path}")
                else:
                    if replacement_entry.get("csrf") != "required":
                        errors.append(f"implemented replacement route must set csrf=required: {replacement_key[0]} {replacement_entry['path']}")
                    if replacement_entry.get("audit") is not True:
                        errors.append(f"implemented replacement route must set audit=true: {replacement_key[0]} {replacement_entry['path']}")
                    replaces = replacement_entry.get("replaces")
                    if not isinstance(replaces, dict):
                        errors.append(f"implemented replacement must define replaces: {replacement_key[0]} {replacement_entry['path']}")
                    else:
                        if str(replaces.get("method", "")).upper() != "GET":
                            errors.append(f"implemented replacement replaces.method must be GET: {replacement_key[0]} {replacement_entry['path']}")
                        if normalize_template(str(replaces.get("path", ""))) != normalize_template(path):
                            errors.append(f"implemented replacement replaces.path must match legacy GET: {replacement_key[0]} {replacement_entry['path']}")
                if "deprecated_compatibility_alias" not in legacy_flags:
                    errors.append(f"implemented replacement legacy route must set deprecated_compatibility_alias: {key[0]} {path}")
                if "legacy_policy_gap" in legacy_flags:
                    errors.append(f"implemented replacement legacy route must drop legacy_policy_gap: {key[0]} {path}")
                if deprecation_obj is None:
                    errors.append(f"implemented replacement legacy route must define deprecation metadata: {key[0]} {path}")
                else:
                    if str(deprecation_obj.get("successor_method", "")).upper() != "POST":
                        errors.append(f"deprecation.successor_method must be POST: {key[0]} {path}")
                    if normalize_template(str(deprecation_obj.get("successor_path", ""))) != normalize_template(path):
                        errors.append(f"deprecation.successor_path must match legacy GET path: {key[0]} {path}")
                    if deprecation_obj.get("header") != "Deprecation":
                        errors.append(f"deprecation.header must be Deprecation: {key[0]} {path}")
    return errors


def route_inventory(root: Path) -> dict[str, int]:
    contract = load_json_yaml(root / "contracts" / "routes.yaml")
    entries = contract.get("routes", [])
    contract_routes = {
        (str(entry["method"]).upper(), normalize_template(str(entry["path"])))
        for entry in entries
    }
    actual_routes = extract_legacy_routes(root / "services" / "api-gateway" / "src" / "server.py")
    admin_mutations = [
        entry
        for entry in entries
        if str(entry["path"]).startswith("/api/admin/")
        and (bool(entry.get("mutation")) or str(entry["method"]).upper() in MUTATION_METHODS)
    ]

    def replacement_status(entry: dict[str, Any]) -> str | None:
        replacement = entry.get("replacement")
        if isinstance(replacement, dict):
            value = replacement.get("status")
            return str(value) if value is not None else None
        return None

    return {
        "total routes": len(entries),
        "registered routes": len(contract_routes & actual_routes),
        "admin mutations": len(admin_mutations),
        "csrf required": sum(1 for entry in entries if entry.get("csrf") == "required"),
        "legacy gaps": sum(1 for entry in entries if "legacy_policy_gap" in entry.get("legacy_flags", [])),
        "state-changing GET gaps": sum(
            1
            for entry in entries
            if "state_changing_get" in entry.get("legacy_flags", [])
            and replacement_status(entry) != "implemented"
        ),
        "deprecated compatibility aliases": sum(
            1 for entry in entries if "deprecated_compatibility_alias" in entry.get("legacy_flags", [])
        ),
        "legacy usage tracking enabled": sum(
            1 for entry in entries if entry.get("legacy_usage_tracking", {}).get("status") == "enabled"
        ),
        "unowned routes": sum(1 for entry in entries if not entry.get("owner")),
        "unmapped openapi paths": sum(
            1
            for entry in entries
            if entry.get("openapi_ref")
            and (
                entry["path"] not in load_json_yaml(root / str(entry["openapi_ref"])).get("paths", {})
                or str(entry["method"]).lower()
                not in load_json_yaml(root / str(entry["openapi_ref"])).get("paths", {}).get(entry["path"], {})
            )
        ),
    }


def check_admin_proxy_guard(root: Path, allowlist: str) -> list[str]:
    if not allowlist or not allowlist.strip():
        return []
    contract = load_json_yaml(root / "contracts" / "routes.yaml")
    entries_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in contract.get("routes", []):
        key = (str(entry["method"]).upper(), normalize_template(str(entry["path"])))
        entries_by_key[key] = entry

    errors: list[str] = []
    for raw in allowlist.split(","):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split(" ", 1)
        if len(parts) != 2:
            errors.append(f"proxy allowlist item must be 'METHOD /path': {raw}")
            continue
        method = parts[0].upper()
        path = normalize_template(parts[1])
        key = (method, path)
        entry = entries_by_key.get(key)
        if entry is None:
            errors.append(f"proxy allowlist item not found in routes.yaml: {method} {parts[1]}")
            continue
        legacy_flags = set(entry.get("legacy_flags", []))
        if "deprecated_compatibility_alias" in legacy_flags:
            errors.append(f"proxy allowlist cannot include deprecated_compatibility_alias route: {method} {parts[1]}")
        if "state_changing_get" in legacy_flags:
            errors.append(f"proxy allowlist cannot include state_changing_get route: {method} {parts[1]}")
        if method != "POST":
            errors.append(f"proxy allowlist admin mutation must be POST: {method} {parts[1]}")
        if entry.get("csrf") != "required":
            errors.append(f"proxy allowlist admin mutation must set csrf=required: {method} {parts[1]}")
        if entry.get("audit") is not True:
            errors.append(f"proxy allowlist admin mutation must set audit=true: {method} {parts[1]}")
        if not str(entry.get("path", "")).startswith("/api/admin/"):
            errors.append(f"proxy allowlist admin mutation must be under /api/admin/: {method} {parts[1]}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--admin-proxy-allowlist", type=str, default="")
    args = parser.parse_args()
    if args.admin_proxy_allowlist:
        errors = check_admin_proxy_guard(args.root, args.admin_proxy_allowlist)
        if errors:
            for error in errors:
                print(f"ADMIN PROXY GUARD FAIL: {error}")
            return 1
        print("admin proxy guard: OK")
        return 0
    if args.inventory:
        inventory = route_inventory(args.root)
        for name, value in inventory.items():
            print(f"{name}: {value}")
        return 0
    errors = check_route_contract(args.root)
    if errors:
        for error in errors:
            print(f"ROUTE CONTRACT FAIL: {error}")
        return 1
    print("route contract checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
