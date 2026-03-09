from typing import List


def build_agent_command(*, udp_port: int) -> List[str]:
    return ['MicroXRCEAgent', 'udp4', '-p', str(udp_port)]


def build_px4_command(*, model: str, world: str, simulation_speed_factor: float) -> List[str]:
    return [
        'make',
        'px4_sitl',
        model,
        f'PX4_GZ_WORLD={world}',
        f'PX4_SIM_SPEED_FACTOR={simulation_speed_factor}',
    ]
