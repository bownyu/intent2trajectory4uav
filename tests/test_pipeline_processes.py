from intent2trajectory_pipeline.processes import build_agent_command, build_px4_command


def test_build_agent_command_returns_non_empty_tokens():
    command = build_agent_command(udp_port=8888)
    assert command[0]
    assert '8888' in ' '.join(command)


def test_build_px4_command_includes_model_and_world_and_speed():
    command = build_px4_command(model='gz_x500', world='default', simulation_speed_factor=2.0)
    joined = ' '.join(command)
    assert 'gz_x500' in joined
    assert 'default' in joined
    assert '2.0' in joined
