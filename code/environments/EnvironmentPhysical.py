import os
import time
import requests
import numpy as np
from environments.Environment import Environment


class EnvironmentPhysical(Environment):
    """
    Physical environment abstraction communicating with an ESP32-based
    differential-drive mobile robot over Wi-Fi via HTTP.
    """

    def __init__(self, config):
        super().__init__(config)
        # Local IP address assigned to the ESP32 HTTP server
        self.ip_robo = os.getenv("ROBO_IP", "http://192.168.4.17")
        self.headers = {"Connection": "close"}

        self.observation_space_dimension = 2
        self.action_space_dimension = 2
        self.prev_obs = np.array([1.0, 1.0])
        self.current_obs = np.array([1.0, 1.0])
        self.last_action = [255, 255]
        self.step_count = 0
        self.off_track_streak = 0

    def create_environment(self):
        print("[Physical Environment] Initializing HTTP communication interface.")

    def get_initial_observation(self):
        self._stop_robot()
        print("\n[TRIAL SETUP] Position the robot at the start of the track (3s)...")
        time.sleep(3.0)
        self.current_obs = self._read_sensors()
        self.prev_obs = self.current_obs.copy()
        self.step_count = 0
        self.off_track_streak = 0
        return self.current_obs

    def get_observation(self):
        return self.current_obs

    def _stop_robot(self):
        try:
            t0 = time.perf_counter()
            requests.get(f"{self.ip_robo}/parar", headers=self.headers, timeout=1.5)
            lat_stop = (time.perf_counter() - t0) * 1000
            print(f"[NETWORK LATENCY] Stop (/parar): {lat_stop:.1f} ms")
        except Exception:
            print("[NETWORK WARNING] Timeout on /parar request.")

    def set_action(self, action):
        try:
            v_esq = float(np.squeeze(action[0]))
            v_dir = float(np.squeeze(action[1]))
            self.last_action = [v_esq, v_dir]

            # Map wheel commands to H-bridge rotation directions
            cmd_esq = 255 if v_esq >= 0 else -255
            cmd_dir = 255 if v_dir >= 0 else -255

            t0 = time.perf_counter()
            requests.get(
                f"{self.ip_robo}/mover?e={cmd_esq}&d={cmd_dir}",
                headers=self.headers,
                timeout=3.0
            )
            lat_move = (time.perf_counter() - t0) * 1000
            print(f"[NETWORK LATENCY] Actuation (/mover?e={cmd_esq}&d={cmd_dir}): {lat_move:.1f} ms")

            time.sleep(0.05)
        except Exception as e:
            print(f"[NETWORK WARNING] Failed /mover request: {e}")

    def is_done(self):
        return self._check_if_done(self.current_obs)

    def get_reward(self):
        return self._calculate_reward(self.current_obs)

    def _read_sensors(self):
        try:
            t0 = time.perf_counter()
            resp = requests.get(
                f"{self.ip_robo}/sensores",
                headers=self.headers,
                timeout=2.5
            ).json()
            lat_sensor = (time.perf_counter() - t0) * 1000
            print(f"[NETWORK LATENCY] Perception (/sensores): {lat_sensor:.1f} ms")
            return np.array([float(resp["esq"]), float(resp["dir"])])
        except Exception:
            print("[NETWORK WARNING] Timeout on /sensores. Keeping previous observation.")
            return self.current_obs

    def step(self):
        self.step_count += 1
        self.prev_obs = self.current_obs.copy()
        self.current_obs = self._read_sensors()

        if self.current_obs[0] == 0.0 and self.current_obs[1] == 0.0:
            self.off_track_streak += 1
        else:
            self.off_track_streak = 0

        reward = self._calculate_reward(self.current_obs)
        done = self._check_if_done(self.current_obs)
        return self.current_obs, reward, done

    def _calculate_reward(self, obs):
        if obs[0] == 1.0 and obs[1] == 1.0:
            # Maximum reward for advancing straight while centered
            if self.last_action[0] > 0 and self.last_action[1] > 0:
                return 1.0
            # Maximum reward when a differential turn corrects a prior drift
            if not (self.prev_obs[0] == 1.0 and self.prev_obs[1] == 1.0) and (
                self.last_action[0] != self.last_action[1]
            ):
                return 1.0
            return 0.0
        elif obs[0] == 0.0 and obs[1] == 0.0:
            return -1.0
        else:
            return 0.2

    def _check_if_done(self, obs):
        if self.step_count >= 20:
            return True
        if self.step_count >= 2 and self.off_track_streak >= 2:
            print("[TERMINATION] Robot off-track for 2 consecutive steps.")
            return True
        return False
