"""Make an honest task set from the Fusion 360 Gallery reconstruction data (harrisonxliang/Fusion360Dataset).

Every Gallery design is a picture plus its build history (sketches and extrudes) and the measured volume of
the result. This script turns the simple ones into tasks of the app's runner: the prompt is the picture plus
the steps in words with every size in mm, the reference is the same history replayed with the CAD helpers,
and the hand volume is the Gallery's own measurement, so a wrong replay is caught by --check-references.

    .venv\\Scripts\\python -X utf8 tools\\gallery_cases.py scanned.json cases\\gallery_holdout.json --limit 60

The scanned file is a list of designs (id, image URL, code = the Gallery JSON) made by a scan of the dataset
through the Hugging Face datasets-server API. Designs are kept when they use only lines, arcs and circles,
sketch planes parallel to the base planes, one-sided or symmetric extrudes without taper, and are 10..500 mm.
"""
import argparse
import io
import json
import math
import os
import random
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)

AXIS_NAMES = "XYZ"
PLANE_BY_NORMAL = {2: "XY", 1: "XZ", 0: "YZ"}
IN_PLANE = {"XY": (0, 1), "XZ": (0, 2), "YZ": (1, 2)}
OPERATIONS = {"NewBodyFeatureOperation": "new", "JoinFeatureOperation": "join", "CutFeatureOperation": "cut"}
OPERATION_WORDS = {"new": "новое тело", "join": "добавить к телу", "cut": "вырезать из тела"}


class Skip(Exception):
    """This design is not one the task set takes."""


def fmt(value):
    text = "%.3f" % value
    text = text.rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def mm(point):
    return [point["x"] * 10, point["y"] * 10, point["z"] * 10]


def to_world(transform, local):
    """Profile curves are stored in the sketch's own coordinates: world = origin + x*X + y*Y + z*Z."""
    origin = mm(transform["origin"])
    axes = [transform["x_axis"], transform["y_axis"], transform["z_axis"]]
    result = list(origin)
    for axis, value in zip(axes, local):
        result[0] += value * axis["x"]
        result[1] += value * axis["y"]
        result[2] += value * axis["z"]
    return result


def axis_of(vector):
    """World axis index of a unit vector parallel to an axis, and its sign; Skip otherwise."""
    values = [vector["x"], vector["y"], vector["z"]]
    index = max(range(3), key=lambda i: abs(values[i]))
    if abs(abs(values[index]) - 1) > 1e-6:
        raise Skip("sketch plane is tilted")
    return index, (1 if values[index] > 0 else -1)


def same(a, b):
    return all(abs(a[i] - b[i]) < 1e-4 for i in range(3))


def loop_to_2d(loop, plane, transform, normal_index, offsets):
    """One loop as ("circle", (u, v), diameter) or ("outline", [(u, v) | (u, v, "arc")...]);
    the world coordinate along the sketch normal of every point goes into offsets."""
    u_index, v_index = IN_PLANE[plane]
    curves = loop["profile_curves"]

    def mm(point):
        world = to_world(transform, [point["x"] * 10, point["y"] * 10, point["z"] * 10])
        offsets.append(world[normal_index])
        return world

    def arc_middle(curve):
        center = [curve["center_point"]["x"] * 10, curve["center_point"]["y"] * 10, curve["center_point"]["z"] * 10]
        radius = curve["radius"] * 10
        reference = curve["reference_vector"]
        normal = curve["normal"]
        ref = [reference["x"], reference["y"], reference["z"]]
        nrm = [normal["x"], normal["y"], normal["z"]]
        side = [nrm[1] * ref[2] - nrm[2] * ref[1], nrm[2] * ref[0] - nrm[0] * ref[2], nrm[0] * ref[1] - nrm[1] * ref[0]]
        angle = (curve["start_angle"] + curve["end_angle"]) / 2
        local = [center[i] + radius * (math.cos(angle) * ref[i] + math.sin(angle) * side[i]) for i in range(3)]
        return to_world(transform, local)

    if len(curves) == 1 and curves[0]["type"] == "Circle3D":
        center = mm(curves[0]["center_point"])
        return ("circle", (center[u_index], center[v_index]), curves[0]["radius"] * 20)
    for curve in curves:
        if curve["type"] not in ("Line3D", "Arc3D"):
            raise Skip("curve %s" % curve["type"])
    # Chain the curves end to end; each may be stored in either direction.
    remaining = list(curves)
    first = remaining.pop(0)
    points = [(mm(first["start_point"]), None), (mm(first["end_point"]), first if first["type"] == "Arc3D" else None)]
    current = mm(first["end_point"])
    while remaining:
        for index, curve in enumerate(remaining):
            start, end = mm(curve["start_point"]), mm(curve["end_point"])
            if same(start, current):
                nxt = end
            elif same(end, current):
                nxt = start
            else:
                continue
            remaining.pop(index)
            points.append((nxt, curve if curve["type"] == "Arc3D" else None))
            current = nxt
            break
        else:
            raise Skip("loop curves do not chain")
    if not same(points[-1][0], points[0][0]):
        raise Skip("loop is not closed")
    points.pop()  # the closing point repeats the first one
    result = []
    for index, (point, arc) in enumerate(points):
        if arc is not None:
            middle = arc_middle(arc)
            result.append((middle[u_index], middle[v_index], "arc"))
        result.append((point[u_index], point[v_index]))
    # An arc that closes the loop: its "arc" marker was attached to the first point; move it to the end.
    if result and len(result[0]) == 3:
        result.append(result.pop(0))
    return ("outline", result)


