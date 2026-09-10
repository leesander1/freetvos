include brand/brand.env
export

ARCH ?= $(ARCH_DEFAULT)

.PHONY: help build disk iso run widevine clean lint

help:
	@echo "$(BRAND_NAME) $(BRAND_VERSION)"
	@echo "  make build          build the OS container image (ARCH=arm64|amd64)"
	@echo "  make disk           produce a bootable qcow2 in ./output"
	@echo "  make iso            produce an installer ISO in ./output"
	@echo "  make run            boot ./output/qcow2/disk.qcow2 in QEMU"
	@echo "  make widevine       install the CDM on the running VM (cached)"
	@echo "  make lint           shellcheck and python syntax checks"
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

lint:
	@python3 -m py_compile cast/dial/freetvos-dial.py \
	  image/overlay/usr/share/freetvos/generate-desktop-entries.py
	@command -v shellcheck >/dev/null && shellcheck tools/*.sh webapps/freetvos-webapp \
	  image/overlay/usr/bin/freetvos-* || echo "shellcheck not installed, skipped"
	@echo "lint ok"

clean:
	rm -rf output
