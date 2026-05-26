package parity

import (
	"encoding/json"
	"fmt"
)

func (expectation *BodyCompareExpectation) UnmarshalJSON(data []byte) error {
	if string(data) == "null" {
		*expectation = BodyCompareExpectation{}
		return nil
	}
	var mode string
	if err := json.Unmarshal(data, &mode); err == nil {
		expectation.Mode = mode
		expectation.RequiredFields = nil
		return nil
	}
	type alias BodyCompareExpectation
	var decoded alias
	if err := json.Unmarshal(data, &decoded); err != nil {
		return fmt.Errorf("decode body compare expectation: %w", err)
	}
	*expectation = BodyCompareExpectation(decoded)
	return nil
}
