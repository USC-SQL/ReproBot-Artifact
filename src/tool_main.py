from shutil import copy

from nlp_module.process_bug_report import nlp_main
from rl_module.rl_trainer import rl_main
import utils.config as Config

if __name__ == '__main__':
    if Config.onlyNLP:
        nlp_main(Config.bug_report_file_path, Config.s2r_file_path, Config.graphene_output_file)
    elif Config.onlyRL:
        copy(Config.s2r_file_path, Config.nlp_output_dir)
        rl_main(Config.s2r_file_path)
    else:
        nlp_main(Config.bug_report_file_path, Config.s2r_file_path, Config.graphene_output_file)
        rl_main(Config.s2r_file_path)
