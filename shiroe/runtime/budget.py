"""Per-run cost + token budget tracker."""

from __future__ import annotations

from dataclasses import dataclass


class BudgetError(RuntimeError):
    pass


@dataclass
class BudgetTracker:
    usd_max: float
    tokens_input_max: int
    tokens_output_max: int
    usd_spent: float = 0.0
    tokens_input_spent: int = 0
    tokens_output_spent: int = 0

    def charge(self, *, usd: float = 0.0,
               tokens_input: int = 0,
               tokens_output: int = 0) -> None:
        self.usd_spent += usd
        self.tokens_input_spent += tokens_input
        self.tokens_output_spent += tokens_output

    def exceeded(self) -> str | None:
        if self.usd_max and self.usd_spent > self.usd_max:
            return f"usd_max exceeded: {self.usd_spent:.2f} > {self.usd_max:.2f}"
        if self.tokens_input_max and self.tokens_input_spent > self.tokens_input_max:
            return (f"tokens_input_max exceeded: "
                    f"{self.tokens_input_spent} > {self.tokens_input_max}")
        if self.tokens_output_max and self.tokens_output_spent > self.tokens_output_max:
            return (f"tokens_output_max exceeded: "
                    f"{self.tokens_output_spent} > {self.tokens_output_max}")
        return None

    def snapshot(self) -> dict:
        return {
            "usd_spent": round(self.usd_spent, 4),
            "tokens_input_spent": self.tokens_input_spent,
            "tokens_output_spent": self.tokens_output_spent,
        }
