import subprocess
import time
from os.path import join

import adbutils.errors
import cv2
import numpy as np
import uiautomator2
import uiautomator2 as u2
from bs4 import BeautifulSoup
from uiautomator2 import RetryError, UiObjectNotFoundError, GatewayError
from urllib3.exceptions import ReadTimeoutError

from rl_module.components.s2r import S2R
from rl_module.components.state_obj import State
from rl_module.environment.reward_calculator import calculate_reward
from rl_module.environment.telnet_wrapper import TelnetWrapper
from utils.cmd_args import crash_log, device_id, adb_port, setup_apk, setup_test_apk, setup_apk_pkg, \
    setup_test_apk_pkg, apk_file_path
from utils.config import app_name, pkg_name, snapshot, logcat_dir
from utils.nlp_util import parse_uiautomator_location
from utils.setup_run import run
from utils.utils import read_json, get_logger, restart_adb, dump_file
from copy import deepcopy

logger = get_logger("environment")


class App_Env:
    def __init__(self, s2r_file, total_missing_step):
        self.s2rs = self.load_s2rs(s2r_file)
        self.unmatched_s2r = deepcopy(self.s2rs)
        self.app_pid = None
        self.total_missing_step = total_missing_step
        self.remaining_missing_steps = total_missing_step
        self.cur_orientation = 'natural'
        self.telnet = TelnetWrapper(adb_port)
        self.connect_uiautomator()
        logger.info(f"Telnet connected to emulator.")
        self.setup_apk_start_time = 0

    def print_device_info(self):
        logger.debug("Trying to connect to uiautomator")
        restart_times = 10
        while restart_times >= 0:
            try:
                # self.d.shell(['pm', 'install', '-r', '-t', '/data/local/tmp/app-uiautomator.apk'])
                logger.info(f"Android emulator info: {self.d.info}")
                return
            except (OSError, uiautomator2.exceptions.GatewayError, uiautomator2.GatewayError) as e:
                logger.info("Trying to reinit uiautomator")
                p = subprocess.Popen(["python", "-m", "uiautomator2", "init"])
                p.wait(60)
            restart_times -= 1
        logger.error("Unable to start UIAutomator...")
        raise Exception("ConnectionRefusedError: Unable to connect to UIAutomator")

    def connect_uiautomator(self):
        self.d = u2.connect(device_id)
        logger.info(f"RL environment initialized: {app_name}, {pkg_name}, {len(self.s2rs)} steps")
        self.print_device_info()
        self.d.app_uninstall_all(excludes=['com.wparam.nullkeyboard'])

    def start_app_use_adb(self):
        logger.info(f"Starting App {app_name}")
        self.d.app_stop(pkg_name)
        self.d.app_start(pkg_name,use_monkey=True)
        pid = self.d.app_wait(pkg_name,
                              front=True)  # remember to add fron argument, it will wait the app until it becomes the current running one
        current_running = self.d.current_app()['package'] == pkg_name
        if not (pid and current_running):
            logger.error("App is not running!")
            raise Exception("App cannot start")
        else:
            logger.info("App started!")
            self.app_pid = pid

    def start_setup_apk(self):
        # self.setup_apk_start_time += 1
        # if self.setup_apk_start_time % 10 == 0:
        #     logger.debug("Reached %d times of setup apk starts. Reset UIAutomator." % self.setup_apk_start_time)
        #     self.d._force_reset_uiautomator_v2()
        if self.d.uiautomator.running():
            self.d.uiautomator.stop()
        if setup_apk_pkg in self.d.app_list():
            self.d.app_uninstall(setup_apk_pkg)
        self.d.app_install(setup_apk)
        if setup_test_apk_pkg in self.d.app_list():
            self.d.app_uninstall(setup_test_apk_pkg)
        self.d.app_install(setup_test_apk)
        self.d.shell(["am", "instrument", "-w", setup_test_apk_pkg + "/android.support.test.runner.AndroidJUnitRunner"])
        # self.d.app_uninstall(setup_apk_pkg)
        # self.d.app_uninstall(setup_test_apk_pkg)
        if not self.d.uiautomator.running():
            self.d.uiautomator.start()
            time.sleep(2)

    def start_app_load_snapshot(self):
        self.telnet.load_snapshot(snapshot)

    # start/restart the app
    def stat_app(self):
        setup_start = time.time()
        if pkg_name in self.d.app_list():
            self.d.app_uninstall(pkg_name)
        self.d.app_install(apk_file_path)
        if snapshot is not None:
            self.start_app_load_snapshot()
        elif setup_apk is not None and setup_test_apk is not None:
            self.start_setup_apk()
        else:
            self.d.app_start(pkg_name,use_monkey=True)
            self.d.app_wait(pkg_name,front=True)
            time.sleep(1)
            run(self.d, pkg_name)
            time.sleep(1)
        self.print_device_info()
        setup_end = time.time()
        logger.info("Setup delay: %s" % (setup_end - setup_start))

    def cur_state(self):
        # time.sleep(2)  # wait the app started or the action finished before dumping the state
        retry_time = 10
        xml = None
        while retry_time > 0:
            time.sleep(1.5)
            try:
                xml = self.d.dump_hierarchy()  # return the hierarchy in xml string
                break
            except Exception as e:
                logger.error("Cannot dump hierarchy. Try again..")
                retry_time -= 1
        if xml is None:
            logger.error("Failed to capture VH, Created a empty one as replace")
            xml = '<?xml version="1.0" encoding="utf-8"?><hierarchy rotation="0"></hierarchy>'  # an empty xml
        state_xml = BeautifulSoup(xml, 'xml')
        screen_shot = self.get_screen_shot()
        return State(state_xml, deepcopy(self.unmatched_s2r), self.remaining_missing_steps, screen_shot)

    # execute the action using controller and return the next state as well as the reward
    def execute_action(self, action):
        reward = calculate_reward(action, self.d.window_size())
        # execute ui event onto app
        self.execute_ui_event(action.ui_event)

        # modify unmatched s2r
        s2r_to_be_removed = [i for i in self.unmatched_s2r if i.get_index() == action.s2r.get_index()]
        for s2r in s2r_to_be_removed:
            self.unmatched_s2r.remove(s2r)

        if action.matched_with_empty_s2r():
            self.remaining_missing_steps -= 1
        return reward

    def interact_with_app(self, tgt_x, tgt_y, event_action, resource_id, input_value,
                          scroll_or_swipe_range):  # starting point and ending point of scroll and swipe
        if event_action == "INPUT":
            self.d.click(tgt_x, tgt_y)  # click the EditText box to focuse it
            try:
                self.d(resourceId=resource_id, focused=True).set_text(
                    input_value)  # An add-hoc way to avoid selector to be matched with several EditText box which happend when only using resourceId.
            except UiObjectNotFoundError as e:
                logger.error(f"Unable to find target view using just resource_id: {resource_id}.")
            if resource_id == "android:id/search_src_text":
                self.d.press("enter")  # the enter button needs to be pressed after input in a search box
            # self.d.press("back") # cannot add this, used for hidding keyboard, but would have unexpected behavior
        elif event_action == "BACK":
            self.d.press("back")
        elif event_action == "ROTATE":
            if self.cur_orientation == 'natural':
                orientation = 'left'
            else:
                orientation = 'natural'
            retry_time = 3
            while retry_time > 0:
                self.d.set_orientation(orientation)
                time.sleep(2)
                if self.d.orientation != self.cur_orientation and self.d.orientation == orientation:
                    self.cur_orientation = orientation
                    break
                else:
                    logger.error("Failed to rotate, retry..")
                    retry_time -= 1
        elif event_action == "CLICK":
            self.d.click(tgt_x, tgt_y)
        elif event_action == "LONG CLICK":
            self.d.long_click(tgt_x, tgt_y, duration=1)
        elif event_action in ["SWIPE", "SCROLL"]:
            x_1, y_1, x_2, y_2 = parse_uiautomator_location(scroll_or_swipe_range)
            self.d.swipe(x_1, y_1, x_2, y_2)

    def execute_ui_event(self, event):
        tgt_x, tgt_y = event.get_xy()
        resource_id = event.get_resource_id()
        self.interact_with_app(tgt_x, tgt_y, event.action, resource_id, event.input_value,
                               event.get_scroll_or_swipe_range())

    def check_termination(self, next_state: State):
        crashed = self.is_crashed(next_state)
        if crashed:
            logger.info("Successfully reproduced!")
            return True

        available_actions = next_state.obtain_available_actions()
        if len(available_actions) == 0:
            logger.info("Epoch Terminate: No available actions in next state.")
            return False
        return None

    def jumped_out_of_app(self):
        return self.d.current_app()['package'] != pkg_name

    def shown_error_msg(self, cur_state: State):  # not very correct since the crash msg may not be using such id
        android_texts = cur_state.ui_hierarchy.find_all(
            attrs={"resource-id": lambda x: x in ["android:id/message", "android:id/alertTitle"],
                   "text": lambda x: "stopped" in x or "keeps stopping" in x})
        return len(android_texts) != 0

    def clear_logcat(self):
        self.d.shell("logcat -c")

    def show_crash_in_log(self):
        log = self.d.shell("logcat -d")
        fatal_in = "FATAL" in log.output or "ACRA caught a"  # some app used ACRA to catch report which would not be thrown to the system level such like: recdrod-30 or recdroid-64
        crash_log_in = crash_log in log.output
        if fatal_in and not crash_log_in:
            logger.info("Triggered a crash, but not the same with bug report")
        match_crash = fatal_in and crash_log_in
        return match_crash

    def is_crashed(self, cur_state) -> bool:
        # running_app = self.d.app_list_running()
        # app_stoped = pkg_name not in running_app
        # app_crashed = self.shown_error_msg(cur_state)
        app_crashed = self.show_crash_in_log()
        return app_crashed

    def get_screen_shot(self):
        try:
            screenshot = self.d.screenshot(format='opencv')
            if screenshot is None:
                raise cv2.error
            return screenshot
        except cv2.error or IOError or ReadTimeoutError as e:
            w, h = self.d.window_size()
            fake_img = np.zeros((h, w), np.uint8)
            fake_img.fill(255)
            return fake_img

    def refresh_env(self):
        self.unmatched_s2r = deepcopy(self.s2rs)
        self.remaining_missing_steps = self.total_missing_step
        self.d.press('home')
        self.d.set_orientation("n")  # refresh orientation back to normal
        self.stat_app()
        self.clear_logcat()

    def stop_app(self):
        self.d.app_stop(pkg_name)

    def dump_logcat(self, epoch, step):
        log = self.d.shell("logcat -d")
        logcat_file = join(logcat_dir, f"epoch_{epoch}_step_{step}.txt")
        dump_file(log.output, logcat_file)

    def load_s2rs(self, s2r_file):
        s2rs = read_json(s2r_file)
        s2r_objs = [S2R(s2r) for s2r in s2rs]
        return s2r_objs
