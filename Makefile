.PHONY: setup db-up db-down ai-engine-run agent-build daemon-run extension-build health test clean \
        sensor-up sensor-down sensor-status \
        dataset-gen dataset-serve mock-ai-up mock-ai-down \
        endpoints-build endpoints-up endpoints-down endpoints-test eval-run \
        dashboard-setup dashboard-dev \
        report-setup report-build

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
	sudo systemctl stop bas-zeek bas-zeek-lo bas-suricata

sensor-status:
	systemctl status bas-zeek bas-zeek-lo bas-suricata --no-pager

# --- Phase 3: labeled dataset + mock AI + test fleet + eval ---------------------------------

dataset-gen:
	python3 eval/generate_dataset.py

dataset-serve:
	cd eval/dataset && python3 -m http.server 8877

mock-ai-up:
	bash sensor/mock-ai/serve.sh

mock-ai-down:
	pkill -f "s_server .*-accept 8543" || true
	pkill -f "s_server .*-accept 8544" || true

endpoints-build:
	docker compose -f endpoints/docker-compose.yml build

endpoints-up:
	docker compose -f endpoints/docker-compose.yml up -d

endpoints-down:
	docker compose -f endpoints/docker-compose.yml down

# Runs driver.py inside each already-running endpoint container, one at a time (sequential —
# see the plan's resource note: 4 concurrent headless-Chrome-plus-Go-daemon containers alongside
# everything else already running on this VM is not free lunch). svc:user pairs match
# endpoints/docker-compose.yml's OS_USERNAME values.
endpoints-test:
	for pair in endpoint-priya:priya.sharma endpoint-arjun:arjun.mehta \
	            endpoint-karan:karan.iyer endpoint-divya:divya.rao; do \
		svc="$${pair%%:*}"; user="$${pair##*:}"; \
		echo "=== $$svc ($$user) ==="; \
		docker compose -f endpoints/docker-compose.yml exec -T --user "$$user" "$$svc" \
			/opt/browser-ai-sentinel/venv/bin/python \
			/opt/browser-ai-sentinel/endpoints/driver.py; \
	done

eval-run:
	python3 eval/evaluate.py

# --- Phase 4: dashboard --------------------------------------------------------------------

dashboard-setup:
	cd dashboard && npm install --no-fund --no-audit

dashboard-dev:
	cd dashboard && npm run dev

# --- Capstone report ------------------------------------------------------------------------

report-setup:
	cd docs/report && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

report-build:
	cd docs/report && .venv/bin/python build_report.py && \
	libreoffice --headless --convert-to pdf Browser_AI_Sentinel_Final_Report_Sushanth_Sridhar.docx

health:
	@echo "-- ai-engine :8100 --"; curl -sf http://127.0.0.1:8100/health || echo "DOWN"
	@echo "-- daemon :8090 --"; curl -sf http://127.0.0.1:8090/health || echo "DOWN"
	@echo "-- bas-zeek --"; systemctl is-active bas-zeek || echo "DOWN"
	@echo "-- bas-zeek-lo --"; systemctl is-active bas-zeek-lo || echo "DOWN"
	@echo "-- bas-suricata --"; systemctl is-active bas-suricata || echo "DOWN"

test:
	cd agent && go vet ./... && go build ./...
	cd extension && npx tsc --noEmit

clean:
	rm -rf agent/bin extension/dist extension/node_modules ai-engine/.venv eval/dataset eval/results dashboard/node_modules dashboard/dist docs/report/.venv
