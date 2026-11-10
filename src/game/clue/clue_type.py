from enum import Enum


class ClueType(str, Enum):
    FACT = "FACT"
    DIFFERENT = "DIFFERENT"
    SAME = "SAME"
    EXACTLY = "EXACTLY"
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"
