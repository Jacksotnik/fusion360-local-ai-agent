"""Prelude for reference scripts of the graded tasks (runs inside Fusion before a case's reference body)."""

REFERENCE_PRELUDE = r'''
import adsk.core, adsk.fusion, math

MM = 0.1  # Fusion API length unit is cm

design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
root = design.rootComponent


def P(x_mm, y_mm):
    """Point on the XY plane (sketch coordinates equal model coordinates there)."""
    return adsk.core.Point3D.create(x_mm * MM, y_mm * MM, 0)


def Q(sketch, x_mm, z_mm):
    """Model point (x, 0, z) converted into the coordinates of a sketch on the XZ plane."""
    point = adsk.core.Point3D.create(x_mm * MM, 0, z_mm * MM)
    to_sketch = sketch.transform.copy()
    to_sketch.invert()
    point.transformBy(to_sketch)
    return point


def outer_profile(sketch):
    """The profile with the most loops: the solid region with all holes cut out."""
    best = None
    for profile in sketch.profiles:
        if best is None or profile.profileLoops.count > best.profileLoops.count:
            best = profile
    return best


def extrude(profile, distance_mm):
    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude_input.setDistanceExtent(False, adsk.core.ValueInput.createByString("%s mm" % distance_mm))
    return extrudes.add(extrude_input)


def revolve(profile, axis):
    revolves = root.features.revolveFeatures
    revolve_input = revolves.createInput(profile, axis, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    revolve_input.setAngleExtent(False, adsk.core.ValueInput.createByString("360 deg"))
    return revolves.add(revolve_input)


def _collection(edges):
    if not edges:
        raise ValueError("no edges selected")
    collection = adsk.core.ObjectCollection.create()
    for edge in edges:
        collection.add(edge)
    return collection


def fillet(edges, radius_mm):
    fillets = root.features.filletFeatures
    fillet_input = fillets.createInput()
    fillet_input.addConstantRadiusEdgeSet(_collection(edges), adsk.core.ValueInput.createByString("%s mm" % radius_mm), True)
    return fillets.add(fillet_input)


def chamfer(edges, distance_mm):
    chamfers = root.features.chamferFeatures
    chamfer_input = chamfers.createInput2()
    chamfer_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
        _collection(edges), adsk.core.ValueInput.createByString("%s mm" % distance_mm), True)
    return chamfers.add(chamfer_input)
'''
