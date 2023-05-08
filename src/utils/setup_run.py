import subprocess
from sys import argv

import uiautomator2 as u2


def print_info(d):
    restart_times = 10
    while restart_times >= 0:
        try:
            # self.d.shell(['pm', 'install', '-r', '-t', '/data/local/tmp/app-uiautomator.apk'])
            print(f"Android emulator info: {d.info}")
            return
        except (OSError, u2.exceptions.GatewayError, u2.GatewayError) as e:
            print("Trying to reinit uiautomator")
            p = subprocess.Popen(["python", "-m", "uiautomator2", "init"])
            p.wait(60)
        restart_times -= 1
    print("Unable to start UIAutomator...")
    raise Exception("ConnectionRefusedError: Unable to connect to UIAutomator")


def run(my_device: u2.Device, pkg_name):
    pass


if __name__ == '__main__':
    if len(argv)<3:
        print("Please input: (1) emulator id (2) package name")
    emulator_id = argv[1]
    pkg_name = argv[2]
    d = u2.connect(emulator_id)
    print_info(d)
    d.app_start(pkg_name, use_monkey=True)
    d.app_wait(pkg_name)
    run(d, pkg_name)
