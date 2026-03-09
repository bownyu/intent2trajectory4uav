from intent2trajectory_pipeline.ulog_export import build_executed_rows, restore_absolute_rows


def test_build_executed_rows_emits_required_columns():
    rows = build_executed_rows(
        samples=[
            {
                'time_relative': 0.0,
                'x': 1.0,
                'y': 2.0,
                'z': 3.0,
                'vx': 0.1,
                'vy': 0.2,
                'vz': 0.3,
                'yaw': 0.4,
            }
        ]
    )

    first = rows[0]
    assert first['act_pos_x'] == 1.0
    assert first['act_vel_z'] == 0.3
    assert first['act_yaw'] == 0.4


def test_restore_absolute_rows_adds_ned_origin_back():
    rows = [{'time_relative': 0.0, 'act_pos_x': 1.0, 'act_pos_y': 2.0, 'act_pos_z': 3.0, 'act_yaw': 0.4}]
    restored = restore_absolute_rows(rows, origin_ned={'x': 10.0, 'y': 20.0, 'z': 30.0})
    assert restored[0]['act_pos_x'] == 11.0
    assert restored[0]['act_pos_y'] == 22.0
    assert restored[0]['act_pos_z'] == 33.0
