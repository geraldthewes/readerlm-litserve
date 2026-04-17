package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"
)

func TestDiscoverReaderLMURL_FlagOverride(t *testing.T) {
	os.Setenv("READERLM_URL", "http://env-url:8000")
	defer os.Unsetenv("READERLM_URL")

	got := discoverReaderLMURL("http://flag-url:8000", time.Second)
	if got != "http://flag-url:8000" {
		t.Errorf("expected flag URL, got %q", got)
	}
}

func TestDiscoverReaderLMURL_EnvOverride(t *testing.T) {
	os.Setenv("READERLM_URL", "http://env-url:8000")
	defer os.Unsetenv("READERLM_URL")

	got := discoverReaderLMURL("", time.Second)
	if got != "http://env-url:8000" {
		t.Errorf("expected env URL, got %q", got)
	}
}

func TestDiscoverReaderLMURL_ConsulKV(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v1/kv/services/readerlm-litserve/url" {
			_, _ = w.Write([]byte("http://consul-readerlm:8000"))
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()

	os.Setenv("CONSUL_HTTP_ADDR", srv.URL)
	defer os.Unsetenv("CONSUL_HTTP_ADDR")
	os.Unsetenv("READERLM_URL")

	got := discoverReaderLMURL("", time.Second)
	if got != "http://consul-readerlm:8000" {
		t.Errorf("expected Consul URL, got %q", got)
	}
}

func TestDiscoverReaderLMURL_Fallback(t *testing.T) {
	os.Unsetenv("READERLM_URL")
	os.Setenv("CONSUL_HTTP_ADDR", "http://127.0.0.1:19999") // nothing listening
	defer os.Unsetenv("CONSUL_HTTP_ADDR")

	got := discoverReaderLMURL("", 100*time.Millisecond)
	if got != defaultReaderLMURL {
		t.Errorf("expected fallback URL %q, got %q", defaultReaderLMURL, got)
	}
}
