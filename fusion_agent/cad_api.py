"""Small mm-based CAD API that the runner prepends to the model's Fusion scripts.

Source of truth since 2026-10-31 (moved here from fusion-ladder, where it was measured).
"""

CAD_PRELUDE = r'''
import adsk.core, adsk.fusion, math
import sys as _sys_for_lines
import traceback as _traceback_for_lines

MM = 0.1  # the Fusion API works in cm; every helper below takes and prints mm


def _report_model_error(error, first_line):
    """Re-raise an error of the model's script with the line number counted in the model's own script."""
    line = None
    for frame in _traceback_for_lines.extract_tb(error.__traceback__):
        if frame.name == "run":
            line = frame.lineno - first_line + 1
    raise RuntimeError("MODEL_LINE %s | %s: %s" % (line, type(error).__name__, error)) from None

app = adsk.core.Application.get()
design = adsk.fusion.Design.cast(app.activeProduct)
root = design.rootComponent
_BODIES_BEFORE_SCRIPT = root.bRepBodies.count + sum(o.bRepBodies.count for o in root.allOccurrences)
_SCRIPT_CLEARED = False
_NEW_BASE_BODIES = 0
_SPLINE_SIZES = set()
_RIM_SIZES = {}
_NOMINAL_SIZES = {}  # a size the request names -> (what the part measures, why): gear tips, threads
_STEP_VOLUMES = []  # (feature name, change of the part's volume in mm3) for every extrude, revolve, cut

_AXES = {"X": 0, "Y": 1, "Z": 2}
_OPERATIONS = {
    "new": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
    "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
    "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
}


def _length(mm):
    return adsk.core.ValueInput.createByReal(mm * MM)


def _fusion_message(error):
    """The human part of a Fusion error, e.g. '3 : Fillet1 / Compute Failed // ASM_X -   text' -> 'text'."""
    text = str(error)
    if " -   " in text:
        text = text.split(" -   ", 1)[1]
    elif " : " in text:
        text = text.split(" : ", 1)[1]
    return " ".join(text.split())


def _add(add_call, what, hint=""):
    """Run a Fusion add() call; turn its error into a short message with a hint for the next attempt."""
    try:
        return add_call()
    except RuntimeError as error:
        message = "%s failed: %s" % (what, _fusion_message(error))
        if hint:
            message += " " + hint
        raise ValueError(message) from None


def _axis_entity(axis):
    axis = axis.upper()
    if axis == "X":
        return root.xConstructionAxis
    if axis == "Y":
        return root.yConstructionAxis
    if axis == "Z":
        return root.zConstructionAxis
    raise ValueError("axis must be 'X', 'Y' or 'Z', got %r" % axis)


def _base_plane(plane):
    plane = plane.upper()
    if plane == "XY":
        return root.xYConstructionPlane, "Z"
    if plane == "XZ":
        return root.xZConstructionPlane, "Y"
    if plane == "YZ":
        return root.yZConstructionPlane, "X"
    raise ValueError("plane must be 'XY', 'XZ' or 'YZ', got %r" % plane)


def _sketch_frame(sketch):
    """Origin (cm) and the model axis index of the sketch normal."""
    matrix = sketch.transform
    origin = [matrix.getCell(0, 3), matrix.getCell(1, 3), matrix.getCell(2, 3)]
    normal = [matrix.getCell(0, 2), matrix.getCell(1, 2), matrix.getCell(2, 2)]
    normal_axis = max(range(3), key=lambda i: abs(normal[i]))
    return origin, normal_axis, normal[normal_axis]


def _point(sketch, u, v):
    """Sketch point from plane coordinates in mm: XY -> (x, y), XZ -> (x, z), YZ -> (y, z)."""
    origin, normal_axis, _ = _sketch_frame(sketch)
    coordinates = list(origin)
    in_plane = [i for i in range(3) if i != normal_axis]
    coordinates[in_plane[0]] = u * MM
    coordinates[in_plane[1]] = v * MM
    return sketch.modelToSketchSpace(adsk.core.Point3D.create(*coordinates))


def new_sketch(plane="XY", offset=0):
    """Sketch on a base plane. offset (mm) moves the plane along its normal axis:
    XY at z=offset, XZ at y=offset, YZ at x=offset. plane may also be a construction plane from
    tilted_plane()."""
    if not isinstance(plane, str):
        return root.sketches.add(plane)
    base, normal_axis_name = _base_plane(plane)
    if offset:
        normal = base.geometry.normal.asArray()[_AXES[normal_axis_name]]
        signed = offset if normal > 0 else -offset
        plane_input = root.constructionPlanes.createInput()
        plane_input.setByOffset(base, _length(signed))
        base = root.constructionPlanes.add(plane_input)
    return root.sketches.add(base)


def _sketch_argument(sketch, name):
    if getattr(sketch, "sketchCurves", None) is None:
        raise ValueError('%s() takes the sketch first: sk = new_sketch("XY"); %s(sk, ...)' % (name, name))


def _world_axis(line):
    """"X", "Y" or "Z" when the sketch line runs along that world axis, else None."""
    start = line.worldGeometry.startPoint
    end = line.worldGeometry.endPoint
    deltas = {"X": end.x - start.x, "Y": end.y - start.y, "Z": end.z - start.z}
    length = math.sqrt(sum(value * value for value in deltas.values()))
    if length == 0:
        return None
    for name, value in deltas.items():
        if abs(abs(value) - length) < 1e-6 * length:
            return name
    return None


def _dimension(sketch, line, comment):
    """An aligned dimension on the line; the comment tells the model what the dimension is."""
    start = line.startSketchPoint.geometry
    end = line.endSketchPoint.geometry
    text = adsk.core.Point3D.create((start.x + end.x) / 2 + 0.3, (start.y + end.y) / 2 + 0.3, 0)
    dimension = sketch.sketchDimensions.addDistanceDimension(
        line.startSketchPoint, line.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, text)
    dimension.parameter.comment = comment
    return dimension


def _hold_rectangle(sketch, lines, fixed_corner):
    """Fix the corner nearest to fixed_corner and dimension one line along each axis, so that
    set_parameter() on a size grows the rectangle away from that corner."""
    nearest = None
    for line in lines:
        for point in (line.startSketchPoint, line.endSketchPoint):
            if nearest is None or point.geometry.distanceTo(fixed_corner) < nearest.geometry.distanceTo(fixed_corner):
                nearest = point
    nearest.isFixed = True
    sizes = {}
    for line in lines:
        axis = _world_axis(line)
        if axis is not None and axis not in sizes:
            sizes[axis] = line.length * 10
    longest = max(sizes.values()) if sizes else 0
    shortest = min(sizes.values()) if sizes else 0
    held = set()
    for line in lines:
        axis = _world_axis(line)
        if axis is None or axis in held:
            continue
        held.add(axis)
        if abs(longest - shortest) < 1e-6:
            name = "side"
        elif abs(sizes[axis] - longest) < 1e-6:
            name = "length"
        else:
            name = "width"
        _dimension(sketch, line, "%s, along %s" % (name, axis))


def rect(sketch, x1, y1, x2, y2):
    """Rectangle by two opposite corners (mm, plane coordinates). Two dimensions hold its sizes
    (describe() lists them as "along X" / "along Y"; set_parameter() changes them); its minimum corner
    is fixed, so a changed size grows away from that corner."""
    _sketch_argument(sketch, "rect")
    lines = sketch.sketchCurves.sketchLines.addTwoPointRectangle(_point(sketch, x1, y1), _point(sketch, x2, y2))
    _hold_rectangle(sketch, lines, _point(sketch, min(x1, x2), min(y1, y2)))


def rect_center(sketch, cx, cy, width, height):
    """Rectangle by its center and size (mm)."""
    rect(sketch, cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)


def circle(sketch, cx, cy, diameter):
    """Circle by center and DIAMETER (mm). A diameter dimension holds it (describe() lists it as
    "diameter"; set_parameter() or set_diameter() changes it); the center is fixed, move_circle() moves it."""
    _sketch_argument(sketch, "circle")
    sketch_circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(_point(sketch, cx, cy), diameter / 2 * MM)
    sketch_circle.centerSketchPoint.isFixed = True
    text = _point(sketch, cx + diameter * 0.6, cy + diameter * 0.6)
    dimension = sketch.sketchDimensions.addDiameterDimension(sketch_circle, text)
    dimension.parameter.comment = "diameter"
    return sketch_circle


def _diameter_dimension(sketch_circle):
    """The diameter dimension that holds the circle, or None (compared by geometry: proxies differ)."""
    center = sketch_circle.centerSketchPoint.geometry
    for dimension in sketch_circle.parentSketch.sketchDimensions:
        diameter = adsk.fusion.SketchDiameterDimension.cast(dimension)
        if diameter is None:
            continue
        held = adsk.fusion.SketchCircle.cast(diameter.entity)
        if held is None:
            continue
        if held.centerSketchPoint.geometry.isEqualTo(center) and abs(held.radius - sketch_circle.radius) < 1e-9:
            return diameter
    return None


def slot(sketch, cx, cy, length, width=None, angle=0):
    """Slot with rounded ends: center, overall length end to end, width (mm); angle in degrees from +u."""
    _sketch_argument(sketch, "slot")
    if width is None:
        raise ValueError("slot() needs the width: slot(sk, cx, cy, length, width)")
    direction = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
    normal = (-direction[1], direction[0])
    half_straight = (length - width) / 2
    radius = width / 2

    def at(along, across):
        return _point(sketch, cx + direction[0] * along + normal[0] * across,
                      cy + direction[1] * along + normal[1] * across)

    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs
    top = lines.addByTwoPoints(at(-half_straight, radius), at(half_straight, radius))
    bottom = lines.addByTwoPoints(at(half_straight, -radius), at(-half_straight, -radius))
    arcs.addByThreePoints(top.endSketchPoint, at(half_straight + radius, 0), bottom.startSketchPoint)
    arcs.addByThreePoints(bottom.endSketchPoint, at(-half_straight - radius, 0), top.startSketchPoint)


def polygon(sketch, points):
    """Closed polygon through a list of (u, v) points in mm."""
    _sketch_argument(sketch, "polygon")
    lines = sketch.sketchCurves.sketchLines
    first = lines.addByTwoPoints(_point(sketch, *points[0]), _point(sketch, *points[1]))
    previous = first
    for u, v in points[2:]:
        previous = lines.addByTwoPoints(previous.endSketchPoint, _point(sketch, u, v))
    lines.addByTwoPoints(previous.endSketchPoint, first.startSketchPoint)


def points_on_circle(cx, cy, circle_diameter, count, start_angle=0):
    """count points evenly spaced on a circle of the given diameter (mm); start_angle in degrees from +u."""
    result = []
    for k in range(count):
        angle = math.radians(start_angle + 360.0 * k / count)
        result.append((cx + circle_diameter / 2 * math.cos(angle), cy + circle_diameter / 2 * math.sin(angle)))
    return result


def _loop_key(loop):
    boxes = []
    for curve in loop.profileCurves:
        box = curve.boundingBox
        boxes.append(tuple(round(value, 5) for value in box.minPoint.asArray() + box.maxPoint.asArray()))
    return tuple(sorted(boxes))


def solid_profiles(sketch):
    """All regions of the sketch except the ones that are holes in another region."""
    inner_keys = set()
    outer = []
    for profile in sketch.profiles:
        for loop in profile.profileLoops:
            if loop.isOuter:
                outer.append((profile, _loop_key(loop)))
            else:
                inner_keys.add(_loop_key(loop))
    profiles = [profile for profile, key in outer if key not in inner_keys]
    if not profiles:
        raise ValueError("the sketch has no closed region")
    collection = adsk.core.ObjectCollection.create()
    for profile in profiles:
        collection.add(profile)
    return collection


def _direction_sign(sketch, distance):
    """Extent direction so that a positive distance goes toward +axis of the sketch normal."""
    _, _, normal_component = _sketch_frame(sketch)
    is_positive = (distance > 0) == (normal_component > 0)
    if is_positive:
        return adsk.fusion.ExtentDirections.PositiveExtentDirection
    return adsk.fusion.ExtentDirections.NegativeExtentDirection


def extrude(sketch, distance, operation="new", symmetric=False, taper=0):
    """Extrude the solid regions of the sketch by distance mm. Positive goes toward +Z for an XY
    sketch (+Y for XZ, +X for YZ), negative the other way. symmetric=True: distance is the total
    length, centered on the sketch plane. operation: 'new', 'join', 'cut' or 'intersect'.
    taper: draft angle in degrees (уклон, конусность): negative narrows the shape as it goes
    (a frustum from a circle, a pyramid stump from a square), positive widens it."""
    global _NEW_BASE_BODIES
    if operation == "new":
        _NEW_BASE_BODIES += 1
    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(solid_profiles(sketch), _OPERATIONS[operation])
    if symmetric:
        if taper:
            extrude_input.setSymmetricExtent(_length(abs(distance)), True,
                                             adsk.core.ValueInput.createByString("%s deg" % taper))
        else:
            extrude_input.setSymmetricExtent(_length(abs(distance)), True)
    else:
        extent = adsk.fusion.DistanceExtentDefinition.create(_length(abs(distance)))
        if taper:
            extrude_input.setOneSideExtent(extent, _direction_sign(sketch, distance),
                                           adsk.core.ValueInput.createByString("%s deg" % taper))
        else:
            extrude_input.setOneSideExtent(extent, _direction_sign(sketch, distance))
    where = _extents_text() if operation != "new" else ""
    span_before = _extents_mm() if _all_bodies() else None
    volume_before = sum(body.volume for body in _all_bodies())
    feature = _add(lambda: extrudes.add(extrude_input), "extrude (%s)" % operation,
                   "For join/cut/intersect the sketch shapes must overlap the body; check positions with describe()."
                   + (" Now " + where + "." if where else ""))
    _STEP_VOLUMES.append((feature.name, (sum(body.volume for body in _all_bodies()) - volume_before) * 1000))
    if operation == "join":
        added = (sum(body.volume for body in _all_bodies()) - volume_before) * 1000
        own = 0.0
        try:
            for profile in solid_profiles(sketch):
                own += profile.areaProperties().area * 100 * abs(distance)
        except Exception:
            own = 0.0
        if own and 1e-6 <= added < own * 0.995:
            print("extrude (join) of %s mm: the piece is %s mm3 but only %s mm3 is new material, %s lay inside the "
                  "part (count only %s in a volume formula)" % (
                      _fmt(distance), _fmt(own), _fmt(added), _fmt(own - added), _fmt(added)))
        if own and span_before is not None and added >= own * 0.995:
            _note_piece_beyond_edge(span_before)
        if added < 1e-6:
            _, _, normal_axis = _sketch_frame_axis(sketch)
            leftover = ""
            if _BODIES_BEFORE_SCRIPT:
                leftover = (" NOTE: this script ran on top of the earlier attempt (%d bodies existed before it): "
                            "start the script with clear()." % _BODIES_BEFORE_SCRIPT)
            raise ValueError("extrude (join) of %s mm added nothing: the new piece lies entirely inside the part "
                             "(%s). To add material at an end of the part extrude the other way (a negative "
                             "distance goes toward -%s) or start the sketch on the end face (offset=).%s" % (
                                 _fmt(distance), where, normal_axis, leftover))
    return feature


def _sketch_frame_axis(sketch):
    """Origin, normal axis index and the axis letter of a sketch's plane."""
    origin, normal_axis, _ = _sketch_frame(sketch)
    return origin, normal_axis, "XYZ"[normal_axis]


def cut(sketch, depth=None):
    """Cut the solid regions of the sketch out of the bodies. depth=None: through everything in
    both directions. A number: blind cut of that depth, sign as in extrude()."""
    if depth is not None:
        return extrude(sketch, depth, operation="cut")
    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(solid_profiles(sketch), _OPERATIONS["cut"])
    direction = _through_all_direction(sketch)
    if direction == adsk.fusion.ExtentDirections.SymmetricExtentDirection:
        # setAllExtent(Symmetric) cuts only one way in practice; two through-all sides cut both.
        extrude_input.setTwoSidesExtent(adsk.fusion.ThroughAllExtentDefinition.create(),
                                        adsk.fusion.ThroughAllExtentDefinition.create())
    else:
        extrude_input.setAllExtent(direction)
    where = _extents_text()
    return _add(lambda: extrudes.add(extrude_input), "cut",
                "There is no material under the sketch shapes. If this cut was already made by an earlier "
                "script, it is done: look at the current state. Otherwise check the positions"
                + (": " + where + "." if where else "."))


def _through_all_direction(sketch):
    """Through-all toward the bodies: Fusion refuses a through-all into a side with no body."""
    origin, normal_axis, normal_component = _sketch_frame(sketch)
    plane_coordinate = origin[normal_axis]
    low = None
    high = None
    for body in root.bRepBodies:
        box = body.boundingBox
        body_low = box.minPoint.asArray()[normal_axis]
        body_high = box.maxPoint.asArray()[normal_axis]
        low = body_low if low is None else min(low, body_low)
        high = body_high if high is None else max(high, body_high)
    if low is None or low + 1e-6 < plane_coordinate < high - 1e-6:
        return adsk.fusion.ExtentDirections.SymmetricExtentDirection
    toward_positive_axis = plane_coordinate <= low + 1e-6
    if toward_positive_axis == (normal_component > 0):
        return adsk.fusion.ExtentDirections.PositiveExtentDirection
    return adsk.fusion.ExtentDirections.NegativeExtentDirection


def revolve(sketch, axis="Z", angle=360, operation="new"):
    """Revolve the solid regions of the sketch around a model axis 'X', 'Y' or 'Z'."""
    revolves = root.features.revolveFeatures
    revolve_input = revolves.createInput(solid_profiles(sketch), _axis_entity(axis), _OPERATIONS[operation])
    revolve_input.setAngleExtent(False, adsk.core.ValueInput.createByString("%s deg" % angle))
    return _add(lambda: revolves.add(revolve_input), "revolve",
                "The profile must lie on one side of the axis, e.g. u >= 0 on XZ for axis Z.")


def _axis_plane(axis):
    axis = axis.upper()
    if axis == "Z":
        return "XY", (0, 1, 2)
    if axis == "Y":
        return "XZ", (0, 2, 1)
    if axis == "X":
        return "YZ", (1, 2, 0)
    raise ValueError("axis must be 'X', 'Y' or 'Z', got %r" % axis)


def _xyz_argument(value, name, function):
    if value is None or len(value) != 3:
        raise ValueError("%s() needs %s=(x, y, z) in mm" % (function, name))
    return tuple(float(v) for v in value)


def _no_center(center, function):
    if center is not None:
        raise ValueError("%s() has no center=; use base=(x, y, z): the center of the BOTTOM circle or face" % function)


def _note_piece_beyond_edge(span_before):
    """After a join that overlapped nothing: say when the part grew sideways, i.e. the piece sits beyond an
    edge of the part and touches it only by a face (a wall meant to stand ON the base at its edge)."""
    low_before, high_before = span_before
    low, high = _extents_mm()
    for index, axis in ((0, "x"), (1, "y")):
        if high[index] > high_before[index] + 0.01 or low[index] < low_before[index] - 0.01:
            print("extrude (join): the piece lies beyond the part's edge along %s (the part was %s %s..%s, now %s..%s) "
                  "and touches it only by a face. A wall or a boss ON the part at its edge stays within the part's "
                  "span, flush with the edge: its outer face AT the edge, its corner one thickness inside." % (
                      axis, axis, _fmt(low_before[index]), _fmt(high_before[index]), _fmt(low[index]), _fmt(high[index])))
            return


def _extents_text():
    """Where the part is: "the part spans x -60..60, y -60..60, z 0..28 (its center is (0, 0))", or ""."""
    if not _all_bodies():
        return ""
    low, high = _extents_mm()
    return "the part spans x %s..%s, y %s..%s, z %s..%s (its center is (%s, %s))" % (
        _fmt(low[0]), _fmt(high[0]), _fmt(low[1]), _fmt(high[1]), _fmt(low[2]), _fmt(high[2]),
        _fmt((low[0] + high[0]) / 2), _fmt((low[1] + high[1]) / 2))


def _check_join_overlap(what, min_x, max_x, min_y, max_y):
    """A joined piece whose footprint misses the part entirely is a wrong position, not a part."""
    if not _all_bodies():
        return
    low, high = _extents_mm()
    if max_x < low[0] - 1e-6 or min_x > high[0] + 1e-6 or max_y < low[1] - 1e-6 or min_y > high[1] + 1e-6:
        raise ValueError("%s with operation=\"join\" lies entirely outside the part: it covers x %s..%s, "
                         "y %s..%s, while %s. A box built from corner=(0, 0, 0) has its center at half its "
                         "sizes; a cylinder's base=(x, y, z) IS its center. Put the new piece on the part." % (
                             what, _fmt(min_x), _fmt(max_x), _fmt(min_y), _fmt(max_y), _extents_text()))


def box(size_x, size_y, size_z, corner=None, base=None, operation="new", center=None, corner_radius=None, taper=0):
    """Box with sizes along X, Y, Z (mm). Give corner=(x, y, z), its minimum corner, or base=(x, y, z),
    the center of its BOTTOM face. corner_radius rounds its four vertical corner edges (a plate with
    rounded corners)."""
    _no_center(center, "box")
    if corner is None and base is None:
        raise ValueError("box() needs corner=(x, y, z) or base=(x, y, z)")
    if corner is not None:
        x, y, z = _xyz_argument(corner, "corner", "box")
    else:
        cx, cy, z = _xyz_argument(base, "base", "box")
        x = cx - size_x / 2
        y = cy - size_y / 2
    if operation == "join":
        _check_join_overlap("box(%s, %s, %s)" % (_fmt(size_x), _fmt(size_y), _fmt(size_z)), x, x + size_x, y, y + size_y)
    sketch = new_sketch("XY", offset=z)
    rect(sketch, x, y, x + size_x, y + size_y)
    feature = extrude(sketch, size_z, operation=operation, taper=taper)
    if corner_radius:
        corners = []
        for corner_x in (x, x + size_x):
            for corner_y in (y, y + size_y):
                corners.extend(find_edges(parallel_to="Z", x=corner_x, y=corner_y))
        fillet(corners, corner_radius)
    return feature


def cylinder(diameter, length, base=None, axis="Z", operation="new", center=None, taper=0):
    """Cylinder whose bottom circle is centered at base=(x, y, z); it grows by length along +axis."""
    _no_center(center, "cylinder")
    base = _xyz_argument(base, "base", "cylinder")
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    if operation == "join" and axis.upper() == "Z":
        radius = diameter / 2.0
        _check_join_overlap("cylinder(%s, %s) at base (%s, %s, %s)" % (
            _fmt(diameter), _fmt(length), _fmt(base[0]), _fmt(base[1]), _fmt(base[2])),
            base[0] - radius, base[0] + radius, base[1] - radius, base[1] + radius)
    sketch = new_sketch(plane, offset=base[n_index])
    circle(sketch, base[u_index], base[v_index], diameter)
    if taper:
        top = diameter + 2 * length * math.tan(math.radians(taper))
        print("cylinder with taper %s deg: diameter %s at the base, %s at the top; volume = pi*h/3*(R*R + R*r + r*r) = %s mm3" % (
            _fmt(taper), _fmt(diameter), _fmt(top), _fmt(math.pi * length / 3 * (diameter ** 2 + diameter * top + top ** 2) / 4)))
    return extrude(sketch, length, operation=operation, taper=taper)


def tube(outer_diameter, inner_diameter, length, base=None, axis="Z", operation="new", center=None):
    """Tube (bushing, ring) whose bottom is centered at base=(x, y, z); it grows by length along +axis."""
    _no_center(center, "tube")
    if inner_diameter >= outer_diameter:
        raise ValueError("tube() needs inner_diameter smaller than outer_diameter")
    base = _xyz_argument(base, "base", "tube")
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    sketch = new_sketch(plane, offset=base[n_index])
    circle(sketch, base[u_index], base[v_index], outer_diameter)
    circle(sketch, base[u_index], base[v_index], inner_diameter)
    return extrude(sketch, length, operation=operation)


def groove(diameter, width, depth, center=None, axis="Z"):
    """Канавка по кругу: a ring of this width and depth cut around a cylinder of this diameter
    (the part's diameter there), centered at the point center=(x, y, z) on the cylinder's axis.
    Material removed = pi * ((D/2)**2 - (D/2 - depth)**2) * width."""
    center = _xyz_argument(center, "center", "groove")
    if depth <= 0 or depth * 2 >= diameter:
        raise ValueError("groove() needs a depth between 0 and half the diameter")
    if width <= 0:
        raise ValueError("groove() needs a width above 0")
    _, (u_index, v_index, n_index) = _axis_plane(axis)
    base = list(center)
    base[n_index] = center[n_index] - width / 2
    return tube(diameter + 2, diameter - 2 * depth, width, base=tuple(base), axis=axis, operation="cut")


def keyway(bore_diameter, width, depth, length, center=(0, 0, 0), angle=90):
    """Шпоночный паз in a bore along Z: a rectangular groove of this width, going depth beyond the bore
    wall, over length from the bottom of the bore at center=(x, y, z); angle (degrees from +X) says on
    which side of the bore it lies. Prints the material removed (the box minus the circle segment)."""
    center = _xyz_argument(center, "center", "keyway")
    radius = bore_diameter / 2.0
    if width <= 0 or width >= bore_diameter:
        raise ValueError("keyway() needs a width between 0 and the bore diameter")
    if depth <= 0:
        raise ValueError("keyway() needs a depth above 0")
    sketch = new_sketch("XY", offset=center[2])
    # The box in the bore's own frame: across the width, from 2 mm inside the hole (air) to depth beyond the wall.
    inner = radius - 2
    outer = radius + depth
    corners = [(-width / 2.0, inner), (width / 2.0, inner), (width / 2.0, outer), (-width / 2.0, outer)]
    cos_a = math.cos(math.radians(angle - 90))
    sin_a = math.sin(math.radians(angle - 90))
    points = []
    for u, v in corners:
        points.append((center[0] + u * cos_a - v * sin_a, center[1] + u * sin_a + v * cos_a))
    polygon(sketch, points)
    feature = extrude(sketch, length, operation="cut")
    half = width / 2.0
    segment = half * math.sqrt(radius * radius - half * half) + radius * radius * math.asin(half / radius)
    removed = (width * outer - segment) * length
    print("keyway: %s wide, %s deep beyond the bore wall, %s long; material removed %s mm3 (use it in "
          "check(volume=...)); the bore stays a round face of %s" % (
              _fmt(width), _fmt(depth), _fmt(length), _fmt(removed), _fmt(bore_diameter)))
    return feature


def shaft(sections, base=(0, 0, 0), axis="Z", bore=None, operation="new"):
    """Turned part (shaft, pin, stepped shaft, bushing with a collar) from (diameter, length) sections
    listed from the base along +axis. bore: diameter of a through hole along the axis."""
    if not sections:
        raise ValueError("shaft() needs sections=[(diameter, length), ...]")
    base = _xyz_argument(base, "base", "shaft")
    axis = axis.upper()
    if axis == "Z":
        plane, along_index, radial_index = "XZ", 2, 0
    elif axis == "X":
        plane, along_index, radial_index = "XY", 0, 1
    elif axis == "Y":
        plane, along_index, radial_index = "XY", 1, 0
    else:
        raise ValueError("axis must be 'X', 'Y' or 'Z', got %r" % axis)
    offset_index = 3 - along_index - radial_index
    sketch = new_sketch(plane, offset=base[offset_index])
    in_plane = [i for i in range(3) if i != offset_index]

    def at(along, radius):
        point = list(base)
        point[along_index] += along
        point[radial_index] += radius
        return (point[in_plane[0]], point[in_plane[1]])

    inner = bore / 2 if bore else 0
    outline = [at(0, inner)]
    position = 0
    for diameter, length in sections:
        if diameter / 2 <= inner:
            raise ValueError("every section diameter must be bigger than the bore")
        outline.append(at(position, diameter / 2))
        position += length
        outline.append(at(position, diameter / 2))
    outline.append(at(position, inner))
    cleaned = []
    for point in outline:
        if not cleaned or abs(point[0] - cleaned[-1][0]) > 1e-9 or abs(point[1] - cleaned[-1][1]) > 1e-9:
            cleaned.append(point)
    polygon(sketch, cleaned)
    start = at(0, 0)
    end = at(position, 0)
    axis_line = sketch.sketchCurves.sketchLines.addByTwoPoints(_point(sketch, *start), _point(sketch, *end))
    axis_line.isConstruction = True
    revolves = root.features.revolveFeatures
    revolve_input = revolves.createInput(solid_profiles(sketch), axis_line, _OPERATIONS[operation])
    revolve_input.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
    return _add(lambda: revolves.add(revolve_input), "shaft")


def arc(sketch, start, through, end):
    """Arc through three (u, v) points in mm: from start, through the middle point, to end."""
    _sketch_argument(sketch, "arc")
    return sketch.sketchCurves.sketchArcs.addByThreePoints(
        _point(sketch, *start), _point(sketch, *through), _point(sketch, *end))


def outline(sketch, points):
    """Closed outline through (u, v) points in mm, like polygon(); a point written as (u, v, "arc") is
    not a corner: the outline passes through it by an arc from the previous point to the next one."""
    _sketch_argument(sketch, "outline")
    corners = []
    arcs_through = {}
    for point in points:
        if len(point) == 3 and point[2] == "arc":
            if not corners:
                raise ValueError('outline(): an "arc" point needs a corner before it')
            arcs_through[len(corners) - 1] = (point[0], point[1])
        else:
            corners.append((point[0], point[1]))
    if len(corners) < 2:
        raise ValueError("outline() needs at least two corner points")
    lines = sketch.sketchCurves.sketchLines
    for index in range(len(corners)):
        start = corners[index]
        end = corners[(index + 1) % len(corners)]
        through = arcs_through.get(index)
        if abs(start[0] - end[0]) < 1e-9 and abs(start[1] - end[1]) < 1e-9:
            if through is not None:
                raise ValueError('outline(): the arc through (%s, %s) starts and ends at the same corner (%s, %s): '
                                 'an "arc" point lies between two DIFFERENT corners, and a corner is written once; '
                                 'remove the repeated corner' % (_fmt(through[0]), _fmt(through[1]), _fmt(start[0]), _fmt(start[1])))
            continue
        if through is None:
            lines.addByTwoPoints(_point(sketch, *start), _point(sketch, *end))
            continue
        for corner in (start, end):
            if abs(through[0] - corner[0]) < 1e-9 and abs(through[1] - corner[1]) < 1e-9:
                raise ValueError('outline(): the "arc" point (%s, %s) coincides with a corner; it is the point the '
                                 'arc passes THROUGH between the corner before it and the corner after it' % (
                                     _fmt(through[0]), _fmt(through[1])))
        cross = (end[0] - start[0]) * (through[1] - start[1]) - (end[1] - start[1]) * (through[0] - start[0])
        if abs(cross) < 1e-9:
            raise ValueError('outline(): the "arc" point (%s, %s) lies on the straight line from (%s, %s) to (%s, %s); '
                             'an arc needs a point off that line' % (_fmt(through[0]), _fmt(through[1]),
                                                                     _fmt(start[0]), _fmt(start[1]), _fmt(end[0]), _fmt(end[1])))
        arc(sketch, start, through, end)


def _check_profile_arcs(outline_points):
    """An "arc" point between two corners must be the arc's widest place: an arc that bulges far beyond
    its three points means the model kept a corner the "arc" point was meant to replace."""
    for index in range(1, len(outline_points) - 1):
        point = outline_points[index]
        if len(point) != 3:
            continue
        (u1, v1), (u2, v2), (u3, v3) = outline_points[index - 1][:2], point[:2], outline_points[index + 1][:2]
        d = 2 * (u1 * (v2 - v3) + u2 * (v3 - v1) + u3 * (v1 - v2))
        if abs(d) < 1e-9:
            raise ValueError('the "arc" point (%s, %s) lies on the straight line between its corners: '
                             'an arc needs a point off that line' % (_fmt(u2 * 2), _fmt(v2)))
        cu = ((u1 * u1 + v1 * v1) * (v2 - v3) + (u2 * u2 + v2 * v2) * (v3 - v1) + (u3 * u3 + v3 * v3) * (v1 - v2)) / d
        cv = ((u1 * u1 + v1 * v1) * (u3 - u2) + (u2 * u2 + v2 * v2) * (u1 - u3) + (u3 * u3 + v3 * v3) * (u2 - u1)) / d
        radius = math.hypot(u1 - cu, v1 - cv)
        a1, a2, a3 = (math.atan2(v - cv, u - cu) for u, v in ((u1, v1), (u2, v2), (u3, v3)))
        # Sweep from the start to the end through the middle point.
        sweep = (a3 - a1) % (2 * math.pi)
        middle = (a2 - a1) % (2 * math.pi)
        if middle > sweep:
            sweep = sweep - 2 * math.pi
        widest = max(cu + radius * math.cos(a1 + sweep * k / 40.0) for k in range(41))
        narrowest = min(cu + radius * math.cos(a1 + sweep * k / 40.0) for k in range(41))
        if widest > max(u1, u2, u3) + 0.5 or narrowest < -1e-6:
            raise ValueError('the arc from (%s, %s) through (%s, %s) to (%s, %s) bulges out to diameter %s: an '
                             '"arc" point REPLACES the corner at its height, e.g. a barrel is '
                             '[(60, 0), (80, 50, "arc"), (60, 100)], not [(60, 0), (60, 50), (80, 50, "arc"), ...]' % (
                                 _fmt(u1 * 2), _fmt(v1), _fmt(u2 * 2), _fmt(v2), _fmt(u3 * 2), _fmt(v3), _fmt(widest * 2)))


def revolved_profile(points, base=(0, 0, 0), axis="Z", operation="new"):
    """ТЕЛО ВРАЩЕНИЯ (bottle, vase, knob, handle, dome, bowl) from its outline, listed from the bottom up
    as (diameter, height) points measured from base along the axis. A point (diameter, height, r) is a
    corner rounded with radius r (rounded shoulders, a rounded bottom edge); a point (diameter, height,
    "arc") is not a corner but a point the outline passes through by an arc from the previous point to the
    next: a bulge (barrel, dome) when its diameter is bigger than its neighbours, a waist when smaller.
    The first and the last point may lie on the axis (diameter 0: a tip or a dome top). Prints the overall
    size and the volume (use it in check(volume=...))."""
    base = _xyz_argument(base, "base", "revolved_profile")
    axis = axis.upper()
    if axis == "Z":
        plane, along_index, radial_index = "XZ", 2, 0
    elif axis == "X":
        plane, along_index, radial_index = "XY", 0, 1
    elif axis == "Y":
        plane, along_index, radial_index = "XY", 1, 0
    else:
        raise ValueError("axis must be 'X', 'Y' or 'Z', got %r" % axis)
    if len(points) < 2:
        raise ValueError("revolved_profile() needs at least two (diameter, height) points")
    corners = []
    rounds = []
    outline_points = []
    previous_height = None
    for point in points:
        if len(point) not in (2, 3):
            raise ValueError("every point is (diameter, height), (diameter, height, round_radius) or "
                             "(diameter, height, \"arc\"); got %r" % (point,))
        diameter, height = float(point[0]), float(point[1])
        if diameter < 0:
            raise ValueError("a diameter cannot be negative: %r" % (point,))
        if previous_height is not None and height < previous_height - 1e-9:
            raise ValueError("the points go from the bottom up: heights must not decrease (%r)" % (point,))
        previous_height = height
        if len(point) == 3 and point[2] == "arc":
            if outline_points and len(outline_points[-1]) == 3:
                raise ValueError('two "arc" points in a row: an "arc" point lies between two corners, '
                                 'e.g. [(60, 0), (80, 50, "arc"), (60, 100)] for a barrel')
            outline_points.append((diameter / 2, height, "arc"))
            continue
        if corners and abs(corners[-1][0] - diameter) < 1e-9 and abs(corners[-1][1] - height) < 1e-9:
            if outline_points and len(outline_points[-1]) == 3:
                raise ValueError('the "arc" point (%s, %s) must differ from the corners around it: an "arc" '
                                 'point REPLACES the corner there, e.g. [(60, 0), (80, 50, "arc"), (60, 100)]' % (
                                     _fmt(outline_points[-1][0] * 2), _fmt(outline_points[-1][1])))
            continue  # the same corner twice is one corner
        outline_points.append((diameter / 2, height))
        corners.append((diameter, height))
        if len(point) == 3 and float(point[2]) > 0:
            rounds.append((diameter, height, float(point[2])))
    if len(corners) < 2:
        raise ValueError("revolved_profile() needs at least two different (diameter, height) corners")
    for index, point in enumerate(outline_points):
        if len(point) == 3 and (index == 0 or index == len(outline_points) - 1):
            raise ValueError('an "arc" point lies between two corners; the first and the last point are corners')
    _check_profile_arcs(outline_points)
    first_corner, last_corner = corners[0], corners[-1]
    if outline_points[0][0] > 0:
        outline_points.insert(0, (0, first_corner[1]))
    if outline_points[-1][0] > 0:
        outline_points.append((0, last_corner[1]))
    offset_index = 3 - along_index - radial_index
    sketch = new_sketch(plane, offset=base[offset_index])
    in_plane = [i for i in range(3) if i != offset_index]

    def at(along, radius):
        point = list(base)
        point[along_index] += along
        point[radial_index] += radius
        return (point[in_plane[0]], point[in_plane[1]])

    placed = []
    for point in outline_points:
        u, v = at(point[1], point[0])
        placed.append((u, v, "arc") if len(point) == 3 else (u, v))
    outline(sketch, placed)
    start = at(first_corner[1], 0)
    end = at(last_corner[1], 0)
    axis_line = sketch.sketchCurves.sketchLines.addByTwoPoints(_point(sketch, *start), _point(sketch, *end))
    axis_line.isConstruction = True
    revolves = root.features.revolveFeatures
    revolve_input = revolves.createInput(solid_profiles(sketch), axis_line, _OPERATIONS[operation])
    revolve_input.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
    feature = _add(lambda: revolves.add(revolve_input), "revolved_profile",
                   "The outline must not cross itself; an \"arc\" point lies between two corners.")
    body = feature.bodies.item(0)
    axis_name = "xyz"[along_index]
    for diameter, height, radius in rounds:
        if diameter <= 0:
            raise ValueError("a point on the axis (diameter 0) has no edge to round; round the point next to it")
        filters = {axis_name: base[along_index] + height}
        edges = find_edges(kind="circle", diameter=diameter, body=body, **filters)
        if not edges:
            raise ValueError("no corner edge at diameter %s, height %s to round: this point lies on a straight "
                             "part of the outline" % (_fmt(diameter), _fmt(height)))
        fillet(edges, radius)
    low, high = _extents_mm()
    print("revolved_profile: overall size %s x %s x %s mm, volume %s mm3 (use it in check(volume=...))" % (
        _fmt(high[0] - low[0]), _fmt(high[1] - low[1]), _fmt(high[2] - low[2]), _fmt(body.volume * 1000)))
    return feature


def sphere(diameter, center=(0, 0, 0), operation="new"):
    """Шар of this DIAMETER (radius = diameter / 2) with its center at center=(x, y, z)."""
    center = _xyz_argument(center, "center", "sphere")
    radius = diameter / 2.0
    base = (center[0], center[1], center[2] - radius)
    print("sphere: diameter %s (radius %s), center (%s, %s, %s), from z=%s to z=%s" % (
        _fmt(diameter), _fmt(radius), _fmt(center[0]), _fmt(center[1]), _fmt(center[2]),
        _fmt(center[2] - radius), _fmt(center[2] + radius)))
    return revolved_profile([(0, 0), (diameter, radius, "arc"), (0, diameter)], base=base, operation=operation)


def dome(diameter, base=(0, 0, 0), operation="new", up=True):
    """Купол, полусфера: half a sphere of this DIAMETER standing on the horizontal plane z = base z with
    its rim centered at base=(x, y, z); it bulges up (+Z), or down with up=False (a rounded bottom).
    Height = diameter / 2. Volume = 2/3 * pi * (diameter/2)**3. operation="join" puts it on a part."""
    base = _xyz_argument(base, "base", "dome")
    radius = diameter / 2.0
    middle = radius * math.sqrt(0.5)
    if up:
        points = [(diameter, 0), (2 * middle, middle, "arc"), (0, radius)]
        start = base
    else:
        points = [(0, 0), (2 * middle, radius - middle, "arc"), (diameter, radius)]
        start = (base[0], base[1], base[2] - radius)
    print("dome: diameter %s, height %s, from z=%s to z=%s, volume %s mm3" % (
        _fmt(diameter), _fmt(radius), _fmt(start[2]), _fmt(start[2] + radius), _fmt(2.0 / 3 * math.pi * radius ** 3)))
    return revolved_profile(points, base=start, operation=operation)


def _involute_half_angle(radius, base_radius, pitch_radius, teeth, pressure_angle):
    """Half the tooth's angular thickness at this radius, for an involute flank (radians)."""
    def involute(alpha):
        return math.tan(alpha) - alpha
    half_at_pitch = math.pi / (2 * teeth)
    alpha_here = math.acos(min(1.0, base_radius / radius))
    return half_at_pitch + involute(math.radians(pressure_angle)) - involute(alpha_here)


def gear_points(cx, cy, module, teeth, pressure_angle=20, flank_points=8):
    """Outline (u, v) of a spur gear with involute teeth: pitch diameter module * teeth, outer diameter
    module * (teeth + 2), root diameter module * (teeth - 2.5). For polygon(); spur_gear() uses it."""
    if teeth < 6:
        raise ValueError("gear_points() needs at least 6 teeth")
    if module <= 0:
        raise ValueError("the module must be above 0 (pitch diameter = module * teeth)")
    pitch_radius = module * teeth / 2.0
    outer_radius = pitch_radius + module
    root_radius = pitch_radius - 1.25 * module
    base_radius = pitch_radius * math.cos(math.radians(pressure_angle))
    flank_start = max(base_radius, root_radius)
    points = []
    for tooth in range(teeth):
        center = 2 * math.pi * tooth / teeth
        root_half = _involute_half_angle(flank_start, base_radius, pitch_radius, teeth, pressure_angle)
        # the root between this tooth and the previous one, then the right flank up, the left flank down
        if root_radius < flank_start - 1e-9:
            points.append((root_radius, center - root_half))
        for step in range(flank_points + 1):
            radius = flank_start + (outer_radius - flank_start) * step / float(flank_points)
            points.append((radius, center - _involute_half_angle(radius, base_radius, pitch_radius, teeth, pressure_angle)))
        points.append((outer_radius, center))  # the tip itself, so the outer diameter is exact
        for step in range(flank_points, -1, -1):
            radius = flank_start + (outer_radius - flank_start) * step / float(flank_points)
            points.append((radius, center + _involute_half_angle(radius, base_radius, pitch_radius, teeth, pressure_angle)))
        if root_radius < flank_start - 1e-9:
            points.append((root_radius, center + root_half))
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for r, a in points]


def spur_gear(module, teeth, width, base=(0, 0, 0), bore=None, axis="Z", pressure_angle=20, operation="new"):
    """ШЕСТЕРНЯ, зубчатое колесо (прямозубое): involute teeth of this module and count, width along the
    axis from base=(x, y, z) (the center of the bottom face). bore: diameter of the through hole.
    Pitch diameter = module * teeth, outer diameter = module * (teeth + 2) (the size across the tips),
    root diameter = module * (teeth - 2.5). Prints these and the volume (use it in check(volume=...));
    the outer size for check(size=...) is the outer diameter."""
    base = _xyz_argument(base, "base", "spur_gear")
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    sketch = new_sketch(plane, offset=base[n_index])
    polygon(sketch, gear_points(base[u_index], base[v_index], module, teeth, pressure_angle))
    if bore:
        if bore >= module * (teeth - 2.5):
            raise ValueError("the bore %s must be smaller than the root diameter %s" % (_fmt(bore), _fmt(module * (teeth - 2.5))))
        circle(sketch, base[u_index], base[v_index], bore)
    feature = extrude(sketch, width, operation=operation)
    body = feature.bodies.item(0)
    print("spur_gear: module %s, %d teeth, pitch diameter %s, outer diameter %s (size across the tips), root "
          "diameter %s, width %s%s; volume %s mm3 (use it in check(volume=...))" % (
              _fmt(module), teeth, _fmt(module * teeth), _fmt(module * (teeth + 2)), _fmt(module * (teeth - 2.5)),
              _fmt(width), (", bore %s" % _fmt(bore)) if bore else "", _fmt(body.volume * 1000)))
    _SPLINE_SIZES.update((module * (teeth + 2), module * teeth, module * (teeth - 2.5)))
    low, high = _extents_mm()
    for index in (u_index, v_index):
        _NOMINAL_SIZES.setdefault(round(module * (teeth + 2), 6), []).append(
            (high[index] - low[index], "the outer diameter of the gear (its teeth span %s)" % _fmt(high[index] - low[index])))
    return feature


def hexagon_points(cx, cy, across_flats, angle=0):
    """Six corners of a regular hexagon by its size ACROSS FLATS (размер под ключ); angle turns it."""
    radius = across_flats / math.sqrt(3)  # across corners / 2
    return [(cx + radius * math.cos(math.radians(angle + 60 * k)), cy + radius * math.sin(math.radians(angle + 60 * k)))
            for k in range(6)]


def hex_prism(across_flats, height, base=(0, 0, 0), axis="Z", bore=None, operation="new"):
    """ШЕСТИГРАННИК (a nut body, a bolt head, a hex standoff): a regular hexagonal prism of this size
    across flats (размер под ключ) and height along the axis from base=(x, y, z), the center of its bottom.
    bore: a through hole of this diameter. Across corners = across_flats * 2 / sqrt(3).
    Volume = across_flats**2 * sqrt(3) / 2 * height (minus the bore)."""
    base = _xyz_argument(base, "base", "hex_prism")
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    sketch = new_sketch(plane, offset=base[n_index])
    polygon(sketch, hexagon_points(base[u_index], base[v_index], across_flats))
    if bore:
        circle(sketch, base[u_index], base[v_index], bore)
    _SPLINE_SIZES.update((across_flats, across_flats * 2 / math.sqrt(3)))
    return extrude(sketch, height, operation=operation)


def hex_socket(across_flats, depth, center=(0, 0, 0), axis="Z"):
    """ВНУТРЕННИЙ ШЕСТИГРАННИК (под ключ, a socket in a screw head): a hexagonal pocket of this size
    across flats cut depth mm into the part from the surface point center=(x, y, z), along -axis."""
    center = _xyz_argument(center, "center", "hex_socket")
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    sketch = new_sketch(plane, offset=center[n_index])
    polygon(sketch, hexagon_points(center[u_index], center[v_index], across_flats))
    print("hex_socket: %s across flats, %s deep; material removed %s mm3" % (
        _fmt(across_flats), _fmt(depth), _fmt(across_flats ** 2 * math.sqrt(3) / 2 * depth)))
    return _cut_into_body(sketch, depth)


def _cylindrical_faces(diameter, axis_index=None):
    """Cylindrical faces of this diameter (optionally with their axis along this world axis)."""
    result = []
    for body in _all_bodies():
        for face in body.faces:
            geometry = face.geometry
            if geometry.surfaceType != adsk.core.SurfaceTypes.CylinderSurfaceType:
                continue
            if abs(geometry.radius * 20 - diameter) > 0.01:
                continue
            if axis_index is not None:
                direction = geometry.axis.asArray()
                if abs(abs(direction[axis_index]) - 1) > 1e-6:
                    continue
            result.append(face)
    return result


def _thread_designation(diameter, pitch, internal):
    """ISO metric thread type, designation and class for this nominal diameter and pitch (None = coarse)."""
    threads = root.features.threadFeatures
    query = threads.threadDataQuery
    thread_type = None
    for name in query.allThreadTypes:
        if "ISO Metric" in name and "profile" in name:
            thread_type = name
            break
    if thread_type is None:
        raise ValueError("Fusion has no ISO Metric thread table here; types: %s" % list(query.allThreadTypes)[:6])
    size = None
    for candidate in query.allSizes(thread_type):
        try:
            if abs(float(candidate) - diameter) < 1e-6:
                size = candidate
                break
        except ValueError:
            continue
    if size is None:
        raise ValueError("no ISO metric thread of diameter %s; sizes: %s" % (_fmt(diameter), list(query.allSizes(thread_type))))
    designations = list(query.allDesignations(thread_type, size))
    if not designations:
        raise ValueError("no thread designation for M%s" % size)
    designation = designations[0]  # the coarse pitch comes first
    if pitch is not None:
        wanted = [d for d in designations if d.lower().endswith("x" + _fmt(pitch)) or d.lower().endswith("x%.2f" % pitch)]
        if not wanted:
            raise ValueError("M%s has no pitch %s; designations: %s" % (size, _fmt(pitch), designations))
        designation = wanted[0]
    classes = list(query.allClasses(internal, thread_type, designation))
    if not classes:
        raise ValueError("no thread class for %s" % designation)
    thread_class = classes[0]
    for candidate in classes:
        if candidate in ("6H", "6g"):
            thread_class = candidate
    return thread_type, designation, thread_class


def thread(diameter, length=None, base=None, axis="Z", internal=False, pitch=None, modeled=True, all_faces=False):
    """РЕЗЬБА, metric ISO (M6, M8, M10 ...): on the cylindrical face of this nominal diameter along the axis.
    internal=False: the outside of a shaft or pin of this diameter; internal=True: a hole of this
    diameter (drill the hole with the nominal size, e.g. 8 for M8). length=None: the whole face; a length
    threads that much from the face end nearest to base=(x, y, z). pitch=None: the coarse pitch
    (M8x1.25, M10x1.5); modeled=True cuts the real helix (slow to display), False marks it cosmetically.
    check(operations=["thread"]) sees it in the timeline. all_faces=True threads every face of this
    diameter (all the holes of a plate), base= picks the one nearest that point."""
    axis_index = _AXES[axis.upper()]
    faces = _cylindrical_faces(diameter, axis_index)
    if not faces:
        raise ValueError("no cylindrical face of diameter %s along %s to thread; faces of the part: %s. Build the "
                         "shaft or drill the hole with the nominal diameter first." % (
                             _fmt(diameter), axis.upper(), sorted(set(_round_face_diameters()))))
    if len(faces) > 1 and all_faces:
        if length is not None:
            raise ValueError("thread(all_faces=True) threads whole faces: leave length out, or thread one face "
                             "at a time with base=(x, y, z)")
    elif len(faces) > 1:
        if base is None:
            raise ValueError("%d cylindrical faces of diameter %s: give base=(x, y, z) near the one to thread, "
                             "or all_faces=True to thread every one of them" % (len(faces), _fmt(diameter)))
        base = _xyz_argument(base, "base", "thread")
        faces.sort(key=lambda face: _distance_to_box(base, face.boundingBox))
        faces = faces[:1]
    # One thread feature for all the faces: a face found before the feature is stale after it.
    face = faces[0]
    threads = root.features.threadFeatures
    thread_type, designation, thread_class = _thread_designation(diameter, pitch, internal)
    info = threads.createThreadInfo(internal, thread_type, designation, thread_class)
    collection = adsk.core.ObjectCollection.create()
    for each_face in faces:
        collection.add(each_face)
    thread_input = threads.createInput(collection, info)
    thread_input.isModeled = modeled
    if length is None:
        thread_input.isFullLength = True
    else:
        thread_input.isFullLength = False
        thread_input.threadLength = _length(length)
        if base is not None:
            low, high = _range_mm(face.boundingBox, axis_index)
            if abs(base[axis_index] - high) < abs(base[axis_index] - low):
                thread_input.isRightHanded = True
                thread_input.threadOffset = _length(0)
    feature = _add(lambda: threads.add(thread_input), "thread",
                   "Fusion could not cut a %s thread on this face: a thread needs a plain cylindrical face of the "
                   "nominal diameter, long enough for the length; try modeled=False." % designation)
    if modeled and not internal:
        low, high = _extents_mm()
        for index in range(3):
            if index != axis_index:
                _NOMINAL_SIZES.setdefault(round(diameter, 6), []).append(
                    (high[index] - low[index], "the nominal thread diameter (the cut thread measures %s)" % _fmt(high[index] - low[index])))
    _SPLINE_SIZES.add(diameter)
    if len(faces) > 1:
        where = "in %d holes" if internal else "on %d faces"
        where = where % len(faces)
    else:
        box = face.boundingBox
        center = [(box.minPoint.asArray()[i] + box.maxPoint.asArray()[i]) * 5 for i in range(3)]
        center[axis_index] = box.minPoint.asArray()[axis_index] * 10
        where = "%s at %s" % ("in the hole" if internal else "on the shaft", _xyz(center))
    _remember_about(feature, "%s %s d%s" % (designation, where, _fmt(diameter)))
    print("thread: %s %s on the %s of diameter %s%s (%s)" % (
        designation, thread_class,
        ("inside of %d holes" % len(faces)) if internal and len(faces) > 1 else
        "inside of the hole face" if internal else "outside face", _fmt(diameter),
        "" if length is None else ", length %s" % _fmt(length), "modeled" if modeled else "cosmetic"))
    return feature


def _distance_to_box(point, box):
    low = box.minPoint.asArray()
    high = box.maxPoint.asArray()
    total = 0.0
    for i in range(3):
        value = point[i] * MM
        if value < low[i]:
            total += (low[i] - value) ** 2
        elif value > high[i]:
            total += (value - high[i]) ** 2
    return total


def _round_face_diameters():
    result = []
    for body in _all_bodies():
        for face in body.faces:
            if face.geometry.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType:
                result.append(round(face.geometry.radius * 20, 3))
    return result


def body(name_or_index=1):
    """A body of the design by its name from describe() ("Body1") or by its number counted from 1."""
    bodies = _all_bodies()
    if not bodies:
        raise ValueError("there is no body yet")
    if isinstance(name_or_index, int):
        # counted from 1, like Fusion's names: body(1) is Body1
        if name_or_index < 1 or name_or_index > len(bodies):
            raise ValueError("body(%d): there are %d bodies, counted from 1: %s" % (
                name_or_index, len(bodies), [b.name for b in bodies]))
        return bodies[name_or_index - 1]
    if getattr(name_or_index, "objectType", "").endswith("BRepBody"):
        return name_or_index
    for candidate in bodies:
        if candidate.name == name_or_index:
            return candidate
    raise ValueError("no body named %r; the bodies are %s" % (name_or_index, [b.name for b in bodies]))


def _combine(target, tools, operation, keep_tools):
    target = body(target)
    collection = adsk.core.ObjectCollection.create()
    for tool in (tools if isinstance(tools, (list, tuple)) else [tools]):
        tool_body = body(tool)
        if tool_body == target:
            raise ValueError("the tool body is the target itself")
        collection.add(tool_body)
    combines = root.features.combineFeatures
    combine_input = combines.createInput(target, collection)
    combine_input.operation = _OPERATIONS[operation]
    combine_input.isKeepToolBodies = keep_tools
    combine_input.isNewComponent = False
    before = sum(b.volume for b in _all_bodies())
    feature = _add(lambda: combines.add(combine_input), "combine (%s)" % operation,
                   "The bodies must overlap for cut and intersect; see their positions with describe().")
    after = sum(b.volume for b in _all_bodies())
    print("combine (%s): %s -> the part now has %d bodies, volume %s mm3 (%s%s mm3)" % (
        operation, target.name, len(_all_bodies()), _fmt(after * 1000), "+" if after >= before else "",
        _fmt((after - before) * 1000)))
    return feature


def subtract(target, tool, keep_tool=False):
    """ВЫЧЕСТЬ одно тело из другого (Combine - Cut): the tool body's shape is removed from the target body;
    keep_tool=True leaves the tool body in place (a mould, a cavity for a part). Bodies by name or index."""
    return _combine(target, tool, "cut", keep_tool)


def union(target, tools):
    """ОБЪЕДИНИТЬ тела в одно (Combine - Join): tools is one body or a list, merged into the target."""
    if len(_all_bodies()) == 1:
        print("union: the design already has one body (%s); a joined piece touching two bodies merges them" % _all_bodies()[0].name)
        return None
    return _combine(target, tools, "join", False)


def intersect(target, tool, keep_tool=False):
    """ПЕРЕСЕЧЕНИЕ тел (Combine - Intersect): only the common volume of the two bodies stays."""
    return _combine(target, tool, "intersect", keep_tool)


def _move_bodies(target, transform, what):
    target = body(target)
    collection = adsk.core.ObjectCollection.create()
    collection.add(target)
    moves = root.features.moveFeatures
    move_input = moves.createInput(collection, transform)
    feature = _add(lambda: moves.add(move_input), what, "")
    low, high = _extents_mm()
    print("%s: %s now spans x %s..%s, y %s..%s, z %s..%s" % (
        what, target.name, _fmt(low[0]), _fmt(high[0]), _fmt(low[1]), _fmt(high[1]), _fmt(low[2]), _fmt(high[2])))
    return feature


def move_body(target, dx=0, dy=0, dz=0):
    """СДВИНУТЬ тело by dx, dy, dz mm (by name from describe() or index)."""
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(dx * MM, dy * MM, dz * MM)
    return _move_bodies(target, transform, "move_body")


def rotate_body(target, angle, axis="Z", center=(0, 0, 0)):
    """ПОВЕРНУТЬ тело by angle degrees around the line through center=(x, y, z) parallel to the axis."""
    center = _xyz_argument(center, "center", "rotate_body")
    direction = [0, 0, 0]
    direction[_AXES[axis.upper()]] = 1
    transform = adsk.core.Matrix3D.create()
    transform.setToRotation(math.radians(angle), adsk.core.Vector3D.create(*direction),
                            adsk.core.Point3D.create(center[0] * MM, center[1] * MM, center[2] * MM))
    return _move_bodies(target, transform, "rotate_body")


def copy_body(target, dx=0, dy=0, dz=0):
    """КОПИЯ тела, moved by dx, dy, dz mm; returns the new body (the design then has one body more)."""
    source = body(target)
    copy = source.copyToComponent(root)
    if dx or dy or dz:
        _move_bodies(copy, _translation(dx, dy, dz), "copy_body")
    else:
        print("copy_body: %s copied as %s (it lies on the original until moved)" % (source.name, copy.name))
    return copy


def _translation(dx, dy, dz):
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(dx * MM, dy * MM, dz * MM)
    return transform


def loft(sketches, operation="new"):
    """ПЕРЕХОД между сечениями (loft): a solid through the closed shapes of two or more sketches on
    parallel offset planes, e.g. a circle at z=0 and a square at z=50 (квадрат-круг переходник). Draw each
    section in its own sketch (new_sketch("XY", offset=z)), then loft([sk1, sk2]). The volume has no simple
    formula: read it from the printed line."""
    if len(sketches) < 2:
        raise ValueError("loft() needs at least two sketches, one section each")
    lofts = root.features.loftFeatures
    loft_input = lofts.createInput(_OPERATIONS[operation])
    for sketch in sketches:
        profiles = solid_profiles(sketch)
        if len(profiles) != 1:
            raise ValueError("every loft section must be ONE closed shape; a sketch has %d" % len(profiles))
        loft_input.loftSections.add(profiles[0])
    loft_input.isSolid = True
    feature = _add(lambda: lofts.add(loft_input), "loft",
                   "The sections must lie on different parallel planes and not cross each other.")
    low, high = _extents_mm()
    print("loft: %d sections, overall size %s x %s x %s mm, volume %s mm3 (use it in check(volume=...))" % (
        len(sketches), _fmt(high[0] - low[0]), _fmt(high[1] - low[1]), _fmt(high[2] - low[2]),
        _fmt(sum(b.volume for b in feature.bodies) * 1000)))
    return feature


def _path_sketch(points, plane, offset, bend_radius):
    """Open polyline through (u, v) points on a base plane, corners rounded with bend_radius; the sketch
    and its curves."""
    if len(points) < 2:
        raise ValueError("a path needs at least two points")
    sketch = new_sketch(plane, offset=offset)
    lines = sketch.sketchCurves.sketchLines
    segments = []
    previous = None
    pending_arc = None
    for point in points:
        if len(point) == 3 and point[2] == "arc":
            if previous is None:
                raise ValueError('a path cannot start with an "arc" point')
            pending_arc = (point[0], point[1])
            continue
        current = _point(sketch, *point[:2])
        if previous is not None:
            if pending_arc is not None:
                arc_curve = sketch.sketchCurves.sketchArcs.addByThreePoints(previous, _point(sketch, *pending_arc), current)
                geometry = arc_curve.geometry
                center = sketch.sketchToModelSpace(arc_curve.centerSketchPoint.geometry)
                print("path arc through (%s, %s): radius %s, center (%s, %s, %s)" % (
                    _fmt(pending_arc[0]), _fmt(pending_arc[1]), _fmt(geometry.radius / MM),
                    _fmt(center.x / MM), _fmt(center.y / MM), _fmt(center.z / MM)))
                previous = arc_curve.endSketchPoint
                pending_arc = None
                continue
            segments.append(lines.addByTwoPoints(previous, current))
            previous = segments[-1].endSketchPoint
        else:
            previous = current
    # the first line starts from a free point; chain the rest from the previous line's end
    if bend_radius and len(segments) > 1:
        arcs = sketch.sketchCurves.sketchArcs
        for first, second in zip(segments, segments[1:]):
            corner = first.endSketchPoint.geometry
            try:
                arcs.addFillet(first, first.startSketchPoint.geometry, second, second.endSketchPoint.geometry,
                               bend_radius * MM)
            except RuntimeError:
                raise ValueError("the bend radius %s does not fit at the corner (%s, %s): segments are too short" % (
                    _fmt(bend_radius), _fmt(corner.x / MM), _fmt(corner.y / MM)))
    return sketch


def _sweep(profile_sketch, path_sketch, operation, what):
    curves = adsk.core.ObjectCollection.create()
    for curve in path_sketch.sketchCurves:
        if not curve.isConstruction:
            curves.add(curve)
    path = root.features.createPath(curves.item(0), True)
    sweeps = root.features.sweepFeatures
    sweep_input = sweeps.createInput(solid_profiles(profile_sketch)[0], path, _OPERATIONS[operation])
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    return _add(lambda: sweeps.add(sweep_input), what,
                "The bends must be wider than the section (bend_radius > the diameter), and the path must not "
                "double back. The simplest valid call: pipe([(0, 0, 0), (50, 0, 0), (50, 0, 30)], 8, bend_radius=10): "
                "the CORNER points with bend_radius, no arc points; an \"arc\" point is only for a path that IS an "
                "arc, and it must lie on that arc between two corners.")


def _plane_at_path_start(path_sketch):
    curves = adsk.core.ObjectCollection.create()
    for curve in path_sketch.sketchCurves:
        if not curve.isConstruction:
            curves.add(curve)
    path = root.features.createPath(curves.item(0), True)
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByDistanceOnPath(path, adsk.core.ValueInput.createByReal(0))
    return root.constructionPlanes.add(plane_input)


def _path_points(points, plane, offset):
    """(u, v) points on the given plane; (x, y, z) points are accepted when they all lie in one base plane,
    which then becomes the plane and its offset. (u, v, "arc") marks an arc's through point."""
    for point in points:
        if isinstance(point, str) or len(point) not in (2, 3):
            raise ValueError('every path point is (u, v), (x, y, z) or (u, v, "arc"); got %r. An arc is marked on the '
                             'point the path passes THROUGH, e.g. [(40, 0), (28.28, 28.28, "arc"), (0, 40)]' % (point,))
    if all(len(point) == 3 and point[2] != "arc" for point in points):
        for axis_index, name in ((2, "XY"), (1, "XZ"), (0, "YZ")):
            values = set(round(point[axis_index], 6) for point in points)
            if len(values) == 1:
                u_index, v_index = {"XY": (0, 1), "XZ": (0, 2), "YZ": (1, 2)}[name]
                return [(p[u_index], p[v_index]) for p in points], name, values.pop()
        raise ValueError("the path points (x, y, z) must lie in one plane parallel to XY, XZ or YZ")
    return [p if (len(p) == 3 and p[2] == "arc") else (p[0], p[1]) for p in points], plane.upper(), offset


def pipe(points, diameter, inner_diameter=None, plane="XY", offset=0, bend_radius=None, operation="new",
         section="round"):
    """ТРУБА, ПРУТОК ПО ТРАЕКТОРИИ (sweep): a section of this size (round of this diameter, or
    section="square" of this side; hollow when inner_diameter / inner side is given) swept along the path
    through points: (u, v) on the plane (XY: (x, y) at z=offset; XZ: (x, z) at y=offset; YZ: (y, z) at
    x=offset) or (x, y, z) points lying in one such plane; a point (u, v, "arc") is passed through by an
    arc (a quarter-circle path); bend_radius rounds the corners between straight parts (a bent tube, an
    elbow). Volume = section area * path length; it prints the length. The part's size is the path's
    extent plus the section's half size at each end (check() accepts the path's extent as the size)."""
    points, plane, offset = _path_points(points, plane, offset)
    path_sketch = _path_sketch(points, plane, offset, bend_radius)
    start_plane = _plane_at_path_start(path_sketch)
    profile_sketch = root.sketches.add(start_plane)
    u_index, v_index = {"XY": (0, 1), "XZ": (0, 2), "YZ": (1, 2)}[plane.upper()]
    start = [0.0, 0.0, 0.0]
    start[u_index] = points[0][0]
    start[v_index] = points[0][1]
    start[3 - u_index - v_index] = offset
    center = profile_sketch.modelToSketchSpace(adsk.core.Point3D.create(start[0] * MM, start[1] * MM, start[2] * MM))
    if inner_diameter and inner_diameter >= diameter:
        raise ValueError("the inner size must be smaller than the outer size")
    if section == "square":
        lines = profile_sketch.sketchCurves.sketchLines
        lines.addCenterPointRectangle(center, adsk.core.Point3D.create(center.x + diameter / 2 * MM, center.y + diameter / 2 * MM, 0))
        if inner_diameter:
            lines.addCenterPointRectangle(center, adsk.core.Point3D.create(center.x + inner_diameter / 2 * MM, center.y + inner_diameter / 2 * MM, 0))
        area = diameter ** 2 - (inner_diameter or 0) ** 2
    elif section == "round":
        profile_sketch.sketchCurves.sketchCircles.addByCenterRadius(center, diameter / 2 * MM)
        if inner_diameter:
            profile_sketch.sketchCurves.sketchCircles.addByCenterRadius(center, inner_diameter / 2 * MM)
        area = math.pi * (diameter ** 2 - (inner_diameter or 0) ** 2) / 4
    else:
        raise ValueError('section must be "round" or "square"')
    feature = _sweep(profile_sketch, path_sketch, operation, "pipe (sweep)")
    length = 0.0
    for curve in path_sketch.sketchCurves:
        if not curve.isConstruction:
            length += curve.length / MM
    low, high = _extents_mm()
    corners = [(p[0], p[1]) for p in points if len(p) == 2]
    for axis_index, values in ((u_index, [p[0] for p in corners]), (v_index, [p[1] for p in corners])):
        extent = max(values) - min(values)
        if extent > 0:
            _NOMINAL_SIZES.setdefault(round(extent, 6), []).append(
                (high[axis_index] - low[axis_index], "the path's extent; the section sticks out %s past each end" % _fmt(diameter / 2)))
    print("pipe: %s section %s%s along a path of length %s mm; volume = area %s * length = %s mm3; overall size "
          "%s x %s x %s" % (
              section, _fmt(diameter), (", inner %s" % _fmt(inner_diameter)) if inner_diameter else "", _fmt(length),
              _fmt(area), _fmt(area * length), _fmt(high[0] - low[0]), _fmt(high[1] - low[1]), _fmt(high[2] - low[2])))
    return feature


def spring(wire_diameter, mean_diameter, pitch, turns, base=(0, 0, 0), axis="Z", operation="new"):
    """ПРУЖИНА (a helical coil): wire of wire_diameter wound on a helix of mean_diameter (center to
    center of the wire), this pitch (mm per turn) and number of turns, starting at base=(x, y, z) and
    rising along the axis. Height = pitch * turns + wire_diameter. Volume ~ pi * (wire/2)**2 * helix
    length, helix length = turns * sqrt((pi * mean_diameter)**2 + pitch**2); it prints both."""
    base = _xyz_argument(base, "base", "spring")
    if wire_diameter >= pitch:
        raise ValueError("the pitch %s must be bigger than the wire diameter %s, or the coils overlap" % (
            _fmt(pitch), _fmt(wire_diameter)))
    axis_index = _AXES[axis.upper()]
    u_index, v_index = [i for i in range(3) if i != axis_index]
    radius = mean_diameter / 2.0
    steps_per_turn = 24
    count = int(round(turns * steps_per_turn))
    path_sketch = root.sketches.add(root.xYConstructionPlane)
    points = adsk.core.ObjectCollection.create()
    for step in range(count + 1):
        angle = 2 * math.pi * step / steps_per_turn
        point = list(base)
        point[u_index] += radius * math.cos(angle)
        point[v_index] += radius * math.sin(angle)
        point[axis_index] += pitch * step / steps_per_turn
        points.add(path_sketch.modelToSketchSpace(adsk.core.Point3D.create(point[0] * MM, point[1] * MM, point[2] * MM)))
    helix = path_sketch.sketchCurves.sketchFittedSplines.add(points)
    path = root.features.createPath(helix, False)
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByDistanceOnPath(path, adsk.core.ValueInput.createByReal(0))
    start_plane = root.constructionPlanes.add(plane_input)
    profile_sketch = root.sketches.add(start_plane)
    start = list(base)
    start[u_index] += radius
    center = profile_sketch.modelToSketchSpace(adsk.core.Point3D.create(start[0] * MM, start[1] * MM, start[2] * MM))
    profile_sketch.sketchCurves.sketchCircles.addByCenterRadius(center, wire_diameter / 2 * MM)
    sweeps = root.features.sweepFeatures
    sweep_input = sweeps.createInput(solid_profiles(profile_sketch)[0], path, _OPERATIONS[operation])
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    feature = _add(lambda: sweeps.add(sweep_input), "spring (sweep)",
                   "The wire must be thinner than the pitch and much thinner than the mean diameter.")
    helix_length = turns * math.sqrt((math.pi * mean_diameter) ** 2 + pitch ** 2)
    print("spring: wire %s on mean diameter %s, pitch %s, %s turns; height %s, outer diameter %s; helix length "
          "%s mm, volume ~ %s mm3 (measured %s)" % (
              _fmt(wire_diameter), _fmt(mean_diameter), _fmt(pitch), _fmt(turns), _fmt(pitch * turns + wire_diameter),
              _fmt(mean_diameter + wire_diameter), _fmt(helix_length),
              _fmt(math.pi * (wire_diameter / 2) ** 2 * helix_length), _fmt(sum(b.volume for b in feature.bodies) * 1000)))
    return feature


def plate(points, thickness, z=0, operation="new"):
    """ПЛАСТИНА ЛЮБОЙ ФОРМЫ (фигурное основание, плита с лепестками, вырезами, скруглёнными выступами):
    its outline as (x, y) points in mm, drawn on the XY plane at height z and extruded up by thickness.
    Corners are (x, y); a point (x, y, "arc") is not a corner but a point the edge passes through by an arc
    from the previous corner to the next one: a round lobe = corner, the lobe's outermost point as "arc",
    corner; a concave notch between two corners = its deepest point as "arc". Prints the outline's area and
    the volume for check(volume=...). points may also be a sketch that already holds the outline."""
    if getattr(points, "objectType", "").endswith("Sketch"):
        sketch = points
    else:
        sketch = new_sketch("XY", offset=z)
        outline(sketch, points)
    area = sum(profile.areaProperties().area for profile in solid_profiles(sketch)) * 100
    feature = extrude(sketch, thickness, operation=operation)
    print("plate: outline area %s mm2 x thickness %s = %s mm3, from z %s to %s" % (
        _fmt(area), _fmt(thickness), _fmt(area * thickness), _fmt(z), _fmt(z + thickness)))
    for sketch_arc in sketch.sketchCurves.sketchArcs:
        geometry = sketch_arc.geometry
        center = sketch.sketchToModelSpace(geometry.center)
        print("  arc: center (%s, %s), radius %s" % (_fmt(center.x / MM), _fmt(center.y / MM), _fmt(geometry.radius / MM)))
    return feature


def rib(points, thickness, plane="XZ", offset=0, operation="join"):
    """РЕБРО ЖЁСТКОСТИ, косынка: a closed outline (u, v) drawn on the plane (XZ: (x, z) at y=offset) and
    extruded symmetrically by thickness, joined to the part. A triangular gusset between a plate (z=0..t)
    and a wall (x=0..w): rib([(w, t), (w + L, t), (w, t + H)], thickness, "XZ", offset=y). Volume added
    = outline area * thickness (a right triangle: L * H / 2 * thickness)."""
    sketch = new_sketch(plane, offset=offset)
    outline(sketch, points)
    before = sum(b.volume for b in _all_bodies()) * 1000
    feature = extrude(sketch, thickness, operation=operation, symmetric=True)
    added = sum(b.volume for b in _all_bodies()) * 1000 - before
    area = 0.0
    corners = [(p[0], p[1]) for p in points if len(p) == 2]
    for index in range(len(corners)):
        u1, v1 = corners[index]
        u2, v2 = corners[(index + 1) % len(corners)]
        area += u1 * v2 - u2 * v1
    expected = abs(area) / 2 * thickness
    if operation == "join" and added < expected * 0.99:
        raise ValueError("rib: only %s of the rib's %s mm3 is new material, the rest lies inside the part. A rib "
                         "stands in the plane %s at %s and must run AWAY from the wall, perpendicular to the "
                         "wall's face, with its corner on the floor's top face at the foot of that face: for a wall "
                         "that is thin along Y (face at y = y0) use gusset(..., corner=(x on the wall, y0, floor top), "
                         "along=\"Y\"); for a wall thin along X use along=\"X\" from its face at x0. Do not start "
                         "the rib inside the wall's own span; %s" % (
                             _fmt(added), _fmt(expected), plane, _fmt(offset), _extents_text()))
    print("rib: outline area %s mm2 (straight sides) x thickness %s = %s mm3 added" % (
        _fmt(abs(area) / 2), _fmt(thickness), _fmt(expected)))
    return feature


def _is_outside_part(x, y, z):
    """True when the point (mm) lies outside every body of the design."""
    probe = adsk.core.Point3D.create(x * MM, y * MM, z * MM)
    for candidate in _all_bodies():
        if candidate.pointContainment(probe) != adsk.fusion.PointContainment.PointOutsidePointContainment:
            return False
    return True


_ALONG_STEPS = {"X": (1, 0), "-X": (-1, 0), "Y": (0, 1), "-Y": (0, -1)}


def _free_direction(corner):
    """The one direction away from the wall at an inner corner: 1 mm that way (just above the floor) is
    air and 1 mm the opposite way is the wall. None when the corner does not look like an inner corner."""
    if not _all_bodies():
        return None
    free = []
    for name, (dx, dy) in _ALONG_STEPS.items():
        ahead = _is_outside_part(corner[0] + dx, corner[1] + dy, corner[2] + 1)
        behind = _is_outside_part(corner[0] - dx, corner[1] - dy, corner[2] + 1)
        floor_ahead = not _is_outside_part(corner[0] + dx, corner[1] + dy, corner[2] - 1)
        if ahead and not behind and floor_ahead:
            free.append(name)
    if len(free) == 1:
        return free[0]
    return None


def gusset(length, height, thickness, corner=(0, 0, 0), along=None, operation="join", lean=0):
    """КОСЫНКА, треугольное ребро between a floor and a wall meeting at the inner corner corner=(x, y, z):
    the triangle runs length mm along the floor AWAY from the wall's face (the along axis, "X", "-X",
    "Y" or "-Y": perpendicular to the wall's face) and height mm up the wall (+Z); thickness is centered
    on the corner's other coordinate. The corner is a point ON the wall's face at the floor's top (for a
    wall thin along Y with its face at y0: corner=(x, y0, floor top)). along may be left out: the helper
    finds the free direction at the corner itself (and corrects a wrong one). Two ribs = two calls at two x
    (or y) positions. Volume added = length * height / 2 * thickness.
    lean (mm): the rib leans sideways along the wall's face: its foot stays at the corner and its top is
    moved lean mm along the face (positive toward +X for a wall thin along Y, toward +Y for a wall thin
    along X). The rib keeps its length, so its top ends a little lower than height. Ribs that meet under
    an eye and spread down toward the feet: two gussets with opposite lean."""
    global _NEW_BASE_BODIES
    corner = _xyz_argument(corner, "corner", "gusset")
    free = _free_direction(corner)
    if along is None:
        if free is None:
            raise ValueError("gusset: the corner (%s, %s, %s) is not an inner corner of a wall and a floor: it needs the "
                             "wall on one side, air on the other side just above the floor, and the floor right under that air. "
                             "Put the corner ON the wall's face at the floor's TOP (z = the floor's thickness), where the rib "
                             "will stand on the floor; %s" % (_fmt(corner[0]), _fmt(corner[1]), _fmt(corner[2]), _extents_text()))
        along = free
        print("gusset: the rib runs along %s, away from the wall's face" % along)
    else:
        along = str(along).upper()
        if along not in _ALONG_STEPS:
            raise ValueError('along must be "X", "-X", "Y" or "-Y"')
        if free is not None and free != along:
            print('gusset: along="%s" would run into the part, the free direction at the corner is "%s": using it' % (along, free))
            along = free
    if along == "X":
        points = [(corner[0], corner[2]), (corner[0] + length, corner[2]), (corner[0], corner[2] + height)]
        plane, offset = "XZ", corner[1]
    elif along == "Y":
        points = [(corner[1], corner[2]), (corner[1] + length, corner[2]), (corner[1], corner[2] + height)]
        plane, offset = "YZ", corner[0]
    elif along == "-X":
        points = [(corner[0], corner[2]), (corner[0] - length, corner[2]), (corner[0], corner[2] + height)]
        plane, offset = "XZ", corner[1]
    else:
        points = [(corner[1], corner[2]), (corner[1] - length, corner[2]), (corner[1], corner[2] + height)]
        plane, offset = "YZ", corner[0]
    if not lean:
        return rib(points, thickness, plane, offset=offset, operation=operation)

    # A leaning rib: the upright triangle as its own body, turned about the line through the corner along
    # the rib's length (its foot stays), then merged into the part.
    bodies_before = _all_bodies()
    volume_before = sum(body.volume for body in bodies_before) * 1000
    new_bodies_before = _NEW_BASE_BODIES
    feature = rib(points, thickness, plane, offset=offset, operation="new")
    _NEW_BASE_BODIES = new_bodies_before
    rib_body = feature.bodies.item(0)
    if plane == "XZ":
        turn_axis = adsk.core.Vector3D.create(1, 0, 0)
        sideways_index = 1
    else:
        turn_axis = adsk.core.Vector3D.create(0, 1, 0)
        sideways_index = 0
    pivot = adsk.core.Point3D.create(corner[0] * MM, corner[1] * MM, corner[2] * MM)
    angle = math.atan2(lean, height)
    moves = root.features.moveFeatures
    is_turned = False
    for signed_angle in (angle, -angle):
        transform = adsk.core.Matrix3D.create()
        transform.setToRotation(signed_angle, turn_axis, pivot)
        collection = adsk.core.ObjectCollection.create()
        collection.add(rib_body)
        move = _add(lambda: moves.add(moves.createInput(collection, transform)), "gusset (lean)", "")
        bounds = rib_body.boundingBox
        middle = (bounds.maxPoint.asArray()[sideways_index] + bounds.minPoint.asArray()[sideways_index]) / 2 / MM
        shift = middle - corner[sideways_index]
        if shift * lean > 0:
            is_turned = True
            break
        move.deleteMe()
    if not is_turned:
        raise ValueError("gusset: could not lean the rib by %s mm" % _fmt(lean))

    if operation == "join" and bodies_before:
        _combine(bodies_before[0], rib_body, "join", False)
        added = sum(body.volume for body in _all_bodies()) * 1000 - volume_before
        expected = length * height / 2 * thickness
        if added < expected * 0.99:
            raise ValueError("gusset: only %s of the leaning rib's %s mm3 is new material, the rest lies inside the "
                             "part: the corner must sit ON the wall's face at the floor's top, and the rib must run "
                             "away from the face; %s" % (_fmt(added), _fmt(expected), _extents_text()))
    print("gusset: leaning %s mm sideways (%.1f degrees), top at height %s" % (
        _fmt(lean), math.degrees(angle), _fmt(corner[2] + height * math.cos(angle))))
    return feature


def tilted_plane(angle, axis="X", through=(0, 0, 0), plane="XY"):
    """A construction plane: the base plane turned by angle degrees around the line through through=(x, y, z)
    parallel to the axis (axis must lie in the plane: X or Y for XY). new_sketch() accepts it:
    sk = new_sketch(tilted_plane(30, "X")); the sketch's (u, v) are measured in the tilted plane."""
    through = _xyz_argument(through, "through", "tilted_plane")
    plane = plane.upper()
    u_index, v_index = {"XY": (0, 1), "XZ": (0, 2), "YZ": (1, 2)}[plane]
    n_index = 3 - u_index - v_index
    axis_index = _AXES[axis.upper()]
    if axis_index == n_index:
        raise ValueError("the axis %s is normal to the %s plane; turn around an axis lying in it" % (axis.upper(), plane))
    # The hinge is a construction line drawn in a sketch on the plane through the point: a construction
    # axis made from a bare line is refused in a parametric design.
    hinge_sketch = new_sketch(plane, offset=through[n_index])
    start = list(through)
    end = list(through)
    start[axis_index] -= 10
    end[axis_index] += 10
    hinge = hinge_sketch.sketchCurves.sketchLines.addByTwoPoints(
        hinge_sketch.modelToSketchSpace(adsk.core.Point3D.create(start[0] * MM, start[1] * MM, start[2] * MM)),
        hinge_sketch.modelToSketchSpace(adsk.core.Point3D.create(end[0] * MM, end[1] * MM, end[2] * MM)))
    hinge.isConstruction = True
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByAngle(hinge, adsk.core.ValueInput.createByString("%s deg" % angle), hinge_sketch.referencePlane)
    return _add(lambda: root.constructionPlanes.add(plane_input), "tilted_plane", "")


def angled_hole(x, y, z, diameter, angle, tilt_axis="X", depth=None):
    """ОТВЕРСТИЕ ПОД УГЛОМ: a round hole whose axis passes through the surface point (x, y, z) and is tilted
    by angle degrees from the vertical (Z), turning around the tilt_axis ("X" or "Y"); depth=None: through
    everything. Material removed when it goes straight through a plate of thickness t without leaving its
    sides: pi * (d/2)**2 * t / cos(angle)."""
    plane = tilted_plane(angle, tilt_axis, through=(x, y, z), plane="XY")
    sketch = root.sketches.add(plane)
    center = sketch.modelToSketchSpace(adsk.core.Point3D.create(x * MM, y * MM, z * MM))
    sketch.sketchCurves.sketchCircles.addByCenterRadius(center, diameter / 2 * MM)
    if depth is None:
        return cut(sketch)
    return extrude(sketch, -abs(depth), operation="cut")


def engrave(text, height, depth, corner=(0, 0, 0), plane="XY", width=None, raised=False):
    """ТЕКСТ, надпись, гравировка: letters of this height (mm) starting at corner=(x, y, z) (bottom-left of
    the text) on the plane (XY: a face at z = corner z), cut depth mm into the part, or raised (embossed)
    by depth when raised=True. width: the text box width (default 0.8 * height per character)."""
    corner = _xyz_argument(corner, "corner", "engrave")
    plane = plane.upper()
    u_index, v_index = {"XY": (0, 1), "XZ": (0, 2), "YZ": (1, 2)}[plane]
    n_index = 3 - u_index - v_index
    sketch = new_sketch(plane, offset=corner[n_index])
    box_width = width if width else max(height, 0.8 * height * len(text))
    texts = sketch.sketchTexts
    text_input = texts.createInput2(text, height * MM)
    text_input.setAsMultiLine(_point(sketch, corner[u_index], corner[v_index]),
                              _point(sketch, corner[u_index] + box_width, corner[v_index] + height * 1.3),
                              adsk.core.HorizontalAlignments.LeftHorizontalAlignment,
                              adsk.core.VerticalAlignments.BottomVerticalAlignment, 0)
    sketch_text = texts.add(text_input)
    extrudes = root.features.extrudeFeatures
    operation = "join" if raised else "cut"
    extrude_input = extrudes.createInput(sketch_text, _OPERATIONS[operation])
    extent = adsk.fusion.DistanceExtentDefinition.create(_length(abs(depth)))
    direction = _direction_sign(sketch, depth if raised else -depth)
    extrude_input.setOneSideExtent(extent, direction)
    feature = _add(lambda: extrudes.add(extrude_input), "engrave",
                   "The text must lie on a face of the part (corner z = that face's height) and fit on it.")
    print("engrave: %r, letters %s mm high, %s %s mm" % (text, _fmt(height), "raised" if raised else "cut", _fmt(abs(depth))))
    return feature


def lug(diameter, hole_diameter, thickness, center=(0, 0, 0), axis="Y", operation="join", stands_on=None):
    """ПРОУШИНА, ушко (an eye for a pin or a bolt): a round disk of this diameter and thickness whose axis
    runs along the axis through center=(x, y, z) (the middle of the disk), with a through hole of
    hole_diameter along the SAME axis. axis="Y" or "X" is a standing eye with a horizontal hole (on top
    of a post, at the end of a lever); axis="Z" a flat eye. Volume added = pi/4 * (D*D - d*d) * thickness
    minus what overlaps the part (the join line says how much).
    stands_on=(x1, x2, z): the eye is the top of a flat STANDING PLATE of this thickness whose bottom edge
    is the line from x1 to x2 (y1 to y2 for axis="X") at height z; the plate narrows up to the eye, its two
    sides tangent to the eye's circle (a hanger, a bracket's wall that ends in an eye, a clevis plate). It
    is the whole wall: nothing is built under it, it stands on the base's top face (z = base thickness) or
    on the ground (z = 0). The hole goes through the eye; the call prints the volume for check(volume=...)."""
    center = _xyz_argument(center, "center", "lug")
    if hole_diameter >= diameter:
        raise ValueError("the hole %s must be smaller than the lug's diameter %s" % (_fmt(hole_diameter), _fmt(diameter)))
    axis_index = _AXES[axis.upper()]
    if stands_on is None:
        base = list(center)
        base[axis_index] -= thickness / 2.0
        feature = cylinder(diameter, thickness, base=tuple(base), axis=axis, operation=operation)
        drill(center[0], center[1], center[2], hole_diameter, axis=axis)
        print("lug: diameter %s, hole %s along %s, thickness %s, center (%s, %s, %s); own volume %s mm3" % (
            _fmt(diameter), _fmt(hole_diameter), axis.upper(), _fmt(thickness), _fmt(center[0]), _fmt(center[1]),
            _fmt(center[2]), _fmt(math.pi / 4 * (diameter ** 2 - hole_diameter ** 2) * thickness)))
        return feature

    if axis_index == 2:
        raise ValueError('lug(stands_on=...) needs a standing eye, axis="Y" or "X"; a flat eye (axis="Z") stands on nothing')
    if len(stands_on) != 3:
        raise ValueError("stands_on is (x1, x2, z): the plate's bottom edge from x1 to x2 at height z, got %r" % (stands_on,))
    a, b, foot_z = float(stands_on[0]), float(stands_on[1]), float(stands_on[2])
    if a > b:
        a, b = b, a
    if a == b:
        raise ValueError("the plate's bottom edge must have a length: x1 and x2 are both %s" % _fmt(a))
    radius = diameter / 2.0
    if axis_index == 1:
        plane, u_center = "XZ", center[0]
    else:
        plane, u_center = "YZ", center[1]
    v_center = center[2]
    if foot_z >= v_center - radius:
        raise ValueError("the plate's bottom edge at height %s must lie below the eye, whose bottom is at %s. "
                         "stands_on=(x1, x2, z) is not a point: x1 and x2 are the two ends of the plate's bottom edge "
                         "(its full width on the base), z is the height of that edge (the base's top face or the ground); "
                         "the plate itself is the whole wall, do not build a post under it" % (
                             _fmt(foot_z), _fmt(v_center - radius)))

    # The plate's sides are the outer tangents from the foot corners to the eye's circle.
    tangents = []
    for u in (a, b):
        distance = math.hypot(u - u_center, foot_z - v_center)
        if distance <= radius:
            raise ValueError("the bottom corner at %s lies inside the eye's circle; widen the bottom edge or raise the eye" % _fmt(u))
        angle_to_corner = math.atan2(foot_z - v_center, u - u_center)
        half_spread = math.acos(radius / distance)
        outer_sign = 1 if u > u_center else -1
        candidates = []
        for angle in (angle_to_corner + half_spread, angle_to_corner - half_spread):
            candidates.append((u_center + radius * math.cos(angle), v_center + radius * math.sin(angle)))
        tangents.append(max(candidates, key=lambda point: outer_sign * (point[0] - u_center)))
    left_tangent, right_tangent = tangents

    sketch = new_sketch(plane, offset=center[axis_index])
    outline(sketch, [(a, foot_z), (b, foot_z), right_tangent, (u_center, v_center + radius, "arc"), left_tangent])
    if operation == "join" and not _all_bodies():
        operation = "new"
    feature = extrude(sketch, thickness, operation=operation, symmetric=True)
    drill(center[0], center[1], center[2], hole_diameter, axis=axis)

    # Own volume: the four-corner plate plus the circle's cap above the chord between the tangent points, minus the hole.
    corners = [(a, foot_z), (b, foot_z), right_tangent, left_tangent]
    polygon_area = 0.0
    for index in range(len(corners)):
        u1, v1 = corners[index]
        u2, v2 = corners[(index + 1) % len(corners)]
        polygon_area += u1 * v2 - u2 * v1
    polygon_area = abs(polygon_area) / 2
    chord = math.hypot(right_tangent[0] - left_tangent[0], right_tangent[1] - left_tangent[1])
    half_chord = min(chord / 2, radius)
    to_chord = math.sqrt(max(radius ** 2 - half_chord ** 2, 0.0))
    minor_segment = radius ** 2 * math.acos(to_chord / radius) - to_chord * half_chord
    chord_middle_v = (left_tangent[1] + right_tangent[1]) / 2
    if v_center > chord_middle_v:
        cap = math.pi * radius ** 2 - minor_segment
    else:
        cap = minor_segment
    own = (polygon_area + cap - math.pi / 4 * hole_diameter ** 2) * thickness
    size = [0, 0, 0]
    size[axis_index] = thickness
    size[0 if axis_index == 1 else 1] = max(b, u_center + radius) - min(a, u_center - radius)
    size[2] = v_center + radius - foot_z
    print("lug on a plate: eye diameter %s, hole %s along %s, thickness %s, center (%s, %s, %s); the plate stands "
          "on %s..%s at height %s, its sides touch the eye at heights %s and %s; own volume %s mm3, own size "
          "%s x %s x %s mm (x, y, z: the eye's top is at height %s)" % (
              _fmt(diameter), _fmt(hole_diameter), axis.upper(), _fmt(thickness), _fmt(center[0]), _fmt(center[1]),
              _fmt(center[2]), _fmt(a), _fmt(b), _fmt(foot_z), _fmt(left_tangent[1]), _fmt(right_tangent[1]), _fmt(own),
              _fmt(size[0]), _fmt(size[1]), _fmt(size[2]), _fmt(v_center + radius)))
    return feature


def _profile(points, length, base):
    """Extrude a cross-section drawn on XZ (u = x, v = z, relative to base) along +Y by length."""
    base = _xyz_argument(base, "base", "profile")
    sketch = new_sketch("XZ", offset=base[1])
    polygon(sketch, [(base[0] + u, base[2] + v) for u, v in points])
    return extrude(sketch, length)


def angle_profile(leg_x, leg_z, thickness, length, base=(0, 0, 0), inner_radius=None):
    """Уголок (L) with its outer corner at base: the horizontal flange is the plate z = 0..thickness,
    x = 0..leg_x; the vertical flange is the wall x = 0..thickness, z = 0..leg_z; both run along +Y
    for length. inner_radius rounds the inside corner between the flanges."""
    t = thickness
    feature = _profile([(0, 0), (leg_x, 0), (leg_x, t), (t, t), (t, leg_z), (0, leg_z)], length, base)
    if inner_radius:
        corner_x = base[0] + t
        corner_z = base[2] + t
        fillet(find_edges(parallel_to="Y", x=corner_x, z=corner_z), inner_radius)
    return feature


def channel(height, flange_width, thickness, length, base=(0, 0, 0)):
    """Швеллер (U): a web of full height along Z at x 0..thickness and two flanges of flange_width
    (full, web included) along +X at the bottom and the top; extruded along +Y by length."""
    h, b, t = height, flange_width, thickness
    return _profile([(0, 0), (b, 0), (b, t), (t, t), (t, h - t), (b, h - t), (b, h), (0, h)], length, base)


def _extents_mm():
    """(low, high) corners in mm of the box around every body."""
    low = [None, None, None]
    high = [None, None, None]
    for body in _all_bodies():
        box_min = body.boundingBox.minPoint.asArray()
        box_max = body.boundingBox.maxPoint.asArray()
        for i in range(3):
            if low[i] is None or box_min[i] * 10 < low[i]:
                low[i] = box_min[i] * 10
            if high[i] is None or box_max[i] * 10 > high[i]:
                high[i] = box_max[i] * 10
    return low, high


def _is_round_footprint(size_x, size_y):
    """True when the part is a disk seen from above: a square footprint spanned by one cylindrical face."""
    if abs(size_x - size_y) > 1e-6:
        return False
    for body in _all_bodies():
        for face in body.faces:
            if face.geometry.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType:
                if abs(face.geometry.radius * 20 - size_x) < 1e-6:
                    return True
    return False


def wall_on_edge(thickness, height, edge="long"):
    """Стенка, бортик, перегородка standing on the part along one of its edges: a thin box as long as
    that edge, thickness across it, height above the part's top face, flush with the edge, joined.
    edge="long": along the longer side of the part's footprint; "short": along the shorter side.
    Volume added = edge length * thickness * height."""
    if edge not in ("long", "short"):
        raise ValueError('wall_on_edge() needs edge="long" (along the longer side) or edge="short"')
    if not _all_bodies():
        raise ValueError("wall_on_edge() needs a part to stand on: build the plate first")
    low, high = _extents_mm()
    size_x = high[0] - low[0]
    size_y = high[1] - low[1]
    if _is_round_footprint(size_x, size_y):
        raise ValueError("wall_on_edge() is for a rectangular plate; this part is a disk. A бортик around a disk "
                         "of diameter D is a ring: tube(D, D - 2*thickness, height, base=(x, y, top), "
                         "operation=\"join\")")
    if edge == "long":
        along_x = size_x >= size_y
    else:
        along_x = size_x < size_y
    top = high[2]
    if along_x:
        return box(size_x, thickness, height, corner=(low[0], high[1] - thickness, top), operation="join")
    return box(thickness, size_y, height, corner=(high[0] - thickness, low[1], top), operation="join")


def u_bracket(width, height, strip_width, thickness, base=(0, 0, 0)):
    """Скоба, стойка, держатель буквой П bent from a strip: the back lies flat at the bottom along +X
    (width), the two legs go up to height at x = 0 and x = width; the strip's width runs along +Y.
    The arguments follow the words: ширина, высота, полоска шириной, толщиной."""
    w, h, t = width, height, thickness
    return _profile([(0, 0), (w, 0), (w, h), (w - t, h), (w - t, t), (t, t), (t, h), (0, h)], strip_width, base)


def l_bracket(side_x, side_z, strip_width, thickness, base=(0, 0, 0)):
    """Уголок буквой Г bent from a strip: side_x lies flat along +X, side_z goes up along +Z; the
    strip's width runs along +Y."""
    return angle_profile(side_x, side_z, thickness, strip_width, base=base)


def tee(flange_width, height, flange_thickness, web_thickness, length, base=(0, 0, 0)):
    """Тавр (T): a flange of flange_width on top, full height, web centered on x = base x; along +Y."""
    b, h, tf, tw = flange_width, height, flange_thickness, web_thickness
    return _profile([(-tw / 2, 0), (tw / 2, 0), (tw / 2, h - tf), (b / 2, h - tf), (b / 2, h),
                     (-b / 2, h), (-b / 2, h - tf), (-tw / 2, h - tf)], length, base)


def ibeam(height, flange_width, flange_thickness, web_thickness, length, base=(0, 0, 0)):
    """Двутавр (I): flanges of flange_width at the bottom and the top, web centered; along +Y."""
    h, b, tf, tw = height, flange_width, flange_thickness, web_thickness
    return _profile([(-b / 2, 0), (b / 2, 0), (b / 2, tf), (tw / 2, tf), (tw / 2, h - tf), (b / 2, h - tf),
                     (b / 2, h), (-b / 2, h), (-b / 2, h - tf), (-tw / 2, h - tf), (-tw / 2, tf), (-b / 2, tf)],
                    length, base)


def _check_hole_inside(what, u, v, diameter, u_index=0, v_index=1):
    """A hole whose circle sticks out of the part's extents in its own plane is a wrong position."""
    if not _all_bodies():
        return
    low, high = _extents_mm()
    radius = diameter / 2.0
    for index, value in ((u_index, u), (v_index, v)):
        extent = high[index] - low[index]
        if value - radius < low[index] - 1e-6 or value + radius > high[index] + 1e-6:
            name = "XYZ"[index]
            if diameter > extent + 1e-6:
                axis_name = "XYZ"[3 - u_index - v_index]
                raise ValueError("%s is wider than the part along %s: the part is only %s mm there (%s..%s), the "
                                 "hole's circle spans %s..%s. A hole this wide cannot cross the part sideways; "
                                 "drill it along the axis the part is thick along (not %s), e.g. through an eye or "
                                 "lug along the eye's own axis." % (
                                     what, name, _fmt(extent), _fmt(low[index]), _fmt(high[index]),
                                     _fmt(value - radius), _fmt(value + radius), axis_name))
            raise ValueError("%s sticks out of the part along %s (the hole's circle spans %s..%s, the part %s..%s): %s. "
                             "Measure hole positions from the part's own corner or center (a cylinder's base is its "
                             "center; a box from corner=(0, 0, 0) has its center at half its sizes)." % (
                                 what, name, _fmt(value - radius), _fmt(value + radius), _fmt(low[index]),
                                 _fmt(high[index]), _extents_text()))


def drill(x, y, z, diameter, axis=None, depth=None):
    """Round hole whose axis passes through the point (x, y, z) along axis 'X', 'Y' or 'Z' (required:
    a default made the model drill side holes from the top).
    depth=None: through everything. With a depth, (x, y, z) is the entry point on the surface and
    the hole goes into the body."""
    if axis is None:
        raise ValueError('drill() needs axis="Z" (hole from the top or bottom) or axis="X" / "Y" (hole from a side)')
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    point = (x, y, z)
    _check_hole_inside("drill() at (%s, %s, %s) along %s of diameter %s" % (
        _fmt(x), _fmt(y), _fmt(z), axis.upper(), _fmt(diameter)),
        point[u_index], point[v_index], diameter, u_index, v_index)
    sketch = new_sketch(plane, offset=point[n_index])
    circle(sketch, point[u_index], point[v_index], diameter)
    return _cut_into_body(sketch, depth)


def _cut_into_body(sketch, depth):
    """Through everything (depth=None) or a blind cut of depth from the sketch plane into the body."""
    if depth is None:
        return cut(sketch)
    direction = _through_all_direction(sketch)
    _, _, normal_component = _sketch_frame(sketch)
    goes_positive = (direction == adsk.fusion.ExtentDirections.PositiveExtentDirection) == (normal_component > 0)
    return extrude(sketch, depth if goes_positive else -depth, operation="cut")


def spline_points(cx, cy, teeth, inner_diameter, outer_diameter, start_angle=0):
    """Outline of a straight-sided spline (a star) that alternates between the circle of inner_diameter
    and the circle of outer_diameter, each segment half a pitch wide. (u, v) points for polygon().
    Area inside = teeth * (inner_diameter**2 + outer_diameter**2) / 8 * sin(180 / teeth degrees)."""
    if teeth < 3:
        raise ValueError("spline_points() needs at least 3 teeth")
    if outer_diameter == inner_diameter:
        raise ValueError("a spline needs two different diameters (tooth tips and gap bottoms)")
    if outer_diameter < inner_diameter:
        print("spline: the sizes %s and %s were taken as inner %s, outer %s (the star is the same)" % (
            _fmt(inner_diameter), _fmt(outer_diameter), _fmt(outer_diameter), _fmt(inner_diameter)))
        inner_diameter, outer_diameter = outer_diameter, inner_diameter
    inner = inner_diameter / 2
    outer = outer_diameter / 2
    pitch = 360.0 / teeth
    points = []
    for index in range(teeth):
        tooth_start = start_angle + index * pitch
        gap_start = tooth_start + pitch / 2
        gap_end = tooth_start + pitch
        for radius, angle in ((inner, tooth_start), (inner, gap_start), (outer, gap_start), (outer, gap_end)):
            points.append((cx + radius * math.cos(math.radians(angle)), cy + radius * math.sin(math.radians(angle))))
    return points


def spline_hole(teeth, inner_diameter, outer_diameter, axis="Z", center=(0, 0, 0), depth=None):
    """Шлицевое отверстие: a hole with teeth inside (a straight-sided star) whose axis passes through
    center=(x, y, z) along axis 'X', 'Y' or 'Z'. inner_diameter is across the tooth tips (the smaller
    size), outer_diameter across the bottoms of the gaps. depth=None: through everything; with a depth
    center is the entry point on the surface. Material removed per mm of length:
    teeth * (inner_diameter**2 + outer_diameter**2) / 8 * sin(180 / teeth degrees)."""
    if isinstance(axis, (int, float)):
        raise ValueError('spline_hole(teeth, inner_diameter, outer_diameter, axis="Z", center=(x, y, z)): '
                         'the fourth argument is the axis letter')
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    point = _xyz_argument(center, "center", "spline_hole")
    sketch = new_sketch(plane, offset=point[n_index])
    polygon(sketch, spline_points(point[u_index], point[v_index], teeth, inner_diameter, outer_diameter))
    _SPLINE_SIZES.update((inner_diameter, outer_diameter))
    return _cut_into_body(sketch, depth)


def spline_shaft(teeth, inner_diameter, outer_diameter, length, base=(0, 0, 0), axis="Z", operation="new"):
    """Шлицевой вал: a solid straight-sided star (teeth on the outside) whose bottom is centered at
    base=(x, y, z); it grows by length along +axis. inner_diameter is across the bottoms of the gaps
    (впадины), outer_diameter across the tooth tips (вершины).
    Volume = teeth * (inner_diameter**2 + outer_diameter**2) / 8 * sin(180 / teeth degrees) * length."""
    base = _xyz_argument(base, "base", "spline_shaft")
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    sketch = new_sketch(plane, offset=base[n_index])
    polygon(sketch, spline_points(base[u_index], base[v_index], teeth, inner_diameter, outer_diameter))
    _SPLINE_SIZES.update((inner_diameter, outer_diameter))
    return extrude(sketch, length, operation=operation)


def rim_cutout_area(disk_diameter, cutout_diameter):
    """Area (mm2) that one rim cutout removes from a disk: the lens where a circle of cutout_diameter
    centered ON the rim overlaps the disk. Volume removed = rim_cutout_area(D, d) * thickness."""
    big = disk_diameter / 2
    small = cutout_diameter / 2
    if small <= 0 or small >= 2 * big:
        raise ValueError("rim_cutout_area() needs a cutout smaller than twice the disk")
    return (small * small * math.acos(small / (2 * big)) + big * big * math.acos(1 - small * small / (2 * big * big))
            - 0.5 * math.sqrt(small * small * (2 * big + small) * (2 * big - small)))


def rim_cutouts(disk_diameter, cutout_diameter, count, center=None, start_angle=0, axis="Z"):
    """Полукруглые вырезы по краю: count round notches cut THROUGH a disk (or any part) of
    disk_diameter whose axis passes through center=(x, y, z); each cutter circle of cutout_diameter is
    centered on the rim, the first at start_angle (degrees from +X for axis Z), the rest evenly around.
    The part's size across the cutouts becomes D - d*d/(2*D). Volume removed = count *
    rim_cutout_area(D, d) * thickness."""
    center = _xyz_argument(center, "center", "rim_cutouts")
    if count < 1:
        raise ValueError("rim_cutouts() needs count of at least 1")
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    sketch = new_sketch(plane, offset=center[n_index])
    for u, v in points_on_circle(center[u_index], center[v_index], disk_diameter, count, start_angle=start_angle):
        circle(sketch, u, v, cutout_diameter)
    feature = cut(sketch)
    across = disk_diameter - cutout_diameter * cutout_diameter / (2.0 * disk_diameter)
    _RIM_SIZES[round(disk_diameter, 6)] = across
    print("rim_cutouts: %d notches of %s cut; the size across them is now %s (was %s): use %s in check(size=...); "
          "each notch removed rim_cutout_area(%s, %s) = %s mm2 per mm of thickness" % (
              count, _fmt(cutout_diameter), _fmt(across), _fmt(disk_diameter), _fmt(across),
              _fmt(disk_diameter), _fmt(cutout_diameter), _fmt(rim_cutout_area(disk_diameter, cutout_diameter))))
    return feature


def holes(points, diameter, plane="XY", offset=0, depth=None):
    """Round holes of the given DIAMETER at (u, v) points of a plane; depth=None means through all."""
    if plane.upper() == "XY":
        for u, v in points:
            _check_hole_inside("the hole at (%s, %s) of diameter %s" % (_fmt(u), _fmt(v), _fmt(diameter)), u, v, diameter)
    sketch = new_sketch(plane, offset)
    for u, v in points:
        circle(sketch, u, v, diameter)
    return cut(sketch, depth)


def screw_holes(points, diameter, z, counterbore=None, countersink=None, depth=None):
    """Holes drilled down (toward -Z) from the face at height z (mm) at (x, y) points.
    counterbore=(diameter, depth): a wider flat-bottom recess for a screw head (цековка);
    countersink=diameter: a 90-degree cone for a flat head (зенковка); depth=None: through everything."""
    sketch = new_sketch("XY", offset=z)
    sketch_points = adsk.core.ObjectCollection.create()
    for x, y in points:
        sketch_points.add(sketch.sketchPoints.add(_point(sketch, x, y)))
    hole_features = root.features.holeFeatures
    if counterbore is not None:
        hole_input = hole_features.createCounterboreInput(_length(diameter), _length(counterbore[0]),
                                                          _length(counterbore[1]))
    elif countersink is not None:
        hole_input = hole_features.createCountersinkInput(_length(diameter), _length(countersink),
                                                          adsk.core.ValueInput.createByString("90 deg"))
    else:
        hole_input = hole_features.createSimpleInput(_length(diameter))
    hole_input.setPositionBySketchPoints(sketch_points)
    if depth is None:
        hole_input.setAllExtent(adsk.fusion.ExtentDirections.PositiveExtentDirection)
    else:
        hole_input.setDistanceExtent(_length(depth))
    return _add(lambda: hole_features.add(hole_input), "screw_holes",
                "z must be the height of the top face the holes start from, and the points must be on it.")


def _planar_face(body, side):
    """The outermost flat face of the body on a side: 'top', 'bottom', '+x', '-x', '+y', '-y'."""
    side = side.lower()
    targets = {"top": (2, 1), "bottom": (2, -1), "+z": (2, 1), "-z": (2, -1),
               "+x": (0, 1), "-x": (0, -1), "+y": (1, 1), "-y": (1, -1)}
    if side not in targets:
        raise ValueError("side must be one of %s" % ", ".join(sorted(targets)))
    axis_index, sign = targets[side]
    best = None
    best_value = None
    for face in body.faces:
        if not isinstance(face.geometry, adsk.core.Plane):
            continue
        normal = face.geometry.normal.asArray()
        if abs(abs(normal[axis_index]) - 1) > 1e-6:
            continue
        value = face.centroid.asArray()[axis_index] * sign
        if best is None or value > best_value:
            best = face
            best_value = value
    if best is None:
        raise ValueError("no flat face on side %r" % side)
    return best


def shell(thickness, open_side="top", body=None):
    """Hollow the body out, leaving walls of the given thickness (mm). open_side: 'top', 'bottom',
    '+x', '-x', '+y', '-y' (that face is removed) or None (closed hollow body)."""
    target = body if body is not None else root.bRepBodies.item(0)
    entities = adsk.core.ObjectCollection.create()
    if open_side is None:
        entities.add(target)
    else:
        entities.add(_planar_face(target, open_side))
    shell_input = root.features.shellFeatures.createInput(entities, False)
    shell_input.insideThickness = _length(thickness)
    return _add(lambda: root.features.shellFeatures.add(shell_input), "shell",
                "The wall thickness must be smaller than half of the smallest size of the body.")


def mirror(feature, plane="YZ", offset=0):
    """Mirror a feature across a base plane moved by offset (mm) along its normal axis."""
    base, normal_axis_name = _base_plane(plane)
    if offset:
        normal = base.geometry.normal.asArray()[_AXES[normal_axis_name]]
        plane_input = root.constructionPlanes.createInput()
        plane_input.setByOffset(base, _length(offset if normal > 0 else -offset))
        base = root.constructionPlanes.add(plane_input)
    entities = adsk.core.ObjectCollection.create()
    entities.add(feature)
    mirror_input = root.features.mirrorFeatures.createInput(entities, base)
    return _add(lambda: root.features.mirrorFeatures.add(mirror_input), "mirror")


def circular_pattern(feature, count, axis="Z", angle=360):
    """Repeat a feature count times (the original included) around a model axis."""
    entities = adsk.core.ObjectCollection.create()
    entities.add(feature)
    patterns = root.features.circularPatternFeatures
    pattern_input = patterns.createInput(entities, _axis_entity(axis))
    pattern_input.quantity = adsk.core.ValueInput.createByReal(count)
    pattern_input.totalAngle = adsk.core.ValueInput.createByString("%s deg" % angle)
    return _add(lambda: patterns.add(pattern_input), "circular_pattern",
                "The copies rotate around the model axis through (0, 0, 0): the part must be centered on it.")


def rectangular_pattern(feature, count_x, spacing_x, count_y=1, spacing_y=0):
    """Repeat a feature in a grid along +X and +Y; spacing is the distance between copies (mm)."""
    entities = adsk.core.ObjectCollection.create()
    entities.add(feature)
    patterns = root.features.rectangularPatternFeatures
    pattern_input = patterns.createInput(entities, root.xConstructionAxis,
                                         adsk.core.ValueInput.createByReal(count_x), _length(spacing_x),
                                         adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    if count_y > 1:
        pattern_input.setDirectionTwo(root.yConstructionAxis, adsk.core.ValueInput.createByReal(count_y),
                                      _length(spacing_y))
    return _add(lambda: patterns.add(pattern_input), "rectangular_pattern",
                "All copies must stay on the body: they go along +X and +Y from the original.")


def _edge_kind(edge):
    geometry_type = edge.geometry.objectType
    if geometry_type.endswith("Line3D"):
        return "line"
    if geometry_type.endswith("Circle3D") or geometry_type.endswith("Arc3D"):
        return "circle"
    return "other"


def _range_mm(box, axis_index):
    return box.minPoint.asArray()[axis_index] * 10, box.maxPoint.asArray()[axis_index] * 10


def find_edges(kind=None, parallel_to=None, x=None, y=None, z=None, diameter=None, body=None):
    """Edges of the bodies that match every given filter:
    kind 'line' or 'circle'; parallel_to 'X'/'Y'/'Z' (straight edges along that axis);
    x/y/z: the whole edge lies at that coordinate (mm), e.g. z=15 for edges on a top face at 15 mm;
    diameter: circular edges of that diameter (mm); body: only this body."""
    bodies = [body] if body is not None else list(root.bRepBodies)
    result = []
    for each_body in bodies:
        for edge in each_body.edges:
            edge_kind = _edge_kind(edge)
            if kind is not None and edge_kind != kind:
                continue
            box = edge.boundingBox
            if parallel_to is not None:
                if edge_kind != "line":
                    continue
                axis_index = _AXES[parallel_to.upper()]
                start = edge.startVertex.geometry.asArray()
                end = edge.endVertex.geometry.asArray()
                along = [abs(end[i] - start[i]) for i in range(3)]
                if max(along) < 1e-9 or along.index(max(along)) != axis_index or sum(along) - along[axis_index] > 1e-6:
                    continue
            is_off_plane = False
            for axis_index, wanted in ((0, x), (1, y), (2, z)):
                if wanted is None:
                    continue
                low, high = _range_mm(box, axis_index)
                if abs(low - wanted) > 0.01 or abs(high - wanted) > 0.01:
                    is_off_plane = True
            if is_off_plane:
                continue
            if diameter is not None:
                if edge_kind != "circle" or abs(edge.geometry.radius * 20 - diameter) > 0.01:
                    continue
            result.append(edge)
    return result


def _edge_collection(edges):
    if not edges:
        raise ValueError("no edges given: find_edges() matched nothing, call describe_edges() to see the edges")
    collection = adsk.core.ObjectCollection.create()
    for edge in edges:
        collection.add(edge)
    return collection


def _edges_summary(edges):
    counts = {}
    for edge in edges:
        kind = _edge_kind(edge)
        if kind == "line":
            start = edge.startVertex.geometry.asArray()
            end = edge.endVertex.geometry.asArray()
            along = [abs(end[i] - start[i]) for i in range(3)]
            kind = "lines along " + "XYZ"[along.index(max(along))]
        else:
            kind += "s"
        counts[kind] = counts.get(kind, 0) + 1
    return "you selected %d edges: %s." % (len(edges), ", ".join("%d %s" % (n, k) for k, n in sorted(counts.items())))


def fillet(edges, radius):
    """Round the given edges with a radius (mm). Скругление."""
    fillets = root.features.filletFeatures
    fillet_input = fillets.createInput()
    fillet_input.addConstantRadiusEdgeSet(_edge_collection(edges), _length(radius), True)
    about = "r%s on %s" % (_fmt(radius), _edges_about(edges))
    feature = _add(lambda: fillets.add(fillet_input), "fillet",
                   _edges_summary(edges) + " Select only the edges the request names, e.g. find_edges(parallel_to='Z')"
                   " for the vertical corners of a plate; the radius must fit the faces next to the edges."
                   + _already_done_text("Fillet", "fillet"))
    _remember_about(feature, about)
    return feature


def _edges_about(edges):
    """Short words for what a fillet or chamfer was put on: '8 circles d6', '4 lines along Z', '12 lines'."""
    kinds = set(_edge_kind(edge) for edge in edges)
    if kinds == {"circle"}:
        diameters = sorted(set(round(edge.geometry.radius * 20, 3) for edge in edges))
        return "%d circles %s" % (len(edges), " ".join("d" + _fmt(diameter) for diameter in diameters))
    if kinds == {"line"}:
        axes = set()
        for edge in edges:
            start = edge.startVertex.geometry.asArray()
            end = edge.endVertex.geometry.asArray()
            along = [abs(end[i] - start[i]) for i in range(3)]
            axes.add("XYZ"[along.index(max(along))])
        if len(axes) == 1:
            return "%d lines along %s" % (len(edges), axes.pop())
        return "%d lines" % len(edges)
    return "%d edges" % len(edges)


def _remember_about(feature, text):
    """Keep what a feature did as an attribute: the timeline then says 'Fillet2 (r1 on 8 circles d6)',
    and remove() can find the step by its kind and diameter."""
    try:
        feature.attributes.add("fusion-agent", "about", text)
    except RuntimeError:
        pass


def _about_of(entity):
    try:
        attribute = entity.attributes.itemByName("fusion-agent", "about")
    except (RuntimeError, AttributeError):
        return ""
    if attribute is None:
        return ""
    return attribute.value


def _step_label(item):
    """A timeline step's name with what it did when that is known: 'Fillet2 (r1 on 8 circles d6)'."""
    about = _about_of(item.entity)
    if about:
        return "%s (%s)" % (item.name, about)
    return item.name


def _already_done_text(prefix, what):
    """When the timeline already holds such a feature, say so: the model re-runs a finished fillet."""
    names = [design.timeline.item(i).name for i in range(design.timeline.count)]
    done = [name for name in names if name.startswith(prefix)]
    if not done:
        return ""
    return (" The timeline already has %s: if that is the %s the request asks for, it is DONE, the edges are "
            "already rounded; do not run it again, run check() and answer." % (", ".join(done), what))


def chamfer(edges, distance):
    """Equal-distance chamfer of the given edges (mm). Фаска."""
    chamfers = root.features.chamferFeatures
    chamfer_input = chamfers.createInput2()
    chamfer_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(_edge_collection(edges), _length(distance), True)
    about = "%s mm on %s" % (_fmt(distance), _edges_about(edges))
    feature = _add(lambda: chamfers.add(chamfer_input), "chamfer",
                   _edges_summary(edges) + " Select only the edges the request names; the distance must fit the faces."
                   + _already_done_text("Chamfer", "chamfer"))
    _remember_about(feature, about)
    return feature


def find_circles(diameter=None):
    """Sketch circles of all sketches, optionally only those of the given diameter (mm)."""
    result = []
    for sketch in root.sketches:
        for each_circle in sketch.sketchCurves.sketchCircles:
            if diameter is None or abs(each_circle.radius * 20 - diameter) <= 0.01:
                result.append(each_circle)
    return result


def _circle_list(circles):
    if isinstance(circles, (list, tuple)):
        if not circles:
            raise ValueError("no circles given: find_circles() matched nothing, describe() lists the sketch circles")
        return list(circles)
    return [circles]


def set_diameter(circles, diameter):
    """Change the diameter (mm) of one sketch circle or of a list of them; the features built on them update."""
    for sketch_circle in _circle_list(circles):
        dimension = _diameter_dimension(sketch_circle)
        if dimension is not None:
            dimension.parameter.expression = "%s mm" % diameter
        else:
            sketch_circle.radius = diameter / 2 * MM
    design.computeAll()


def move_circle(sketch_circle, cx, cy):
    """Move a sketch circle so its center is at (cx, cy) in its plane (mm); the features update."""
    if isinstance(sketch_circle, (list, tuple)):
        if len(sketch_circle) != 1:
            raise ValueError("move_circle() moves one circle; pick it, e.g. find_circles(diameter=8)[0]")
        sketch_circle = sketch_circle[0]
    sketch = sketch_circle.parentSketch
    target = _point(sketch, cx, cy)
    center = sketch_circle.centerSketchPoint
    current = center.geometry
    was_fixed = center.isFixed
    center.isFixed = False
    center.move(adsk.core.Vector3D.create(target.x - current.x, target.y - current.y, 0))
    center.isFixed = was_fixed
    design.computeAll()


def set_parameter(name, value):
    """Change a feature dimension listed by describe(), e.g. set_parameter("d3", 8): lengths in mm,
    angles in degrees, counts as numbers. Everything built after it updates."""
    parameter = design.allParameters.itemByName(name)
    if parameter is None:
        raise ValueError("no parameter %r; describe() lists them" % name)
    unit = parameter.unit
    if unit in ("mm", "cm", "m", "in"):
        parameter.expression = "%s mm" % value
    elif unit == "deg":
        parameter.expression = "%s deg" % value
    else:
        parameter.expression = str(value)
    design.computeAll()
    comment = (' "%s"' % parameter.comment) if parameter.comment else ""
    holder = ""
    try:
        created_by = parameter.createdBy
        if created_by is not None:
            holder = " (held by %s" % created_by.name
            if getattr(created_by, "extentOne", None) is not None or created_by.objectType.endswith("ExtrudeFeature"):
                holder += ": the extrude distance, i.e. the thickness or height, not a sketch size"
            holder += ")"
    except Exception:
        holder = ""
    print("set_parameter: %s%s = %s%s" % (name, comment, parameter.expression, holder))
    state_summary()


_OPERATION_PREFIXES = {
    "fillet": "Fillet", "chamfer": "Chamfer", "shell": "Shell", "mirror": "Mirror",
    "circular_pattern": "C-Pattern", "rectangular_pattern": "R-Pattern", "thread": "Thread",
}


def check(size=None, diameters=None, volume=None, bodies=1, operations=None):
    """Compare the design with the numbers of the request and print CHECK OK or CHECK FAILED with reasons.
    size: the three overall dimensions in any order; diameters: every diameter the request names (of the
    part and of the holes); volume: expected volume in mm3 (0.5% tolerance); bodies: expected body count;
    operations: names the request asks for, e.g. ["chamfer"] for фаска, ["fillet"] for скругление."""
    found = _all_bodies()
    problems = []
    for operation in operations or []:
        prefix = _OPERATION_PREFIXES.get(operation)
        if prefix is None:
            continue
        names = [design.timeline.item(i).name for i in range(design.timeline.count)]
        if not any(name.startswith(prefix) for name in names):
            problems.append("the timeline has no %s" % operation)
    duplicate = False
    if len(found) != bodies:
        problems.append("there are %d bodies, expected %d" % (len(found), bodies))
        seen = set()
        for body in found:
            box = body.boundingBox
            key = (round(body.volume, 6),) + tuple(round(v, 4) for v in box.minPoint.asArray() + box.maxPoint.asArray())
            if key in seen:
                problems.append("two bodies are identical: the part was built twice; start the script with clear()")
                duplicate = True
                break
            seen.add(key)
    if (bodies == 1 and _BODIES_BEFORE_SCRIPT > 0 and _user_steps() == 0 and not _SCRIPT_CLEARED
            and _NEW_BASE_BODIES > 0):
        problems.append("the design already had %d bodies before this script and this script made a new base "
                        "body without clear(): the earlier attempt is still inside the part; start the script "
                        "with clear() and build the whole part again" % _BODIES_BEFORE_SCRIPT)
    if len(found) != bodies:
        if not duplicate and len(found) > bodies and _BODIES_BEFORE_SCRIPT > 0 and _user_steps() == 0:
            problems.append("%d of them were already in the design before this script: if that is your earlier "
                            "attempt, start the script with clear() and build the whole part again; if the new "
                            "piece belongs to that body, build it with operation=\"join\"" % _BODIES_BEFORE_SCRIPT)
    low = [None, None, None]
    high = [None, None, None]
    all_diameters = set()
    total_volume = 0.0
    for body in found:
        box = body.boundingBox
        for i in range(3):
            body_low = box.minPoint.asArray()[i] * 10
            body_high = box.maxPoint.asArray()[i] * 10
            low[i] = body_low if low[i] is None else min(low[i], body_low)
            high[i] = body_high if high[i] is None else max(high[i], body_high)
        for face in body.faces:
            if isinstance(face.geometry, adsk.core.Cylinder):
                all_diameters.add(round(face.geometry.radius * 20, 3))
        total_volume += body.volume * 1000
    actual_size = sorted(high[i] - low[i] for i in range(3)) if found else []
    notes = []
    if size is not None and found:
        wanted_size = sorted(size)
        if any(abs(a - b) > 0.01 for a, b in zip(actual_size, wanted_size)):
            # A size given as the disk diameter is accepted when the rim cutouts explain the difference.
            for disk_diameter, across in _RIM_SIZES.items():
                for index, value in enumerate(wanted_size):
                    if abs(value - disk_diameter) > 0.01:
                        continue
                    candidate = sorted(wanted_size[:index] + [across] + wanted_size[index + 1:])
                    if all(abs(a - b) <= 0.01 for a, b in zip(actual_size, candidate)):
                        notes.append("size %s is %s across the rim cutouts: accepted" % (_fmt(value), _fmt(across)))
                        wanted_size = candidate
                        break
        if any(abs(a - b) > 0.01 for a, b in zip(actual_size, wanted_size)):
            # A nominal size (a gear's outer diameter, a thread's nominal diameter) is accepted for what it measures.
            remaining = list(actual_size)
            matched = []
            for value in wanted_size:
                exact = [a for a in remaining if abs(a - value) <= 0.01]
                if exact:
                    remaining.remove(exact[0])
                    matched.append(exact[0])
                    continue
                for measured, why in _NOMINAL_SIZES.get(round(value, 6), []):
                    near = [a for a in remaining if abs(a - measured) <= 0.01]
                    if near:
                        remaining.remove(near[0])
                        matched.append(near[0])
                        notes.append("size %s is %s: accepted" % (_fmt(value), why))
                        break
            if len(matched) == len(wanted_size):
                wanted_size = sorted(matched)
        if any(abs(a - b) > 0.01 for a, b in zip(actual_size, wanted_size)):
            problems.append("size is %s mm, expected %s" % (
                " x ".join(_fmt(v) for v in actual_size), " x ".join(_fmt(v) for v in wanted_size)))
    if diameters is not None:
        footprint = sorted(high[i] - low[i] for i in range(2)) if found else []
        for wanted in diameters:
            if not any(abs(wanted - d) <= 0.01 for d in all_diameters):
                if any(abs(wanted - size) < 1e-6 for size in _SPLINE_SIZES):
                    notes.append("%s is a spline, gear, hexagon or thread size, not a plain round face: accepted" % _fmt(wanted))
                elif any(abs(2 * wanted - d) <= 0.01 for d in all_diameters) and any(
                        design.timeline.item(i).name.startswith("Fillet") for i in range(design.timeline.count)):
                    notes.append("%s is the fillet radius; its round face has diameter %s: accepted" % (
                        _fmt(wanted), _fmt(2 * wanted)))
                elif len(footprint) == 2 and all(abs(wanted - f) <= 0.01 for f in footprint):
                    problems.append("no cylindrical face of diameter %s: the part is a square %s x %s block, "
                                    "not a disk; a диск / круг of diameter D is cylinder(D, thickness), not "
                                    "box(D, D, thickness)" % (_fmt(wanted), _fmt(footprint[0]), _fmt(footprint[1])))
                else:
                    problems.append("no cylindrical face of diameter %s (found %s)" % (_fmt(wanted), sorted(all_diameters)))
    if volume is not None and abs(total_volume - volume) > 0.005 * volume:
        problems.append("volume is %s mm3, expected %s" % (_fmt(total_volume), _fmt(volume)))
        if _STEP_VOLUMES:
            steps = ", ".join("%s %s%s" % (name, "+" if delta >= 0 else "", _fmt(delta)) for name, delta in _STEP_VOLUMES[-8:])
            problems.append("the part was built as: %s = %s; compare your formula with these numbers term by term "
                            "(each extrude's own size times its area, minus what overlapped)" % (steps, _fmt(total_volume)))
        if len(problems) == 1:
            problems.append("only the volume differs: first recheck your volume formula (box a*b*c, "
                            "cylinder pi*r*r*h, hole pi*r*r*L where L is the length of material the hole "
                            "goes through, r = diameter / 2, a groove or ring of width w between the outer "
                            "radius R and the inner radius r is pi*(R*R - r*r)*w, a slot with round ends of "
                            "length L and width w through thickness t is ((L - w)*w + pi*(w/2)**2)*t); "
                            "if the formula is right, the part is wrong, "
                            "most often a hole or a cut is in the wrong place, partly outside the part "
                            "(compare its position with the box from ... to ... of the body); if you are not "
                            "sure about the formula, run check() again without volume")
    summary = "bodies %d, size %s mm, cylinder diameters %s, volume %s mm3" % (
        len(found), " x ".join(_fmt(v) for v in actual_size), sorted(all_diameters), _fmt(total_volume))
    if notes:
        summary = summary + ". Notes: " + "; ".join(notes)
    if problems:
        print("CHECK FAILED: " + "; ".join(problems) + ". Measured: " + summary)
    else:
        print("CHECK OK: " + summary)


def state_summary():
    """One line about the design: bodies, size, cylinder diameters, volume and the timeline."""
    found = _all_bodies()
    low = [None, None, None]
    high = [None, None, None]
    diameters = set()
    volume = 0.0
    for body in found:
        box = body.boundingBox
        for i in range(3):
            body_low = box.minPoint.asArray()[i] * 10
            body_high = box.maxPoint.asArray()[i] * 10
            low[i] = body_low if low[i] is None else min(low[i], body_low)
            high[i] = body_high if high[i] is None else max(high[i], body_high)
        for face in body.faces:
            if isinstance(face.geometry, adsk.core.Cylinder):
                diameters.add(round(face.geometry.radius * 20, 3))
        volume += body.volume * 1000
    size = " x ".join(_fmt(high[i] - low[i]) for i in range(3)) if found else "-"
    steps = [_step_label(design.timeline.item(i)) for i in range(design.timeline.count)]
    print("State of the design now: bodies %d, size %s mm, cylinder diameters %s, volume %s mm3, timeline: %s" % (
        len(found), size, sorted(diameters), _fmt(volume), ", ".join(steps) or "empty"))


def _user_steps():
    """How many first timeline steps are the user's own part (the design was opened by the user)."""
    attribute = design.attributes.itemByName("fusion-agent", "user_steps")
    if attribute is None:
        return 0
    try:
        return int(attribute.value)
    except ValueError:
        return 0


def undo(steps=1):
    """Delete the last steps of the timeline (each sketch, plane and feature is one step, see describe())."""
    timeline = design.timeline
    own_steps = timeline.count - _user_steps()
    if own_steps < 1:
        raise ValueError("there are no steps of yours to undo: the timeline is the user's own part; "
                         "change it with set_parameter() or add features")
    if steps < 1 or steps > own_steps:
        raise ValueError("steps must be from 1 to %d: the first %d steps are the user's own part" % (
            own_steps, _user_steps()))
    removed = [timeline.item(i).name for i in range(timeline.count - steps, timeline.count)]
    timeline.markerPosition = timeline.count - steps
    timeline.deleteAllAfterMarker()
    print("undo: removed %s." % ", ".join(removed))
    state_summary()


def remove(step, diameter=None):
    """Delete ONE step of the timeline wherever it is, the steps after it stay (undo() takes only the last ones):
    remove("Fillet2") by its name, or by its kind: remove("fillet", diameter=6) the fillet on the edges of
    diameter 6 (убери скругление у отверстий), remove("chamfer"), remove("thread", diameter=8).
    The timeline in the state names every fillet, chamfer and thread with what it did."""
    timeline = design.timeline
    items = [timeline.item(i) for i in range(timeline.count)]
    wanted = str(step).strip()
    matches = [item for item in items if item.name.lower() == wanted.lower()]
    is_by_kind = not matches
    if is_by_kind:
        matches = [item for item in items if item.name.lower().startswith(wanted.lower())]
        if diameter is not None:
            token = "d" + _fmt(diameter)
            matches = [item for item in matches if token in _about_of(item.entity).split()]
    if not matches:
        raise ValueError("no step %r%s in the timeline: %s" % (
            wanted, "" if diameter is None else " with diameter %s" % _fmt(diameter),
            ", ".join(_step_label(item) for item in items) or "empty"))
    if len(matches) > 1:
        raise ValueError("%d steps match %r: %s. Give the name of the one to remove, or its diameter" % (
            len(matches), wanted, ", ".join(_step_label(item) for item in matches)))
    item = matches[0]
    if item.index < _user_steps():
        raise ValueError("%s is a step of the user's own part: it stays; change it with set_parameter()" % item.name)
    label = _step_label(item)
    entity = item.entity
    if entity is None or not hasattr(entity, "deleteMe") or not entity.deleteMe():
        raise ValueError("Fusion could not delete %s; undo() the steps up to it and build again" % label)
    print("remove: deleted %s." % label)
    for i in range(design.timeline.count):
        left = design.timeline.item(i)
        if left.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
            print("  PROBLEM in %s after the removal: %s" % (left.name, left.errorOrWarningMessage))
    state_summary()


def clear():
    """Delete everything in the design, to build it again from scratch."""
    if _user_steps() > 0:
        raise ValueError("clear() would delete the user's own part: this design was opened by the user. "
                         "Change it with set_parameter() (describe() lists the parameters) or add features; "
                         "undo() removes only the steps you added")
    global _SCRIPT_CLEARED
    _SCRIPT_CLEARED = True
    timeline = design.timeline
    timeline.moveToBeginning()
    timeline.deleteAllAfterMarker()


def _fmt(value):
    return ("%.3f" % value).rstrip("0").rstrip(".")


def _xyz(values):
    return "(" + ", ".join(_fmt(value) for value in values) + ")"


def describe_edges(body=None, limit=60):
    """Print the edges of the bodies: index, kind, ends or center and diameter (mm)."""
    bodies = [body] if body is not None else list(root.bRepBodies)
    count = 0
    for each_body in bodies:
        print("edges of %s:" % each_body.name)
        for index, edge in enumerate(each_body.edges):
            if count >= limit:
                print("  ... more edges not shown")
                return
            count += 1
            kind = _edge_kind(edge)
            if kind == "line":
                start = [value * 10 for value in edge.startVertex.geometry.asArray()]
                end = [value * 10 for value in edge.endVertex.geometry.asArray()]
                print("  %d line %s -> %s" % (index, _xyz(start), _xyz(end)))
            elif kind == "circle":
                center = [value * 10 for value in edge.geometry.center.asArray()]
                print("  %d circle center %s diameter %s" % (index, _xyz(center), _fmt(edge.geometry.radius * 20)))
            else:
                box = edge.boundingBox
                print("  %d %s from %s to %s" % (index, edge.geometry.objectType.split("::")[-1],
                                                 _xyz([v * 10 for v in box.minPoint.asArray()]),
                                                 _xyz([v * 10 for v in box.maxPoint.asArray()])))


def _all_bodies():
    """The bodies of the root component and of the components in it (as occurrence proxies)."""
    found = list(root.bRepBodies)
    for occurrence in root.allOccurrences:
        for body in occurrence.bRepBodies:
            found.append(body)
    return found


def _parameter_value(parameter):
    """The value of a parameter in mm, degrees or as a plain number."""
    if parameter.unit in ("mm", "cm", "m", "in", "ft"):
        return "%s mm" % _fmt(parameter.value * 10)
    if parameter.unit == "deg":
        return "%s deg" % _fmt(math.degrees(parameter.value))
    return _fmt(parameter.value)


def _parameter_text(parameter):
    """name=expression, plus the value when the expression is not a plain number, plus the comment."""
    expression = parameter.expression
    text = "%s=%s" % (parameter.name, expression)
    plain = expression.replace("mm", "").replace("deg", "").strip()
    try:
        float(plain)
    except ValueError:
        text += " (= %s)" % _parameter_value(parameter)
    if parameter.comment:
        text += ' "%s"' % parameter.comment
    return text


def _parameter_owner(parameter):
    """The name of the feature, sketch or plane that a model parameter belongs to, or None."""
    owner = parameter.createdBy
    if owner is None:
        return None
    name = getattr(owner, "name", None)
    if name:
        return name
    sketch = getattr(owner, "parentSketch", None)
    if sketch is not None:
        return sketch.name
    return None


def _extrude_axis(entity):
    """The axis X, Y or Z of an extrude from a sketch on a main plane, else None: tells the model that the
    extrude's distance is the size along that axis (a plate extruded along Z: d1 is its thickness)."""
    extrude = adsk.fusion.ExtrudeFeature.cast(entity)
    if extrude is None:
        return None
    try:
        profile = extrude.profile
        collection = adsk.core.ObjectCollection.cast(profile)
        if collection is not None:
            profile = collection.item(0)
        sketch = adsk.fusion.Profile.cast(profile).parentSketch
        normal = sketch.transform.getAsCoordinateSystem()[3]
    except Exception:
        return None
    for name, value in (("X", normal.x), ("Y", normal.y), ("Z", normal.z)):
        if abs(abs(value) - 1) < 1e-6:
            return name
    return None


def _body_text(body, label):
    box = body.boundingBox
    low = [value * 10 for value in box.minPoint.asArray()]
    high = [value * 10 for value in box.maxPoint.asArray()]
    size = [high[i] - low[i] for i in range(3)]
    diameters = set()
    for face in body.faces:
        if isinstance(face.geometry, adsk.core.Cylinder):
            diameters.add(round(face.geometry.radius * 20, 3))
    text = "  %s: volume %s mm3, size %s mm, box from %s to %s, faces %d, cylinder diameters %s" % (
        label, _fmt(body.volume * 1000), " x ".join(_fmt(value) for value in size),
        _xyz(low), _xyz(high), body.faces.count, sorted(diameters))
    if body.material is not None:
        text += ", material %s, mass %s g" % (body.material.name, _fmt(body.physicalProperties.mass * 1000))
    return text


def describe():
    """Print what is in the design: bodies with volume, box, cylinder diameters (mm), material and mass;
    user parameters; sketches; the timeline with the dimensions of every step."""
    body_lines = []
    for body in root.bRepBodies:
        body_lines.append(_body_text(body, body.name))
    for occurrence in root.allOccurrences:
        for body in occurrence.bRepBodies:
            body_lines.append(_body_text(body, "%s (component %s)" % (body.name, occurrence.component.name)))
    print("bodies: %d" % len(body_lines))
    for line in body_lines[:20]:
        print(line)
    if len(body_lines) > 20:
        print("  ... %d more bodies not shown" % (len(body_lines) - 20))

    user_parameters = [design.userParameters.item(i) for i in range(design.userParameters.count)]
    if user_parameters:
        texts = [_parameter_text(parameter) for parameter in user_parameters[:40]]
        print("  user parameters: " + "; ".join(texts))

    sketch_lines = []
    is_users_design = _user_steps() > 0
    for component in design.allComponents:
        for sketch in component.sketches:
            circles = []
            for each_circle in sketch.sketchCurves.sketchCircles:
                center = [value * 10 for value in each_circle.worldGeometry.center.asArray()]
                circles.append("d%s at %s" % (_fmt(each_circle.radius * 20), _xyz(center)))
            lines = sketch.sketchCurves.sketchLines.count
            name = sketch.name if component == root else "%s/%s" % (component.name, sketch.name)
            text = "  sketch %s: %d lines, %d circles" % (name, lines, len(circles))
            if circles:
                text += ": " + "; ".join(circles[:12])
            if is_users_design and sketch.sketchDimensions.count == 0:
                # A sketch the user drew without sizes: no parameter holds them, so say how to change them.
                text += " (no dimensions: change its sizes with material, box join or cut)"
            sketch_lines.append(text)
    for line in sketch_lines[:15]:
        print(line)
    if len(sketch_lines) > 15:
        print("  ... %d more sketches not shown" % (len(sketch_lines) - 15))

    parameters_by_owner = {}
    for parameter in design.allParameters:
        model_parameter = adsk.fusion.ModelParameter.cast(parameter)
        if model_parameter is None:
            continue
        if model_parameter.role in ("TaperAngle", "TangencyWeight", "ExtraOffset"):
            continue
        owner = _parameter_owner(model_parameter)
        if owner is None:
            continue
        parameters_by_owner.setdefault(owner, []).append(_parameter_text(model_parameter))
    steps = []
    for i in range(design.timeline.count):
        item = design.timeline.item(i)
        label = _step_label(item)
        axis = _extrude_axis(item.entity)
        if axis is not None:
            label += " (along %s)" % axis
        owner_parameters = parameters_by_owner.get(item.name)
        if owner_parameters:
            steps.append("%s [%s]" % (label, ", ".join(owner_parameters[:12])))
        else:
            steps.append(label)
        if item.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
            print("  PROBLEM in %s: %s" % (item.name, item.errorOrWarningMessage))
    if len(steps) > 80:
        steps = ["(%d first steps not shown)" % (len(steps) - 80)] + steps[-80:]
    print("  timeline (%d steps): %s" % (design.timeline.count, ", ".join(steps)))
    if _user_steps() > 0:
        print("  the user opened this design: its first %d timeline steps are the user's own part" % _user_steps())
'''
