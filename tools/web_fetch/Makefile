BINARY   := web_fetch
LDFLAGS  := -ldflags="-s -w"
DESTDIR  := /usr/local/bin

.PHONY: build test lint install clean

build:
	go build $(LDFLAGS) -o $(BINARY) .

test:
	go test ./... -v -count=1

lint:
	go vet ./...

install: build
	sudo install -m 755 $(BINARY) $(DESTDIR)/$(BINARY)
	@echo "Installed: $(DESTDIR)/$(BINARY)"

clean:
	rm -f $(BINARY)
