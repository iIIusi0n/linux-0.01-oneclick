IMAGE ?= linux-0.01:latest
RUNTIME ?= docker
VERIFY_RUNTIME ?= $(RUNTIME)
OUTPUT_DIR ?= artifacts/verify

.PHONY: build run setup-dev verify clean-artifacts

build:
	$(RUNTIME) build -t $(IMAGE) .

run:
	$(RUNTIME) run --rm -it $(IMAGE)

setup-dev:
	python3 -m pip install -r requirements-dev.txt

verify:
	python3 scripts/verify_container.py \
		--runtime $(VERIFY_RUNTIME) \
		--image $(IMAGE) \
		--output-dir $(OUTPUT_DIR)

clean-artifacts:
	rm -rf $(OUTPUT_DIR)
