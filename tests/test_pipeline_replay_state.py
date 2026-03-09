from intent2trajectory_pipeline.replay_state import ReplayStateMachine


def test_replay_state_machine_visits_required_states():
    machine = ReplayStateMachine()

    assert machine.state == 'LOAD_TRAJECTORY'
    machine.mark_loaded()
    assert machine.state == 'PREPARE_START'
    machine.mark_prepared()
    assert machine.state == 'WARMUP'
    machine.mark_warmup_complete()
    assert machine.state == 'ARM_AND_OFFBOARD'
    machine.mark_armed()
    assert machine.state == 'PLAYBACK'
    machine.mark_playback_complete()
    assert machine.state == 'HOLD_LAST_SETPOINT'
    machine.mark_hold_complete()
    assert machine.state == 'FINISH'


def test_replay_state_machine_rejects_invalid_transition():
    machine = ReplayStateMachine()
    try:
        machine.mark_armed()
    except RuntimeError as exc:
        assert 'LOAD_TRAJECTORY' in str(exc)
    else:
        raise AssertionError('expected RuntimeError')
