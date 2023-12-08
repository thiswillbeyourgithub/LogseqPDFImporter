import time
import shutil
import textwrap
import hashlib
import simplejson as json  # only simplejson can dump decimal
from pathlib import Path
import sys
import uuid
import fire

import fitz

from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000


COLORS = {
        'yellow': sRGBColor(1.0, 0.78431372549, 0.196078431373),
        'red': sRGBColor(1.0, 0.0, 0.0),
        'green': sRGBColor(0.78431372549, 1, 0.392156862745),
        'blue': sRGBColor(0.294117647059, 0.688235294118, 1.0),
        'purple': sRGBColor(0.78431372549, 0.392156862745, 0.78431372549),
}


def _check_contain(r_word, points, thresh):
    """
    source: https://github.com/pymupdf/PyMuPDF/issues/318
    If `r_word` is contained in the rectangular area.

    The area of the intersection should be large enough compared to the
    area of the given word.

    Args:
        r_word (fitz.Rect): rectangular area of a single word.
        points (list): list of points in the rectangular area of the
            given part of a highlight.
        thresh: a higher number means tighter boxing boundaries for
            the text. Lower number to allow catching text outside of the
            highlight boundary.

    Returns:
        bool: whether `r_word` is contained in the rectangular area.
    """

    # `r` is mutable, so everytime a new `r` should be initiated.
    r = fitz.Quad(points).rect
    r.intersect(r_word)

    if r.get_area() >= r_word.get_area() * thresh:
        contain = True
    else:
        contain = False
    return contain


def _extract_annot(annot, words_on_page, keep_newlines, thresh):
    """
    source: https://github.com/pymupdf/PyMuPDF/issues/318
    Extract words in a given highlight.

    Args:
        annot (fitz.Annot): [description]
        words_on_page (list): [description]

    Returns:
        str: words in the entire highlight.
    """
    quad_points = annot.vertices
    if not quad_points:  # square and ink annotation apparently don't have vertices
        quad_points = annot.rect.quad
    quad_count = int(len(quad_points) / 4)
    sentences = ['' for i in range(quad_count)]
    for i in range(quad_count):
        points = quad_points[i * 4: i * 4 + 4]
        words = [
            w for w in words_on_page if
            _check_contain(fitz.Rect(w[:4]), points, thresh)
        ]
        sentences[i] = ' '.join(w[4] for w in words)

    if keep_newlines:
        for i, s in enumerate(sentences):
            if s.startswith("#"):
                sentences[i] = "\\" + sentences[i]
            if s.startswith("-"):
                sentences[i] = "\\" + sentences[i]
        sentence = '\n'.join(sentences)
    else:
        sentence = ' '.join(sentences)

    return sentence


