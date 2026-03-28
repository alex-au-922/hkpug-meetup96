# 🧊 Project Cool Down: Home Edition

Welcome to the Home Edition of the HKPUG Systems Engineering Challenge! 
In this simulator, you will build a smart, autonomous Python AI to control a home Air Conditioning unit based on messy, real-world IoT data.

This local environment runs entirely on your machine using Docker. It automatically provisions an enterprise-grade Zero-Trust mTLS network, a physics engine, and a live visual dashboard.

---

## 📦 Step 0: Prerequisites
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Install Python 3.10+.
3. Install the required Python libraries for your AI script:
   ```bash
   pip install paho-mqtt==1.6.1 requests
   ```

---

## 🚀 Step 1: Boot the Environment
Open your terminal in this folder and run:
```bash
docker compose up -d --build
```
**What happens behind the scenes?**
1. Docker temporarily boots an Alpine Linux container to generate secure **mTLS Certificates** specific to your machine.
2. The certificates are placed in a new `certs/` folder on your hard drive.
3. The secure MQTT Broker (Mosquitto) and Physics Engine (FastAPI) boot up.
4. The Visual Dashboard boots up.

Verify it is working by opening your web browser to: 👉 **[http://localhost:9000](http://localhost:9000)**

---

## 🔐 Step 2: The Security Certificates (mTLS)
Because this simulates a real enterprise IoT network, you cannot connect to the data streams or send commands without proving your identity. 

Your Docker stack generated your keys inside the `./certs` folder. You will use these 3 files in your Python code:
* **Root CA:** `certs/ca/ca.crt` (To verify the server)
* **Client Cert:** `certs/client/client.crt` (Your public ID)
* **Client Key:** `certs/client/client.key` (Your private password)

---

## 📡 Step 3: Connecting to the Data (MQTT)
The physics engine emits sensor data every second (1 real second = 1 simulated minute). 
You must subscribe to these topics:
* `cooldown/team_local/<ENV>/sensors/room` (Temperature)
* `cooldown/team_local/<ENV>/sensors/gps` (Distance from home)
* `cooldown/team_local/<ENV>/sensors/occupancy` (Wife presence)

*(Note: `<ENV>` will be `staging` for practice, and `prod` for the official run).*

**Python MQTT Snippet:**
```python
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    print(f"Received: {msg.topic} -> {msg.payload.decode()}")

client = mqtt.Client()

# Attach your secure identity!
client.tls_set(
    ca_certs="certs/ca/ca.crt", 
    certfile="certs/client/client.crt", 
    keyfile="certs/client/client.key"
)

client.on_message = on_message
client.connect("localhost", 8883)
client.subscribe("cooldown/team_local/staging/sensors/#") 
client.loop_forever()
```

---

## 🎛️ Step 4: Sending Commands (REST API)
To turn the AC on or off, you must send an HTTP POST request to the API.

**Python API Snippet:**
```python
import requests

url = "https://localhost:8000/api/staging/ac"
certs = ("certs/client/client.crt", "certs/client/client.key")
payload = {"command": "ON"} # or "OFF"

# We pass verify="certs/ca/ca.crt" to securely verify the local server!
response = requests.post(url, json=payload, cert=certs, verify="certs/ca/ca.crt")
print(response.json())
```

---

## 🧪 Step 5: How to Test Your AI (The Digital Twin)
The physics engine is paused until you tell it to start. 
You can trigger a fast, 60-second staging simulation whenever you want by running this Python script in a separate terminal:

```python
# trigger_staging.py
import requests

url = "https://localhost:8000/api/staging/start?level=1" # Change level here!
certs = ("certs/client/client.crt", "certs/client/client.key")

print("🚀 Triggering Staging Simulation...")
response = requests.post(url, cert=certs, verify="certs/ca/ca.crt")
print(response.json())
```
Run your AI script, then run this trigger script, and watch your Dashboard score go up!

---

## 📊 The Rules & Scoring

### 🌍 The Physics Engine
* **Heating:** When AC is OFF, the room heats up by `+0.5°C/min`.
* **Cooling:** When AC is ON, the room cools down by `-1.0°C/min`.

### 🟢 Level 1: Hello World
*Just get the AC running and keep the room cool!*
* If Temp <= 28.0°C ➡️ **+10 pts / min**

### 🟡 Level 2: The Goldilocks Zone
*Electricity is expensive. Optimize your pre-cooling to hit the 21°C - 27°C window.*
* User is Far (>1.5km) & AC is OFF ➡️ **+10 pts / min (Eco Mode)**
* User is Far (>1.5km) & AC is ON ➡️ **-20 pts / min (Wasting Power)**
* User is Close (<=1.5km) & Temp > 27.0°C ➡️ **-50 pts / min (Too Hot)**
* User is Close (<=1.5km) & Temp < 21.0°C ➡️ **-20 pts / min (Freezing)**
* User is Close (<=1.5km) & Temp is 21.0°C - 27.0°C ➡️ **+10 pts / min (Perfect!)**

### 🟠 Level 3: Compressor Protection
*Real sensors are noisy. Hardware breaks.*
* **99.9°C Spikes:** The temperature sensor will occasionally glitch. If you don't filter it, your AI will panic.
* **5-Minute Hardware Lock:** If you toggle the AC state in under 5 minutes, the compressor violently explodes.
* **Penalty:** **-500 pts** and the AC is permanently destroyed for the run.

### 🔴 Level 4 & 5: The Boss Fight
*The network drops your requests, and the Wife is home!*
* **Network Blips:** 10% of your API requests will return `HTTP 503`. You must implement Retries!
* **W.A.F Penalty:** If the Wife is Home, the AC is OFF, and Temp > 27.0°C ➡️ **-100 pts / min** *(She overrides the GPS distance rules!)*
