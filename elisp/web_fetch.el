;;; web_fetch.el --- Emacs Lisp interface to readerlm-litserve web service  -*- lexical-binding: t; -*-

;; Provides a function to fetch URLs and convert to markdown using the readerlm-litserve service directly
;;
;; Requirements:
;; - readerlm-litserve service must be running and accessible
;; - Optional: plz package for HTTP calls (M-x package-install RET plz RET)
;;   If not available, uses built-in url-retrieve-synchronously

;; Author: Gerald
;; Version: 1.0
;; Package-Requires: ((emacs "29.1") (cl-lib "1.0") (json "1.0"))
;; Keywords: web, http, fetch
;; URL: https://github.com/geraldthewes/readerlm-litserve

;;; Commentary:
;; This package provides a simple interface to the readerlm-litserve web service
;; for fetching URLs and converting their content to markdown format.
;;
;; The package offers two main functions:
;; - `web-fetch`: Tries to use plz if available, falls back to url-retrieve-synchronously
;; - `web-fetch-plz`: Uses plz exclusively for HTTP requests
;;
;; Both functions take a URL and optional timeout, returning the markdown content
;; or signaling a web-fetch-error on failure.
;;
;; To use with gptel, see the tool definition at the end of this file.

;;; Code:

(require 'json)

;; Declare plz function for byte-compiler
(eval-when-compile
  (declare-function plz "plz" (method &rest args)))

(defcustom web-fetch-service-url "http://fabio:9999/readerlm/"
   "Base URL of the readerlm-litserve service.
Should be accessible URL where service runs (e.g., via Fabio).
Service expects URLs at root path (Jina.ai-style endpoint)."
   :type 'string
   :group 'web-fetch)

(defun web-fetch (url &optional timeout)
  "Fetch URL and return content as Markdown using the readerlm-litserve service.
URL is the URL to fetch.
TIMEOUT is optional HTTP timeout in seconds (default: 30).
Returns the markdown content as a string, or signals an error on failure.

This function makes a direct HTTP request to the readerlm-litserve service
configured in `web-fetch-service-url', emulating the Jina.ai reader API pattern:
GET {service-url}/{url-to-fetch}"
  (let* ((timeout (or timeout 30))
         (service-url (if (string-match-p "/$" web-fetch-service-url)
                          web-fetch-service-url
                        (concat web-fetch-service-url "/")))
         (target-url (url-hexify-string url))
         (request-url (concat service-url target-url))
         (error nil)
         (result nil))
    
     ;; Try to use plz if available, otherwise fall back to built-in
     (let ((fetch-error nil))
       (condition-case err
           (progn
             ;; Check if plz is available
             (when (and (featurep 'plz) (fboundp 'plz))
               ;; Use plz for HTTP request (more modern interface)
               (let ((response (plz 'get request-url
                                    :timeout timeout
                                    :as 'string)))
                 (if (plist-get response :status-code)
                     (if (= 200 (plist-get response :status-code))
                         (setq result (plist-get response :body))
                       (setq error (format "Service returned HTTP %d: %s"
                                           (plist-get response :status-code)
                                           (plist-get response :body))))
                   (setq error (format "Invalid response from plz: %S" response)))))
             ;; Fall back to built-in url-retrieve-synchronously
             (unless (or result error)
               (let ((status-code 0))
                 (url-retrieve-synchronously
                  request-url
                  ;; Callback function
                  (lambda (status)
                    (setq status-code status)
                    (when (or (not (eq status 200))
                              (not (buffer-string)))
                      (setq error (format "URL retrieve failed with status %d" status)))))
               (unless error
                 (setq result (buffer-string)))
               (when (and (not error) (/= status-code 200))
                 (setq error (format "Service returned HTTP %d" status-code))))))
         (error (setq fetch-error err)))
       ;; Handle errors
       (when fetch-error
         (setq error (format "Error fetching URL: %s" (error-message-string fetch-error)))))
    
    ;; Return result or signal error
    (if error
        (signal 'web-fetch-error (list error))
      result)))

;; Alternative implementation using plz exclusively (if you prefer to depend on plz)
(defun web-fetch-plz (url &optional timeout)
  "Fetch URL and return content as Markdown using plz HTTP client.
This version requires the plz package to be installed.
URL is the URL to fetch.
TIMEOUT is optional HTTP timeout in seconds (default: 30).
Returns the markdown content as a string, or signals an error on failure."
  (unless (featurep 'plz)
    (signal 'web-fetch-error (list "plz package not installed. Install with: M-x package-install RET plz RET")))
  (let* ((timeout (or timeout 30))
         (service-url (if (string-match-p "/$" web-fetch-service-url)
                          web-fetch-service-url
                        (concat web-fetch-service-url "/")))
         (target-url (url-hexify-string url))
         (request-url (concat service-url target-url))
         (response (plz 'get request-url
                        :timeout timeout
                        :as 'string)))
    (if (= 200 (plist-get response :status-code))
        (plist-get response :body)
      (signal 'web-fetch-error
              (list (format "Service returned HTTP %d: %s"
                            (plist-get response :status-code)
                            (plist-get response :body)))))))

;; Tool definition for gptel integration
;; To use with gptel, add something like this to your init.el:
;;
;; (require 'plz) ; or use url-retrieve-synchronously if you prefer built-in only
;; 
;; (defvar my-gptel-tool-web-fetch
;;   (gptel-make-tool
;;    :name "web_fetch"
;;    :description "Fetch a URL and convert its content to Markdown using the readerlm-litserve service. Use this when the user asks about web content or needs to summarize/articles from URLs."
;;    :args (list '(:name "url"
;;                  :type "string"
;;                  :description "The URL to fetch")
;;                '(:name "timeout"
;;                  :type "integer"
;;                  :description "HTTP timeout in seconds (default: 30)"))
;;    :function (lambda (url &optional timeout)
;;                (web-fetch url timeout))  ;; or (web-fetch-plz url timeout) if you prefer plz
;;    :category "web"
;;    :confirm nil))
;;
;; Then register it:
;; (setq gptel-tools (append gptel-tools (list my-gptel-tool-web-fetch)))

;; Define a custom error type for web-fetch
(define-error 'web-fetch-error "Web fetch failed" nil)

(provide 'web_fetch)
;;; web_fetch.el ends here