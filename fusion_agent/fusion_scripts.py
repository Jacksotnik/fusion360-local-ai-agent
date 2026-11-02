"""Scripts the app itself runs in Fusion through the MCP execute tool (never the model's scripts).

Every design the app works in carries the attribute `fusion-agent/session=<id>`. The app refuses to
work in any other document and never saves or closes a document; only the self-test closes the
documents it created itself (they also carry `fusion-agent/selftest`).
"""
import json

ATTRIBUTE_GROUP = "fusion-agent"
SESSION_ATTRIBUTE = "session"
SELFTEST_ATTRIBUTE = "selftest"
# How many first timeline steps are the user's own part; the CAD helpers' undo() and clear() never delete them.
USER_STEPS_ATTRIBUTE = "user_steps"

ROUND_TRIP_MARKER = "fusion-agent round trip ok"

ROUND_TRIP_SCRIPT = '''def run(_context: str):
    print("%s")
''' % ROUND_TRIP_MARKER


def new_design_script(session_id, is_selftest=False):
    """Open a new empty parametric design, make it active and mark it; prints the document name."""
    selftest_line = ""
    if is_selftest:
        selftest_line = '    design.attributes.add("%s", "%s", "1")\n' % (ATTRIBUTE_GROUP, SELFTEST_ATTRIBUTE)
    return f'''import adsk.core, adsk.fusion

def run(_context: str):
    app = adsk.core.Application.get()
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    doc.activate()
    design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    design.attributes.add("{ATTRIBUTE_GROUP}", "{SESSION_ATTRIBUTE}", "{session_id}")
{selftest_line}    print(doc.name)
'''


# JSON about the active document: is it a design in the Design workspace, is it empty, whose is it.
ACTIVE_DOCUMENT_SCRIPT = f'''import adsk.core, adsk.fusion, json

def run(_context: str):
    app = adsk.core.Application.get()
    doc = app.activeDocument
    info = {{"has_document": doc is not None}}
    if doc is None:
        print(json.dumps(info))
        return
    info["name"] = doc.name
    info["is_saved"] = doc.dataFile is not None
    design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
    info["is_design"] = design is not None
    product = app.activeProduct
    info["workspace_product"] = product.productType if product is not None else ""
    info["is_design_workspace"] = adsk.fusion.Design.cast(product) is not None
    if design is not None:
        root = design.rootComponent
        bodies = root.bRepBodies.count
        for occurrence in root.allOccurrences:
            bodies += occurrence.bRepBodies.count
        info["bodies"] = bodies
        info["sketches"] = root.sketches.count
        info["occurrences"] = root.allOccurrences.count
        info["timeline"] = design.timeline.count if design.designType == adsk.fusion.DesignTypes.ParametricDesignType else 0
        info["is_parametric"] = design.designType == adsk.fusion.DesignTypes.ParametricDesignType
        attribute = design.attributes.itemByName("{ATTRIBUTE_GROUP}", "{SESSION_ATTRIBUTE}")
        info["session"] = attribute.value if attribute is not None else None
    print(json.dumps(info))
'''


def mark_active_script(session_id, records_user_steps=True):
    """Mark the active design as the session design (the user opened it for the app). In a design that
    no fusion-agent session has worked in yet, record how many timeline steps are already there: those
    are the user's own part. A design of an earlier session keeps what that session recorded, so the
    steps the app built there stay the app's (missing = 0)."""
    return f'''import adsk.core, adsk.fusion

def run(_context: str):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("the active document is not a design in the Design workspace")
    is_new_to_the_app = design.attributes.itemByName("{ATTRIBUTE_GROUP}", "{SESSION_ATTRIBUTE}") is None
    design.attributes.add("{ATTRIBUTE_GROUP}", "{SESSION_ATTRIBUTE}", "{session_id}")
    if {records_user_steps} and is_new_to_the_app:
        design.attributes.add("{ATTRIBUTE_GROUP}", "{USER_STEPS_ATTRIBUTE}", str(design.timeline.count))
    print(app.activeDocument.name)
'''


# The test runner builds "the user's own part" in a new design, then marks its steps as the user's.
MARK_USER_STEPS_SCRIPT = f'''import adsk.core, adsk.fusion

def run(_context: str):
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    design.attributes.add("{ATTRIBUTE_GROUP}", "{USER_STEPS_ATTRIBUTE}", str(design.timeline.count))
    print(design.timeline.count)
'''


def active_is_session_script(session_id):
    """Prints "session" when the active document is the session design, else "other"."""
    return f'''import adsk.core, adsk.fusion

def run(_context: str):
    app = adsk.core.Application.get()
    doc = app.activeDocument
    design = adsk.fusion.Design.cast(app.activeProduct) if doc is not None else None
    attribute = design.attributes.itemByName("{ATTRIBUTE_GROUP}", "{SESSION_ATTRIBUTE}") if design is not None else None
    print("session" if attribute is not None and attribute.value == "{session_id}" else "other")
'''


