from rl_module.components.action import Action
from rl_module.components.state_obj import State
from utils.config import missing_step_penalty, textual_similarity_reward_on, reward_scale_base, \
    failure_penalty, use_adhoc_reward_for_input, exploration_reward_on, \
    include_content_dsc_resource_id_similarity, enable_scroll_reward, scroll_default_reward, enable_swipe_reward, \
    swipe_default_reward, reward_bar, rotate_default_reward, enable_rotate_reward
from utils.nlp_util import get_word_similarity


def calculate_reward(action: Action, screen_size):  # screen size will be in form of (width, height)
    event = action.ui_event
    s2r = action.s2r
    reward = {}
    if action.matched_with_empty_s2r():  # matched with a missing step
        reward['missing_step_penalty'] = missing_step_penalty
    elif event.action == "ROTATE" and enable_rotate_reward:
        reward['rotate_default_reward'] = rotate_default_reward
    elif event.action == "SCROLL" and enable_scroll_reward:
        reward['scroll_default_reward'] = scroll_default_reward
    elif event.action == "SWIPE" and enable_swipe_reward:
        reward['swipe_default_reward'] = swipe_default_reward
    else:
        if event.action == "INPUT" and use_adhoc_reward_for_input: # found a EditText box for an input s2r
            reward['input_adhoc_reward'] = 0.7
        if textual_similarity_reward_on:
            textual_similarity = max([
                get_word_similarity(s2r.get_target_word(), text)
                for text in event.get_text_on_target_view()
            ], default=0)
            reward['textual_similarity'] =  textual_similarity
            if include_content_dsc_resource_id_similarity:
                resource_id_similarity = get_word_similarity(s2r.get_target_word(), event.get_resource_id_name())
                content_description_similarity = get_word_similarity(s2r.get_target_word(), event.get_content_description())
                reward['textual_similarity'] = max(resource_id_similarity, content_description_similarity, textual_similarity)
    reward['total'] = scale_reward_value(list(reward.values()))
    return reward


def modify_reward_according_to_next_state(reward, cur_state: State, next_state: State):
    if cur_state.get_ui_hierarchy_str() == next_state.get_ui_hierarchy_str() and exploration_reward_on:
        return failure_penalty # give a large penalty for action with no effect on the UI
    else:
        return reward

def scale_reward_value(org_reward):
    filtered_reward = [i for i in org_reward if not isinstance(i, str) and (i >= reward_bar or i < 0)]
    if len(filtered_reward) == 0: # a concreate s2r matched with a unsimilar step
        return missing_step_penalty
    filtered_sum = sum(filtered_reward)
    if filtered_sum < 0: # failure reward
        return filtered_sum
    return round(reward_scale_base * filtered_sum, 4)