def annot_to_dict(
        file_name,
        annot,  # a dict
        annot_fitz,
        pagefitz,
        ):
    """Convert an annotation to a dictionary representation suitable for JSON encoding."""

    result = {
        "page": annot["page"] + 1,
        "properties": {},
    }

    annot["boxes"] = []
    if "quadpoints" in annot and annot["quadpoints"] is not None:
        assert len(annot["quadpoints"]) % 8 == 0
        while annot["quadpoints"] != []:
            (x0, y0, x1, y1, x2, y2, x3, y3) = annot["quadpoints"][:8]
            annot["quadpoints"] = annot["quadpoints"][8:]
            xvals = [x0, x1, x2, x3]
            yvals = [y0, y1, y2, y3]
            box = {
                    "x0": min(xvals),
                    "y0": min(yvals),
                    "x1": max(xvals),
                    "y1": max(yvals)
                    }
            annot["boxes"].append(box)

    if annot["boxes"]:
        # try using rect
        bd_x1 = annot["rect"][0]
        bd_y1 = annot["rect"][1]
        bd_x2 = annot["rect"][2]
        bd_y2 = annot["rect"][3]
        bd_w = (bd_x2 - bd_x1)
        bd_h = (bd_y2 - bd_y1)

        # try using boxes
        # bd_x1 = float(min([b["x0"] for b in annot["boxes"]]))
        # bd_y1 = float(min([b["y0"] for b in annot["boxes"]]))
        # bd_x2 = float(max([b["x1"] for b in annot["boxes"]]))
        # bd_y2 = float(max([b["y1"] for b in annot["boxes"]]))
        # bd_w = (bd_x2 - bd_x1)
        # bd_h = (bd_y2 - bd_y1)
        # breakpoint()
        result['position'] = {
            "bounding": {
                "x1": bd_x1,
                "y1": bd_y1,
                "x2": bd_x2,
                "y2": bd_y2,
                "width": bd_w,
                "height": float(bd_h) * 10 * 6,
            },
            "rects": [
                {
                    "x1": float(b["x0"]),
                    "y1": float(b["y0"]),
                    "x2": float(b["x1"]),
                    "y2": float(b["y1"]),
                    "width": (b["x1"] - b["x0"]),
                    "height": float(b["y1"] - b["y0"]) * 10 * 6,
                }
                for b in annot["boxes"]
            ],
            "page": int(result["page"]),
        }

        # # testing with a different offset derived from the page geometry
        # px, py = annot["pagesize"][2:]
        # bd_w = (bd_x2 - bd_x1)
        # bd_h = (bd_y2 - bd_y1)
        # result['position'] = {
        #     "bounding": {
        #         "x1": bd_x1,
        #         "y1": bd_y1,
        #         "x2": bd_x2,
        #         "y2": bd_y2,
        #         "width": bd_w,
        #         "height": float(bd_h),
        #     },
        #     "rects": [
        #         {
        #             "x1": float(b["x0"]),
        #             "y1": py - float(b["y0"]),
        #             "x2": float(b["x1"]),
        #             "y2": py - float(b["y1"]),
        #             "width": (b["x1"] - b["x0"]),
        #             "height": float(b["y1"] - b["y0"]) * 10 * 6,
        #         }
        #         for b in annot["boxes"]
        #     ],
        #     "page": int(result["page"]),
        # }

    if annot["subtype"].lower() in ["square", "ink"]:
        # render image
        image_uuid = str(uuid.uuid4())
        image_id = str(result["page"]) + "_" + image_uuid + "_" + str(int(time.time() * 1000))
        annot_irect = annot_fitz.get_pixmap().irect
        pagefitz.get_pixmap(clip=annot_irect, alpha=True, annots=True).save("./images_cache/" + image_id + ".png")
        result["content"] = {
                "text": "[:span]",
                "image_id": image_id,
                }
        result["id #uuid"] = image_uuid
    else:
        result['content'] = {"text": str(annot["contents"]).strip()}

        # create a reproducible uuid based on the filename and highlight content
        result["id #uuid"] = str(
                uuid.uuid3(
                    uuid.NAMESPACE_URL,
                    file_name + result["content"]["text"],
                    )
                )

    # add author (usually stored in 'title')
    if "author" not in annot and "title" in annot:
        annot["author"] = annot["title"]
    if "author" in annot and annot["author"]:
        result["author"] = str(annot["author"]).strip()
    else:
        result["author"] = "Unknown"

    # add color if present
    try:
        if annot["color"]:
            colorname = getColorName(annot["color"])
    except Exception as err:
        print(f"Error when parsing color: '{err}'. Using yellow")
        colorname = "yellow"
    result["properties"]["color"] = colorname


    return result

def getColorName(color):
    """
    Determine neartest color based on Delta-E difference between input and reference colors.
    Create sRGBColor object from input
    """
    annotationcolor = sRGBColor(color[0], color[1], color[2])

    deltae = {}

    # Iterate over reference colors and calculate Delta-E for each one.
    # deltae will contain a dictionary in the form of 'colorname': <float> deltae.
    for colorname, referencecolor in COLORS.items():
        deltae[colorname] = delta_e_cie2000(convert_color(referencecolor, LabColor), convert_color(annotationcolor, LabColor))

    # return first key from dictionary sorted asc by value
    likelycolor = sorted(deltae, key=deltae.get)[0]
    return likelycolor


def idt(n):
    "simple indenter"
    return "\t" * n


def edn_var_formatter(text, var):
    return text.replace(f'"{var}": ', f':{var} ')


