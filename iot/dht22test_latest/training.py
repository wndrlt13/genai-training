#!/usr/bin/env python3
import json, os, csv, time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

BROKER  = "test.mosquitto.org"
PORT    = 1883
TOPIC   = "smartcity/env"
CSV_PATH = "smartcity_env_log.csv"

# Ensure the CSV file has a header
def ensure_header(path):
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    if not exists:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["iso_time", "epoch_ms", "temp_c", "hum"])

# MQTT connect callback
def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected:", rc)
    client.subscribe(TOPIC)

# MQTT message callback
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        temp = payload.get("temp")
        hum  = payload.get("hum")
        ts = payload.get("ts")  # millis since boot

        # Validate fields
        if temp is None or hum is None or ts is None:
            print("Skipping (missing fields):", payload)
            return

        # Generate wall-clock timestamp for logging
        iso_time = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([iso_time, ts, temp, hum])
        print(f"Logged -> {CSV_PATH}: temp={temp}, hum={hum}, ts={ts}")

    except Exception as e:
        print("Error handling message:", e)

# Main function
def main():
    ensure_header(CSV_PATH)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, keepalive=60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nExiting.")

if __name__ == "__main__":
    main()