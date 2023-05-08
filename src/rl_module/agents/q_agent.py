import random
from os import makedirs
from os.path import join, exists

from rl_module.components.action import Action
from rl_module.components.state_obj import State
from rl_module.environment.reward_calculator import calculate_reward
from utils.config import rl_running_log_dir, failure_penalty, init_q_value_with_reward, use_state_based_epsilon, \
    enable_menu_drawer_heuristic, menu_drawer_init_q_value, enable_init_q_value_for_rotate, \
    enable_init_q_value_for_swipe, enable_init_q_value_for_scroll, default_scroll_init_q_value, \
    default_swipe_init_q_value, default_rotate_init_q_value, enable_init_q_value_for_input, default_input_init_q_value, \
    enable_init_q_value_for_OK, default_OK_init_q_value, missing_step_penalty
from utils.utils import get_logger, dump_json, dump_file, dump_pkl, is_expand_menu_or_drawer_noop
import pickle
logger = get_logger("Q-Agent")


class QAgent():
    # init the Q table
    def __init__(self, learning_rate, discount_factor, epsilon, epsilon_decay):
        self.lr = learning_rate
        self.df = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_table = {}
        self.q_table = {}
        self.state_hash_obj_map = {}
        self.action_hash_obj_map = {}

    def try_init_q_value_for_state(self, cur_state: State, screen_size):
        state_hash = cur_state.__hash__()
        self.state_hash_obj_map[state_hash] = cur_state
        if state_hash not in self.q_table:
            self.q_table[state_hash] = {}
        available_actions = cur_state.obtain_available_actions()
        for action in available_actions:
            action_hash = action.__hash__()
            self.action_hash_obj_map[action_hash] = action
            if action_hash in self.q_table[state_hash]:
                continue
            if len(cur_state.unmatched_s2rs) == 0: # there is no s2r to be matched, then we don't give any action a init-Q, we just want it to random explore
                self.q_table[state_hash][action_hash] = missing_step_penalty
                continue
            if action.s2r.get_first_ui_action_type() == 'ROTATE' and enable_init_q_value_for_rotate: # if the matched s2r is a rotate s2r, give it a higher init q_value to encourage it
                init_q_value = default_rotate_init_q_value
            elif action.ui_event.action == 'SWIPE' and enable_init_q_value_for_swipe: # if the matched ui event is a rotate s2r, give it a higher init q_value to encourage it
                logger.info("Give initial Q value for a swipe action")
                init_q_value = default_swipe_init_q_value
            elif action.ui_event.action == 'SCROLL' and enable_init_q_value_for_scroll:
                logger.info("Give initial Q value for a scroll action")
                init_q_value = default_scroll_init_q_value
            elif action.ui_event.action == "CLICK" and "OK" in action.ui_event.get_text_on_target_view() and action.s2r.is_noop_s2r() and enable_init_q_value_for_OK:
                logger.info("Give initial Q value for a click OK action")
                init_q_value = default_OK_init_q_value
            else:
                reward = calculate_reward(action, screen_size)
                init_q_value = reward['total']
            if action.s2r.get_first_ui_action_type() == "INPUT" and enable_init_q_value_for_input:
                logger.info("Give initial Q value for a matched input action")
                init_q_value = max(default_input_init_q_value, init_q_value)
            self.q_table[state_hash][action_hash] = init_q_value
            if is_expand_menu_or_drawer_noop(action) and enable_menu_drawer_heuristic and len(self.q_table) == 1: # check the length of the q-table to only apply this heuristic to the initial UI state
                logger.debug("identified a menu button or a drawer button")
                self.q_table[state_hash][action_hash] = menu_drawer_init_q_value

    def get_epsilon_for_state(self, state_hash):
        if use_state_based_epsilon:
            if state_hash not in self.epsilon_table:
                self.epsilon_table[state_hash] = self.epsilon
            epsilon = self.epsilon_table[state_hash]
            self.epsilon_table[state_hash] = self.epsilon_table[state_hash] - self.epsilon_decay
        else:
            epsilon = self.epsilon
        return epsilon

    def choose_action(self, cur_state: State):
        available_actions = cur_state.obtain_available_actions()
        state_hash = cur_state.__hash__()
        max_reward_action = self.exploit_action(available_actions, state_hash)
        epsilon = self.get_epsilon_for_state(state_hash)
        if random.random() > epsilon and max_reward_action is not None:
            logger.info(f'Exploitation, ep={epsilon}')
            cur_state.annotate_exploration(f'Exploitation, ep={epsilon}')
            final_selected_action = max_reward_action
        else:
            # exploration
            logger.info(f"Exploration, ep={epsilon}")
            cur_state.annotate_exploration(f"Exploration, ep={epsilon}")
            valid_actions = []
            for action in available_actions:
                action_hash = action.__hash__()
                if action_hash in self.q_table[state_hash]:
                    q_value = self.q_table[state_hash][action_hash]
                    if q_value <= failure_penalty:  # if the q-value of a state action pair is less than failure penalty, don't consider to choose it anymore
                        logger.info("Avoided failure action from retrying.")
                        continue
                valid_actions.append(action)
            if max_reward_action in valid_actions:
                valid_actions.remove(max_reward_action)
            if len(valid_actions) == 0:
                final_selected_action = max_reward_action
            else:
                final_selected_action = random.choice(valid_actions)
        if final_selected_action is None:
            logger.error("Selected a None action")
            raise IndexError
        return final_selected_action

    def exploit_action(self, available_actions, state_hash):
        random.shuffle(available_actions)
        # exploitation
        max_reward = -float('inf')
        max_action = []
        for action in available_actions:
            action_hash = action.__hash__()
            if action_hash in self.q_table[state_hash]:
                reward = self.q_table[state_hash][action_hash]
            else:
                logger.warn("Found action not initialized: %d at state: %d" % (action_hash, state_hash))
                continue
            if reward > max_reward:
                max_reward = reward
                max_action = [action]
            elif reward == max_reward:
                max_action.append(action)
        if len(max_action) == 0:
            logger.error("Error happened when selecting max-q-value action at state %d. No action available." % state_hash)
            return None
        final_selected_action = random.choice(max_action)
        return final_selected_action

    def learn(self, state, action, reward, next_state):
        state_hash = state.__hash__()
        action_hash = action.__hash__()
        next_state_hash = next_state.__hash__()
        try:
            max_next_state_value = max(self.q_table[next_state_hash].values())
        except ValueError: # next state is failure state, with no entry in Q-table
            max_next_state_value = failure_penalty
        old_q_value = self.q_table[state_hash][action_hash]
        self.q_table[state_hash][action_hash] = old_q_value + self.lr * (
                    reward + self.df * max_next_state_value - old_q_value)
        logger.info(
            f"Updated value of ({state_hash},{action_hash}) from {old_q_value} to {self.q_table[state_hash][action_hash]}")

    def dump_q_table(self):
        output_dir = join(rl_running_log_dir, f"q_table")
        state_hash_output_dir = join(output_dir, "state_hash")
        action_hash_output_dir = join(output_dir, "action_hash")
        action_pickle_output_dir = join(output_dir, "action_pickle")
        dump_json(self.q_table, join(output_dir, "q_table.json"))
        self.dump_hash_map(state_hash_output_dir, action_hash_output_dir, action_pickle_output_dir)

    def dump_hash_map(self, state_hash_map_output_dir, action_hash_map_output_dir, action_pickle_output_dir):
        for h, state in self.state_hash_obj_map.items():
            file_path = join(state_hash_map_output_dir, str(h) + '.png')
            state.dump_screen_shot(file_path)
            file_path = join(state_hash_map_output_dir, str(h) + '.txt')
            dump_file(state.id_str, file_path)

        for h, action in self.action_hash_obj_map.items():
            file_path = join(action_hash_map_output_dir, str(h) + '.json')
            dump_json(action.get_dict(), file_path)

        # for h, action in self.action_hash_obj_map.items():
        #     file_path = join(action_pickle_output_dir, str(h)+".pkl")
        #     dump_pkl(action,file_path)
                
    def decrease_epsilon(self):
        self.epsilon -= self.epsilon_decay
