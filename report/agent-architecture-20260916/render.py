"""Validate the standalone SVG and render a PNG with installed librsvg/Cairo."""

import ctypes as C
import ctypes.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
SVG = HERE / "agent-workflow.svg"
NS = {"s": "http://www.w3.org/2000/svg"}


class Rectangle(C.Structure):
    _fields_ = [(key, C.c_double) for key in ("x", "y", "width", "height")]


def bind(lib, name, result, *args):
    func = getattr(lib, name)
    func.restype, func.argtypes = result, args
    return func


def main():
    root = ET.parse(SVG).getroot()
    width, height = map(int, (root.get("width"), root.get("height")))
    ids = [e.get("id") for e in root.iter() if e.get("id")]
    assert len(ids) == len(set(ids)), "Duplicate SVG IDs"
    for element in root.iter():
        assert element.tag not in {f"{{{NS['s']}}}{tag}" for tag in
                                   ("script", "foreignObject", "image")}
        for key, value in element.attrib.items():
            if key.endswith("href"):
                assert value.startswith("#") and value[1:] in ids, value
    texts = root.findall(".//s:text", NS)
    for i, text in enumerate(texts):
        text.set("id", f"check-text-{i}")

    rsvg = C.CDLL(ctypes.util.find_library("rsvg-2"))
    cairo = C.CDLL(ctypes.util.find_library("cairo"))
    gobject = C.CDLL(ctypes.util.find_library("gobject-2.0"))
    new = bind(rsvg, "rsvg_handle_new_from_data", C.c_void_p,
               C.c_char_p, C.c_size_t, C.c_void_p)
    render = bind(rsvg, "rsvg_handle_render_document", C.c_int,
                  C.c_void_p, C.c_void_p, C.POINTER(Rectangle), C.c_void_p)
    geometry = bind(rsvg, "rsvg_handle_get_geometry_for_layer", C.c_int,
                    C.c_void_p, C.c_char_p, C.POINTER(Rectangle),
                    C.POINTER(Rectangle), C.POINTER(Rectangle), C.c_void_p)
    surface_new = bind(cairo, "cairo_image_surface_create", C.c_void_p,
                       C.c_int, C.c_int, C.c_int)
    context_new = bind(cairo, "cairo_create", C.c_void_p, C.c_void_p)
    write_png = bind(cairo, "cairo_surface_write_to_png", C.c_int,
                     C.c_void_p, C.c_char_p)
    context_free = bind(cairo, "cairo_destroy", None, C.c_void_p)
    surface_free = bind(cairo, "cairo_surface_destroy", None, C.c_void_p)
    unref = bind(gobject, "g_object_unref", None, C.c_void_p)
    data = ET.tostring(root, encoding="utf-8")
    handle = new(data, len(data), None)
    assert handle, "SVG could not be loaded"
    surface = surface_new(0, width, height)
    context = context_new(surface)
    viewport = Rectangle(0, 0, width, height)
    try:
        assert render(handle, context, C.byref(viewport), None), "Render failed"
        assert write_png(surface, str(HERE / "agent-workflow.png").encode()) == 0
        boxes = []
        for text in texts:
            ink, logical = Rectangle(), Rectangle()
            assert geometry(handle, ("#" + text.get("id")).encode(),
                            C.byref(viewport), C.byref(ink), C.byref(logical), None)
            content = " ".join("".join(text.itertext()).split())
            assert ink.x >= 0 and ink.y >= 0, content
            assert ink.x + ink.width <= width and ink.y + ink.height <= height, content
            boxes.append((content, ink))
        overlaps = []
        for i, (first, a) in enumerate(boxes):
            for second, b in boxes[i + 1:]:
                dx = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
                dy = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
                if dx > 1 and dy > 1:
                    overlaps.append([first, second])
        report = {"svg_valid": True, "standalone": True, "width": width,
                  "height": height, "text_elements": len(texts),
                  "text_outside_canvas": 0, "text_overlaps": overlaps,
                  "renderer": "system librsvg + Cairo"}
        (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        assert not overlaps, "Overlapping labels"
    finally:
        context_free(context)
        surface_free(surface)
        unref(handle)


if __name__ == "__main__":
    main()
