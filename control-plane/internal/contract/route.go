package contract

import "strings"

type Contract struct {
	Version      int     `json:"version"`
	FrozenSource string  `json:"frozen_source"`
	Description  string  `json:"description"`
	Routes       []Route `json:"routes"`
}

type Route struct {
	Method         string      `json:"method"`
	Path           string      `json:"path"`
	Owner          string      `json:"owner"`
	Surface        string      `json:"surface"`
	Visibility     string      `json:"visibility"`
	Auth           string      `json:"auth"`
	CSRF           string      `json:"csrf"`
	RateLimit      string      `json:"rate_limit"`
	Audit          bool        `json:"audit"`
	Backend        string      `json:"backend"`
	RequestSchema  string      `json:"request_schema"`
	ResponseSchema string      `json:"response_schema"`
	MigrationWave  string      `json:"migration_wave"`
	LegacyFlags    []string    `json:"legacy_flags"`
	LegacyExit     *LegacyExit `json:"legacy_exit"`
	OpenAPIRef     string      `json:"openapi_ref"`
	OpenAPI        string      `json:"openapi"`
	Mutation       bool        `json:"mutation"`
}

type LegacyExit struct {
	TargetPhase  string `json:"target_phase"`
	AllowedUntil string `json:"allowed_until"`
	RequiredFix  string `json:"required_fix"`
}

func (route Route) Key() string {
	return route.Method + " " + route.Path
}

func (route Route) IsPublic() bool {
	return route.Surface == "public"
}

func (route Route) HasLegacyFlag(flag string) bool {
	for _, candidate := range route.LegacyFlags {
		if candidate == flag {
			return true
		}
	}
	return false
}

func (route Route) MatchPath(actualPath string) bool {
	templateSegs := strings.Split(strings.Trim(route.Path, "/"), "/")
	actualSegs := strings.Split(strings.Trim(actualPath, "/"), "/")
	if len(templateSegs) != len(actualSegs) {
		return false
	}
	for i, seg := range templateSegs {
		if strings.HasPrefix(seg, "{") && strings.HasSuffix(seg, "}") {
			continue
		}
		if seg != actualSegs[i] {
			return false
		}
	}
	return true
}

func (loaded *Contract) FindExactRoute(method string, path string) (Route, bool) {
	if loaded == nil {
		return Route{}, false
	}
	for _, route := range loaded.Routes {
		if route.Method == method && route.Path == path {
			return route, true
		}
	}
	return Route{}, false
}

func (loaded *Contract) FindMatchingRoute(method string, path string) (Route, bool) {
	if loaded == nil {
		return Route{}, false
	}
	if route, ok := loaded.FindExactRoute(method, path); ok {
		return route, true
	}
	for _, route := range loaded.Routes {
		if route.Method == method && route.MatchPath(path) {
			return route, true
		}
	}
	return Route{}, false
}

func (loaded *Contract) HasExactPath(path string) bool {
	if loaded == nil {
		return false
	}
	for _, route := range loaded.Routes {
		if route.Path == path {
			return true
		}
	}
	return false
}

func (loaded *Contract) HasMatchingPath(path string) bool {
	if loaded == nil {
		return false
	}
	for _, route := range loaded.Routes {
		if route.MatchPath(path) {
			return true
		}
	}
	return false
}
