from src.game.logic.game_engine import GameEngine


def get_primary_auxiliary_variables(engine: GameEngine) -> tuple[int, int]:
    return engine.get_map_size(), 0
