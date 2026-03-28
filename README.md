# 🧊 Project Cool Down: Participant Starter Guide

Welcome to the HKPUG Systems Engineering Workshop. You are tasked with building a smart, autonomous AI to control a home Air Conditioning unit based on live IoT data.

You have been assigned to a **Team (A or B)**, and your local Raspberry Pi server acts as your "Home Gateway".

## 📦 Step 0: Prerequisites
Before you write any code, install the required Python libraries. Create a `requirements.txt` file with the following:
```text
paho-mqtt==1.6.1
requests
```
Install them via terminal:
```bash
pip install -r requirements.txt
```

---

## 🛠️ Step 1: Security Setup (mTLS)
Your server enforces **Zero-Trust Security**. You cannot subscribe to data or send commands without proving your identity.
1. Go to your assigned Dashboard URL (e.g., `http://<HOSTNAME>:9001`).
2. Click the blue button to download your `certs.zip` file.
3. Extract `ca.crt`, `client.crt`, and `client.key` into your Python project folder.

---

## 📡 Step 2: The MQTT Data Stream (Sensors)
The Raspberry Pi emits sensor data exactly once per second (1 real second = 1 simulated minute). 
There are 3 separate sensor topics you must subscribe to:

* **Room Temperature:** `cooldown/team_<YOUR_TEAM>/<ENV>/sensors/room`
* **GPS Distance:** `cooldown/team_<YOUR_TEAM>/<ENV>/sensors/gps`
* **Occupancy (Wife):** `cooldown/team_<YOUR_TEAM>/<ENV>/sensors/occupancy`

*Note: Replace `<YOUR_TEAM>` with `a` or `b`. Replace `<ENV>` with `staging` or `prod`.*

### MQTT Python Connection Example:
```python
import paho.mqtt.client as mqtt

# Define your environment
TEAM = "<YOUR_TEAM>"
ENV = "staging"  # Change to 'prod' during the official tournament!
HOSTNAME = "<HOSTNAME>" # Update to your assigned Pi's hostname or IP

def on_message(client, userdata, msg):
    print(f"Received on {msg.topic}: {msg.payload.decode()}")

client = mqtt.Client()

# Security: Attach your certificates!
client.tls_set(ca_certs="ca.crt", certfile="client.crt", keyfile="client.key")

client.on_message = on_message
client.connect(HOSTNAME, 8883)

# Subscribe to ALL sensor topics using the # wildcard
client.subscribe(f"cooldown/team_{TEAM}/{ENV}/sensors/#") 
client.loop_forever()
```

---

## 🎛️ Step 3: The REST API (Control)
To turn the AC on or off, you must send an HTTP POST request to the API.

* **URL:** `https://<HOSTNAME>:8001/api/<ENV>/ac`
* **Method:** `POST`
* **Payload:** `{"command": "ON"}` or `{"command": "OFF"}`

### REST API Python Connection Example:
```python
import requests
import urllib3

# Suppress warnings for local DNS certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOSTNAME = "<HOSTNAME>" # Update to your assigned Pi
ENV = "staging"
PORT = 8001 # Port 8001 for Team A, 8002 for Team B

url = f"https://{HOSTNAME}:{PORT}/api/{ENV}/ac"
certs = ("client.crt", "client.key")
payload = {"command": "ON"}

response = requests.post(url, json=payload, cert=certs, verify="ca.crt")
print(response.json())
```

---

## 🧪 Step 4: How to Test Your Code (The Digital Twin)
**DO NOT TEST IN PROD.** 
If you crash the Prod server, your official score is ruined. Use your Staging environment.

You can trigger a fast, 60-second staging simulation whenever you want. Create a file called `trigger_staging.py` and run it in a separate terminal:

```python
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOSTNAME = "<HOSTNAME>"
PORT = 8001
ENV = "staging"
LEVEL = 1  # Change this to test harder levels!

url = f"https://{HOSTNAME}:{PORT}/api/{ENV}/start?level={LEVEL}"
certs = ("client.crt", "client.key")

print(f"🚀 Triggering {ENV.upper()} Simulation - Level {LEVEL}...")
response = requests.post(url, cert=certs, verify="ca.crt")
print(response.json())
```
Watch your main Python script react to the incoming data, and check your Dashboard to see your score!
