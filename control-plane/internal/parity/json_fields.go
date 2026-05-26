package parity

import (
	"encoding/json"
	"strings"
)

func decodeJSONObject(body string) (map[string]any, error) {
	var decoded map[string]any
	if err := json.Unmarshal([]byte(body), &decoded); err != nil {
		return nil, err
	}
	return decoded, nil
}

func lookupJSONField(body map[string]any, path string) (any, bool) {
	current := any(body)
	for _, segment := range strings.Split(path, ".") {
		object, ok := current.(map[string]any)
		if !ok {
			return nil, false
		}
		current, ok = object[segment]
		if !ok {
			return nil, false
		}
	}
	return current, true
}
