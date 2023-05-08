import json
import logging
import pickle
import subprocess
import sys
from os import makedirs
from os.path import join, dirname, exists
import cv2 as cv
from bs4 import Tag

from utils.config import log_dir, CURRENT_TIME, logger_level, silent, ADB_CMD, retrieve_text_from_siblings, \
    default_input_text


class Blacklist(logging.Filter):
    def __init__(self, *blacklist):
        self.blacklist = [logging.Filter(name) for name in blacklist]

    def filter(self, record):
        return not any(f.filter(record) for f in self.blacklist)


FORMAT = '%(asctime)s [%(levelname)s] [%(name)s] [%(filename)s-%(lineno)d] %(message)s'
LOG_FILE = join(log_dir, '%s.log' % CURRENT_TIME)
handlers = [logging.FileHandler(LOG_FILE, mode='w')]
if not silent:
    handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    format=FORMAT,
    level=logger_level,
    handlers=handlers,
    datefmt='%m/%d/%Y %I:%M:%S'
)
for handler in logging.root.handlers:
    handler.addFilter(Blacklist('urllib3.connectionpool'))

viewGroupClasses = ['android.widget.ListView', 'android.widget.GridView']

def get_logger(logger_name):
    return logging.getLogger(logger_name)


def read_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


def dump_json(json_obj, file_path):
    dir_name = dirname(file_path)
    if not exists(dir_name):
        makedirs(dir_name)
    with open(file_path, "w") as f:
        json.dump(json_obj, f, indent=4)


def dump_file(content, file_path):
    dir_name = dirname(file_path)
    if not exists(dir_name):
        makedirs(dir_name)
    with open(file_path, "w") as f:
        f.write(content)


def dump_pkl(content, file_path):
    dir_name = dirname(file_path)
    if not exists(dir_name):
        makedirs(dir_name)
    with open(file_path, "wb") as f:
        pickle.dump(content, f)


def read_pkl(file_path):
    with open(file_path, "rb") as f:
        return pickle.load(f)


def dump_cv_img(img, file_path):
    dir_name = dirname(file_path)
    if not exists(dir_name):
        makedirs(dir_name)
    cv.imwrite(file_path, img)


def singleton(cls):
    _instance = {}

    def inner():
        if cls not in _instance:
            _instance[cls] = cls()
        return _instance[cls]

    return inner

def retrieve_text_from_xml_siblings(xml_tag: Tag):
    text_set = set()
    siblings = set(xml_tag.previous_siblings).union(set(xml_tag.next_siblings))
    for child in siblings:
        if isinstance(child, Tag) and "" != child['text']:
            if is_clickable_view(child) or is_editable_view(child):  # if the child node is another interactable view, then do not include its text
                continue
            text_set.add(child['text'].strip())
    if xml_tag['text'] != "":
        text_set.add(xml_tag['text'].strip())
    return text_set


def retrieve_text_from_text_label_siblings(xml_tag: Tag):
    def __overlap(inner, outer):
        pass
    ext_set = set()
    siblings = list(filter( lambda x: isinstance(x, Tag),set(xml_tag.previous_siblings).union(set(xml_tag.next_siblings))))
    if len(siblings) == 1 and siblings[0]["class"]=="android.widget.TextView" and siblings[0]["clickable"]=="false" and xml_tag['text']=="" and xml_tag['content-desc'] == "" and siblings[0]['text']!="":
        # likely to be a text label for a FAB button
        ext_set.add(siblings[0]['text'])
    return ext_set


def get_text_from_view(view: Tag):
    text_set = {view['text']}
    if retrieve_text_from_siblings:
        if view['class'] == 'android.widget.EditText':
            text_set.update(retrieve_text_from_xml_siblings(view))
        else:
            text_set.update(retrieve_text_from_text_label_siblings(view))
    if len(text_set) == 0 or all([i == "" for i in text_set]):
        text_set.update(retrieve_text_from_xml_child(view))
    return text_set

def retrieve_text_from_xml_child(xml_tag: Tag):
    text_set = set()
    if xml_tag['text'] != "":
        text_set.add(xml_tag['text'].strip())
    for child in xml_tag.children:
        if isinstance(child, Tag):
            if is_clickable_view(child) or is_editable_view(child):  # if the child node is another interactable view, then do not include its text
                continue
            text_set.update(retrieve_text_from_xml_child(child))
    return text_set

def get_content_description_from_view(view:Tag):
    return view['content-desc']

def get_resource_id_from_view(view:Tag):
    resource_id = view['resource-id'].split('/')[-1].replace("_", " ").strip()
    return resource_id

def compute_input_value():
    return default_input_text

def is_not_filled_by_default_text(view):
    return view['text'] != compute_input_value()

def is_long_clickable_view(view):
    return view['long-clickable'] == "true" and view['class'] not in viewGroupClasses and not is_editable_view(view) # scrollable view and editable view is also clickable, so need to filter them

def is_clickable_view(view):
    return view['clickable'] == "true" and view['class'] not in viewGroupClasses and not is_editable_view(view) # scrollable view and editable view is also clickable, so need to filter them
def is_editable_view(view):
    return view['class'] == "android.widget.EditText"
def is_swipable_view(view):
    return view['class'] is not None and view['class'].endswith("ViewPager")
def is_scrollable_view(view):
    return view['scrollable'] == "true" and not view['class'].endswith("ViewPager")

def is_back_view(view): # since back view is a fake one (manually created), i just defined its resource id like this
    return view["resource-id"]  == "com.android.systemui:id/back"
def restart_adb():
    p = subprocess.Popen(
        [ADB_CMD, "start-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()
    stdout, stderr = p.communicate()


def is_expand_menu_or_drawer_noop(action):
    if action.ui_event.view_xml is None or not action.s2r.is_noop_s2r(): # not noop click action
        return False
    view = action.ui_event.view_xml
    tgt_classes = ["android.widget.ImageView","android.widget.ImageButton"]
    if action.ui_event.action == "CLICK":
        tgt_x, tgt_y = action.ui_event.get_xy()
        if tgt_x<154 and  tgt_y < 223 and "open" in view['content-desc'].lower() and view['class'] in tgt_classes: # [0,69][154,223] example drawer button
            return True
        if 969<tgt_x and tgt_y< 212 and "option" in view['content-desc'].lower() and view['class'] in tgt_classes: # [969,80][1080,212] exmaple menu
            return True
    return False
