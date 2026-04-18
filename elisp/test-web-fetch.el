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
(load "web_fetch.el" nil t)  ;; Load the package we're testing

(ert-deftest test-web-fetch-exists ()
  "Test that web-fetch function exists."
  (should (fboundp 'web-fetch)))

(ert-deftest test-web-fetch-plz-exists ()
  "Test that web-fetch-plz function exists."
  (should (fboundp 'web-fetch-plz)))

;;; test-web-fetch.el ends here
