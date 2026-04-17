package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

const (
	defaultConsulAddr    = "http://127.0.0.1:8500"
	defaultReaderLMURL   = "http://fabio.service.consul:9999/readerlm"
	consulKVReaderLMURL  = "services/readerlm-litserve/url"
)

// discoverReaderLMURL returns the best readerlm service URL to use.
// Priority: --url flag > READERLM_URL env > Consul KV > hardcoded fallback.
func discoverReaderLMURL(flagURL string, timeout time.Duration) string {
	if flagURL != "" {
		return strings.TrimRight(flagURL, "/")
	}

	if envURL := os.Getenv("READERLM_URL"); envURL != "" {
		return strings.TrimRight(envURL, "/")
	}

	if u := consulKVGet(consulKVReaderLMURL, timeout); u != "" {
		return strings.TrimRight(u, "/")
	}

	return defaultReaderLMURL
}

// consulKVGet fetches a raw string value from the Consul KV HTTP API.
// Returns "" silently on any failure — callers fall back to defaults.
func consulKVGet(key string, timeout time.Duration) string {
	consulAddr := os.Getenv("CONSUL_HTTP_ADDR")
	if consulAddr == "" {
		consulAddr = defaultConsulAddr
	}

	reqURL := fmt.Sprintf("%s/v1/kv/%s?raw", consulAddr, key)

	client := &http.Client{Timeout: timeout}
	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return ""
	}
	req.Header.Set("User-Agent", "web_fetch-cli/1.0")

	resp, err := client.Do(req)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return ""
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, 2048))
	if err != nil {
		return ""
	}

	return strings.TrimSpace(string(body))
}
