from utils.config import input_target_cue_words, input_value_cue_words
from utils.utils import get_logger

logger = get_logger("context_extractor")


def initialize_simple_context(S2R, simple_contexts):
    if S2R['action'] == "INPUT":
        logger.debug("extracting input value for input action")
        # get input value for input action
        extract_input_value(S2R, simple_contexts)
        extracted_input = S2R['input_value']
        numbers = find_all_numbers(extracted_input)
        if len(numbers) == 1:
            S2R['input_value'] = numbers[
                0]  # if the described input value contains only one number, the only take that number as input value


def find_all_numbers(target_word):
    return [i for i in target_word.split() if i.isnumeric()]


def extract_input_value(S2R, simple_contexts):
    for context in simple_contexts:
        extract_input_value_from_phrase(S2R, context['text'])
    target_word = S2R['target_word']
    cue_word_for_target = next(filter(lambda x: " " + x + " " in target_word, input_target_cue_words), -1)
    cue_word_for_input_value = next(filter(lambda x: " " + x + " " in target_word, input_value_cue_words), -1)
    if len(simple_contexts) == 0 and cue_word_for_target != -1:  # graphene failed to accurately extract contexts
        S2R['input_value'] = target_word.split(" " + cue_word_for_target + " ")[0].strip()
        S2R['target_word'] = target_word.split(" " + cue_word_for_target + " ")[1].strip()
        return
    if len(simple_contexts) == 0 and cue_word_for_input_value != -1:  # graphene failed to accurately extract contexts
        S2R['input_value'] = target_word.split(" " + cue_word_for_input_value + " ")[1].strip()
        S2R['target_word'] = target_word.split(" " + cue_word_for_input_value + " ")[0].strip()
        return
    if S2R['input_value'] == "" and S2R[
        'target_word'] != "":  # didn't use phrases to describe contexts, default the object is set as target
        target_word = S2R['target_word']
        numbers = find_all_numbers(target_word)
        if len(numbers) > 0:
            S2R['input_value'] = target_word
            S2R['target_word'] = ""
        if "space" in target_word:
            S2R['input_value'] = " "
            S2R['target_word'] = ""


def extract_input_value_from_phrase(S2R, text):
    def __simple_process(txt):
        return txt

    cue_word_for_target = next(filter(lambda x: x in input_target_cue_words, text.split()), -1)
    cue_word_for_input_value = next(filter(lambda x: x in input_value_cue_words, text.split()), -1)
    if cue_word_for_target != -1:
        S2R['input_value'] = S2R['target_word'].replace("\"", "").strip()
        S2R['target_word'] = __simple_process(text.replace(cue_word_for_target, "", 1))
    if cue_word_for_input_value != -1:
        S2R['input_value'] = __simple_process(text.replace(cue_word_for_input_value, "", 1))
    S2R['input_value'] = S2R['input_value'].replace("\"", "").rstrip(".").strip()
