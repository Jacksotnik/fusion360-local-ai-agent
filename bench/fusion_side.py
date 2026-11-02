"""Fusion-side scripts for the ladder bench (sent through the MCP execute tool)."""

BENCH_ATTRIBUTE_GROUP = "fusion-bench"

# Opens a new empty design and marks it, so only bench documents are ever closed.
NEW_DOCUMENT_SCRIPT = f'''import adsk.core, adsk.fusion

def run(_context: str):
    app = adsk.core.Application.get()
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    doc.activate()
    design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    design.attributes.add("{BENCH_ATTRIBUTE_GROUP}", "copy", "1")
    print(doc.name)
'''

CLOSE_BENCH_DOC_SCRIPT = f'''import adsk.core, adsk.fusion

def run(_context: str):
    app = adsk.core.Application.get()
    doc = app.activeDocument
    name = doc.name
    design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
    is_marked = design is not None and design.attributes.itemByName("{BENCH_ATTRIBUTE_GROUP}", "copy") is not None
    if doc.dataFile is not None or not is_marked:
        raise RuntimeError("refusing to close a non-bench document: " + name)
    doc.close(False)
    print("closed " + name)
'''

# Prints "bench" when the active document is a marked bench document, else "other".
ACTIVE_IS_BENCH_SCRIPT = f'''import adsk.core, adsk.fusion

def run(_context: str):
    doc = adsk.core.Application.get().activeDocument
    design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType")) if doc else None
    is_marked = design is not None and design.attributes.itemByName("{BENCH_ATTRIBUTE_GROUP}", "copy") is not None
    print("bench" if is_marked and doc.dataFile is None else "other")
'''

# Cleanup after an agent left the bench document: closes every marked unsaved document, nothing else.
CLOSE_ALL_BENCH_DOCS_SCRIPT = f'''import adsk.core, adsk.fusion

def run(_context: str):
    app = adsk.core.Application.get()
    marked = []
    for doc in app.documents:
        design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        if design is None or doc.dataFile is not None:
            continue
        if design.attributes.itemByName("{BENCH_ATTRIBUTE_GROUP}", "copy") is not None:
            marked.append(doc)
    for doc in marked:
        doc.close(False)
    print("closed %d bench documents" % len(marked))
'''

_VIEW_ORIENTATIONS = {
    "front": "FrontViewOrientation", "back": "BackViewOrientation", "top": "TopViewOrientation",
    "bottom": "BottomViewOrientation", "left": "LeftViewOrientation", "right": "RightViewOrientation",
    "iso-top-right": "IsoTopRightViewOrientation", "iso-top-left": "IsoTopLeftViewOrientation",
    "iso-bottom-right": "IsoBottomRightViewOrientation", "iso-bottom-left": "IsoBottomLeftViewOrientation",
}


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


# Geometry summary used for comparison: independent of how the part was built.
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


def reference_script(prelude, body):
    """Wrap a reference body (code that builds the expected change) into a runnable script."""
    indented = "\n".join("    " + line for line in body.splitlines())
    return prelude + "\n\ndef run(_context: str):\n" + indented + "\n    print('reference ok')\n"
