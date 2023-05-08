import argparse
import logging
from os.path import basename, join, exists, dirname, realpath
from pyaxmlparser import APK
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--apkFile", help="path to the apk file to be analyzed", default=None)
parser.add_argument("--outputDir",help="path to output", default="./output")
parser.add_argument("--reportFile", help="path to the bug report file to be analyzed", default=None)
parser.add_argument("--configFile", help="path to config file, default file is under src/utils/config.json", default=None)
parser.add_argument("--crashLogFile", help="path to file containing crash log served as oracle", default=None)
parser.add_argument("--snapshot", help="snapshot name to be load", default=None)
parser.add_argument("--setupApk", help="the path to the app used to provide setup scripts", default=None)
parser.add_argument("--setupTestApk", help="the path to the test apk containing the setup scripts", default=None)
parser.add_argument("--deviceId", help="android device ID", default=None)
parser.add_argument("--adbPort", help="adb port", default=None)
parser.add_argument("-overwriteLog", default=False, action="store_true")
parser.add_argument("-overwriteNLP", default=False, action="store_true")
parser.add_argument("-silent", help="if enabled, the log will be only saved to file", default=False, action="store_true")

# args for variants onlyNLP or onlyRL
parser.add_argument("-onlyNLP", help="if added, only S2R extraction phase would be executed", default=False, action="store_true")
parser.add_argument("-onlyRL", help="if added, only S2R matching phase would be executed", default=False, action="store_true")
parser.add_argument("--s2rFilePath",help="the path to provided S2R file, need if using onlyRL mode", default=None)

# args for replay and exploit
parser.add_argument("-replay", default=False, action="store_true")
parser.add_argument("-exploit", default=False, action="store_true")
parser.add_argument("--qTableFile", default=None,type=str, required=False)
parser.add_argument("--actionsDir", default=None, type=str, required=False)
parser.add_argument("--succStepFile", default="", type=str, required=False)

parser.add_argument("--openieIP", default="localhost", type=str, required=False)

args = parser.parse_args()

apk_file_path = args.apkFile
app_name, pkg_name  = None, None
if apk_file_path:
    app_name = basename(apk_file_path).rstrip(".apk")
    pkg_name = APK(apk_file_path).package
output_dir = args.outputDir
bug_report_file_path = args.reportFile
config_file = args.configFile
if config_file is None:
    config_file = join(dirname(realpath(__file__)), "config.json")
    if not exists(config_file):
        raise Exception("Neither customized config file nor default config file are found. Please use --configFile to set the path for config file.")
crash_log_file = args.crashLogFile
if crash_log_file:
    try:
        with open(crash_log_file,"r") as f:
            crash_log = f.read().strip()
    except FileNotFoundError:
        raise Exception(f"Crash log file {crash_log_file} doesn't exist. Please specify it again.")
else:
    crash_log = None
snapshot = args.snapshot
setup_apk = args.setupApk
setup_test_apk = args.setupTestApk
setup_apk_pkg = None
setup_test_apk_pkg= None
if setup_apk:
    setup_apk_pkg = APK(setup_apk).package
if setup_test_apk:
    setup_test_apk_pkg = APK(setup_test_apk).package
device_id = args.deviceId
adb_port = args.adbPort
overwriteNLP = args.overwriteNLP
overwriteLog = args.overwriteLog
silent = args.silent
onlyNLP = args.onlyNLP
onlyRL = args.onlyRL
s2rFilePath = args.s2rFilePath
replay = args.replay
exploit = args.exploit
q_table_file = args.qTableFile
actions_dir = args.actionsDir
succStepFile = args.succStepFile
openie_id = args.openieIP 

device_info = [not device_id, not adb_port]
if exploit:
    raise Exception("Unifinished only exploit mode.")

if replay:
    raise Exception("Unifinished replay mode.")

if onlyNLP and (not bug_report_file_path or not s2rFilePath):
    raise Exception("Please config reportFile, s2rFilePath in cmd args when using onlyNLP mode.")

if onlyRL and (not s2rFilePath or not apk_file_path or not crash_log_file or not bug_report_file_path or any(device_info)):
    raise Exception("Please config reportFile, s2rFilePath, apkFile, crashLogFile, device id, adb port in cmd args when using onlyRL mode.")

normal_run = not onlyRL and not onlyNLP and not replay and not exploit
if normal_run and (not apk_file_path or not crash_log_file or not bug_report_file_path or any(device_info)):
    raise Exception("Please config reportFile, apkFile, crashLog, device id, adb port in cmd args when using normal mode.")




