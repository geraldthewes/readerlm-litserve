;;; simple-test.el --- Simple test for web-fetch.el  -*- LexicalBinding: t; -*-

;; This file is NOT part of GNU Emacs.

;;; Code:

(add-to-list 'load-path (expand-file-name "."))
(require 'ert)
(load "web_fetch.el" nil t)  ;; Load the package we're testing

(ert-deftest test-web-fetch-exists ()
  "Test that web-fetch function exists."
  (should (fboundp 'web-fetch)))

;;; simple-test.el ends here