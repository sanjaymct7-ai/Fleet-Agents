"""One-click day: the entire pipeline, run in-process for the Command Center.
Phases: reset -> plan -> dispatch -> simulate -> track -> recover -> arbitrate/execute -> comms -> report."""
import src.simulator as simulator
from src.comms_agent import render as write_comms
from src.db import get_client
from src.dispatch_agent import dispatch
from src.executor import run as execute
from src.manager_agent import review
from src.planner import plan_and_save
from src.recovery_agent import run as recover
from src.reporting_agent import report
from src.reset_day import reset
from src.tracking_agent import scan


def run_day(log=print):
    log("1/9 Resetting the world…")
    reset()
    log("2/9 Planning routes (OR-Tools)…")
    plan_and_save()
    log("3/9 Dispatching drivers…")
    dispatch()
    log("4/9 Simulating the day (compressed)…")
    simulator.SPEED = 0.01   # ~6s per sim-hour: fast, map still animates
    simulator.run()
    log("5/9 Tracking: raising exceptions…")
    scan(get_client())
    log("6/9 Recovery agent judging exceptions…")
    recover()
    log("7/9 Manager reviewing T2s, executor applying approved actions…")
    review()
    execute()
    log("8/9 Comms agent writing customer messages…")
    write_comms()
    log("9/9 Reporting agent writing the daily digest…")
    report()
    log("✅ Day complete — check the feed, inbox, and any escalation cards.")


if __name__ == "__main__":
    run_day()