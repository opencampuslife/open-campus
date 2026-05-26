package parity

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

func LoadFixture(path string) (*Fixture, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("load parity fixture: %w", err)
	}
	var fixture Fixture
	if err := json.Unmarshal(data, &fixture); err != nil {
		return nil, fmt.Errorf("parse parity fixture: %w", err)
	}
	if err := ValidateFixture(&fixture); err != nil {
		return nil, fmt.Errorf("validate parity fixture: %w", err)
	}
	return &fixture, nil
}

func RunFixture(fixture *Fixture, legacyBaseURL string, shadowBaseURL string, client *http.Client) (Report, error) {
	if client == nil {
		client = &http.Client{Timeout: 30 * time.Second}
	}
	report := Report{
		Summary: Summary{Total: len(fixture.Cases)},
		Cases:   make([]CaseResult, 0, len(fixture.Cases)),
	}
	for _, parityCase := range fixture.Cases {
		result, err := RunCase(parityCase, legacyBaseURL, shadowBaseURL, client)
		if err != nil {
			return Report{}, err
		}
		report.Cases = append(report.Cases, result)
		switch result.Status {
		case "passed":
			report.Summary.Passed++
		case "warned":
			report.Summary.Warned++
		default:
			report.Summary.Failed++
		}
	}
	return report, nil
}

func RunCase(parityCase Case, legacyBaseURL string, shadowBaseURL string, client *http.Client) (CaseResult, error) {
	legacyResult, err := performRequest(parityCase, legacyBaseURL, client)
	if err != nil {
		return CaseResult{}, fmt.Errorf("run legacy case %s: %w", parityCase.Name, err)
	}
	shadowResult, err := performRequest(parityCase, shadowBaseURL, client)
	if err != nil {
		return CaseResult{}, fmt.Errorf("run shadow case %s: %w", parityCase.Name, err)
	}
	diffResult := CompareCase(parityCase, legacyResult, shadowResult)
	return CaseResult{
		Name:   parityCase.Name,
		Status: diffResult.Status,
		Legacy: legacyResult,
		Shadow: shadowResult,
		Diffs:  diffResult.Diffs,
	}, nil
}

func performRequest(parityCase Case, baseURL string, client *http.Client) (EndpointResult, error) {
	bodyReader, bodyString, err := requestBody(parityCase)
	if err != nil {
		return EndpointResult{}, err
	}
	request, err := http.NewRequest(parityCase.Method, strings.TrimRight(baseURL, "/")+parityCase.Path, bodyReader)
	if err != nil {
		return EndpointResult{}, err
	}
	for name, value := range parityCase.Headers {
		request.Header.Set(name, value)
	}
	if bodyString != "" && request.Header.Get("Content-Type") == "" {
		request.Header.Set("Content-Type", "application/json")
	}
	start := time.Now()
	response, err := client.Do(request)
	if err != nil {
		return EndpointResult{}, err
	}
	defer response.Body.Close()
	data, err := io.ReadAll(response.Body)
	if err != nil {
		return EndpointResult{}, err
	}
	headers := make(map[string]string, len(response.Header))
	for name, values := range response.Header {
		headers[strings.ToLower(name)] = strings.Join(values, ", ")
	}
	return EndpointResult{
		Status:    response.StatusCode,
		LatencyMS: time.Since(start).Milliseconds(),
		Headers:   headers,
		Body:      string(data),
	}, nil
}

func requestBody(parityCase Case) (io.Reader, string, error) {
	if parityCase.Body != "" {
		return strings.NewReader(parityCase.Body), parityCase.Body, nil
	}
	if parityCase.BodyJSON != nil {
		data, err := json.Marshal(parityCase.BodyJSON)
		if err != nil {
			return nil, "", err
		}
		return bytes.NewReader(data), string(data), nil
	}
	return nil, "", nil
}
