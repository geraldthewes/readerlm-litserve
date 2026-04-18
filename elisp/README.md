# web-fetch.el - Emacs Lisp Interface to readerlm-litserve Web Service

This package provides Emacs Lisp functions to fetch URLs and convert their content to Markdown by making direct HTTP requests to the [readerlm-litserve](https://github.com/geraldthewes/readerlm-litserve) web service.

## Installation

### Prerequisites

1. **readerlm-litserve service**: Must be running and accessible
   - Deploy using: `make deploy` from the readerlm-litserve project root
   - Service accessible via Fabio: `http://fabio:9999/readerlm/`
   - The service provides a Jina.ai-style endpoint that fetches URLs and converts them to Markdown

2. **Optional HTTP client**: 
   - The package can use either Emacs' built-in `url-retrieve-synchronously` or the `plz` package
   - For better functionality, install plz: `M-x package-install RET plz RET`

### Manual Installation

1. Copy `web_fetch.el` to your Emacs lisp directory (e.g., `~/.emacs.d/lisp/`)
2. Add the directory to your `load-path` if not already there:
   ```elisp
   (add-to-list 'load-path "~/.emacs.d/lisp/")
   ```
3. Require the package:
   ```elisp
   (require 'web-fetch)
   ```

## Usage

### Direct Function Calls

You can call the functions directly in Emacs Lisp:

```elisp
;; Fetch a URL with default timeout (30 seconds)
(web-fetch "https://example.com")

;; Fetch a URL with custom timeout
(web-fetch "https://example.com" 60) ;; 60 second timeout
```

### Interactive Use

You can also use it interactively:

```elisp
M-x web-fetch RET https://example.com RET
```

## Configuration

You can customize the service URL by setting the `web-fetch-service-url` variable:

```elisp
(setq web-fetch-service-url "http://localhost:8000/")  ;; For local development
```

Or use Customize: `M-x customize-variable RET web-fetch-service-url RET`

## Integration with gptel

This package is designed to work seamlessly with [gptel](https://github.com/numkem/gptel), an Emacs client for LLMs.

### Basic Setup

Add the following to your Emacs configuration (after requiring web-fetch):

```elisp
;; Optional: Use plz for HTTP calls (recommended) or use built-in url-retrieve-synchronously
(require 'plz)  ;; Install with: M-x package-install RET plz RET

;; Define the gptel tool
(defvar my-gptel-tool-web-fetch
  (gptel-make-tool
   :name "web_fetch"
   :description "Fetch a URL and convert its content to Markdown using the readerlm-litserve service. Use this when the user asks about web content or needs to summarize/articles from URLs."
   :args (list '(:name "url"
                 :type "string"
                 :description "The URL to fetch")
               '(:name "timeout"
                 :type "integer"
                 :description "HTTP timeout in seconds (default: 30)"))
   :function (lambda (url &optional timeout)
               (web-fetch url timeout))  ;; Uses direct HTTP to service
   :category "web"
   :confirm nil))

;; Register the tool with gptel
(setq gptel-tools (append gptel-tools (list my-gptel-tool-web-fetch)))
```

### Advanced Usage with gptel

#### Asynchronous Tool (Recommended for Network Calls)

For better responsiveness, use the async version:

```elisp
(defvar my-gptel-tool-web-fetch-async
  (gptel-make-tool
   :name "web_fetch"
   :description "Fetch a URL and convert its content to Markdown using the readerlm-litserve service."
   :args (list '(:name "url"
                 :type "string"
                 :description "The URL to fetch")
               '(:name "timeout"
                 :type "integer"
                 :description "HTTP timeout in seconds (default: 30)"))
   :function (lambda (url timeout callback)
               ;; Call web-fetch async and return result via callback
               (web-fetch url timeout
                          ;; Success callback
                          (lambda (result)
                            (funcall callback result))
                          ;; Error callback
                          (lambda (error)
                            (funcall callback (format "Error: %s" error)))))
   :category "web"
   :confirm nil
   :async t))  ;; Important: Mark as async
```

#### Using with Presets

Create a preset for easy switching:

```elisp
(gptel-make-preset 'my-web-tools
  :tools '("web_fetch")
  :system "You have access to a web fetching service that can retrieve and summarize web content. Use the web_fetch tool when users ask about current web content or need information from specific URLs.")
```

Then activate with: `M-x gptel-use-preset RET my-web-tools RET`

## Functions

### `web-fetch URL &optional TIMEOUT`

Fetch a URL and return its content as Markdown by making an HTTP request to the readerlm-litserve service.

- **URL**: The URL to fetch (string)
- **TIMEOUT**: Optional timeout in seconds (integer, default: 30)
- **Returns**: Markdown content as string
- **Errors**: Signals `web-fetch-error` on failure (network issues, service errors, etc.)

### `web-fetch-plz URL &optional TIMEOUT`

Alternative implementation that requires the plz package. Similar to `web-fetch` but uses plz exclusively.

## How It Works

The Emacs Lisp functions make direct HTTP requests to the readerlm-litserve service:
1. Constructs a request to `{service-url}/{url-to-fetch}` (Jina.ai-style endpoint)
2. The service fetches the specified URL using its internal `url_fetcher.py` with SSRF protection
3. The service extracts and converts the content to Markdown using its 3-tier fallback extraction pipeline (`html_extractor.py`)
4. Returns the Markdown result to the Emacs Lisp function

## Troubleshooting

### Connection refused or service unavailable
- Verify the readerlm-litserve service is running: `make status` in the readerlm-litserve project
- Check service accessibility: `curl http://fabio:9999/readerlm/` should return service info
- Ensure proper network connectivity to the service cluster
- Verify the `web-fetch-service-url` variable is set correctly

### Timeout errors
- Increase the timeout parameter when calling the functions
- Check if the target URL is accessible and responsive
- Verify the readerlm-litserve service is not overloaded

### HTTP error responses
- 400: Invalid URL format (must start with http:// or https://)
- 403: Request blocked by SSRF protection
- 502: Service failed to fetch the URL
- 504: Service timed out during conversion
- 500: Internal service error

## Requirements

- Emacs 25.1 or later
- Running readerlm-litserve service
- Optional: plz package for enhanced HTTP capabilities

## License

Same as the readerlm-litserve project - see the main repository for license details.