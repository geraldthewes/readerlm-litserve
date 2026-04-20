.PHONY: build deploy status restart logs test test-unit test-integration lint typecheck security-scan emacs-install emacs-uninstall

# Build and deployment
build:
	git push origin
	jobforge submit-job --image-tags "latest" --watch --history deploy/build.yaml

deploy:
	nomad job run deploy/readerlm-litserve.nomad

restart:
	nomad job restart -on-error=fail readerlm-litserve

status:
	nomad job status readerlm-litserve

logs:
	nomad alloc logs -job readerlm-litserve

# Testing
test: test-unit test-integration test-elisp

# Emacs package installation
EMACS_DIR ?= ~/.emacs.d
ELPA_DIR ?= $(EMACS_DIR)/elpa
ELISP_DIR = elisp

.PHONY: emacs-install emacs-uninstall

emacs-install:
	mkdir -p $(ELPA_DIR)/web_fetch
	cp $(ELISP_DIR)/web_fetch.el $(ELPA_DIR)/web_fetch/
	cp $(ELISP_DIR)/web_fetch-pkg.el $(ELPA_DIR)/web_fetch/
	@echo "Installed web_fetch to $(ELPA_DIR)/web_fetch/"
	@echo "Add to your init.el:"
	@echo "  (add-to-list 'load-path \"$(ELPA_DIR)/web_fetch\")"
	@echo "  (require 'web_fetch)"

emacs-uninstall:
	rm -rf $(ELPA_DIR)/web_fetch
	@echo "Removed web_fetch from $(ELPA_DIR)"

test-unit:
	python -m pytest tests/test_html_extractor.py tests/test_url_fetcher.py -v

test-integration:
	python tests/integration_test.py

test-elisp:
	cd elisp && emacs --batch -l ert -l ./simple-test.el -f ert-run-tests-batch-and-exit
	cd elisp && emacs --batch -l ert -l ./test-web-fetch.el -f ert-run-tests-batch-and-exit

# Code quality
lint:
	ruff check .

typecheck:
	mypy server.py html_extractor.py url_fetcher.py --ignore-missing-imports

security-scan:
	bandit -r . -x ./tests
