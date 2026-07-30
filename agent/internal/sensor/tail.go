// Package sensor tails the JSON-lines logs produced by the standalone Zeek/Suricata sensors
// (sensor/zeek/bas.zeek, sensor/suricata/suricata.yaml) and emits parsed TLS/SNI/JA3/JA4 events.
// Pure parsing/tailing lives here; classification against the known-AI domain list and shadow-AI
// clustering (which need the DB) live in the daemon, wired via the Event callback.
package sensor

import (
	"bufio"
	"bytes"
	"fmt"
	"os"
	"strconv"
	"time"
)

// Event is what both tailers emit — a single TLS connection's identifying fields, tagged with
// which sensor produced it (agent/cmd/daemon/main.go writes this straight into platform_events).
type Event struct {
	SNI    string
	JA3    string
	JA4    string
	Source string
}

// tailFile follows path forever, calling onLine for each complete (newline-terminated) line.
// The read offset is persisted to offsetPath after each batch so a daemon restart resumes where
// it left off instead of reprocessing the whole log or silently skipping the gap. Deliberately
// does NOT handle log rotation — sensor/zeek/bas.zeek disables rotation and the Suricata config
// here has no rotation configured either, so there's exactly one growing file per sensor for
// Phase 2. If the file is ever truncated (smaller than our recorded offset), the offset resets
// to 0 rather than erroring, since that can only mean the file was legitimately recreated.
func tailFile(path, offsetPath string, onLine func([]byte)) error {
	offset := readOffset(offsetPath)

	for {
		f, err := os.Open(path)
		if err != nil {
			time.Sleep(2 * time.Second)
			continue
		}

		if stat, err := f.Stat(); err == nil && stat.Size() < offset {
			offset = 0
		}
		if _, err := f.Seek(offset, 0); err != nil {
			f.Close()
			time.Sleep(2 * time.Second)
			continue
		}

		reader := bufio.NewReaderSize(f, 64*1024)
		advanced := false
		for {
			line, err := reader.ReadBytes('\n')
			if len(line) > 0 && err == nil {
				onLine(bytes.TrimRight(line, "\n"))
				offset += int64(len(line))
				advanced = true
			}
			if err != nil {
				break // EOF (or a not-yet-newline-terminated partial line) — offset stays before it
			}
		}
		f.Close()

		if advanced {
			writeOffset(offsetPath, offset)
		}
		time.Sleep(2 * time.Second)
	}
}

func readOffset(path string) int64 {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0
	}
	n, err := strconv.ParseInt(string(bytes.TrimSpace(data)), 10, 64)
	if err != nil {
		return 0
	}
	return n
}

func writeOffset(path string, offset int64) {
	_ = os.WriteFile(path, []byte(fmt.Sprintf("%d", offset)), 0o644)
}
