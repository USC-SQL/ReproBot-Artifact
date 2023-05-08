import time
from os.path import exists, expanduser, join
from telnetlib import Telnet


class TelnetWrapper():
    def __init__(self, port, ip="localhost", auth=None):
        self.tn = Telnet(ip, port)
        if not auth:
            auth_file_path = join(expanduser("~"), ".emulator_console_auth_token")
            if exists(auth_file_path):
                with open(auth_file_path, "r") as f:
                    auth = f.read().rstrip("\n")
            else:
                raise Exception(
                    f"Cannot find auth file for android emulator console at {auth_file_path}. Please check it or specify the auth in the method argument.")
        self.tn.read_until(b"OK", timeout=10)
        self.tn.write(f"auth {auth}\n".encode("ascii"))
        self.tn.read_until(b"OK", timeout=10)

    def load_snapshot(self, snap_shot_name):
        self.tn.write(f"avd snapshot load {snap_shot_name}\n".encode("ascii"))
        t = self.tn.read_until(b"OK", timeout=10)
        if "OK" not in t.decode():
            exit("Timeout when loading snapshot. The snapshot may be lost or damaged")
        time.sleep(3)

    def save_snapshot(self, snap_shot_name):
        self.tn.write(f"avd snapshot save {snap_shot_name}\n".encode("ascii"))
        self.tn.read_until(b"OK", timeout=10)

    def close(self):
        self.tn.write(b"exit\n")
