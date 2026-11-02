"""Builders of "the user's own model" for the task sets cases/user_models_*.json.

The code below runs inside Fusion after the CAD helper prelude (so `design`, `root`, `MM`, `adsk`, `math`
are defined). It builds parts the way a person does in the Fusion UI, not with the app's helpers:
sketches held by dimensions, user parameters, features that refer to them, a component, a fillet feature.
"""

PRELUDE = r'''
_NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
_JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
_CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def _p(x_mm, y_mm):
    return adsk.core.Point3D.create(x_mm * MM, y_mm * MM, 0)


def _user_parameter(name, expression, comment):
    design.userParameters.add(name, adsk.core.ValueInput.createByString(expression), "mm", comment)


def _dimension_line(sketch, line, expression):
    start = line.startSketchPoint.geometry
    end = line.endSketchPoint.geometry
    text = adsk.core.Point3D.create((start.x + end.x) / 2 + 0.4, (start.y + end.y) / 2 + 0.4, 0)
    dimension = sketch.sketchDimensions.addDistanceDimension(
        line.startSketchPoint, line.endSketchPoint,
        adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, text)
    dimension.parameter.expression = expression


def _rectangle_at_origin(sketch, size_x_mm, size_y_mm, x_expression, y_expression):
    lines = sketch.sketchCurves.sketchLines.addTwoPointRectangle(_p(0, 0), _p(size_x_mm, size_y_mm))
    along_x = None
    along_y = None
    for line in lines:
        start = line.startSketchPoint.geometry
        end = line.endSketchPoint.geometry
        if along_x is None and abs(start.y - end.y) < 1e-9:
            along_x = line
        if along_y is None and abs(start.x - end.x) < 1e-9:
            along_y = line
    for line in lines:
        if line.startSketchPoint.geometry.distanceTo(adsk.core.Point3D.create(0, 0, 0)) < 1e-9:
            sketch.geometricConstraints.addCoincident(line.startSketchPoint, sketch.originPoint)
            break
    _dimension_line(sketch, along_x, x_expression)
    _dimension_line(sketch, along_y, y_expression)


def _circle(sketch, cx_mm, cy_mm, diameter_mm, diameter_expression, cx_expression=None, cy_expression=None):
    """A circle held by a diameter dimension; centered on the origin unless position expressions are given."""
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(_p(cx_mm, cy_mm), diameter_mm / 2 * MM)
    diameter = sketch.sketchDimensions.addDiameterDimension(circle, _p(cx_mm + diameter_mm, cy_mm + diameter_mm))
    diameter.parameter.expression = diameter_expression
    if cx_expression is None:
        sketch.geometricConstraints.addCoincident(circle.centerSketchPoint, sketch.originPoint)
        return circle
    horizontal = sketch.sketchDimensions.addDistanceDimension(
        sketch.originPoint, circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation, _p(cx_mm / 2, -8))
    horizontal.parameter.expression = cx_expression
    vertical = sketch.sketchDimensions.addDistanceDimension(
        sketch.originPoint, circle.centerSketchPoint,
        adsk.fusion.DimensionOrientations.VerticalDimensionOrientation, _p(-8, cy_mm / 2))
    vertical.parameter.expression = cy_expression
    return circle


def _extrude(component, sketch, expression, operation, name=None):
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(sketch.profiles.item(0), operation)
    extrude_input.setDistanceExtent(False, adsk.core.ValueInput.createByString(expression))
    feature = extrudes.add(extrude_input)
    if name:
        feature.name = name
    return feature


def _sketch(component, plane, name=None):
    sketch = component.sketches.add(plane)
    if name:
        sketch.name = name
    return sketch


def build_user_plate():
    """Plate 80 x 50 x 6 with a centered hole 8, everything driven by user parameters."""
    _user_parameter("Length", "80 mm", "plate length")
    _user_parameter("Width", "50 mm", "plate width")
    _user_parameter("Thickness", "6 mm", "plate thickness")
    _user_parameter("HoleD", "8 mm", "mounting hole diameter")
    outline = _sketch(root, root.xYConstructionPlane, "Plate outline")
    _rectangle_at_origin(outline, 80, 50, "Length", "Width")
    _extrude(root, outline, "Thickness", _NEW, "Plate")
    hole = _sketch(root, root.xYConstructionPlane, "Hole sketch")
    _circle(hole, 40, 25, 8, "HoleD", "Length / 2", "Width / 2")
    _extrude(root, hole, "Thickness", _CUT, "Mounting hole")


def build_bracket_component():
    """L bracket inside the component "Bracket": base 60 x 30 x 5, wall 5 thick, total height 40.
    Only sketch and feature dimensions, default names, no user parameters."""
    occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    component = occurrence.component
    component.name = "Bracket"
    base = _sketch(component, component.xYConstructionPlane)
    _rectangle_at_origin(base, 60, 30, "60 mm", "30 mm")
    _extrude(component, base, "5 mm", _NEW)
    wall = _sketch(component, component.xYConstructionPlane)
    _rectangle_at_origin(wall, 5, 30, "5 mm", "30 mm")
    _extrude(component, wall, "40 mm", _JOIN)


def build_user_flange():
    """Flange 60 x 8 with a hub 30 x 20 on top and a bore 12 through both, driven by user parameters."""
    _user_parameter("FlangeD", "60 mm", "flange diameter")
    _user_parameter("FlangeT", "8 mm", "flange thickness")
    _user_parameter("HubD", "30 mm", "hub diameter")
    _user_parameter("HubH", "20 mm", "hub height above the flange")
    _user_parameter("BoreD", "12 mm", "bore diameter")
    flange = _sketch(root, root.xYConstructionPlane, "Flange sketch")
    _circle(flange, 0, 0, 60, "FlangeD")
    _extrude(root, flange, "FlangeT", _NEW, "Flange")
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByString("FlangeT"))
    hub_plane = root.constructionPlanes.add(plane_input)
    hub_plane.name = "Hub plane"
    hub = _sketch(root, hub_plane, "Hub sketch")
    _circle(hub, 0, 0, 30, "HubD")
    _extrude(root, hub, "HubH", _JOIN, "Hub")
    bore = _sketch(root, root.xYConstructionPlane, "Bore sketch")
    _circle(bore, 0, 0, 12, "BoreD")
    _extrude(root, bore, "FlangeT + HubH", _CUT, "Bore")


def build_rounded_block():
    """Block 70 x 40 x 25 with its four vertical edges rounded r 4 by a fillet feature; default names."""
    outline = _sketch(root, root.xYConstructionPlane)
    _rectangle_at_origin(outline, 70, 40, "70 mm", "40 mm")
    block = _extrude(root, outline, "25 mm", _NEW)
    edges = adsk.core.ObjectCollection.create()
    for edge in block.bodies.item(0).edges:
        start = edge.startVertex.geometry
        end = edge.endVertex.geometry
        if abs(start.x - end.x) < 1e-9 and abs(start.y - end.y) < 1e-9:
            edges.add(edge)
    fillets = root.features.filletFeatures
    fillet_input = fillets.createInput()
    fillet_input.addConstantRadiusEdgeSet(edges, adsk.core.ValueInput.createByString("4 mm"), True)
    fillets.add(fillet_input)
'''
