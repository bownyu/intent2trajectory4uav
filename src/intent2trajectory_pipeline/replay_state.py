class ReplayStateMachine:
    _TRANSITIONS = {
        'LOAD_TRAJECTORY': 'PREPARE_START',
        'PREPARE_START': 'WARMUP',
        'WARMUP': 'ARM_AND_OFFBOARD',
        'ARM_AND_OFFBOARD': 'PLAYBACK',
        'PLAYBACK': 'HOLD_LAST_SETPOINT',
        'HOLD_LAST_SETPOINT': 'FINISH',
    }

    def __init__(self) -> None:
        self.state = 'LOAD_TRAJECTORY'

    def _advance(self, expected: str) -> None:
        if self.state != expected:
            raise RuntimeError(f'invalid transition from {self.state}')
        self.state = self._TRANSITIONS[self.state]

    def mark_loaded(self) -> None:
        self._advance('LOAD_TRAJECTORY')

    def mark_prepared(self) -> None:
        self._advance('PREPARE_START')

    def mark_warmup_complete(self) -> None:
        self._advance('WARMUP')

    def mark_armed(self) -> None:
        self._advance('ARM_AND_OFFBOARD')

    def mark_playback_complete(self) -> None:
        self._advance('PLAYBACK')

    def mark_hold_complete(self) -> None:
        self._advance('HOLD_LAST_SETPOINT')