def sketch_plane(sketch):
    normal_index, normal_sign = axis_of(sketch["transform"]["z_axis"])
    plane = PLANE_BY_NORMAL[normal_index]
    return plane, normal_index, normal_sign


def point_text(point):
    return "(%s, %s)" % (fmt(point[0]), fmt(point[1]))


def points_code(points):
    parts = []
    for point in points:
        if len(point) == 3:
            parts.append("(%s, %s, 'arc')" % (fmt(point[0]), fmt(point[1])))
        else:
            parts.append("(%s, %s)" % (fmt(point[0]), fmt(point[1])))
    return "[" + ", ".join(parts) + "]"


def loop_words(kind_data):
    if kind_data[0] == "circle":
        return "окружность с центром %s диаметром %s" % (point_text(kind_data[1]), fmt(kind_data[2]))
    words = []
    points = kind_data[1]
    for index, point in enumerate(points):
        if len(point) == 3:
            words.append("дуга через точку %s" % point_text(point))
        else:
            words.append(point_text(point))
    return "контур по точкам " + ", ".join(words) + ", замкнуть"


def loop_code(kind_data):
    if kind_data[0] == "circle":
        return "circle(sk, %s, %s, %s)" % (fmt(kind_data[1][0]), fmt(kind_data[1][1]), fmt(kind_data[2]))
    points = kind_data[1]
    if any(len(point) == 3 for point in points):
        return "outline(sk, %s)" % points_code(points)
    return "polygon(sk, %s)" % points_code(points)