def main(
        input_path: str,
        md_path: str = "infer",
        edn_path: str = "infer",
        imgdir_path: str = "infer",
        keep_newlines: bool = True,
        text_boundary_threshold=0.9,
        ):
    """
    source: https://stackoverflow.com/questions/1106098/parse-annotations-from-a-pdf#12502560

    Parameters
    ----------
    input_path: str
        path to the pdf
    md_path: str, 'infer'
        path to the .md annotations. If 'infer' will automatically try
        to find it based on input_path
    edn_path: str, 'infer'
        path to the .edn annotations. If 'infer' will automatically try
        to find it based on input_path
    imgdir_path: str, 'infer'
        path to the directory to store the area image. If 'infer' will
        automatically try to find it based on input_path
    text_boundary_threshold: float, default 0.9
        Higher number means tighter boxing boundaries for the text.
        Lower number to allow catching text outside of the highlight boundary.
    """

    readerfitz = fitz.open(input_path)  # separate reader that handles annotation text better

    file_name = Path(input_path).name

    Path("images_cache").mkdir(exist_ok=True)

    annots = []
    for i, page in enumerate(readerfitz):
        for ii, annot in enumerate(page.annots()):
            annotdict = {
                    k.replace("/", "").lower(): v
                    for k, v in annot.info.items()
                    }
            assert len(annot.type) == 2
            annotdict["subtype"] = annot.type[-1].lower().replace("/", "")

            if annotdict["subtype"] == "link":
                continue

            # extract text using PyMuPDF
            words = page.get_text("words")
            text = _extract_annot(
                    annot,
                    words,
                    keep_newlines,
                    text_boundary_threshold)
            annotdict["contents"] = text
            annotdict["color"] = annot.colors["fill"] if annot.colors["fill"] else annot.colors['stroke']
            annotdict["rect"] = annot.rect
            annotdict["quadpoints"] = []
            for point in annot.rect.quad:
                annotdict["quadpoints"].append(point[0])
                annotdict["quadpoints"].append(point[1])

            annotdict["pagesize"] = page.bound()

            annotdict["page"] = i

            annotdict = annot_to_dict(file_name, annotdict, annot, page)
            annots.append(annotdict)
            print(annotdict)

    assert annots, "no annotation found"

    ids = [an["id #uuid"] for an in annots]
    assert len(ids) == len(set(ids)), "some annotations uuid were not unique!"

    annots = {
            "highlights": annots,
            }

    if imgdir_path == "infer":
        imgdir_path = (Path(input_path).parent / Path(input_path).stem.lower())
        imgdir_path.mkdir(exist_ok=True)
        imgdir_path = str(imgdir_path)

    # create the md file alongside the annotations
    md = "file-path:: ../assets/" + Path(input_path).name + "\n"
    md += "diy_type:: [[Annotations_page]]\n\n"
    for an in annots["highlights"]:
        # if not "content" in an:
        #     print(f"No content in annotation: '{an}'")
        #     continue
        lines =  an["content"]["text"].split("\n")
        md += "- " + lines.pop(0) + "\n"
        md += "  ls-type:: annotation\n"
        md += "  hl-page:: " + str(an["page"]) + "\n"
        md += "  hl-color:: " + str(an["properties"]["color"]) + "\n"
        md += "  id:: " + an["id #uuid"] + "\n"
        if "image_id" in an["content"] and imgdir_path:
            md += "  hl-type:: area\n"
            tstamp = an["content"]["image_id"].split("_")[-1]
            md += "  hl-stamp:: " + tstamp + "\n"
            # TODO: get the tiemstamp of the creation of the annot
            shutil.move(
                    "images_cache/" + an["content"]["image_id"] + ".png",
                    imgdir_path + "/" + an["content"]["image_id"] + ".png"
                    )
        if lines:
            md += textwrap.indent("\n".join(lines), " " * 2) + "\n"


    edn = json.dumps(annots, indent=2, use_decimal=True)

    for var in ["x1", "y1", "x2", "y2", "width", "height", "id #uuid",
                "page", "position", "content", "text", "properties",
                "color", "rects", "bounding", "highlights", "image",
                "author", "image_id"]:
        edn = edn_var_formatter(edn, var)

    print(md)
    print(edn)

    if md_path:
        if md_path != "infer":
            with open(md_path, "w") as f:
                f.write(md)
        else:
            md_path = str(Path(input_path).parent.parent / "pages" / ("hls__" + str(Path(input_path).name).replace(".pdf", ".md").lower()))
            print(f"Inferred md_path: {md_path}")
            with open(md_path, "w") as f:
                f.write(md)

    if edn_path:
        if edn_path != "infer":
            with open(edn_path, "w") as f:
                f.write(edn)
        else:
            edn_path = str(Path(input_path).parent / Path(input_path).name.lower().replace(".pdf", ".edn"))
            print(f"Inferred edn_path: {edn_path}")
            with open(edn_path, "w") as f:
                f.write(edn)


if __name__ == "__main__":
    inst = fire.Fire(main)
