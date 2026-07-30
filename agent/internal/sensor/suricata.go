package sensor

import "encoding/json"

// suricataEveRecord matches the JSON shape of sensor/suricata/suricata.yaml's eve.json TLS
// events (outputs.eve-log.types: tls, ja3/ja4 enabled), confirmed against real captured output.
// eve.json carries many other event types (flow, alert, etc.) on the same file/stream — only
// "tls" records are relevant here.
type suricataEveRecord struct {
	EventType string `json:"event_type"`
	TLS       struct {
		SNI string `json:"sni"`
		JA3 struct {
			Hash string `json:"hash"`
		} `json:"ja3"`
		JA4 string `json:"ja4"`
	} `json:"tls"`
}

// TailSuricataEve blocks forever, following evePath and calling onEvent for each TLS record
// that has an SNI.
func TailSuricataEve(evePath, offsetPath string, onEvent func(Event)) error {
	return tailFile(evePath, offsetPath, func(line []byte) {
		var rec suricataEveRecord
		if err := json.Unmarshal(line, &rec); err != nil {
			return
		}
		if rec.EventType != "tls" || rec.TLS.SNI == "" {
			return
		}
		onEvent(Event{SNI: rec.TLS.SNI, JA3: rec.TLS.JA3.Hash, JA4: rec.TLS.JA4, Source: "suricata-ja3ja4"})
	})
}
