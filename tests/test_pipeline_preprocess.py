import math

from intent2trajectory_pipeline.preprocess import build_prepare_segment, preprocess_rows


def test_preprocess_rows_converts_ned_absolute_rows_to_local_ned():
    rows = [
        {'time_relative': 0.0, 'x': 10.0, 'y': 20.0, 'z': 30.0, 'yaw': 0.3},
        {'time_relative': 0.1, 'x': 11.0, 'y': 22.0, 'z': 29.0, 'yaw': 0.4},
    ]

    result = preprocess_rows(rows, coordinate_frame='NED')

    assert result.initial_pose == {'x': 10.0, 'y': 20.0, 'z': 30.0, 'yaw': 0.3}
    assert result.local_rows[0]['x'] == 0.0
    assert result.local_rows[0]['y'] == 0.0
    assert result.local_rows[0]['z'] == 0.0
    assert result.local_rows[1]['x'] == 1.0
    assert result.local_rows[1]['y'] == 2.0
    assert result.local_rows[1]['z'] == -1.0


def test_preprocess_rows_converts_enu_absolute_rows_to_local_ned():
    rows = [
        {'time_relative': 0.0, 'x': 100.0, 'y': 200.0, 'z': 50.0, 'yaw': 0.0},
        {'time_relative': 0.1, 'x': 101.0, 'y': 202.0, 'z': 49.5, 'yaw': 0.2},
    ]

    result = preprocess_rows(rows, coordinate_frame='ENU')

    assert result.local_rows[0]['x'] == 0.0
    assert result.local_rows[0]['y'] == 0.0
    assert result.local_rows[0]['z'] == 0.0
    assert result.local_rows[1]['x'] == 2.0
    assert result.local_rows[1]['y'] == 1.0
    assert result.local_rows[1]['z'] == 0.5
    assert math.isclose(result.local_rows[0]['yaw'], math.pi / 2, rel_tol=1e-9)


def test_preprocess_rows_rejects_unknown_coordinate_frame():
    rows = [{'time_relative': 0.0, 'x': 1.0, 'y': 2.0, 'z': 3.0, 'yaw': 0.0}]

    try:
        preprocess_rows(rows, coordinate_frame='AUTO')
    except ValueError as exc:
        assert 'coordinate_frame' in str(exc)
    else:
        raise AssertionError('expected ValueError')


def test_build_prepare_segment_creates_safe_start_before_playback():
    segment = build_prepare_segment(
        initial_local_pose={'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.3},
        safe_spawn_z=5.0,
        prepare_duration=2.0,
        dt=0.5,
    )

    assert segment[0]['z'] == 5.0
    assert segment[-1]['z'] == 0.0
    assert segment[-1]['yaw'] == 0.3
    assert segment[0]['x'] == 0.0
    assert segment[0]['y'] == 0.0
