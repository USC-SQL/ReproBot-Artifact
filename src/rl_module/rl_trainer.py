import time
from os.path import join

from rl_module.agents.q_agent import QAgent
from rl_module.components.action import Action
from rl_module.environment.app_environment import App_Env
from rl_module.environment.reward_calculator import modify_reward_according_to_next_state
from utils.config import training_epoch, default_epsilon_decay, default_epsilon, default_learning_rate, \
    default_discount_factor, rl_running_log_dir, output_dir, allowed_missing_step_count
from utils.utils import dump_json, get_logger

logger = get_logger("rl-trainer")


def dump_state_action_reward(action: Action, reward, state, epoch, step_count):
    file_path = join(rl_running_log_dir, f"epoch_{epoch}_step_{step_count}.json")
    result = {
        "action": action.get_dict(),
        "reward": reward
    }
    # action.ui_event.dump_icon(epoch, step_count)
    dump_json(result, file_path)
    state.dump_state(epoch, step_count)


def dump_total_rewards(total_rewards):
    file_path = join(rl_running_log_dir, "rewards.json")
    dump_json(total_rewards, file_path)


def rl_main(s2r_file):
    rl_agent = QAgent(learning_rate=default_learning_rate, discount_factor=default_discount_factor,
                      epsilon=default_epsilon, epsilon_decay=default_epsilon_decay)

    app_env = App_Env(s2r_file, total_missing_step=allowed_missing_step_count)
    epoch = 1
    total_rewards = []
    rl_running_time = 0
    while True:
        # start the app and dump the initial state to file
        app_env.refresh_env()
        step_count = 1
        success_reproduced = False
        success_action_seqs = []
        total_reward_per_epoch = 0
        epoch_start_time = time.time()
        next_state = None
        while True:
            logger.info(f"Epoch {epoch} Step {step_count}, Epsilon = {rl_agent.epsilon}")
            # obtain the state
            if next_state:
                cur_state = next_state
            else:
                cur_state = app_env.cur_state()
            # choose an action from environment
            rl_agent.try_init_q_value_for_state(cur_state, app_env.d.window_size())
            try:
                action = rl_agent.choose_action(cur_state)
            except IndexError as e:
                logger.error(f"The emulator malfunction, resulting in empty available action list at Epoch {epoch}, step {step_count}")
                raise Exception("The emulator malfunction, resulting in empty available action list.")
            cur_state.annotate_action(action)  # annotate action target on screenshot
            logger.info(f"Select action: {action}")
            # rl_agent.decrease_epsilon()

            # execute the action using controller and return the next state as well as the reward
            reward = app_env.execute_action(action)
            success_action_seqs.append(action.get_dict())
            logger.info(f"Reward: {reward}")

            next_state = app_env.cur_state()
            dump_state_action_reward(action, reward, cur_state, epoch, step_count)
            reward = reward['total']

            reward = modify_reward_according_to_next_state(reward, cur_state, next_state)
            app_env.dump_logcat(epoch, step_count)
            success = app_env.check_termination(next_state)

            # dump the state using app controller
            rl_agent.try_init_q_value_for_state(next_state, app_env.d.window_size())
            rl_agent.learn(cur_state, action, reward, next_state)
            total_reward_per_epoch += reward
            step_count += 1

            if success is not None:
                success_reproduced = success
                break
        epoch_end_time = time.time()
        rl_running_time += (epoch_end_time-epoch_start_time)
        total_rewards.append(total_reward_per_epoch)
        if success_reproduced or epoch >= training_epoch:
            break
        rl_agent.dump_q_table()
        dump_total_rewards(total_rewards)
        epoch += 1
    app_env.stop_app()
    if success_reproduced:
        success_action_output_path = join(output_dir, "success_action_seq.json")
        dump_json(success_action_seqs, success_action_output_path)
    else:
        logger.info(f"Failed to reproduce. Terminated due to epoch limit.")
    logger.info(f"RL Running Time: {rl_running_time}")

