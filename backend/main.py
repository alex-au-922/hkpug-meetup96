import asyncio
import json
import os
import random

import paho.mqtt.client as mqtt
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from pydantic import BaseModel

app = FastAPI()

TEAM_ID = os.getenv("TEAM_ID", "local").lower()
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")

# SECURE MQTT CONNECTION FOR HOME EDITION
mqtt_client = mqtt.Client(client_id=f"backend_{TEAM_ID}")
mqtt_client.tls_set(
    ca_certs="/certs/ca/ca.crt",
    certfile="/certs/server/server.crt",
    keyfile="/certs/server/server.key",
)
try:
    mqtt_client.connect(MQTT_BROKER, 8883)
    mqtt_client.loop_start()
    print("✅ Backend connected to MQTT via mTLS.")
except Exception as e:
    print(f"❌ MQTT Connection failed: {e}")


class GameEngine:
    def __init__(self, env_name: str):
        self.env = env_name
        self.is_running = False
        self.level = 1
        self.current_minute = 0
        self.temp_c = 30.0
        self.distance_km = 5.0
        self.wife_is_home = False
        self.ac_status = False
        self.score = 0
        self.last_toggled_minute = -999
        self.broken_compressor = False
        self.logs = []
        self.last_temp_spike = False
        self.last_gps_drop = False
        self.last_packet_delay = False

        if self.env == "prod":
            self.sensor_rng = random.Random(f"HKPUG_SENSOR_PROD_{self.level}")
            self.api_rng = random.Random(f"HKPUG_API_PROD_{self.level}")
        else:
            self.sensor_rng = random.Random()
            self.api_rng = random.Random()

    def log(self, msg: str):
        hour = 18 + (self.current_minute // 60)
        minute = self.current_minute % 60
        time_str = f"{hour:02d}:{minute:02d}"
        self.logs.insert(0, f"[{time_str}] {msg}")
        if len(self.logs) > 15:
            self.logs.pop()

    def reset(self, level: int):
        self.is_running = True
        self.level = level
        self.current_minute = 0
        self.temp_c = 30.0
        self.distance_km = 5.0
        self.wife_is_home = False
        self.ac_status = False
        self.score = 0
        self.last_toggled_minute = -999
        self.broken_compressor = False
        self.logs = []
        self.last_temp_spike = False
        self.last_gps_drop = False
        self.last_packet_delay = False
        if self.env == "prod":
            self.sensor_rng = random.Random(f"HKPUG_SENSOR_PROD_{level}")
            self.api_rng = random.Random(f"HKPUG_API_PROD_{level}")
        else:
            self.sensor_rng = random.Random()
            self.api_rng = random.Random()
        self.log(f"Started {self.env.upper()} Simulation - Level {level}")


engines = {"staging": GameEngine("staging"), "prod": GameEngine("prod")}


def dump_state():
    try:
        os.makedirs("/shared", exist_ok=True)
        safe_staging = {
            k: v
            for k, v in engines["staging"].__dict__.items()
            if k not in ["sensor_rng", "api_rng"]
        }
        safe_prod = {
            k: v
            for k, v in engines["prod"].__dict__.items()
            if k not in ["sensor_rng", "api_rng"]
        }
        with open("/shared/state.json", "w", encoding="utf-8") as f:
            json.dump({"staging": safe_staging, "prod": safe_prod}, f)
    except Exception:
        pass


dump_state()


class ACCommand(BaseModel):
    command: str


@app.post("/api/{env}/ac")
def control_ac(env: str, payload: ACCommand, response: Response):
    if env not in engines:
        raise HTTPException(status_code=404)
    engine = engines[env]
    if not engine.is_running:
        raise HTTPException(status_code=400, detail="Simulation not running.")
    if engine.broken_compressor:
        raise HTTPException(status_code=400, detail="Compressor is destroyed.")

    if engine.level >= 4 and engine.api_rng.random() < 0.10:
        engine.log("⚠️ API simulated a 503 Network Drop.")
        dump_state()
        response.status_code = 503
        return {"error": "503 Service Unavailable."}

    target_status = payload.command.upper() == "ON"
    if target_status == engine.ac_status:
        return {"status": "ok", "msg": "Already in requested state"}

    if engine.level >= 3:
        if (engine.current_minute - engine.last_toggled_minute) < 5:
            engine.broken_compressor = True
            engine.ac_status = False
            engine.score -= 500
            engine.log("🔥 COMPRESSOR EXPLODED! Toggled under 5 mins.")
            dump_state()
            return {"status": "error", "msg": "Compressor exploded! -500 pts."}

    engine.ac_status = target_status
    engine.last_toggled_minute = engine.current_minute
    engine.log(f"AC turned {'ON' if target_status else 'OFF'}")
    dump_state()
    return {"status": "ok", "ac_status": engine.ac_status}


async def publish_mqtt(topic: str, payload: dict, delay: float = 0.0):
    if delay > 0:
        await asyncio.sleep(delay)
    mqtt_client.publish(topic, json.dumps(payload))


async def simulation_loop(env: str, level: int):
    engine = engines[env]
    engine.reset(level)
    dump_state()

    total_ticks = 60 if env != "prod" else 240 if level < 5 else 600

    for tick in range(total_ticks):
        if not engine.is_running:
            break
        engine.current_minute = tick
        hour = 18 + (tick // 60)
        minute = tick % 60
        time_str = f"{hour:02d}:{minute:02d}"

        if engine.ac_status and not engine.broken_compressor:
            engine.temp_c = max(18.0, engine.temp_c - 1.0)
        else:
            engine.temp_c = min(32.0, engine.temp_c + 0.5)

        base_dist = max(0.0, 5.0 - (tick * 0.2))
        engine.distance_km = max(0.0, base_dist + engine.sensor_rng.gauss(0, 0.15))

        if level >= 4 and tick >= 20:
            engine.wife_is_home = True

        if not engine.broken_compressor:
            if level == 1:
                if engine.temp_c <= 28.0:
                    engine.score += 10
            if level >= 2:
                if engine.wife_is_home:
                    if not engine.ac_status and engine.temp_c > 27.0:
                        engine.score -= 100
                    elif engine.temp_c < 21.0:
                        engine.score -= 20
                    else:
                        engine.score += 10
                elif engine.distance_km > 1.5:
                    if engine.ac_status:
                        engine.score -= 20
                    else:
                        engine.score += 10
                else:
                    if engine.temp_c > 27.0:
                        engine.score -= 50
                    elif engine.temp_c < 21.0:
                        engine.score -= 20
                    else:
                        engine.score += 10

        pub_temp = engine.temp_c
        pub_dist = round(engine.distance_km, 2)

        if level >= 3:
            if not engine.last_temp_spike and engine.sensor_rng.random() < 0.03:
                pub_temp = 99.9
                engine.last_temp_spike = True
            else:
                engine.last_temp_spike = False

            if not engine.last_gps_drop and engine.sensor_rng.random() < 0.03:
                pub_dist = None
                engine.last_gps_drop = True
            else:
                engine.last_gps_drop = False

            delay_room = (
                1.5
                if not engine.last_packet_delay and engine.sensor_rng.random() < 0.03
                else 0.0
            )
            engine.last_packet_delay = delay_room > 0
        else:
            delay_room = 0.0
            engine.last_temp_spike = False
            engine.last_gps_drop = False
            engine.last_packet_delay = False

        room_payload = {
            "sim_time": time_str,
            "temp_c": round(pub_temp, 1) if pub_temp != 99.9 else 99.9,
        }
        gps_payload = {"sim_time": time_str, "distance_km": pub_dist}
        occ_payload = {"sim_time": time_str, "wife_is_home": engine.wife_is_home}

        topic_base = f"cooldown/team_{TEAM_ID}/{env}/sensors"
        asyncio.create_task(
            publish_mqtt(f"{topic_base}/room", room_payload, delay_room)
        )
        asyncio.create_task(publish_mqtt(f"{topic_base}/gps", gps_payload, 0.0))
        asyncio.create_task(publish_mqtt(f"{topic_base}/occupancy", occ_payload, 0.0))

        dump_state()
        await asyncio.sleep(1)

    engine.is_running = False
    engine.log(f"Simulation Complete. Final Score: {engine.score}")
    dump_state()


@app.post("/api/{env}/start")
def start_simulation(env: str, level: int, background_tasks: BackgroundTasks):
    if env not in engines:
        raise HTTPException(status_code=404)
    if engines[env].is_running:
        raise HTTPException(status_code=400, detail="Already running!")
    background_tasks.add_task(simulation_loop, env, level)
    return {"msg": f"Started {env.upper()} Level {level}"}


@app.get("/api/dashboard_state")
def get_dashboard_state():
    return {"staging": engines["staging"].__dict__, "prod": engines["prod"].__dict__}
