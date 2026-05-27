package gatewayhttp

import (
	"hash/fnv"
	"net/http"
	"strconv"
	"strings"
)

type PercentageCanaryConfig struct {
	Enabled         bool
	Percent         int
	BucketKeyName   string
	RequireEvidence bool
}

type PercentageCanaryDecision struct {
	UseCandidate   bool
	Reason         string
	Bucket         int
	EvidencePassed bool
}

func HashBucket(key string) int {
	h := fnv.New32a()
	h.Write([]byte(key))
	return int(h.Sum32() % 100)
}

func ExtractBucketKey(r *http.Request, keyName string) string {
	if strings.TrimSpace(keyName) == "" {
		keyName = "canary-key"
	}

	if headerVal := r.Header.Get("X-Gaokao-Canary-Key"); headerVal != "" {
		return keyName + ":" + headerVal
	}

	accessKey := r.Header.Get("X-Gaokao-Canary-Access-Key")
	if accessKey == "" {
		accessKey = "request"
	}

	reqID := requestIDFromContext(r)
	if reqID != "" {
		return keyName + ":" + accessKey + ":" + reqID
	}
	return keyName + ":" + accessKey + ":fallback"
}

func DecidePercentage(r *http.Request, config PercentageCanaryConfig, evidencePassed bool) PercentageCanaryDecision {
	if !config.Enabled || config.Percent <= 0 {
		return PercentageCanaryDecision{UseCandidate: false, Reason: "percent_disabled"}
	}
	if config.RequireEvidence && !evidencePassed {
		return PercentageCanaryDecision{UseCandidate: false, Reason: "evidence_not_passed"}
	}
	key := ExtractBucketKey(r, config.BucketKeyName)
	bucket := HashBucket(key)
	if config.Percent >= 100 {
		return PercentageCanaryDecision{
			UseCandidate:   true,
			Bucket:         bucket,
			Reason:         "full_cutover",
			EvidencePassed: !config.RequireEvidence || evidencePassed,
		}
	}
	if bucket < config.Percent {
		return PercentageCanaryDecision{
			UseCandidate:   true,
			Bucket:         bucket,
			Reason:         "bucket_selected",
			EvidencePassed: !config.RequireEvidence || evidencePassed,
		}
	}
	return PercentageCanaryDecision{
		UseCandidate:   false,
		Bucket:         bucket,
		Reason:         "bucket_not_selected",
		EvidencePassed: !config.RequireEvidence || evidencePassed,
	}
}

func clampPercent(percent int) int {
	if percent < 0 {
		return 0
	}
	if percent > 100 {
		return 100
	}
	return percent
}

func parseCanaryKeyHeader(r *http.Request) int {
	headerVal := r.Header.Get("X-Gaokao-Canary-Key")
	if headerVal == "" {
		return -1
	}
	val, err := strconv.Atoi(strings.TrimSpace(headerVal))
	if err != nil || val < 0 || val > 99 {
		return -1
	}
	return val
}

func stripCanaryKeyHeaders(header http.Header) {
	header.Del("X-Gaokao-Canary-Key")
	header.Del("X-Gaokao-Canary-Access-Key")
	header.Del("x-gaokao-canary-key")
	header.Del("x-gaokao-canary-access-key")
}
