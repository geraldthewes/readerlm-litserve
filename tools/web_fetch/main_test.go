package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func mockReaderLM(t *testing.T, status int, body string) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/markdown")
		w.WriteHeader(status)
		_, _ = w.Write([]byte(body))
	}))
}

func TestRunSuccess(t *testing.T) {
	srv := mockReaderLM(t, http.StatusOK, "# Hello World\n\nThis is markdown.")
	defer srv.Close()
	os.Setenv("READERLM_URL", srv.URL)
	defer os.Unsetenv("READERLM_URL")

	var stdout, stderr strings.Builder
	code := run([]string{"https://example.com"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d. stderr: %s", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), "Hello World") {
		t.Errorf("expected markdown in output, got: %s", stdout.String())
	}
}

func TestRunNoURL(t *testing.T) {
	var stdout, stderr strings.Builder
	code := run([]string{}, &stdout, &stderr)
	if code != 2 {
		t.Errorf("expected exit 2 for no URL, got %d", code)
	}
}

func TestRunVersion(t *testing.T) {
	var stdout, stderr strings.Builder
	code := run([]string{"-v"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d", code)
	}
	if !strings.Contains(stdout.String(), "web_fetch") {
		t.Error("version output missing 'web_fetch'")
	}
}

func TestRunHTTPError(t *testing.T) {
	srv := mockReaderLM(t, http.StatusInternalServerError, "internal error")
	defer srv.Close()
	os.Setenv("READERLM_URL", srv.URL)
	defer os.Unsetenv("READERLM_URL")

	var stdout, stderr strings.Builder
	code := run([]string{"https://example.com"}, &stdout, &stderr)
	if code != 1 {
		t.Errorf("expected exit 1 for server error, got %d", code)
	}
}

func TestRunURLFlag(t *testing.T) {
	srv := mockReaderLM(t, http.StatusOK, "# Flagged")
	defer srv.Close()

	var stdout, stderr strings.Builder
	code := run([]string{"-u", srv.URL, "https://example.com"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d. stderr: %s", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), "Flagged") {
		t.Errorf("expected markdown in output, got: %s", stdout.String())
	}
}

func TestRunURLLongFlag(t *testing.T) {
	srv := mockReaderLM(t, http.StatusOK, "# LongFlag")
	defer srv.Close()

	var stdout, stderr strings.Builder
	code := run([]string{"--url", srv.URL, "https://example.com"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d. stderr: %s", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), "LongFlag") {
		t.Errorf("expected markdown in output, got: %s", stdout.String())
	}
}
