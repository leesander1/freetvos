include brand/brand.env
export

ARCH ?= $(ARCH_DEFAULT)

.PHONY: help build disk iso run widevine export clean lint

help:
	@echo "$(BRAND_NAME) $(BRAND_VERSION)"
	@echo "  make build          build the OS container image (ARCH=arm64|amd64)"
	@echo "  make disk           produce a bootable qcow2 in ./output"
	@echo "  make iso            produce an installer ISO in ./output"
	@echo "  make run            boot ./output/qcow2/disk.qcow2 in QEMU"
	@echo "  make widevine       install the CDM on the running VM (cached)"
	@echo "  make export         save the image for installing on real hardware"
	@echo "  make lint           shellcheck, python syntax, and the input tests"
	@echo "  make clean          remove build output"

build:
	@tools/build.sh $(ARCH)

disk:
	@tools/make-disk.sh $(ARCH) qcow2

iso:
	@tools/make-disk.sh $(ARCH) anaconda-iso

run:
	@tools/run-qemu.sh

widevine:
	@tools/install-widevine.sh

export:
	@mkdir -p output
	@echo ">> Exporting $(IMAGE_REF):$(BRAND_VERSION)-$(ARCH) for offline install"
	podman save -o output/$(BRAND_ID)-$(ARCH).tar $(IMAGE_REF):$(BRAND_VERSION)-$(ARCH)
	@ls -lh output/$(BRAND_ID)-$(ARCH).tar

# Sorted by shebang rather than by name or suffix. Half the commands in
# /usr/bin are Python with no extension, and handing one of those to shellcheck
# produces nothing but a complaint about the language.
lint:
	@py=""; sh=""; \
	for f in tools/*.sh tools/*.py webapps/freetvos-webapp cast/dial/*.py \
	         image/overlay/usr/bin/freetvos-* \
	         image/overlay/usr/share/freetvos/*.py \
	         image/overlay/usr/share/freetvos/hdmi/*.py; do \
	  case "$$(head -1 "$$f")" in \
	    *python*) py="$$py $$f" ;; \
	    *bash*|*/sh) sh="$$sh $$f" ;; \
	  esac; \
	done; \
	for f in $$py; do \
	  python3 -c 'import sys; compile(open(sys.argv[1]).read(), sys.argv[1], "exec")' \
	    "$$f" || exit 1; \
	done; \
	echo "python syntax ok"; \
	if command -v shellcheck >/dev/null; then shellcheck $$sh || exit 1; \
	else echo "shellcheck not installed, skipped"; fi
	@python3 tools/test-hdmi.py
	@python3 tools/test-services.py
	@python3 tools/test-media.py
	@echo "lint ok"

clean:
	rm -rf output
