from bs4 import Tag

from rl_module.components.s2r import S2R
from utils.nlp_util import parse_uiautomator_location
from utils.utils import get_text_from_view, get_content_description_from_view, get_resource_id_from_view
import hashlib


class Event:
    def __init__(self, view_xml: Tag, action, screen_shot, input_value=None, swipe_direction = "", scroll_direction = ""):
        if swipe_direction == "":
            swipe_direction = "left"
        if scroll_direction == "":
            scroll_direction = "down"
        self.view_xml = view_xml
        self.action = action
        self.input_value = input_value
        self.icon = self.crop_icon_screenshot(screen_shot, self.parse_ui_bound())
        self.caption = None
        self.swipe_direction = swipe_direction
        self.scroll_direction = scroll_direction

    def get_str_for_hash(self):
        return f"{str(self.view_xml.attrs)} {self.action} {self.input_value}"

    def get_xy(self):
        x_1, y_1, x_2, y_2 = self.parse_ui_bound()
        center_x = (int(x_1) + int(x_2)) // 2
        center_y = (int(y_1) + int(y_2)) // 2
        return center_x, center_y

    def parse_ui_bound(self):
        return parse_uiautomator_location(self.view_xml['bounds'])

    def get_resource_id(self):
        return self.view_xml['resource-id']

    def __scroll_down_range(self): # scroll from lower coordinate to higher coordinate
        x_1, y_1, x_2, y_2 = self.parse_ui_bound()
        f_x = (x_1 + x_2) / 2
        f_y = y_2 - 1
        t_x = (x_1 + x_2) / 2
        t_y = y_1 + 1
        return f"[{int(f_x)},{int(f_y)}][{int(t_x)},{int(t_y)}]"

    def __scroll_up_range(self): # scroll from higher coordinate to lower coordinate
        x_1, y_1, x_2, y_2 = self.parse_ui_bound()
        f_x = (x_1 + x_2) / 2
        f_y = y_1 - 1
        t_x = (x_1 + x_2) / 2
        t_y = y_2 + 1
        return f"[{int(f_x)},{int(f_y)}][{int(t_x)},{int(t_y)}]"

    def __swipe_left_range(self):
        x_1, y_1, x_2, y_2 = self.parse_ui_bound()
        # For swipe, default direction is swipe left
        f_x = x_2 - 1
        f_y = (y_1 + y_2) / 2
        t_x = x_1 + 1
        t_y = (y_1 + y_2) / 2
        return f"[{int(f_x)},{int(f_y)}][{int(t_x)},{int(t_y)}]"

    def __swipe_right_range(self):
        x_1, y_1, x_2, y_2 = self.parse_ui_bound()
        # For swipe, default direction is swipe left
        f_x = x_1 + 1
        f_y = (y_1 + y_2) / 2
        t_x = x_2 - 1
        t_y = (y_1 + y_2) / 2
        return f"[{int(f_x)},{int(f_y)}][{int(t_x)},{int(t_y)}]"

    def get_scroll_or_swipe_range(self):
        # For SCROLL, default direction is scroll down
        if self.action == "SCROLL":
            if self.scroll_direction == "up":
                return self.__scroll_up_range()
            else:
                return self.__scroll_down_range()
        if self.action == "SWIPE":
            if self.swipe_direction == "left":
                return self.__swipe_left_range()
            else:
                return self.__swipe_right_range()


    def get_text_on_target_view(self):
        text_set = get_text_from_view(self.view_xml)
        return list(text_set)

    def get_content_description(self):
        return get_content_description_from_view(self.view_xml)


    def get_dict(self):
        return {
            "target_view": self.view_xml.attrs,
            "action": self.action,
            "input_value": self.input_value,
            "content_description": self.get_content_description(),
            "text_on_view": self.get_text_on_target_view(),
            "resource_id_name": self.get_resource_id_name(),
            "scroll_or_swipe_range": self.get_scroll_or_swipe_range()
            # "caption": self.get_caption()
        }

    def crop_icon_screenshot(self, screen_shot, bounds):
        return screen_shot[bounds[1]:bounds[3], bounds[0]:bounds[2]]

    def __str__(self):
        if self.action in ["SCROLL", "SWIPE"]:
            return f"{self.action} from,to {self.get_scroll_or_swipe_range()}"
        if self.action in ["CLICK", "LONG CLICK", "INPUT"]:
            return f"{self.action} on {self.get_xy()}, {self.get_text_on_target_view()}"
        if self.action in ["ROTATE", "BACK"]:
            return f"{self.action}"

    def get_resource_id_name(self):
        return get_resource_id_from_view(self.view_xml)


class Action:
    def __init__(self, ui_event: Event, s2r: S2R):
        self.ui_event = ui_event
        self.s2r = s2r

    def __str__(self):
        return f"step: {self.s2r.get_index()}, {self.s2r.get_first_ui_action_type()}, {self.s2r.get_target_word()}; event: {self.ui_event}"

    def get_dict(self):
        return {
            "ui_event": self.ui_event.get_dict(),
            "s2r": self.s2r.get_dict()
        }

    def matched_with_empty_s2r(self):
        return self.s2r.is_noop_s2r()

    def __eq__(self, other):
        if isinstance(other, Action):
            return self.__hash__() == other.__hash__()
        return False

    def __hash__(self):
        return int(hashlib.md5(f"{self.ui_event.get_str_for_hash()} {str(self.s2r)}".encode()).hexdigest(), 16)
