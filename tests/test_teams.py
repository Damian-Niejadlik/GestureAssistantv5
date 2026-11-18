import pytest

from src.gesture_assistant.integrations import teams
from src.gesture_assistant.integrations.contracts import IntegrationNotImplemented


def test_teams_catalog_and_legacy_entrypoint():
    expected_actions = {
        "teams.toggle_mute",
        "teams.toggle_raise_hand",
        "teams.toggle_camera",
        "teams.reaction_like",
        "teams.reaction_applause",
        "teams.leave_meeting",
    }

    actions = {action.action_id: action for action in teams.ACTIONS}

    assert set(actions) == expected_actions
    assert all(action.implemented for action in actions.values())
    assert actions["teams.leave_meeting"].destructive

    functions = (
        teams.toggle_mute,
        teams.toggle_raise_hand,
        teams.toggle_camera,
        teams.reaction_like,
        teams.reaction_applause,
        teams.leave_meeting,
    )

    assert all(callable(function) for function in functions)

    with pytest.raises(IntegrationNotImplemented):
        teams.execute()

