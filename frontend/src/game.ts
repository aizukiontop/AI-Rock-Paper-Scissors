import type { Move } from "./components";

export type Outcome = "win" | "loss" | "draw";
export type Round = { id: number; player: Move; robot: Move; outcome: Outcome };
export const moves: Move[] = ["Rock", "Paper", "Scissors"];
export const beats: Record<Move, Move> = { Rock: "Scissors", Paper: "Rock", Scissors: "Paper" };
export function getOutcome(player: Move, robot: Move): Outcome {
  return player === robot ? "draw" : beats[player] === robot ? "win" : "loss";
}
export function chooseRobotMove(history: Round[], adaptive: boolean): Move {
  if (!adaptive || history.length < 3 || Math.random() < 0.4)
    return moves[Math.floor(Math.random() * 3)];
  const counts = history.slice(0, 8).reduce(
    (acc, round) => {
      acc[round.player]++;
      return acc;
    },
    { Rock: 0, Paper: 0, Scissors: 0 },
  );
  const likely = [...moves].sort((a, b) => counts[b] - counts[a])[0];
  return moves.find((move) => beats[move] === likely)!;
}
