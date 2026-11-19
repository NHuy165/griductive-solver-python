from src.game.logic.game_engine import GameEngine


def count_primary_auxiliary_indices(engine: GameEngine) -> tuple[int, int]:
    return engine.get_map_size(), engine.get_auxiliary_count()
