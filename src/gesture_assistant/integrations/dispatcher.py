from src.gesture_assistant.integrations import (
    ACTION_CATALOG,
    browser_actions,
    media_actions,
    presentation_actions,
    teams,
    windows_actions,
)
from src.gesture_assistant.integrations.contracts import IntegrationNotImplemented
from src.gesture_assistant.integrations.native_backend import WindowsBackend


class NativeDispatcher:
    def __init__(self, config, backend=None):
        from src.gesture_assistant.config.schema import validate_config

        self.config = validate_config(config)
        self.backend = backend or WindowsBackend()

    def dispatch(self, request, guard):
        if request.action_id not in ACTION_CATALOG:
            raise ValueError("Nieznana akcja.")
        shortcuts = self.config["targets"]["shortcuts"]
        if request.action_id.startswith("teams."):
            name = request.action_id.split(".", 1)[1]
            return getattr(teams, name)(self.backend, guard, shortcuts)
        if request.action_id == "browser.open_url":
            urls = self.config["targets"]["urls"]
            if "browser.open_url" not in urls:
                raise ValueError("Brak targets.urls['browser.open_url'].")
            return browser_actions.open_url(urls["browser.open_url"], guard)
        if request.action_id.startswith("browser."):
            name = request.action_id.split(".", 1)[1]
            return getattr(browser_actions, name)(self.backend, guard, shortcuts)
        for prefix, module in (("presentation.", presentation_actions), ("media.", media_actions)):
            if request.action_id.startswith(prefix):
                name = request.action_id.split(".", 1)[1]
                return getattr(module, name)(self.backend, guard, shortcuts)
        functions = {
            "sleep_computer": windows_actions.sleep_computer,
            "system.toggle_mute": windows_actions.toggle_system_mute,
            "system.take_screenshot": windows_actions.take_screenshot,
            "system.lock": windows_actions.lock_screen,
            "system.close_active_window": windows_actions.close_active_window,
        }
        if request.action_id == "system.switch_virtual_desktop":
            direction = "left" if request.signal == "SWIPE_LEFT" else "right"
            return windows_actions.switch_virtual_desktop(self.backend, guard, direction)
        function = functions.get(request.action_id)
        if function is None:
            raise IntegrationNotImplemented(f"Akcja {request.action_id} nie ma implementacji.")
        return function(self.backend, guard)

