# Browser AI Sentinel — Phase 3 test-fleet endpoint image. One image, parameterized at runtime
# (entrypoint.sh) by OS_USERNAME/DAEMON_PORT/ENDPOINT_NAME/BEHAVIOR_PROFILE — not four separate
# builds — so all four "employees" in docker-compose.yml share one image.
#
# Build context is the REPO ROOT (see endpoints/docker-compose.yml's `context: ..`), since this
# needs agent/ source and extension/dist, not just files under endpoints/.

FROM golang:1.22-bookworm AS agent-build
WORKDIR /src
COPY agent/go.mod agent/go.sum ./
RUN go mod download
COPY agent/ ./
RUN go build -o /out/daemon ./cmd/daemon && go build -o /out/nmhost ./cmd/nmhost

FROM ubuntu:24.04

# Google Chrome via the official apt repo — NOT the `chromium-browser` package, which is a
# snap wrapper on Ubuntu 24.04 and doesn't function inside a container (confirmed via
# `apt-cache policy` during Phase 3 planning: no real chromium candidate, only the snap stub).
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl gnupg ca-certificates python3 python3-venv sudo \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

COPY --from=agent-build /out/daemon /out/nmhost /usr/local/bin/
COPY extension/dist /opt/browser-ai-sentinel/extension
COPY endpoints/driver.py endpoints/requirements.txt /opt/browser-ai-sentinel/endpoints/
COPY endpoints/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/daemon /usr/local/bin/nmhost

RUN python3 -m venv /opt/browser-ai-sentinel/venv \
    && /opt/browser-ai-sentinel/venv/bin/pip install --no-cache-dir -q -r /opt/browser-ai-sentinel/endpoints/requirements.txt

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
