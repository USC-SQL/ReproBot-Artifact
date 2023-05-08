import json
import logging
import sys
from datetime import datetime
import argparse
from os import makedirs
from shutil import rmtree, copyfile
from os.path import exists, join, basename

from bs4 import Tag

from utils.cmd_args import *

with open(config_file, "r") as f:
    config = json.load(f)

# commands
JAVA_CMD = config['commands']['JAVA_CMD']
GRAPHENE_JAR = config['commands']['GRAPHENE_JAR']
ADB_CMD = config['commands']['ADB_CMD']

# logging
logger_level = logging.DEBUG

# setup output
nlp_output_dir = join(output_dir, "nlp_output")
graphene_output_file =  join(dirname(s2rFilePath), basename(bug_report_file_path).replace(".txt","-graphene.json")) if s2rFilePath else join(nlp_output_dir, basename(bug_report_file_path).replace(".txt","-graphene.json"))
s2r_file_path = s2rFilePath if s2rFilePath is not None else join(nlp_output_dir,
                                                                 "s2rs-" + basename(bug_report_file_path).replace(".txt",".json"))
log_dir = join(output_dir, "logs")
CURRENT_TIME = datetime.now().strftime('%m-%d-%H:%M:%S')
uiautomator_state_dir = join(output_dir, "uiautomator_state", CURRENT_TIME)
rl_running_log_dir = join(output_dir, "rl_log", CURRENT_TIME)
logcat_dir = join(output_dir, "logcat", CURRENT_TIME)

if overwriteNLP:
    rmtree(nlp_output_dir, ignore_errors=True)
makedirs(nlp_output_dir, exist_ok=True)
copyfile(bug_report_file_path, join(nlp_output_dir, basename(bug_report_file_path)))

if overwriteLog:
    rmtree(log_dir, ignore_errors=True)
    rmtree(join(output_dir, "uiautomator_state"), ignore_errors=True)
    rmtree(join(output_dir, "rl_log"), ignore_errors=True)
    rmtree(join(output_dir, "logcat"), ignore_errors=True)

makedirs(log_dir, exist_ok=True)
makedirs(uiautomator_state_dir, exist_ok=True)
makedirs(rl_running_log_dir, exist_ok=True)
makedirs(logcat_dir, exist_ok=True)

# NLP config
sim_s2r_threshold = config['nlp']['sim_s2r_threshold']
use_openIE5 = config['nlp']['use_openIE5']
enable_context_analysis = config['nlp']['enable_context_analysis']
enable_relation_analysis = config['nlp']['enable_relation_analysis']
retrieve_text_using_pattern = config['nlp']['retrieve_text_using_pattern']
position_keywords = config['nlp']['position_keywords']
action_word_list = config['nlp']['action_word_list']
device_words = config['nlp']['device_words']
multi_action_type_threshold = config['nlp']['multi_action_type_threshold']
input_target_cue_words = config['nlp']['input_target_cue_words']
input_value_cue_words = config['nlp']['input_value_cue_words']

empty_s2r = {
    "index": -1,
    "relation": "",
    "object": "",
    "subject":"",
    "ui_actions":[],
    "sentence": ""
}

empty_ui_action = {
    "action_word":"",
    "action": "",
    "target_word": "",
    "text": "URL",
    "shape_img_path": "",
    "shape_word": "",
    "position_direction": [],
    "position_view": [],
    "input_value": "",
    "action_similarity": 1.0,
    "color": "",
    "swipe_direction":"",
    "scroll_direction":"",
    "enabled": False
}

back_view_Tag = Tag(
    name = "FakeBack",
    attrs = {
        "index":1,
        "text": "Back",
        "resource-id":"com.android.systemui:id/back",
        "class":"",
        "package": "",
        "content-desc": "Back",
        "checkable":"false",
        "checked":"false",
        "clickable":"true",
        "enabled":"false",
        "focusable":"false",
        "focused":"false",
        "scrollable":"false",
        "long-clickable":"false",
        "password":"false",
        "selected":"false",
        "visible-to-user": "true",
        "bounds": "[0,0][0,0]"
    }
)

# RL config
training_epoch = config['rl']['training_epoch']
allowed_missing_step_count = config['rl']['allowed_missing_step_count']  # max missing steps we allow
default_input_text = config['rl']['default_input_text']
allow_out_of_order_s2r_match = config['rl'][
    'allow_out_of_order_s2r_match']  # False means everytime we only match the next step from the s2r list. True means we can match all unmatched s2rs at each step.
init_q_value_with_reward = config['rl']['init_q_value_with_reward']

# default learning configuration
default_learning_rate = config['rl']['default_learning_rate']
default_epsilon = config['rl']['default_epsilon']
default_epsilon_decay = config['rl']['default_epsilon_decay']
default_discount_factor = config['rl']['default_discount_factor']

## default rewards
failure_penalty = config['rl']['failure_penalty']  # q-value for a failure state
missing_step_penalty = config['rl']['missing_step_penalty']
success_reward = config['rl']['success_reward']
failure_reward = config['rl']['failure_reward']
reward_scale_base = config['rl']['reward_scale_base']
menu_drawer_init_q_value = reward_scale_base**config['rl']['menu_drawer_init_q_value_scale']
scroll_default_reward = config['rl']['scroll_default_reward']
swipe_default_reward = config['rl']['swipe_default_reward']
reward_bar = config['rl']['reward_bar']
rotate_default_reward = config['rl']['rotate_default_reward']
default_action_type_tweak_threshold = config['rl']['default_action_type_tweak_threshold']
default_rotate_init_q_value = config['rl']['default_rotate_init_q_value']
default_swipe_init_q_value = config['rl']['default_swipe_init_q_value']
default_scroll_init_q_value = config['rl']['default_scroll_init_q_value']
default_input_init_q_value = config['rl']['default_input_init_q_value']
default_OK_init_q_value = config['rl']['default_OK_init_q_value']

## reward switch
textual_similarity_reward_on = config['rl']['textual_similarity_reward_on']

# newly added changes
exploration_reward_on = config['rl']['exploration_reward_on']
use_state_based_epsilon = config['rl']['use_state_based_epsilon']
allow_match_missing_step_after_all_s2r = config['rl']['allow_match_missing_step_after_all_s2r']
use_adhoc_reward_for_input = config['rl']['use_adhoc_reward_for_input']
retrieve_text_from_siblings = config['rl']['retrieve_text_from_siblings']
include_content_dsc_resource_id_similarity = config['rl']['include_content_dsc_resource_id_similarity']
enable_menu_drawer_heuristic = config['rl']['enable_menu_drawer_heuristic']
enable_scroll_reward = config['rl']['enable_scroll_reward']
enable_swipe_reward = config['rl']['enable_swipe_reward']
enable_rotate_reward = config['rl']['enable_rotate_reward']
enable_action_type_tweak = config['rl']['enable_action_type_tweak']
enable_init_q_value_for_rotate = config['rl']['enable_init_q_value_for_rotate']
enable_init_q_value_for_swipe= config['rl']['enable_init_q_value_for_swipe']
enable_init_q_value_for_scroll = config['rl']['enable_init_q_value_for_scroll']
enable_init_q_value_for_input = config['rl']['enable_init_q_value_for_input']
enable_init_q_value_for_OK = config['rl']['enable_init_q_value_for_OK']
