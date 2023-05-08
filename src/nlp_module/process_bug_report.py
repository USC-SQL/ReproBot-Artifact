import json
import subprocess
import time
from os.path import basename, join, exists, dirname

import requests
from pyopenie import OpenIE5

from nlp_module.context_extractor import initialize_simple_context, extract_input_value_from_phrase
from utils.config import GRAPHENE_JAR, JAVA_CMD, enable_context_analysis, \
    enable_relation_analysis, action_word_list, position_keywords, empty_s2r, use_openIE5, device_words, \
    multi_action_type_threshold, empty_ui_action
from utils.nlp_util import get_word_similarity, check_if_is_S2R, keyword_match
from utils.preprocess import process_report
from utils.utils import get_logger, read_json, dump_json
from utils.cmd_args import openie_id

logger = get_logger("nlp-module")


def run_graphene(bug_report_file, output_file):
    run_result = subprocess.run([JAVA_CMD, "-jar", "-Xmx4g", GRAPHENE_JAR, bug_report_file, output_file],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run_result.returncode != 0:
        logger.warning("Graphene failed on %s" % basename(bug_report_file))
        logger.error(run_result.stdout.decode())
        logger.error(run_result.stderr.decode())
        exit(1)
    else:
        logger.info("Graphene generated reports in %s" % output_file)



def classify_action(action_word, orig_sent):
    final_type = None
    final_sim = None
    max_sim_for_each_type = []
    for action_type, action_words in action_word_list.items():
        sim_results = [
            (get_word_similarity(action_word, word), word)
            for word in action_words
        ]
        sim_results.sort(key=lambda x: x[0], reverse=True)
        max_sim_for_each_type.append([action_type, sim_results[0][1], sim_results[0][
            0]])  # select the max of the similarity score within one group (type, max_sim_value, max_sim_word)
    max_sim_for_each_type.sort(key=lambda x: x[-1], reverse=True)  # select the most similar group
    final_type = max_sim_for_each_type[0][0]
    final_sim = max_sim_for_each_type[0][2]
    if final_type == "CLICK" and "long" in orig_sent.lower():
        final_type = "LONG CLICK"
    if final_type == "ROTATE":
        if not any([x in orig_sent.lower().split() for x in device_words]):  # the final type is rotate, but the target doesn't contain any device related words, then change to the second most similar action type
            final_type = max_sim_for_each_type[1][0]
            final_sim = max_sim_for_each_type[1][2]
    if "orientation" in orig_sent:  # the target contain the orientation, then must be rotate
        final_type = "ROTATE"
        final_sim = 1
    final_ui_action = empty_ui_action.copy()
    final_ui_action['action'] =final_type
    final_ui_action['action_similarity'] =final_sim
    final_ui_action['enabled'] =True

    ui_actions = [final_ui_action]
    if final_type in ['INPUT','CLICK']:
        alternative_action_type = "INPUT" if final_type == "CLICK" else "CLICK"
        alter_action_sim = max([get_word_similarity(action_word, word) for word in action_word_list[alternative_action_type]])
        alter_action = empty_ui_action.copy()
        alter_action["action"] = alternative_action_type
        alter_action["action_similarity"] = alter_action_sim
        alter_action["enabled"] = abs(final_sim - alter_action_sim) <= multi_action_type_threshold
        ui_actions.append(alter_action)

    return  ui_actions


def extract_with_OpenIE5(s2r, sent):
    extractor = OpenIE5(f'http://{openie_id}:8000')
    extraction = extractor.extract(sent)
    if len(extraction) > 0:
        extraction = sorted(extraction, key=lambda x: x['confidence'], reverse=True)
        try:
            filtered = [x['extraction'] for x in extraction if 'I' in x['extraction']['arg1']['text'] and all(
                [(not _.isalpha()) or _.islower() for _ in x['extraction']['rel']['text']])]
            highest_conf_extraction = filtered[0]
        except Exception as e:
            highest_conf_extraction = extraction[0]['extraction']
        s2r['relation'] = highest_conf_extraction['rel']['text']
        s2r['object'] = highest_conf_extraction['arg2s'][0]['text'] if len(highest_conf_extraction['arg2s']) > 0 else ""
        s2r['subject'] = highest_conf_extraction['arg1']['text']
    else:
        raise Exception("OpenIE 5 Failed to Extract")


def analyze_scroll_direction(ui_action):
    direction_key_words = ['up','down','left','right']
    matched_direction = [d for d in direction_key_words if
                         d in ui_action['action_word'].lower() or d in ui_action['target_word'].lower()]
    if ui_action['action'] == "SCROLL":
        scroll_direction = ""
        if len(matched_direction)>0:
            scroll_direction = matched_direction[0]
        # we use swipe to represent left and right scrolling, the direction is reversed for different semantics
        if scroll_direction == 'left':
            ui_action['action'] = "SWIPE"
            ui_action['swipe_direction'] = "right"
        elif scroll_direction == 'right':
            ui_action['action'] = "SWIPE"
            ui_action['swipe_direction'] = "left"
        else:
            ui_action['scroll_direction'] = scroll_direction
    elif ui_action['action'] == "SWIPE":
        swipe_direction = ""
        if len(matched_direction) > 0:
            swipe_direction = matched_direction[0]
        # we use scroll to represent up and down scrolling, the direction is reversed for different semantics
        if swipe_direction == 'up':
            ui_action['action'] = "SCROLL"
            ui_action['scroll_direction'] = "down"
        elif swipe_direction == 'down':
            ui_action['action'] = "SCROLL"
            ui_action['scroll_direction'] = "up"
        else:
            ui_action['swipe_direction'] = swipe_direction



def s2r_from_sentenceMap(sent, originalSentence, sentence_map):
    logger.debug(f"analysing clause {sent['id']}")
    S2R = dict(empty_s2r)
    if sent['origSent'] == "I specify .":
        sent['origSent'] = "I specify Google account ."
    patch_sentences = [
        "I enter something into Secret fields .",
        "I enter something into the Label .",
        "I set 30 Feb 2018 .",
        "I give the Exercise a name .",
        "I tap the add FAB .",
        "I click Read aloud ."
    ] # openIE5 would make mistakes on these sentences, for them, use Graphene instead
    if use_openIE5 and sent['origSent'] not in patch_sentences:
        try:
            extract_with_OpenIE5(S2R, sent['origSent'])
        except Exception as e:
            logger.error(e)
            S2R["relation"] = sent['relation']
            S2R["object"] = sent['arg2']
            S2R['subject'] = sent['arg1']
    else:
        S2R["relation"] = sent['relation']
        S2R["object"] = sent['arg2']
        S2R['subject'] = sent['arg1']
    predicted_ui_actions = classify_action(S2R["relation"],
                                           sent['origSent'])  # the action is a list of possible interpreted actions
    S2R["sentence"] = originalSentence
    for ui_action in predicted_ui_actions:
        ui_action['action_word'] = S2R['relation']
        ui_action['target_word'] = S2R['object']
        ui_action['position_direction'] = []
        ui_action['position_view'] = []
        analyze_scroll_direction(ui_action)
        # S2R["is_S2R"] = get_bee_confidence(originalSentence)
        if enable_context_analysis:
            logger.debug("extracting simple contexts...")
            initialize_simple_context(ui_action, sent['simpleContexts'])
    S2R['ui_actions'] = predicted_ui_actions
    S2Rs = [S2R]
    if enable_relation_analysis:
        logger.debug("analyzing relations between clauses...")
        S2Rs = analyze_graphene_relations(S2R, S2Rs, sent, originalSentence, sentence_map)
    return S2Rs


# cannot simply extend S2Rs with new constructed S2Rs since the first S2R in new constructed ones might be the same with the last one in the old S2Rs due to clauses in the new sentence
def merge_next_S2Rs(S2Rs, constructed_S2Rs):
    # if len(constructed_S2Rs) == 0 or len(S2Rs) == 0:
    #     S2Rs.extend(constructed_S2Rs)
    #     return
    # previous_last_S2R = S2Rs[-1]
    # next_first_S2R = constructed_S2Rs[0]
    # if check_similar_sentences(construct_str_from_S2R(previous_last_S2R), construct_str_from_S2R(next_first_S2R)):
    #     S2Rs.extend(constructed_S2Rs[1:])
    # else:
    S2Rs.extend(constructed_S2Rs)


def find_head_sentence(sentenceMap):
    head_sentence = sentenceMap[0]
    for sentence in sentenceMap:
        is_head_sentence = True
        for s in sentenceMap:
            if sentence['id'] == s['id']:
                continue
            linked_sentence = [_['targetID'] for _ in s['linkedContexts']]
            if sentence['id'] in linked_sentence:
                is_head_sentence = False
        if is_head_sentence:
            head_sentence = sentence
            break
    return head_sentence




def extract_S2Rs(graphene_result_file):
    sentences: list = graphene_result_file['sentences']
    # sentence_needs_openIE5 = ["Select \"Live map\" view"]
    S2Rs = list()
    while len(sentences) > 0:
        sent = sentences.pop(0)
        logger.debug(f"analyzing sentence {sent['sentenceIdx']}: {sent['originalSentence']}")
        sentenceMap = list(sent['extractionMap'].values())
        if len(sentenceMap) == 0:
            # or sent['originalSentence'] in sentence_needs_openIE5:
            # Graphene failed to extract anything, try OpenIE5
            if use_openIE5:
                S2R = dict(empty_s2r)
                try:
                    extract_with_OpenIE5(S2R, sent['originalSentence'])
                    constructed_S2Rs = [S2R]
                except Exception as e:
                    continue
            else:
                continue
        else:
            head_sentence = find_head_sentence(sentenceMap)
            sentenceMap.remove(head_sentence)
            constructed_S2Rs = s2r_from_sentenceMap(head_sentence, sent['originalSentence'], sentenceMap)
        merge_next_S2Rs(S2Rs, constructed_S2Rs)
    for i, s2r in enumerate(S2Rs):
        s2r["index"] = i + 1
    return S2Rs


def graphene_main(bug_report_path, output_file):
    logger.info("Graphene start run on %s." % basename(bug_report_path))
    graphene_result = run_graphene(bug_report_path, output_file)


def dump_S2Rs_to_file(S2Rs, output_file):
    dump_json(S2Rs, output_file)
    logger.info("Dumped S2Rs into %s" % output_file)
    return output_file


def add_orignal_sentence(bug_report_path, graphene_output):
    with open(bug_report_path, "r") as f:
        report_content = f.read().splitlines()
    for item in graphene_output['sentences']:
        item['originalSentence'] = report_content[int(item['sentenceIdx'])]


def filter_s2rs(S2Rs):
    filtered_s2rs = []
    for s2r in S2Rs:
        if not ("I" in s2r['subject'].split() or "user" in s2r['subject'].lower()):  # check the subject to filter sentence not describing steps
            continue
        if "app" in s2r['object'] or "install" in s2r[
            'relation']:  # check whether the target contains app, normally it's about starting or installing app
            continue
        if s2r['object'] in ['', 'it', 'the dialog'] and s2r['ui_actions'][0]['action'] != "ROTATE":
            substitute_action = empty_ui_action.copy()
            substitute_action['target_word'] = s2r['relation']
            substitute_action['action'] = 'CLICK'
            substitute_action['action_similarity'] = 1
            substitute_action['enabled'] = True
            s2r['ui_actions'] = [substitute_action]
        filtered_s2rs.append(s2r)
    for i, s2r in enumerate(filtered_s2rs):  # prev step may remove some step, reassign the index
        s2r['index'] = i + 1
    return filtered_s2rs


def nlp_main(bug_report_path, s2r_file, graphene_output_file):
    nlp_start_time = time.time()
    logger.info("running Graphene...")
    if not exists(graphene_output_file):
        temp_bug_report_path = join(dirname(s2r_file), basename(bug_report_path).replace(".txt", "-m.txt"))
        process_report(bug_report_path, temp_bug_report_path)
        if not exists(temp_bug_report_path):
            logger.warning("Failed to preprocess bug report.")
            graphene_main(bug_report_path, graphene_output_file)
        else:
            graphene_main(temp_bug_report_path, graphene_output_file)
    graphene_output = read_json(graphene_output_file)
    add_orignal_sentence(bug_report_path, graphene_output)
    logger.info("extracting S2Rs...")
    if not exists(s2r_file):
        S2Rs = extract_S2Rs(graphene_output)
        S2Rs = filter_s2rs(S2Rs)
        dump_S2Rs_to_file(S2Rs, s2r_file)
    logger.info("done...")
    nlp_end_time = time.time()
    logger.info(f"NLP Running Time: {nlp_end_time - nlp_start_time}")


def analyze_graphene_relations(S2R, S2Rs, first_sentence, originalSentence, sentence_map):
    original_S2R = dict(S2R)
    linked_contexts = first_sentence['linkedContexts']
    while len(linked_contexts) > 0:
        context = linked_contexts.pop(0)
        context_type = context['classification']
        try:
            linked_sentence = next(sent for sent in sentence_map if sent['id'] == context['targetID'])
            sentence_map.remove(linked_sentence)
        except Exception as e:
            logger.warning("Did't find %s linked context %s for sentence %s" % (
                context['classification'], context['targetID'], first_sentence['id']))
            continue
        if context['classification'] in ['IDENTIFYING_DEFINITION'] and S2R is not None:
            S2R['position_direction'] = keyword_match(linked_sentence['arg2'], position_keywords)

        if context_type in ['BACKGROUND', 'CONDITION', 'TEMPORAL_BEFORE', 'IDENTIFYING_DEFINITION', 'CONTRAST']:
            # A -> B, perform B then A
            linked_sentences = s2r_from_sentenceMap(linked_sentence, originalSentence, sentence_map)
            S2Rs = linked_sentences + S2Rs
        elif context_type in ['LIST']:
            # A -> B, perform A then B
            linked_sentence['linkedContexts'].remove({"targetID": first_sentence['id'], "classification": "LIST"})
            linked_sentences = s2r_from_sentenceMap(linked_sentence, originalSentence, sentence_map)
            S2Rs = S2Rs + linked_sentences
        elif context_type in ['TEMPORAL_AFTER_C']:
            linked_sentence['linkedContexts'].remove({"targetID": first_sentence['id'], "classification": "TEMPORAL_BEFORE_C"})
            linked_sentences = s2r_from_sentenceMap(linked_sentence, originalSentence, sentence_map)
            S2Rs = S2Rs + linked_sentences
        elif context_type  in ['TEMPORAL_BEFORE_C']:
            linked_sentence['linkedContexts'].remove({"targetID": first_sentence['id'], "classification": "TEMPORAL_AFTER_C"})
            linked_sentences = s2r_from_sentenceMap(linked_sentence, originalSentence, sentence_map)
            S2Rs = linked_sentences + S2Rs
        elif context_type in ['DISJUNCTION']:
            # A -> B, perform A or B
            S2Rs = S2Rs
        else:
            logger.warning(
                "Encounter an unhandled linked context %s in sentence %s" % (context_type, first_sentence['id']))

    return S2Rs
