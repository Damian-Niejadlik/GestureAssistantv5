"""Closed action catalog. Native integrations are not enabled."""

from src.gesture_assistant.integrations import (
    browser_actions,
    media_actions,
    presentation_actions,
    teams,
    windows_actions,
)

ACTION_CATALOG = {
    action.action_id: action
    for module in (teams, windows_actions, browser_actions, presentation_actions, media_actions)
    for action in module.ACTIONS
}

