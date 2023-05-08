from utils.config import default_action_type_tweak_threshold
from utils.nlp_util import get_word_similarity
from utils.utils import is_editable_view, is_clickable_view, get_text_from_view, get_logger

logger = get_logger("s2r")

class S2R:
    def __init__(self, s2r_json):
        self.s2r_json = s2r_json

    # decompose one s2r with multiple predicted ui actions to multiple s2r each of which has one ui action
    def decompose_s2r(self):
        enabled_ui_actions = list(filter(lambda x: x['enabled'], self.s2r_json['ui_actions']))
        decomposed_s2rs = []
        for ui_action in enabled_ui_actions:
            new_s2r = self.s2r_json.copy()
            new_s2r['ui_actions'] = [ui_action]
            decomposed_s2rs.append(S2R(new_s2r))
        return decomposed_s2rs

    def get_first_ui_action_type(self):
        if self.is_noop_s2r():
            return ""
        return self.s2r_json['ui_actions'][0]['action']

    def tweak_ui_action(self, view):
        if self.is_noop_s2r() or len(self.s2r_json['ui_actions']) < 2:
            return
        second_ui_action = self.s2r_json['ui_actions'][1]
        if is_editable_view(view):
            if second_ui_action['action'] != "INPUT":
                return
        elif is_clickable_view(view):
            if second_ui_action['action'] != "CLICK":
                return
        else:
            return
        texts_on_view = get_text_from_view(view)
        textual_similarity = max([
                get_word_similarity(self.get_target_word(), text)
                for text in texts_on_view
            ], default=0)
        if textual_similarity > default_action_type_tweak_threshold:
            second_ui_action['enabled'] = True
            logger.info("Identified a similar target, enabled potential %s action" % second_ui_action['action'])


    def is_noop_s2r(self):
        return self.s2r_json['sentence'] == ""

    def get_input_value(self):
        if self.is_noop_s2r():
            return ""
        return self.s2r_json['ui_actions'][0]['input_value']

    def get_index(self):
        return self.s2r_json['index']

    def get_target_word(self):
        if self.is_noop_s2r():
            return ""
        return self.s2r_json['ui_actions'][0]['target_word']


    def __str__(self):
        return str(self.s2r_json)

    def get_dict(self):
        return self.s2r_json

    def get_position_direction(self):
        if self.is_noop_s2r():
            return ""
        return self.s2r_json['ui_actions'][0]['position_direction']

    def get_action_word(self):
        if self.is_noop_s2r():
            return ""
        return self.s2r_json['ui_actions'][0]['action_word']

    def get_scroll_direction(self):
        return self.s2r_json['ui_actions'][0]['scroll_direction']

    def get_swipe_direction(self):
        return self.s2r_json['ui_actions'][0]['swipe_direction']