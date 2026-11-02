"""`fusion-agent --selftest`: four quick tasks through the real loop, checked against hand-computed numbers.

Each task runs in a new design the self-test marks as its own; it closes only those designs.
"""
import math
import re
import time

from fusion_agent import doctor, term
from fusion_agent.agent import Agent, AgentListener
from fusion_agent.session import DesignSession, new_session_id

# Requests in Russian, as the prompt was tuned; the expected numbers are computed by hand.
PLATE = {
    "title": "plate with holes",
    "request": "Сделай пластину 80 на 50 мм толщиной 6 мм с четырьмя сквозными отверстиями диаметром 6 мм, "
               "центры отверстий в 10 мм от краёв.",
    "extents": [6, 50, 80],
    "volume": 80 * 50 * 6 - 4 * math.pi * 3 * 3 * 6,
    "diameters": [6],
}
THICKER = {
    "title": "edit: make it thicker",
    "request": "Сделай пластину толще: 10 мм.",
    "extents": [10, 50, 80],
    "volume": 80 * 50 * 10 - 4 * math.pi * 3 * 3 * 10,
    "diameters": [6],
}
SHAFT = {
    "title": "stepped shaft",
    "request": "Сделай ступенчатый вал: участок диаметром 20 мм длиной 30 мм, затем 16 мм длиной 40 мм, "
               "затем 12 мм длиной 25 мм.",
    "extents": [20, 20, 95],
    "volume": math.pi * (10 * 10 * 30 + 8 * 8 * 40 + 6 * 6 * 25),
    "diameters": [12, 16, 20],
}
# A question: the design must stay as it is and the answer must give the number.
QUESTION = {
    "title": "question: how thick",
    "request": "Какая сейчас толщина у пластины?",
    "extents": [10, 50, 80],
    "volume": 80 * 50 * 10 - 4 * math.pi * 3 * 3 * 10,
    "diameters": [6],
    "answer": 10,
}
# Each inner list runs in one new design, in order (the edit and the question work on the plate).
GROUPS = [[PLATE, THICKER, QUESTION], [SHAFT]]


def answer_problems(task, result):
    """For a question: the design did not change and the answer names the expected number."""
    found = []
    if result["changed"]:
        found.append("the design changed on a question")
    numbers = [float(number.replace(",", ".")) for number in re.findall(r"\d+(?:[.,]\d+)?", result["final_answer"])]
    if not any(abs(number - task["answer"]) < 0.01 for number in numbers):
        found.append("the answer does not say %s: %r" % (task["answer"], result["final_answer"][:120]))
    return found


def problems_of(task, signature):
    """Empty when the design matches the task: one body, volume within 0.5 %, sizes, round faces."""
    bodies = signature["bodies"]
    if signature["unhealthy"]:
        return ["unhealthy features: " + ", ".join(signature["unhealthy"])]
    if len(bodies) != 1:
        return ["%d bodies instead of 1" % len(bodies)]
    body = bodies[0]
    found = []
    if abs(body["volume_mm3"] - task["volume"]) > 0.005 * task["volume"]:
        found.append("volume %.1f mm3 instead of %.1f" % (body["volume_mm3"], task["volume"]))
    if any(abs(got - want) > 0.05 for got, want in zip(body["extents_mm"], sorted(task["extents"]))):
        found.append("size %s mm instead of %s" % (body["extents_mm"], sorted(task["extents"])))
    diameters = body["cylinder_diameters_mm"]
    if len(diameters) != len(task["diameters"]) or any(
            abs(got - want) > 0.02 for got, want in zip(diameters, sorted(task["diameters"]))):
        found.append("round faces %s mm instead of %s" % (diameters, sorted(task["diameters"])))
    return found


def run_selftest(model):
    print("fusion-agent self-test, model %s" % model)
    checks = doctor.Doctor(model)
    results = checks.run(include_document=False)
    blocking = [result for result in results if result.blocks_start]
    if blocking:
        doctor.print_results(results)
        print("The self-test needs these fixed first.")
        return 1

    session = DesignSession(checks.fusion, new_session_id())
    details = checks.model_details
    passed = 0
    total = 0
    started = time.time()
    try:
        for group in GROUPS:
            session.new_design(is_selftest=True)
            agent = Agent(checks.fusion, checks.ollama, session.session_id, model=model, think=False,
                          has_vision=details["has_vision"], has_thinking=details["has_thinking"],
                          listener=AgentListener())
            for task in group:
                total += 1
                task_started = time.time()
                try:
                    result = agent.turn(task["request"])
                    found = problems_of(task, result["end_signature"] or agent.signature())
                    if "answer" in task:
                        found += answer_problems(task, result)
                except Exception as error:
                    found = ["%s: %s" % (type(error).__name__, error)]
                seconds = time.time() - task_started
                label = ("%d. %s " % (total, task["title"])).ljust(32, ".")
                if found:
                    print("  %s %s  %.1f s  (%s)" % (label, term.paint("FAIL", term.RED), seconds, "; ".join(found)))
                else:
                    passed += 1
                    print("  %s %s  %.1f s" % (label, term.paint("PASS", term.GREEN), seconds))
    finally:
        closed = session.close_selftest_documents()
    print("%d/%d passed in %.1f s; %s." % (passed, total, time.time() - started, closed))
    return 0 if passed == total else 1
