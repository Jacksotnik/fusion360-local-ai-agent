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
    XY at z=offset, XZ at y=offset, YZ at x=offset."""
    base, normal_axis_name = _base_plane(plane)
    if offset:
        normal = base.geometry.normal.asArray()[_AXES[normal_axis_name]]
        signed = offset if normal > 0 else -offset
        plane_input = root.constructionPlanes.createInput()
        plane_input.setByOffset(base, _length(signed))
        base = root.constructionPlanes.add(plane_input)
    return root.sketches.add(base)


def rect(sketch, x1, y1, x2, y2):
    """Rectangle by two opposite corners (mm, plane coordinates)."""
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(_point(sketch, x1, y1), _point(sketch, x2, y2))


def rect_center(sketch, cx, cy, width, height):
    """Rectangle by its center and size (mm)."""
    rect(sketch, cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)


def circle(sketch, cx, cy, diameter):
    """Circle by center and DIAMETER (mm)."""
    return sketch.sketchCurves.sketchCircles.addByCenterRadius(_point(sketch, cx, cy), diameter / 2 * MM)


def slot(sketch, cx, cy, length, width, angle=0):
    """Slot with rounded ends: center, overall length end to end, width (mm); angle in degrees from +u."""
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


def extrude(sketch, distance, operation="new", symmetric=False):
    """Extrude the solid regions of the sketch by distance mm. Positive goes toward +Z for an XY
    sketch (+Y for XZ, +X for YZ), negative the other way. symmetric=True: distance is the total
    length, centered on the sketch plane. operation: 'new', 'join', 'cut' or 'intersect'."""
    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(solid_profiles(sketch), _OPERATIONS[operation])
    if symmetric:
        extrude_input.setSymmetricExtent(_length(abs(distance)), True)
    else:
        extent = adsk.fusion.DistanceExtentDefinition.create(_length(abs(distance)))
        extrude_input.setOneSideExtent(extent, _direction_sign(sketch, distance))
    return _add(lambda: extrudes.add(extrude_input), "extrude (%s)" % operation,
                "For join/cut/intersect the sketch shapes must overlap the body; check positions with describe().")


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
    return _add(lambda: extrudes.add(extrude_input), "cut",
                "There is no material under the sketch shapes. If this cut was already made by an earlier "
                "script, it is done: look at the current state. Otherwise check the positions.")


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


def box(size_x, size_y, size_z, corner=None, base=None, operation="new", center=None, corner_radius=None):
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
    sketch = new_sketch("XY", offset=z)
    rect(sketch, x, y, x + size_x, y + size_y)
    feature = extrude(sketch, size_z, operation=operation)
    if corner_radius:
        corners = []
        for corner_x in (x, x + size_x):
            for corner_y in (y, y + size_y):
                corners.extend(find_edges(parallel_to="Z", x=corner_x, y=corner_y))
        fillet(corners, corner_radius)
    return feature


def cylinder(diameter, length, base=None, axis="Z", operation="new", center=None):
    """Cylinder whose bottom circle is centered at base=(x, y, z); it grows by length along +axis."""
    _no_center(center, "cylinder")
    base = _xyz_argument(base, "base", "cylinder")
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    sketch = new_sketch(plane, offset=base[n_index])
    circle(sketch, base[u_index], base[v_index], diameter)
    return extrude(sketch, length, operation=operation)


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


def drill(x, y, z, diameter, axis=None, depth=None):
    """Round hole whose axis passes through the point (x, y, z) along axis 'X', 'Y' or 'Z' (required:
    a default made the model drill side holes from the top).
    depth=None: through everything. With a depth, (x, y, z) is the entry point on the surface and
    the hole goes into the body."""
    if axis is None:
        raise ValueError('drill() needs axis="Z" (hole from the top or bottom) or axis="X" / "Y" (hole from a side)')
    plane, (u_index, v_index, n_index) = _axis_plane(axis)
    point = (x, y, z)
    sketch = new_sketch(plane, offset=point[n_index])
    circle(sketch, point[u_index], point[v_index], diameter)
    if depth is None:
        return cut(sketch)
    direction = _through_all_direction(sketch)
    _, _, normal_component = _sketch_frame(sketch)
    goes_positive = (direction == adsk.fusion.ExtentDirections.PositiveExtentDirection) == (normal_component > 0)
    return extrude(sketch, depth if goes_positive else -depth, operation="cut")


def holes(points, diameter, plane="XY", offset=0, depth=None):
    """Round holes of the given DIAMETER at (u, v) points of a plane; depth=None means through all."""
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
    return _add(lambda: fillets.add(fillet_input), "fillet",
                _edges_summary(edges) + " Select only the edges the request names, e.g. find_edges(parallel_to='Z')"
                " for the vertical corners of a plate; the radius must fit the faces next to the edges.")


def chamfer(edges, distance):
    """Equal-distance chamfer of the given edges (mm). Фаска."""
    chamfers = root.features.chamferFeatures
    chamfer_input = chamfers.createInput2()
    chamfer_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(_edge_collection(edges), _length(distance), True)
    return _add(lambda: chamfers.add(chamfer_input), "chamfer",
                _edges_summary(edges) + " Select only the edges the request names; the distance must fit the faces.")


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
    current = sketch_circle.centerSketchPoint.geometry
    sketch_circle.centerSketchPoint.move(adsk.core.Vector3D.create(target.x - current.x, target.y - current.y, 0))
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


_OPERATION_PREFIXES = {
    "fillet": "Fillet", "chamfer": "Chamfer", "shell": "Shell", "mirror": "Mirror",
    "circular_pattern": "C-Pattern", "rectangular_pattern": "R-Pattern",
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
    if len(found) != bodies:
        problems.append("there are %d bodies, expected %d" % (len(found), bodies))
        seen = set()
        for body in found:
            box = body.boundingBox
            key = (round(body.volume, 6),) + tuple(round(v, 4) for v in box.minPoint.asArray() + box.maxPoint.asArray())
            if key in seen:
                problems.append("two bodies are identical: the part was built twice; start the script with clear()")
                break
            seen.add(key)
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
    if size is not None and found:
        wanted_size = sorted(size)
        if any(abs(a - b) > 0.01 for a, b in zip(actual_size, wanted_size)):
            problems.append("size is %s mm, expected %s" % (
                " x ".join(_fmt(v) for v in actual_size), " x ".join(_fmt(v) for v in wanted_size)))
    if diameters is not None:
        for wanted in diameters:
            if not any(abs(wanted - d) <= 0.01 for d in all_diameters):
                problems.append("no cylindrical face of diameter %s (found %s)" % (_fmt(wanted), sorted(all_diameters)))
    if volume is not None and abs(total_volume - volume) > 0.005 * volume:
        problems.append("volume is %s mm3, expected %s" % (_fmt(total_volume), _fmt(volume)))
        if len(problems) == 1:
            problems.append("only the volume differs: first recheck your volume formula (box a*b*c, "
                            "cylinder pi*r*r*h, hole pi*r*r*L where L is the length of material the hole "
                            "goes through, r = diameter / 2); if the formula is right, the part is wrong, "
                            "most often a hole or a cut is in the wrong place, partly outside the part "
                            "(compare its position with the box from ... to ... of the body); if you are not "
                            "sure about the formula, run check() again without volume")
    summary = "bodies %d, size %s mm, cylinder diameters %s, volume %s mm3" % (
        len(found), " x ".join(_fmt(v) for v in actual_size), sorted(all_diameters), _fmt(total_volume))
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
    steps = [design.timeline.item(i).name for i in range(design.timeline.count)]
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
    timeline.markerPosition = timeline.count - steps
    timeline.deleteAllAfterMarker()


def clear():
    """Delete everything in the design, to build it again from scratch."""
    if _user_steps() > 0:
        raise ValueError("clear() would delete the user's own part: this design was opened by the user. "
                         "Change it with set_parameter() (describe() lists the parameters) or add features; "
                         "undo() removes only the steps you added")
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
        label = item.name
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
