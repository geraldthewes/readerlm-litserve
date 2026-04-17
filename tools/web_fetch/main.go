package main

import (
	"flag"
	"fmt"
	"io"
	"os"
	"strings"
	"time"
)

const version = "1.0.0"

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("web_fetch", flag.ContinueOnError)
	fs.SetOutput(stderr)

	var (
		baseURL = fs.String("u", "", "readerlm service base URL (overrides READERLM_URL env and Consul)")
		timeout = fs.Int("timeout", 30, "HTTP timeout in seconds")
		showVer = fs.Bool("v", false, "Print version and exit")
	)

	fs.String("url", "", "Alias for -u")
	fs.Bool("version", false, "Alias for -v")

	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			printUsage(stderr)
			return 0
		}
		return 2
	}

	if v := fs.Lookup("url").Value.String(); v != "" && *baseURL == "" {
		*baseURL = v
	}
	if v := fs.Lookup("version").Value.String(); v == "true" {
		*showVer = true
	}

	if *showVer {
		fmt.Fprintf(stdout, "web_fetch %s\n", version)
		return 0
	}

	targetURL := strings.TrimSpace(strings.Join(fs.Args(), " "))
	if targetURL == "" {
		stat, _ := os.Stdin.Stat()
		if (stat.Mode() & os.ModeCharDevice) == 0 {
			b, err := io.ReadAll(os.Stdin)
			if err != nil {
				fmt.Fprintf(stderr, "error reading stdin: %v\n", err)
				return 1
			}
			targetURL = strings.TrimSpace(string(b))
		}
	}

	if targetURL == "" {
		fmt.Fprintf(stderr, "error: no URL provided\n\n")
		printUsage(stderr)
		return 2
	}

	timeoutDur := time.Duration(*timeout) * time.Second
	serviceURL := discoverReaderLMURL(*baseURL, 3*time.Second)

	markdown, err := fetchMarkdown(serviceURL, targetURL, timeoutDur)
	if err != nil {
		fmt.Fprintf(stderr, "error: %v\n", err)
		return 1
	}

	fmt.Fprint(stdout, markdown)
	return 0
}

func printUsage(w io.Writer) {
	fmt.Fprintf(w, `Usage: web_fetch [flags] <url>

web_fetch fetches a URL and returns its content as Markdown using the
cluster readerlm-litserve service.

Flags:
  -u, --url string    readerlm service base URL (overrides READERLM_URL env / Consul)
      --timeout int   HTTP timeout in seconds (default 30)
  -v, --version       Print version and exit

Environment:
  READERLM_URL         Override readerlm service URL
  CONSUL_HTTP_ADDR     Consul address for service discovery (default: http://127.0.0.1:8500)

Examples:
  web_fetch https://example.com
  web_fetch -u http://localhost:8000 https://example.com
  echo "https://example.com" | web_fetch
`)
}