def activate_session_script(session_id):
    """Bring the session design to the front; prints its name, or "missing" when it was closed."""
    return f'''import adsk.core, adsk.fusion

def run(_context: str):
    app = adsk.core.Application.get()
    for doc in app.documents:
        design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        if design is None:
            continue
        attribute = design.attributes.itemByName("{ATTRIBUTE_GROUP}", "{SESSION_ATTRIBUTE}")
        if attribute is not None and attribute.value == "{session_id}":
            doc.activate()
            print(doc.name)
            return
    print("missing")
'''


def close_selftest_documents_script(session_id):
    """Close the unsaved documents the self-test created (both attributes present); nothing else."""
    return f'''import adsk.core, adsk.fusion

def run(_context: str):
    app = adsk.core.Application.get()
    marked = []
    for doc in app.documents:
        design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        if design is None or doc.dataFile is not None:
            continue
        session = design.attributes.itemByName("{ATTRIBUTE_GROUP}", "{SESSION_ATTRIBUTE}")
        selftest = design.attributes.itemByName("{ATTRIBUTE_GROUP}", "{SELFTEST_ATTRIBUTE}")
        if session is not None and session.value == "{session_id}" and selftest is not None:
            marked.append(doc)
    for doc in marked:
        doc.close(False)
    print("closed %d self-test documents" % len(marked))
'''


_VIEW_ORIENTATIONS = {
    "front": "FrontViewOrientation", "back": "BackViewOrientation", "top": "TopViewOrientation",
    "bottom": "BottomViewOrientation", "left": "LeftViewOrientation", "right": "RightViewOrientation",
    "iso-top-right": "IsoTopRightViewOrientation", "iso-top-left": "IsoTopLeftViewOrientation",
    "iso-bottom-right": "IsoBottomRightViewOrientation", "iso-bottom-left": "IsoBottomLeftViewOrientation",
}

VIEW_NAMES = list(_VIEW_ORIENTATIONS)


def fit_view_script(direction):
    """Turn the camera to a standard direction and zoom so the whole part fills the view."""
    orientation = _VIEW_ORIENTATIONS.get(direction, "IsoTopRightViewOrientation")
    return f'''import adsk.core

def run(_context: str):
    viewport = adsk.core.Application.get().activeViewport
    camera = viewport.camera
    camera.viewOrientation = adsk.core.ViewOrientations.{orientation}
    camera.isFitView = True
    viewport.camera = camera
    viewport.refresh()
'''


# Geometry summary used to see whether a turn changed the design: independent of how it was built.
SIGNATURE_SCRIPT = '''import adsk.core, adsk.fusion, json

def run(_context: str):
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    bodies = []
    for body in design.rootComponent.bRepBodies:
        bodies.append(body)
    for occurrence in design.rootComponent.allOccurrences:
        for body in occurrence.bRepBodies:
            bodies.append(body)
    unhealthy = []
    for i in range(design.timeline.count):
        item = design.timeline.item(i)
        if item.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
            unhealthy.append(item.name)
    result = {"bodies": [], "unhealthy": unhealthy}
    for body in bodies:
        box = body.boundingBox
        extents = sorted(round((box.maxPoint.asArray()[i] - box.minPoint.asArray()[i]) * 10, 3) for i in range(3))
        diameters = set()
        for face in body.faces:
            if isinstance(face.geometry, adsk.core.Cylinder):
                diameters.add(round(face.geometry.radius * 20, 2))
        result["bodies"].append({
            "volume_mm3": round(body.volume * 1000, 3),
            "extents_mm": extents,
            "cylinder_diameters_mm": sorted(diameters),
            "faces": body.faces.count,
        })
    print(json.dumps(result))
'''

# Timeline length and every parameter (model and user): enough to undo a turn (new steps and
# set_parameter edits).
SNAPSHOT_SCRIPT = '''import adsk.core, adsk.fusion, json

def run(_context: str):
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    parameters = {}
    for parameter in design.allParameters:
        parameters[parameter.name] = parameter.expression
    print(json.dumps({"timeline": design.timeline.count, "parameters": parameters}))
'''


def restore_snapshot_script(snapshot):
    """Delete the timeline steps added after the snapshot and put the parameters back."""
    snapshot_json = json.dumps(snapshot)
    return f'''import adsk.core, adsk.fusion, json

def run(_context: str):
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    snapshot = json.loads({snapshot_json!r})
    timeline = design.timeline
    removed = 0
    if timeline.count > snapshot["timeline"]:
        removed = timeline.count - snapshot["timeline"]
        timeline.markerPosition = snapshot["timeline"]
        timeline.deleteAllAfterMarker()
    restored = 0
    for name, expression in snapshot["parameters"].items():
        parameter = design.allParameters.itemByName(name)
        if parameter is not None and parameter.expression != expression:
            parameter.expression = expression
            restored += 1
    timeline.moveToEnd()
    design.computeAll()
    print("removed %d timeline steps, restored %d parameters" % (removed, restored))
'''
