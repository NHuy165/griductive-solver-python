from src.game.clue.clue import Clue


class Person:
    def __init__(
        self, name: str, occupation: str, clue: Clue, is_criminal: bool
    ) -> None:
        self.name = name
        self.occupation = occupation
        self.clue = clue
        self.is_criminal = is_criminal

    def get_name(self) -> str:
        return self.name

    def get_occupation(self) -> str:
        return self.occupation

    def get_clue(self) -> Clue:
        return self.clue

    def get_is_criminal(self) -> bool:
        return self.is_criminal