def build_case(design):
    code = design["code"]
    entities = code["entities"]
    props = code.get("properties", {})
    if props.get("body_count") != 1:
        raise Skip("bodies")
    bbox = props.get("bounding_box")
    if not bbox:
        raise Skip("no bbox")
    size = [(bbox["max_point"][a] - bbox["min_point"][a]) * 10 for a in "xyz"]
    if max(size) < 10 or max(size) > 500 or min(size) < 0.5:
        raise Skip("size")
    steps_words = []
    steps_code = []
    step = 0
    for item in code["timeline"]:
        entity = entities[item["entity"]]
        if entity["type"] == "Sketch":
            continue
        if entity["type"] != "ExtrudeFeature":
            raise Skip("feature %s" % entity["type"])
        operation = OPERATIONS.get(entity["operation"])
        if operation is None:
            raise Skip("operation %s" % entity["operation"])
        if entity["start_extent"]["type"] != "ProfilePlaneStartDefinition":
            raise Skip("start extent")
        extent = entity["extent_one"]
        if abs(extent["taper_angle"]["value"]) > 1e-9:
            raise Skip("taper")
        distance = extent["distance"]["value"] * 10
        if entity["extent_type"] == "OneSideFeatureExtentType":
            is_symmetric = False
        elif entity["extent_type"] == "SymmetricFeatureExtentType":
            is_symmetric = True
            if extent.get("is_full_length"):
                raise Skip("symmetric full length")
        else:
            raise Skip("extent %s" % entity["extent_type"])
        sketch_ids = set(profile["sketch"] for profile in entity["profiles"])
        if len(sketch_ids) != 1:
            raise Skip("profiles from several sketches")
        sketch = entities[sketch_ids.pop()]
        plane, normal_index, normal_sign = sketch_plane(sketch)
        loops = []
        offsets = []
        seen = {}
        shared = set()
        for profile_ref in entity["profiles"]:
            profile = sketch["profiles"][profile_ref["profile"]]
            for loop in profile["loops"]:
                data = loop_to_2d(loop, plane, sketch["transform"], normal_index, offsets)
                key = json.dumps(data, sort_keys=True)
                if key in seen:
                    # A loop that bounds two extruded regions (the ring and the disk inside it) is no
                    # boundary of the extruded shape at all: the regions merge, the loop is dropped.
                    if loops[seen[key]][0] != loop["is_outer"]:
                        shared.add(key)
                    continue
                seen[key] = len(loops)
                loops.append((loop["is_outer"], data))
        loops = [loops[index] for key, index in sorted(seen.items(), key=lambda item: item[1]) if key not in shared]
        if max(offsets) - min(offsets) > 1e-3:
            raise Skip("sketch points off the plane")
        offset = sum(offsets) / len(offsets)
        if not any(is_outer for is_outer, _ in loops):
            raise Skip("no outer loop")
        if len(loops) > 6:
            raise Skip("too many loops")
        step += 1
        axis_name = AXIS_NAMES[normal_index]
        u_name, v_name = (AXIS_NAMES[i].lower() for i in IN_PLANE[plane])
        where = "эскиз на плоскости %s" % plane
        if abs(offset) > 1e-6:
            where += " со смещением %s = %s мм" % (axis_name.lower(), fmt(offset))
        where += " (координаты %s, %s в мм)" % (u_name, v_name)
        outer_words = [loop_words(data) for is_outer, data in loops if is_outer]
        inner_words = [loop_words(data) for is_outer, data in loops if not is_outer]
        words = where + ": " + "; ".join(outer_words)
        if inner_words:
            words += "; внутри (отверстия): " + "; ".join(inner_words)
        signed = distance * normal_sign
        if is_symmetric:
            words += ". Выдавить симметрично, по %s мм в каждую сторону, %s." % (fmt(abs(distance)), OPERATION_WORDS[operation])
        else:
            direction = ("+" if signed > 0 else "-") + axis_name
            words += ". Выдавить на %s мм в сторону %s, %s." % (fmt(abs(distance)), direction, OPERATION_WORDS[operation])
        steps_words.append("Шаг %d: %s" % (step, words))
        lines = ['sk = new_sketch("%s", offset=%s)' % (plane, fmt(offset))]
        for _, data in loops:
            lines.append(loop_code(data))
        if is_symmetric:
            lines.append('extrude(sk, %s, operation="%s", symmetric=True)' % (fmt(abs(distance) * 2), operation))
        else:
            lines.append('extrude(sk, %s, operation="%s")' % (fmt(signed), operation))
        steps_code.append("\n".join(lines))
    if step == 0:
        raise Skip("no extrude")
    prompt = ("Сделай деталь как на картинке, по шагам. Габарит %s x %s x %s мм. " % tuple(fmt(s) for s in size)
              + " ".join(steps_words))
    return {
        "id": "G-" + design["id"],
        "images": ["gallery/" + design["id"] + ".png"],
        "prompt": prompt,
        "start": None,
        "reference": "\n".join(steps_code),
        "volume": "%.6f" % (props["volume"] * 1000),
        "size_mm": [round(s, 3) for s in size],
        "steps": step,
    }


def save_image(url, path):
    from PIL import Image
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGB")
        image.thumbnail((512, 512))
        image.save(path, format="PNG", optimize=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scanned")
    parser.add_argument("output")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--images-dir", default=os.path.join(APP_ROOT, "cases", "gallery"))
    parser.add_argument("--no-images", action="store_true")
    args = parser.parse_args()
    designs = json.load(open(args.scanned, encoding="utf-8"))
    random.Random(args.seed).shuffle(designs)
    cases = []
    skipped = {}
    for design in designs:
        try:
            case = build_case(design)
        except Skip as reason:
            key = str(reason).split(" ")[0]
            skipped[key] = skipped.get(key, 0) + 1
            continue
        if not args.no_images:
            os.makedirs(args.images_dir, exist_ok=True)
            try:
                save_image(design["image"], os.path.join(args.images_dir, os.path.basename(case["images"][0])))
            except Exception as error:
                print("no image for %s: %s" % (design["id"], error))
                continue
        cases.append(case)
        print("%-28s %d steps  %s mm" % (case["id"], case["steps"], " x ".join(fmt(s) for s in case["size_mm"])))
        if len(cases) >= args.limit:
            break
    document = {
        "note": "Honest set from the Fusion 360 Gallery reconstruction data (test split): a picture plus the "
                "build steps in words; references replay the Gallery history; volumes are the Gallery's own. "
                "Never tune on it.",
        "images_dir": "gallery",
        "cases": cases,
    }
    with open(args.output, "w", encoding="utf-8", newline="\n") as file:
        json.dump(document, file, ensure_ascii=False, indent=1)
        file.write("\n")
    print("%d cases; skipped: %s" % (len(cases), skipped))


if __name__ == "__main__":
    main()
