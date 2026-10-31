"""Smoke tests of the CAD helper API in Fusion: each test builds a part and checks it against hand numbers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_ladder
from cad_api import CAD_PRELUDE
from fusion_side import CLOSE_ALL_BENCH_DOCS_SCRIPT, NEW_DOCUMENT_SCRIPT
from mcp_client import FusionMcp

TESTS = {
    "box corner": """
box(60, 40, 5, corner=(0, 0, 0))
check(size=(60, 40, 5), volume=12000)""",
    "box base and join": """
box(20, 20, 10, base=(0, 0, 0))
box(10, 10, 5, base=(0, 0, 10), operation='join')
check(size=(20, 20, 15), volume=4000 + 500)""",
    "box center refused": """
box(20, 20, 10, center=(0, 0, 0))""",
    "cylinder Z": """
cylinder(30, 10, base=(0, 0, 0))
check(size=(30, 30, 10), diameters=[30], volume=math.pi*225*10)""",
    "cylinder X": """
cylinder(12, 50, base=(0, 5, 6), axis='X')
check(size=(50, 12, 12), diameters=[12], volume=math.pi*36*50)""",
    "tube": """
tube(20, 10, 15, base=(0, 0, 0))
check(size=(20, 20, 15), diameters=[20, 10], volume=math.pi*(100-25)*15)""",
    "shaft stepped Z": """
shaft([(30, 20), (20, 30), (12, 15)])
check(size=(30, 30, 65), diameters=[30, 20, 12], volume=math.pi*(225*20 + 100*30 + 36*15))""",
    "shaft collar bore": """
shaft([(24, 3), (16, 17)], bore=10)
check(size=(24, 24, 20), diameters=[24, 16, 10], volume=math.pi*(144*3 + 64*17 - 25*20))""",
    "shaft along X offset": """
shaft([(16, 28), (10, 12)], base=(5, 10, 20), axis='X')
check(size=(40, 16, 16), diameters=[16, 10], volume=math.pi*(64*28 + 25*12))
describe()""",
    "shaft along Y": """
shaft([(16, 28), (10, 12)], axis='Y')
check(size=(40, 16, 16), diameters=[16, 10], volume=math.pi*(64*28 + 25*12))""",
    "angle profile": """
angle_profile(40, 30, 4, 25)
check(size=(40, 30, 25), volume=(40*4 + 26*4)*25)""",
    "channel": """
channel(20, 15, 3, 50)
check(size=(20, 15, 50), volume=(20*3 + 2*12*3)*50)""",
    "tee": """
tee(30, 25, 4, 4, 60)
check(size=(30, 25, 60), volume=(30*4 + 4*21)*60)""",
    "ibeam": """
ibeam(40, 30, 5, 4, 100)
check(size=(40, 30, 100), volume=(2*30*5 + 4*30)*100)""",
    "drill cross": """
cylinder(12, 50, base=(0, 0, 0))
drill(0, 0, 44, 4, axis='Y')
check(size=(12, 12, 50), diameters=[4, 12], volume=5506.0)""",
    "drill blind from top": """
box(40, 40, 10, corner=(0, 0, 0))
drill(20, 20, 10, 6, axis='Z', depth=4)
check(size=(40, 40, 10), diameters=[6], volume=16000 - math.pi*9*4)""",
    "screw holes counterbore": """
box(60, 40, 10, corner=(0, 0, 0))
screw_holes([(10, 10), (50, 30)], 5.5, z=10, counterbore=(10, 5))
check(size=(60, 40, 10), diameters=[5.5, 10], volume=24000 - 2*math.pi*(5.5*5.5/4*5 + 25*5), operations=['hole'])""",
    "shell top": """
box(40, 30, 20, corner=(0, 0, 0))
shell(2, 'top')
check(size=(40, 30, 20), volume=40*30*20 - 36*26*18, operations=['shell'])""",
    "mirror": """
box(60, 40, 5, corner=(-30, -20, 0))
f = holes([(20, 10)], 6)
mirror(f, 'YZ')
check(size=(60, 40, 5), diameters=[6], volume=12000 - 2*math.pi*9*5, operations=['mirror'])""",
    "move circle": """
sk = new_sketch('XY')
rect(sk, 0, 0, 60, 40)
circle(sk, 30, 20, 12)
extrude(sk, 5)
move_circle(find_circles(12)[0], 15, 20)
check(size=(60, 40, 5), diameters=[12])""",
    "set parameter": """
box(60, 40, 5, corner=(0, 0, 0))
fillet(find_edges(parallel_to='Z'), 5)
set_parameter('d1', 8)
set_parameter('d4', 3)
check(size=(60, 40, 8), diameters=[6], volume=60*40*8 - 4*(9 - math.pi*9/4)*8, operations=['fillet'])
describe()""",
    "holes from top face": """
box(60, 60, 5, corner=(-30, -30, 0))
f = holes([(20, 0)], 6, offset=5)
circular_pattern(f, 3)
holes([(0, 0)], 12, offset=0)
check(size=(60, 60, 5), diameters=[6, 12], volume=18000 - 3*math.pi*9*5 - math.pi*36*5, operations=['circular_pattern'])""",
}


def main():
    fusion = FusionMcp()
    selected = sys.argv[1:] or list(TESTS)
    for name in selected:
        run_ladder.must(fusion.run_script(NEW_DOCUMENT_SCRIPT), "new document")
        try:
            call = {"function": {"name": "fusion_script", "arguments": {"script": TESTS[name].strip()}}}
            print("==", name)
            print(run_ladder.run_tool(fusion, call, [], CAD_PRELUDE).strip())
        finally:
            fusion.run_script(CLOSE_ALL_BENCH_DOCS_SCRIPT)


if __name__ == "__main__":
    main()
