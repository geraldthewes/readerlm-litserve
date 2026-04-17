package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestFetchMarkdown(t *testing.T) {
	var capturedPath string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		w.Header().Set("Content-Type", "text/markdown")
		_, _ = w.Write([]byte("# Test Page\n\nContent here."))
	}))
	defer srv.Close()

	result, err := fetchMarkdown(srv.URL, "https://example.com", 5*time.Second)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(result, "Test Page") {
		t.Errorf("unexpected result: %s", result)
	}
	if !strings.Contains(capturedPath, "example.com") {
		t.Errorf("expected path to contain target URL, got: %s", capturedPath)
	}
}

func TestFetchMarkdownHTTPError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
	}))
	defer srv.Close()

	_, err := fetchMarkdown(srv.URL, "https://example.com", 5*time.Second)
	if err == nil {
		t.Fatal("expected error for 502, got nil")
	}
	if !strings.Contains(err.Error(), "502") {
		t.Errorf("expected 502 in error message, got: %v", err)
	}
}

func TestFetchMarkdownForbidden(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
	}))
	defer srv.Close()

	_, err := fetchMarkdown(srv.URL, "https://192.168.1.1", 5*time.Second)
	if err == nil {
		t.Fatal("expected error for 403, got nil")
	}
	if !strings.Contains(err.Error(), "403") {
		t.Errorf("expected 403 in error message, got: %v", err)
	}
}

func TestFetchMarkdownBadRequest(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
	}))
	defer srv.Close()

	_, err := fetchMarkdown(srv.URL, "not-a-url", 5*time.Second)
	if err == nil {
		t.Fatal("expected error for 400, got nil")
	}
	if !strings.Contains(err.Error(), "400") {
		t.Errorf("expected 400 in error message, got: %v", err)
	}
}
