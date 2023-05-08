import re
from os import listdir
from os.path import join, basename, dirname

import spacy

from utils.config import action_word_list
from utils.utils import dump_file

nlp = spacy.load("en_core_web_lg")


def read_report(bg_path):
    with open(bg_path, "r") as f:
        content = f.read()
        content = re.sub(r"\([^()]*\)", "", content)
        content = content.replace(" -> ", "\n").replace("->", "\n").replace(" => ", "\n").replace("=>", "\n").replace(">", "\n")
        # .replace("\"apostrophe\"", "apostrophe")\
    # .replace("apostrophe", "\",\"")\
    # .replace("space", "\" \"")\
    # .replace("+", "Add")
    content = re.sub(r"\d\. ", "\n", content).strip()
    content = content.splitlines()
    return content


def preprocess_line(line):
    line = line.strip(" ").rstrip(".")
    # if "->" in linne or ">" in line or "=>" in line:
    #     print("Contains: -> or >")
    line = line.replace("long-click","long click").replace("long-click","long click")
    has_subject = False
    root_verb = None
    mod_word = None
    token_list = list(nlp(line))
    if all([i.pos_ != "VERB" for i in token_list]) and len(token_list) <= 2:
        line = "Click "+line
        token_list = list(nlp(line))
    for i, word in enumerate(token_list):
        if word.dep_ == "nsubj" and word.head.dep_ == "ROOT":
            has_subject = True
        if word.dep_ == "ROOT" and word.pos_ == "VERB" and root_verb is None:
            root_verb = word
        if word.dep_ == "advmod" and word.head.dep_ == "ROOT" and root_verb is None:
            mod_word = word
    if not root_verb:
        mod_word = None
        root_verb = token_list[0]
    ground_action_list = [i for _ in action_word_list.values() for i in _]
    if any([line.lower().startswith(action_word) for action_word in ground_action_list]):
        has_subject = False
        root_verb = token_list[0]
    if root_verb.text == "app":
        has_subject = True
    if not has_subject:
        if root_verb:
            print(line, "...........", root_verb.text, "...........", mod_word.text if mod_word else "")
            tokens = list(line.split())
            try:
                index = tokens.index(root_verb.text if not mod_word else mod_word.text)
                pivot_word = root_verb.text.lower() if not mod_word else mod_word.text.lower()
                del tokens[index]
                tokens.insert(index, pivot_word)
                if "crash" in pivot_word:
                    tokens.insert(index, "The app")
                else:
                    tokens.insert(index, "I")
                line = " ".join(tokens)
            except ValueError as e:
                pass
                # print("Cannot find verb word in sentence.")
        else:
            pass
            # print(line, "......", "Cannot find root verb")
    line = line + "."
    return line

def obtain_all_reports():
    BASE_DIR = "/home/zhaoxu/ResearchProject/BugReportReproduction/Evaluation/dataset/bug_reports"
    reports = []
    for android_version in listdir(BASE_DIR):
        if not android_version.startswith("Android"):
            continue
        for report in listdir(join(BASE_DIR, android_version)):
            if not report.endswith(".txt") or "-m" in report:
                continue
            reports.append(join(BASE_DIR, android_version, report))
    return reports


def process_report(src_report, tgt_report=None):
    content = read_report(src_report)
    new_content = []
    for line in content:
        new_content.append(preprocess_line(line))
    new_content = "\n".join(new_content)
    if tgt_report:
        dump_file(new_content, tgt_report)


if __name__ == '__main__':
    reports = obtain_all_reports()
    for report in reports:
        print(basename(report))
        content = read_report(report)
        new_content = []
        for line in content:
            new_content.append(preprocess_line(line))
        new_file_name = basename(report).replace(".txt", "-m.txt")
        # dump_report("\n".join(new_content), join(dirname(report), new_file_name))
