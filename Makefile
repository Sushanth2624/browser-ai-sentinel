.PHONY: setup db-up db-down ai-engine-run agent-build daemon-run extension-build health test clean sensor-up sensor-down sensor-status

setup: db-up ai-engine-setup agent-build extension-build
	@echo "Phase 1 setup complete. Run 'make sensor-up' (once, needs root), 'make ai-engine-run' and 'make daemon-run' in separate terminals, then load extension/dist unpacked in chrome://extensions."

db-up:
	cd db && docker compose up -d

db-down:
	cd db && docker compose down

ai-engine-setup:
	cd ai-engine && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

ai-engine-run:
	cd ai-engine && .venv/bin/uvicorn api:app --host 127.0.0.1 --port 8100

agent-build:
	cd agent && go build -o bin/daemon ./cmd/daemon && go build -o bin/nmhost ./cmd/nmhost

daemon-run: agent-build
	cd agent && ./bin/daemon

extension-build:
	cd extension && npm install --no-fund --no-audit && npx tsc --noEmit && node build.mjs

sensor-up:
	sudo bash deploy/install-sensors.sh

sensor-down:
	sudo systemctl stop bas-zeek bas-suricata

sensor-status:
	systemctl status bas-zeek bas-suricata --no-pager

health:
	@echo "-- ai-engine :8100 --"; curl -sf http://127.0.0.1:8100/health || echo "DOWN"
	@echo "-- daemon :8090 --"; curl -sf http://127.0.0.1:8090/health || echo "DOWN"
	@echo "-- bas-zeek --"; systemctl is-active bas-zeek || echo "DOWN"
	@echo "-- bas-suricata --"; systemctl is-active bas-suricata || echo "DOWN"

test:
	cd agent && go vet ./... && go build ./...
	cd extension && npx tsc --noEmit

clean:
	rm -rf agent/bin extension/dist extension/node_modules ai-engine/.venv
