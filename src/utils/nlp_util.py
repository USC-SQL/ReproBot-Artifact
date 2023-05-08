# import spacy_universal_sentence_encoder
import re

import spacy
from spacy.matcher import Matcher

from utils.config import sim_s2r_threshold
# sentence_nlp = spacy_universal_sentence_encoder.load_model("en_use_lg")
from utils.utils import get_logger

nlp = spacy.load("en_core_web_lg")
logger = get_logger("nlp_util")


def tokenize(sent):
    if isinstance(sent, str):
        sent = sent.split(" ")
    sent = [w for w in sent if w not in nlp.Defaults.stop_words]
    return sent


def check_similar_sentences(sent_a, sent_b):
    sent_a = nlp(" ".join(tokenize(sent_a)))
    sent_b = nlp(" ".join(tokenize(sent_b)))
    if sent_a.similarity(sent_b) > sim_s2r_threshold:
        return True
    else:
        return False


def clean_word(word: str):
    stop_words = ['the', 'a', 'an', 'in', 'on', 'at', "to", "with","button",'of','or']
    word = " ".join([i for i in word.split() if i not in stop_words])
    word = word.replace("\"", '').replace("\'", '').replace("`", "").replace("+", "add").lstrip(" ").rstrip(" ")
    return word


def get_word_similarity(word_a, word_b):
    word_a = clean_word(word_a.lower())
    word_b = clean_word(word_b.lower())
    if word_a == "" or word_b == "":
        return 0
    # if word_a in word_b or word_b in word_a:
    #     return 1
    word_a_token = nlp(word_a)
    word_a_token_lemma = nlp(" ".join([_.lemma_ for _ in word_a_token]))
    word_b_token = nlp(word_b)
    word_b_token_lemma = nlp(" ".join([_.lemma_ for _ in word_b_token]))
    orig_form_sim = 0
    if not word_a_token.has_vector:
        logger.warning(f"{word_a_token.text} doesn't have embedding.")
        return 0
    if not word_b_token.has_vector:
        logger.warning(f"{word_a_token.text} doesn't have embedding")
        return 0
    else:
        orig_form_sim = max(word_a_token.similarity(word_b_token), 0)  # to avoid return negative cosine similarity
    lemma_form_sim = 0
    if word_a_token_lemma.has_vector and word_b_token_lemma.has_vector:
        lemma_form_sim = max(word_a_token_lemma.similarity(word_b_token_lemma), 0)
    return max(orig_form_sim, lemma_form_sim)

def is_passive_voice(sent):
    matcher = Matcher(nlp.vocab)
    passive_rule = [{'DEP': 'nsubjpass'}, {'DEP': 'aux', 'OP': '*'}, {'DEP': 'auxpass'}, {'TAG': 'VBN'}]
    matcher.add('Passive', [passive_rule])
    matches = matcher(nlp(sent))
    if len(matches) > 0:
        return True
    else:
        return False


def check_if_is_S2R(s2r_sentence):
    sent = "%s %s %s" % (s2r_sentence['arg1'], s2r_sentence['relation'], s2r_sentence['arg2'])
    if s2r_sentence['arg1'].startswith("I") and is_passive_voice(sent):
        # the clause was in passive voice and the subject is "I"
        return False
    elif not s2r_sentence['arg1'].startswith("I") and not is_passive_voice(sent):
        return False
    return True


def keyword_match(match_str, keyword_list):
    try:
        return next(keyword for keyword in keyword_list if keyword in match_str.split(" "))
    except Exception as e:
        return ""


def construct_str_from_S2R(s2r):
    return s2r['action_word'] + " " + s2r['target_word']


def parse_uiautomator_location(loc_str):
    match_result = re.search("\[(\d+),(\d+)]\[(\d+),(\d+)]", loc_str)
    if match_result is None:
        logger.error(f"Error when parsing uiautomator location on string {loc_str}, return (0,0) (0,0)")
        return [0,0,0,0]
    dimensions = [int(i) for i in match_result.groups()]
    return dimensions
