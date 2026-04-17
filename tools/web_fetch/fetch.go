package main

import (
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// fetchMarkdown calls the readerlm service GET /{url} endpoint and returns the markdown body.
func fetchMarkdown(baseURL, targetURL string, timeout time.Duration) (string, error) {
	serviceURL := strings.TrimRight(baseURL, "/") + "/" + strings.TrimLeft(targetURL, "/")

	client := &http.Client{Timeout: timeout}
	req, err := http.NewRequest("GET", serviceURL, nil)
	if err != nil {
		return "", fmt.Errorf("building request: %w", err)
	}
	req.Header.Set("User-Agent", "web_fetch-cli/1.0")

	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("fetching %s: %w", targetURL, err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("reading response: %w", err)
	}

	switch resp.StatusCode {
	case http.StatusOK:
		return string(body), nil
	case http.StatusBadRequest:
		return "", fmt.Errorf("bad request (400): invalid URL %q", targetURL)
	case http.StatusForbidden:
		return "", fmt.Errorf("forbidden (403): URL blocked by SSRF protection")
	case http.StatusBadGateway:
		return "", fmt.Errorf("bad gateway (502): service could not fetch %q", targetURL)
	case http.StatusGatewayTimeout:
		return "", fmt.Errorf("gateway timeout (504): request timed out fetching %q", targetURL)
	default:
		return "", fmt.Errorf("unexpected status %d from service", resp.StatusCode)
	}
}
