# What tools/gen-assets.sh draws with: a rasteriser, and the font the wordmark,
# banners and installer art are outlined from. None of it goes near the
# television's own image, which only ever receives the finished PNGs.
FROM quay.io/fedora/fedora-bootc:44
RUN dnf install -y --setopt=install_weak_deps=False \
      librsvg2-tools \
      python3-fonttools \
      google-noto-sans-fonts \
 && dnf clean all
# HarfBuzz applies the font's kerning. Without it text is still set, only with
# plain advances, so its absence is not worth failing over.
RUN dnf install -y --setopt=install_weak_deps=False python3-uharfbuzz \
 || echo "python3-uharfbuzz unavailable: text will be set without kerning"; \
    dnf clean all
