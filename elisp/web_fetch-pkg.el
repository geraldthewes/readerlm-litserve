;;; web_fetch-pkg.el --- Package definition for web_fetch  -*- lexical-binding: t; -*-

;; Author: Gerald
;; Version: 1.0
;; Package-Requires: ((emacs "29.1") (cl-lib "1.0") (json "1.0"))
;; Keywords: web, http, fetch
;; URL: https://github.com/geraldthewes/readerlm-litserve

;;; Commentary:
;; This package provides Emacs Lisp functions to fetch URLs and convert 
;; them to Markdown via the readerlm-litserve service.
;; 
;; The package includes:
;; - `web-fetch`: Main function to fetch URLs and convert to markdown
;; - `web-fetch-plz`: Alternative implementation using plz package
;; 
;; Requires a running readerlm-litserve service (accessible via Fabio or directly).
;; 
;; See `web_fetch.el` for detailed documentation and usage examples.

;;; Code:
;; Actually load the main package contents
(load "web_fetch" nil t)

;;; web_fetch-pkg.el ends here