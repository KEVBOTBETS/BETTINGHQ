"""Ladder state machine.

Rules:
  - Rung 0 stakes `base_stake` of new money.
  - A win rolls the ENTIRE return forward as the next rung's stake.
  - A loss resets to rung 0. Net uses actual settled stakes, including overrides.
  - A push/void leaves the stake and rung untouched.
  - Reaching `max_rung` cashes out and resets to rung 0.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Ladder:
    base_stake: float = 5.00
    max_rung: int = 5
    currency: str = "CAD"
    max_stake: float = 0.0        # 0 = no ceiling; else auto-cash before exceeding
    stake_increment: float = 0.01  # round stakes DOWN to this (never overstake)
    one_bet_per_day: bool = False
    stop_loss_busts: int = 0      # 0 = off; halt after N busts in the window
    stop_loss_days: int = 30
    timezone: str = "America/Toronto"
    halted: bool = False
    # Preserve earlier bets for reporting, but do not let them advance a new run.
    reset_at: str = ""
    rung: int = 0
    stake: float = 5.00
    pending: dict | None = None
    history: list = field(default_factory=list)
    runs_completed: int = 0
    runs_busted: int = 0
    net: float = 0.0

    # ---------- persistence ----------
    @classmethod
    def load(cls, path: str | Path) -> "Ladder":
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text())
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=2))

    # ---------- core ----------
    def next_stake(self) -> float:
        raw = self.base_stake if self.rung == 0 else self.stake
        inc = self.stake_increment or 0.01
        # Round DOWN: you can always bet less than you have, never more.
        return round(math.floor(raw / inc + 1e-9) * inc, 2)

    def would_exceed_cap(self) -> bool:
        return bool(self.max_stake) and self.next_stake() > self.max_stake

    def local_today(self) -> str:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(self.timezone)
        except Exception:
            tz = timezone.utc
        return datetime.now(tz).strftime("%Y-%m-%d")

    def _local_day(self, iso: str) -> str:
        if not iso:
            return ""
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(self.timezone)
        except Exception:
            tz = timezone.utc
        try:
            return datetime.fromisoformat(iso).astimezone(tz).strftime("%Y-%m-%d")
        except ValueError:
            return iso[:10]

    def bet_already_today(self) -> bool:
        today = self.local_today()
        if self.pending and self._local_day(self.pending.get("placed_at", "")) == today:
            return True
        return any(self._local_day(h.get("placed_at", "")) == today
                   for h in self.history if h.get("placed_at"))

    def recent_busts(self) -> int:
        if not self.stop_loss_busts:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.stop_loss_days)
        n = 0
        for h in self.history:
            if h.get("result") != "loss":
                continue
            try:
                when = datetime.fromisoformat(h.get("settled_at", ""))
            except ValueError:
                continue
            if when >= cutoff:
                n += 1
        return n

    def stop_loss_hit(self) -> bool:
        return bool(self.stop_loss_busts) and self.recent_busts() >= self.stop_loss_busts

    def place(self, candidate: dict, price: float | None = None,
              stake: float | None = None) -> dict:
        """price/stake are what you ACTUALLY got, which is rarely the screened
        number. The ladder compounds the real return, so record the real fill."""
        if self.pending:
            raise RuntimeError("a bet is already pending — settle it first")
        if self.halted:
            raise RuntimeError("ladder is halted — run `ladder resume` to restart")
        if self.stop_loss_hit():
            self.halted = True
            raise RuntimeError(
                f"stop-loss: {self.recent_busts()} busted runs in the last "
                f"{self.stop_loss_days} days (limit {self.stop_loss_busts}). "
                f"Halted. Run `ladder resume` when you have decided to continue.")
        if self.one_bet_per_day and self.bet_already_today():
            raise RuntimeError(
                f"already placed a bet today ({self.local_today()}). "
                f"One bet of the day is the design — use --force to override.")
        if self.would_exceed_cap():
            raise RuntimeError(
                f"next stake ${self.next_stake():.2f} exceeds max_stake "
                f"${self.max_stake:.2f} — run `ladder cashout` to bank "
                f"${self.stake:.2f} and start a fresh ladder")

        screened = float(candidate.get("decimal", 0) or 0)
        actual = float(price) if price else screened
        if actual <= 1.0:
            raise ValueError(f"price must be decimal odds above 1.0, got {actual}")

        s = float(stake) if stake else self.next_stake()
        if s <= 0:
            raise ValueError("stake must be positive")
        self.stake = round(s, 2)

        bet = dict(candidate)
        bet.update({
            "placed_at": _now(),
            "rung": self.rung,
            "stake": self.stake,
            "screened_decimal": round(screened, 4) if screened else None,
            "decimal": round(actual, 4),
            "slippage": round(actual - screened, 4) if screened else None,
            "to_return": round(self.stake * actual, 2),
        })
        self.pending = bet
        return self.pending

    def amend(self, price: float | None = None, stake: float | None = None) -> dict:
        """Fix the pending bet after the fact — the line moved, or the book
        would not take the exact stake."""
        if not self.pending:
            raise RuntimeError("no pending bet to amend")
        if price is not None:
            if float(price) <= 1.0:
                raise ValueError("price must be decimal odds above 1.0")
            self.pending["decimal"] = round(float(price), 4)
            sc = self.pending.get("screened_decimal")
            if sc:
                self.pending["slippage"] = round(float(price) - sc, 4)
        if stake is not None:
            if float(stake) <= 0:
                raise ValueError("stake must be positive")
            self.pending["stake"] = round(float(stake), 2)
            self.stake = self.pending["stake"]
        self.pending["to_return"] = round(
            self.pending["stake"] * self.pending["decimal"], 2)
        self.pending["amended_at"] = _now()
        return self.pending

    def settle(self, result: str, closing: float | None = None) -> dict:
        if not self.pending:
            raise RuntimeError("no pending bet")
        result = result.lower()
        if result not in {"win", "loss", "push"}:
            raise ValueError("result must be win, loss or push")

        bet = dict(self.pending)
        bet["result"] = result
        bet["settled_at"] = _now()

        if closing is not None and bet.get("decimal"):
            bet["closing_decimal"] = round(float(closing), 4)
            # CLV: positive means you beat the number the market settled on.
            bet["clv"] = round(bet["decimal"] - float(closing), 4)

        if result == "win":
            ret = round(bet["stake"] * bet["decimal"], 2)
            self.stake = ret
            self.rung += 1
            bet["returned"] = ret
            if self.rung >= self.max_rung:
                bet["cashed_out"] = ret
                self.net = round(self.net + self.current_run_profit() + ret - bet["stake"], 2)
                self.runs_completed += 1
                self._reset()
        elif result == "loss":
            bet["returned"] = 0.0
            self.net = round(self.net + self.current_run_profit() - bet["stake"], 2)
            self.runs_busted += 1
            self._reset()
        else:  # push
            bet["returned"] = bet["stake"]

        self.pending = None
        self.history.append(bet)
        return bet

    def current_run_profit(self) -> float:
        """Actual wager P/L since the last reset; works with existing history."""
        profit = 0.0
        for bet in reversed(self.history):
            if self.reset_at and (bet.get("placed_at") or bet.get("settled_at") or "") < self.reset_at:
                break
            if bet.get("event") == "cash_out" or bet.get("cashed_out") or bet.get("result") == "loss":
                break
            if bet.get("result") == "win":
                profit += float(bet.get("returned") or 0) - float(bet.get("stake") or 0)
        return round(profit, 2)

    def cash_out(self) -> float:
        """Bank the current stack early and start a fresh ladder."""
        if self.pending:
            raise RuntimeError("settle the pending bet first")
        if self.rung == 0:
            return 0.0
        banked = round(self.stake, 2)
        self.net = round(self.net + self.current_run_profit(), 2)
        self.runs_completed += 1
        self.history.append({"settled_at": _now(), "event": "cash_out",
                             "rung": self.rung, "banked": banked})
        self._reset()
        return banked

    def _reset(self) -> None:
        self.rung = 0
        self.stake = self.base_stake

    def current_run_stakes(self) -> list[float]:
        """Actual stakes of the wins in the unbroken run leading to this rung.

        Rungs already climbed were staked at real, differing prices. Rebuilding
        them from base_stake at one assumed price shows numbers you never bet.
        """
        out: list[float] = []
        for h in reversed(self.history):
            if self.reset_at and (h.get("placed_at") or h.get("settled_at") or "") < self.reset_at:
                break
            if h.get("event") == "cash_out":
                break
            r = h.get("result")
            if r == "win":
                out.append(float(h.get("stake") or 0))
            elif r in ("loss",):
                break
        out.reverse()
        return out[-self.rung:] if self.rung else []

    def projection(self, decimal: float, rungs: int | None = None) -> list[dict]:  # noqa: D401
        rungs = rungs or self.max_rung
        rows, s = [], self.next_stake()
        for i in range(self.rung, rungs):
            rows.append({"rung": i, "stake": round(s, 2),
                         "returns": round(s * decimal, 2)})
            s *= decimal
        return rows
