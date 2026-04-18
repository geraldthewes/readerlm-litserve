;;; test-web-fetch.el --- Tests for web-fetch.el  -*- LexicalBinding: t; -*-

;; Copyright (C) 2026  Gerald

;; Author: Gerald
;; Version: 1.0
;; Package-Requires: ((ert ">= 1.0"))
;; Keywords: testing

;; This file is NOT part of GNU Emacs.

;;; Commentary:

;; Unit tests for web-fetch.el functions.

;;; Code:

;; Add elisp directory to load path
(add-to-list 'load-path (expand-file-name "."))

(require 'ert)
(require 'advice)  ;; For ad-set-arg and advice functions
(load "web_fetch.el" nil t)  ;; Load the package we're testing

;; Mocking support
(defvar web-fetch-mock-urls nil
  "Alist of (URL . RESPONSE) for mocking HTTP requests.")
(defvar web-fetch-mock-errors nil
  "Alist of (URL . ERROR-MESSAGE) for mocking HTTP errors.")

;; Advice to mock url-retrieve-synchronously
(defadvice url-retrieve-synchronously (around web-fetch-mock-advice (url &optional callback))
  "Mock url-retrieve-synchronously for testing."
  (let ((mock-response (assoc url web-fetch-mock-urls))
        (mock-error (assoc url web-fetch-mock-errors)))
    (if mock-response
        (progn
          (with-temp-buffer
            (insert (cdr mock-response)))
          (if callback
              (funcall callback 200)))
      (if mock-error
          (progn
            (if callback
                (funcall callback (cdr mock-error)))))
      ad-do-it))
  (ad-set-arg 0 url)
  (ad-set-arg 1 callback)

(ad-activate 'url-retrieve-synchronously)

;; Clean up mocks after each test
(defun web-fetch-test-cleanup ()
  "Clean up mocks and advice."
  (setq web-fetch-mock-urls nil
        web-fetch-mock-errors nil)
  (ad-deactivate 'url-retrieve-synchronously)
  (ad-activate 'url-retrieve-synchronously))

;; Test web-fetch function
(ert-deftest test-web-fetch-successful-request ()
  "Test web-fetch with a successful request."
  (web-fetch-test-cleanup)
  (let ((test-url "https://example.com")
        (expected-response "<html>Hello World</html>"))
    (push (cons test-url expected-response) web-fetch-mock-urls)
    (ad-activate 'url-retrieve-synchronously)
    (should (string= (web-fetch test-url) expected-response))
    (web-fetch-test-cleanup)))

(ert-deftest test-web-fetch-service-error ()
  "Test web-fetch when service returns error status."
  (web-fetch-test-cleanup)
  (let ((test-url "https://example.com/error"))
    (push (cons test-url 404) web-fetch-mock-errors)
    (ad-activate 'url-retrieve-synchronously)
    (should-error (web-fetch test-url))
    (web-fetch-test-cleanup)))

(ert-deftest test-web-fetch-network-error ()
  "Test web-fetch when network error occurs."
  (web-fetch-test-cleanup)
  (let ((test-url "https://example.com/network-error"))
    (push (cons test-url "Connection refused") web-fetch-mock-errors)
    (ad-activate 'url-retrieve-synchronously)
    (should-error (web-fetch test-url))
    (web-fetch-test-cleanup)))

(ert-deftest test-web-fetch-with-timeout ()
  "Test web-fetch with custom timeout."
  (web-fetch-test-cleanup)
  (let ((test-url "https://example.com")
        (expected-response "Response"))
    (push (cons test-url expected-response) web-fetch-mock-urls)
    (ad-activate 'url-retrieve-synchronously)
    (should (string= (web-fetch test-url 5) expected-response))
    (web-fetch-test-cleanup)))

;; Test web-fetch-plz function if plz is available
(ert-deftest test-web-fetch-plz-available-p ()
  "Test if plz feature detection works."
  (should (booleanp (featurep 'plz))))

;;; test-web-fetch.el ends here