import random
import re
from os.path import join

from bs4 import BeautifulSoup
from typing import List

from rl_module.components.action import Action, Event
from rl_module.components.s2r import S2R
from utils.config import default_input_text, empty_s2r, uiautomator_state_dir, pkg_name, allow_out_of_order_s2r_match, \
    allow_match_missing_step_after_all_s2r, back_view_Tag, enable_action_type_tweak
from utils.nlp_util import parse_uiautomator_location
from utils.utils import dump_json, dump_file, dump_cv_img, is_clickable_view, is_editable_view, \
    is_long_clickable_view, is_swipable_view, is_scrollable_view, is_back_view, viewGroupClasses, compute_input_value, \
    is_not_filled_by_default_text
import cv2 as cv
import hashlib


class State:
    def __init__(self, ui_hierarchy: BeautifulSoup, unmatched_s2rs, remaining_missing_steps, screen_shot):
        self.ui_hierarchy = ui_hierarchy
        self.unmatched_s2rs = unmatched_s2rs
        self.remaining_missing_steps = remaining_missing_steps
        self.interactable_views = self.__init_interactable_view()
        self.id_str = self.get_id_str()
        self.orig_screen_shot = screen_shot.copy()
        self.screen_shot = self.annotate(screen_shot)
        self.available_actions = self.__init_actions()

    def __init_interactable_view(self):
        common_filter = {
            "enabled": "true",
            "package": lambda x: x == pkg_name,
            "visible-to-user": "true"
        }
        not_viewgroup_filter = {
            "class": lambda x: x not in viewGroupClasses
        }
        clickables = self.ui_hierarchy.find_all(attrs={"clickable": "true", **common_filter, **not_viewgroup_filter})
        long_clickables = self.ui_hierarchy.find_all(
            attrs={"long-clickable": "true", **common_filter, **not_viewgroup_filter})
        scrollables = self.ui_hierarchy.find_all(
            attrs={"scrollable": "true", **common_filter, "class": lambda x: not x.endswith("ViewPager")})
        swipables = self.ui_hierarchy.find_all(
            attrs={"class": lambda x: x is not None and x.endswith("ViewPager"), **common_filter})

        permission_button_rsc_id = ['com.android.packageinstaller:id/permission_allow_button',
                                    'com.android.packageinstaller:id/permission_deny_button']

        permission_buttons = self.ui_hierarchy.find_all(
            attrs={"resource-id": lambda x: x in permission_button_rsc_id}
        )

        interactables = set(clickables + long_clickables + scrollables + swipables + permission_buttons)

        if len(interactables) != 0:
            interactables.add(back_view_Tag)
            return interactables
        else:
            return []  # in this case, the app is not the current app.

    def obtain_available_actions(self):
        return self.available_actions

    def __init_actions(self):
        allow_empty_s2r = self.remaining_missing_steps > 0
        action_candidates = []
        if allow_empty_s2r:
            for view in self.interactable_views:
                actions = self.generate_action(view, S2R(empty_s2r))
                action_candidates = action_candidates + actions
        for s2r in self.unmatched_s2rs:
            if enable_action_type_tweak:
                for view in self.interactable_views:
                    s2r.tweak_ui_action(view)
            decomposed_s2rs = s2r.decompose_s2r()
            for s2r_ in decomposed_s2rs:
                for view in self.interactable_views:
                    actions = self.generate_action(view, s2r_)
                    action_candidates = action_candidates + actions
                    if s2r_.get_first_ui_action_type() == "ROTATE":  # rotate action only needs to be matched with one UI element
                        break
            if not allow_out_of_order_s2r_match:
                break
        if not allow_match_missing_step_after_all_s2r:
            all_missing = all([x.matched_with_empty_s2r() for x in action_candidates])
            no_s2r_left = len(self.unmatched_s2rs) == 0
            if all_missing and no_s2r_left:
                action_candidates = []
        return action_candidates

    def generate_action(self, view, s2r: S2R) -> List[Action]:
        random_input_value = compute_input_value()
        generated_actions = []
        if s2r.is_noop_s2r():
            # it's a no-op, need to infer UI action according to the view. Only infer CLICK, LONG-CLICK, BACK, INPUT, SCROLL. Not ROTATE and SWIPE.
            if is_clickable_view(view):  # could be a click event
                if is_back_view(view):
                    event = Event(view, "BACK", self.orig_screen_shot)
                else:
                    event = Event(view, "CLICK", self.orig_screen_shot)
                generated_actions.append(Action(event, s2r))
            if is_editable_view(view) and is_not_filled_by_default_text(view):  # could be a input event and is not be matched with noop before (avoid inject duplicate noop s2r)
                inferred_input_value = random_input_value
                event = Event(view, "INPUT", self.orig_screen_shot, input_value=inferred_input_value)
                generated_actions.append(Action(event, s2r))
            if is_long_clickable_view(view):  # could be a long-click event:
                event = Event(view, "LONG CLICK", self.orig_screen_shot)
                generated_actions.append(Action(event, s2r))
            # if is_swipable_view(view):
            #     event = Event(view,"SWIPE", self.orig_screen_shot)
            #     generated_actions.append(Action(event, s2r))
            if is_scrollable_view(view):
                event = Event(view, "SCROLL", self.orig_screen_shot)
                generated_actions.append(Action(event, s2r))
        elif s2r.get_first_ui_action_type() == "ROTATE":
            event = Event(view, "ROTATE", self.orig_screen_shot)
            generated_actions.append(Action(event, s2r))
        elif s2r.get_first_ui_action_type() == "INPUT" and is_editable_view(view):
            input_value = random_input_value if s2r.get_input_value() == "" else s2r.get_input_value()
            event = Event(view, s2r.get_first_ui_action_type(), self.orig_screen_shot, input_value=input_value)
            generated_actions.append(Action(event, s2r))
        elif s2r.get_first_ui_action_type() == "LONG CLICK" and is_long_clickable_view(view):
            event = Event(view, "LONG CLICK", self.orig_screen_shot)
            generated_actions.append(Action(event, s2r))
        elif s2r.get_first_ui_action_type() == "CLICK" and is_clickable_view(view):
            if is_back_view(view):
                event = Event(view, "BACK", self.orig_screen_shot)
            else:
                event = Event(view, "CLICK", self.orig_screen_shot)
            generated_actions.append(Action(event, s2r))
        elif s2r.get_first_ui_action_type() == "SWIPE" and is_swipable_view(view):
            event = Event(view, "SWIPE", self.orig_screen_shot, swipe_direction=s2r.get_swipe_direction())
            generated_actions.append(Action(event, s2r))
        elif s2r.get_first_ui_action_type() == "SCROLL" and is_scrollable_view(view):
            event = Event(view, "SCROLL", self.orig_screen_shot, scroll_direction=s2r.get_scroll_direction())
            generated_actions.append(Action(event, s2r))
        return generated_actions

    def dump_state(self, epoch, step):
        ui_hierarchy_file = join(uiautomator_state_dir, f"ui_hierarchy_epoch_{epoch}_step_{step}.xml")
        # unmatched_step_file = join(uiautomator_state_dir, f"unmatched_step_epoch_{self.epoch}_step_{self.step}.json")
        screen_shot_file = join(uiautomator_state_dir, f"epoch_{epoch}_step_{step}.jpg")
        dump_file(self.ui_hierarchy.prettify(), ui_hierarchy_file)
        # dump_json(self.unmatched_s2rs, unmatched_step_file)
        self.dump_screen_shot(screen_shot_file)

    def dump_screen_shot(self, screen_shot_file):
        dump_cv_img(self.screen_shot, screen_shot_file)

    def __eq__(self, other):
        if isinstance(other, State):
            return self.__hash__() == other.__hash__()
        else:
            return False

    def get_ui_hierarchy_str(self):
        def _display_time_point(view):
            text = view['text']
            match_result = re.match('((1[0-2]|0?[1-9]):([0-5][0-9]) ?([AaPp][Mm]))', text)
            return match_result is not None

        def _clean_attrs(i):
            attrs = dict(i.attrs)
            if _display_time_point(attrs):
                attrs['text'] = ''
            for attr_tb_del in ["focused"]:
                del attrs[attr_tb_del]
            return attrs

        related_elements = self.ui_hierarchy.find_all(
            attrs={"package": lambda x: x in [pkg_name, "com.google.android.packageinstaller"]})
        view_strs = [
            # f"{i['bounds']} {i['checkable']} {i['clickable']} {i['content-desc']} {i['focusable']} {i['long-clickable']} {i['password']} {i['resource-id']} {i['scrollable']} {i['text']}"
            str(_clean_attrs(i))
            for i in related_elements
            if len(list(i.children)) == 0
        ]
        view_strs.sort()
        app_views_str = " ".join(view_strs)
        return app_views_str

    def get_id_str(self):

        s2r_indexs = [str(s2r.get_index()) for s2r in self.unmatched_s2rs]
        s2r_indexs.sort()
        app_views_str = self.get_ui_hierarchy_str()
        unmatched_s2r_str = " ".join(s2r_indexs)
        whole_str = app_views_str + " " + unmatched_s2r_str + " " + str(self.remaining_missing_steps)
        return whole_str

    def __hash__(self):
        return int(hashlib.md5(self.id_str.encode()).hexdigest(), 16)

    def annotate(self, screen_shot):
        for view in self.interactable_views:
            x_1, y_1, x_2, y_2 = parse_uiautomator_location(view['bounds'])
            color = (255, 0, 0)  # blue
            if is_clickable_view(view) or is_long_clickable_view(view):
                color = (237, 233, 17)  # light blue
            if is_editable_view(view):
                color = (17, 237, 57)  # green
            if is_scrollable_view(view) or is_swipable_view(view):
                color = (0, 255, 255)  # yellow
            screen_shot = cv.rectangle(screen_shot, (x_1, y_1), (x_2, y_2), color=color, thickness=2)
        cv.putText(screen_shot, f"s: {str(self.__hash__())}", (50, 60), cv.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255),
                   thickness=5)
        cv.putText(screen_shot, f"unmatched: {len(self.unmatched_s2rs)} #remain_ms: {self.remaining_missing_steps}",
                   (50, 120), cv.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), thickness=5)
        return screen_shot

    def annotate_exploration(self, text):
        self.screen_shot = cv.putText(self.screen_shot, text, (50, 240), cv.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255),
                                      thickness=5)

    def annotate_action(self, action):
        xy = action.ui_event.get_xy()
        selected_s2r_index = action.s2r.get_index()
        self.screen_shot = cv.putText(self.screen_shot, "s2r: " + str(selected_s2r_index), xy, cv.FONT_HERSHEY_SIMPLEX,
                                      2, (0, 0, 255), thickness=5)
        self.screen_shot = cv.putText(self.screen_shot, "a:" + str(action.__hash__()), (50, 180),
                                      cv.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), thickness=5)
