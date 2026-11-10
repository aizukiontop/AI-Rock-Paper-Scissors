"""
Game logic for Rock Paper Scissors.
Handles rules, AI selection, win/loss/draw determination, and forfeiture.
"""

import random
from enum import Enum


class Move(str, Enum):
    ROCK = "rock"
    PAPER = "paper"
    SCISSORS = "scissors"
    FORFEIT = "forfeit"


# Maps MediaPipe gesture names to game moves
GESTURE_MAP = {
    "Closed_Fist": Move.ROCK,
    "Open_Palm": Move.PAPER,
    "Victory": Move.SCISSORS,
}

# Which move beats which
BEATS = {
    Move.ROCK: Move.SCISSORS,
    Move.SCISSORS: Move.PAPER,
    Move.PAPER: Move.ROCK,
}

# Human-readable labels
MOVE_LABELS = {
    Move.ROCK: "Rock",
    Move.PAPER: "Paper",
    Move.SCISSORS: "Scissors",
    Move.FORFEIT: "Forfeit",
}


def ai_choose() -> Move:
    """Randomly select a move for the AI."""
    return random.choice([Move.ROCK, Move.PAPER, Move.SCISSORS])


def map_gesture(gesture_name: str) -> Move | None:
    """
    Convert a MediaPipe gesture name to a game Move.
    Returns None if gesture is not recognized.
    """
    return GESTURE_MAP.get(gesture_name)


def determine_winner(player: Move, ai: Move) -> str:
    """
    Determine the round outcome.
    Returns: 'win', 'loss', 'draw', or 'forfeit'
    """
    if player == Move.FORFEIT:
        return "forfeit"
    if player == ai:
        return "draw"
    if BEATS[player] == ai:
        return "win"
    return "loss"


def result_message(outcome: str, player: Move, ai: Move) -> dict:
    """Build the display message for a round result."""
    messages = {
        "win": {"headline": "YOU WIN!", "sub": f"Your {MOVE_LABELS[player]} beats AI's {MOVE_LABELS[ai]}", "color": "#4ade80"},
        "loss": {"headline": "AI WINS!", "sub": f"AI's {MOVE_LABELS[ai]} beats your {MOVE_LABELS[player]}", "color": "#f87171"},
        "draw": {"headline": "DRAW!", "sub": f"Both played {MOVE_LABELS[player]}", "color": "#facc15"},
        "forfeit": {"headline": "YOU FORFEITED!", "sub": f"No gesture detected — AI played {MOVE_LABELS[ai]}", "color": "#f87171"},
    }
    return messages.get(outcome, {"headline": "ERROR", "sub": "", "color": "#ffffff"})
