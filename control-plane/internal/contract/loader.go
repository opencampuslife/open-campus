package contract

import (
	"encoding/json"
	"fmt"
	"os"
)

func Load(path string) (*Contract, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("load routes contract: %w", err)
	}
	var loaded Contract
	decoderErr := json.Unmarshal(data, &loaded)
	if decoderErr != nil {
		return nil, fmt.Errorf("parse routes contract: %w", decoderErr)
	}
	if err := Validate(&loaded); err != nil {
		return nil, err
	}
	return &loaded, nil
}
