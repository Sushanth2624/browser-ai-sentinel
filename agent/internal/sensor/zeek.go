package sensor

import "encoding/json"

// zeekSSLRecord matches the JSON shape of sensor/zeek/bas.zeek's ssl.log (LogAscii::use_json =
// T), confirmed against real captured output — only the fields this project needs are declared.
type zeekSSLRecord struct {
	ServerName string `json:"server_name"`
	JA3        string `json:"ja3"`
	JA4        string `json:"ja4"`
}

// TailZeekSSL blocks forever, following sslLogPath and calling onEvent for each connection that
// has an SNI (entries without one — bare-IP TLS connections — aren't useful for platform
// classification and are skipped).
func TailZeekSSL(sslLogPath, offsetPath string, onEvent func(Event)) error {
	return tailFile(sslLogPath, offsetPath, func(line []byte) {
		var rec zeekSSLRecord
		if err := json.Unmarshal(line, &rec); err != nil {
			return
		}
		if rec.ServerName == "" {
			return
		}
		onEvent(Event{SNI: rec.ServerName, JA3: rec.JA3, JA4: rec.JA4, Source: "zeek-ja3ja4"})
	})
}
