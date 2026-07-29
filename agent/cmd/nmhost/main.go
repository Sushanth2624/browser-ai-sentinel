// Command nmhost is the ephemeral half of the agent: Chrome spawns this process per extension
// session via the Native Messaging API and kills it when the port disconnects. It carries no
// logic of its own — it only translates Chrome's native-messaging stdio framing (4-byte
// little-endian length prefix + JSON) into an HTTP POST against the always-on daemon and relays
// the daemon's JSON response back the same way. All real work happens in cmd/daemon.
package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"io"
	"net/http"
	"os"
)

func main() {
	daemonURL := os.Getenv("DAEMON_NM_URL")
	if daemonURL == "" {
		daemonURL = "http://127.0.0.1:8090/nm"
	}

	client := &http.Client{}

	for {
		msg, err := readMessage(os.Stdin)
		if err != nil {
			if err == io.EOF {
				return // Chrome closed the port — normal shutdown
			}
			fatal(err)
		}

		resp, err := client.Post(daemonURL, "application/json", bytes.NewReader(msg))
		if err != nil {
			writeMessage(os.Stdout, errorResponse(err))
			continue
		}
		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			writeMessage(os.Stdout, errorResponse(err))
			continue
		}
		if err := writeMessage(os.Stdout, body); err != nil {
			fatal(err)
		}
	}
}

func readMessage(r io.Reader) ([]byte, error) {
	var length uint32
	if err := binary.Read(r, binary.LittleEndian, &length); err != nil {
		return nil, err
	}
	buf := make([]byte, length)
	if _, err := io.ReadFull(r, buf); err != nil {
		return nil, err
	}
	return buf, nil
}

func writeMessage(w io.Writer, payload []byte) error {
	if err := binary.Write(w, binary.LittleEndian, uint32(len(payload))); err != nil {
		return err
	}
	_, err := w.Write(payload)
	return err
}

func errorResponse(err error) []byte {
	return []byte(fmt.Sprintf(`{"ok":false,"error":%q}`, err.Error()))
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "nmhost fatal:", err)
	os.Exit(1)
}
