import textwrap
import hashlib
import simplejson as json  # only simplejson can dump decimal
from pathlib import Path
import sys
import uuid
import fire
from PyPDF2 import PdfReader

import fitz

from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000


COLORS = {
        'yellow': sRGBColor(1.0, 0.78431372549, 0.196078431373),
        'red': sRGBColor(1.0, 0.0, 0.0),
        'green': sRGBColor(0.78431372549, 1, 0.392156862745),
        'blue': sRGBColor(0.294117647059, 0.588235294118, 1.0),
        'purple': sRGBColor(0.78431372549, 0.392156862745, 0.78431372549),
}




def _check_contain(r_word, points):
    """
    source: https://github.com/pymupdf/PyMuPDF/issues/318
    If `r_word` is contained in the rectangular area.

    The area of the intersection should be large enough compared to the
    area of the given word.

    Args:
        r_word (fitz.Rect): rectangular area of a single word.
        points (list): list of points in the rectangular area of the
            given part of a highlight.

    Returns:
        bool: whether `r_word` is contained in the rectangular area.
    """
    _threshold_intersection = 0.9  # if the intersection is large enough.

    # `r` is mutable, so everytime a new `r` should be initiated.
    r = fitz.Quad(points).rect
    r.intersect(r_word)

    if r.get_area() >= r_word.get_area() * _threshold_intersection:
        contain = True
    else:
        contain = False
    return contain


def _extract_annot(annot, words_on_page, keep_newlines):
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
    if not quad_points:  # square annotation apparently don't have vertices
        quad_points = annot.rect.quad
    quad_count = int(len(quad_points) / 4)
    sentences = ['' for i in range(quad_count)]
    for i in range(quad_count):
        points = quad_points[i * 4: i * 4 + 4]
        words = [
            w for w in words_on_page if
            _check_contain(fitz.Rect(w[:4]), points)
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
        annot
        ):
    """Convert an annotation to a dictionary representation suitable for JSON encoding."""

    result = {
        "page": annot["page"] + 1,
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
        bd_x1 = annot["rect"][0]
        bd_y1 = annot["rect"][1]
        bd_x2 = annot["rect"][2]
        bd_y2 = annot["rect"][3]

        # page geometry
        px, py = annot["pagesize"][2:]

        bd_x1 = float(min([b["x0"] for b in annot["boxes"]]))
        bd_y1 = float(min([b["y0"] for b in annot["boxes"]]))
        bd_x2 = float(max([b["x1"] for b in annot["boxes"]]))
        bd_y2 = float(max([b["y1"] for b in annot["boxes"]]))
        bd_w = (bd_x2 - bd_x1)
        bd_h = (bd_y2 - bd_y1)
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

    if annot["subtype"] in ["/Square", "/Ink"]:
        result["content"] = {
                "text": "[:span]",
                "image": "TODO",  # TODO, render an image here and store it
                # with as name the UNIX timestamp
                }

        # create a reproducible uuid based on the filename and highlight content
        result["id #uuid"] = str(
                uuid.uuid3(
                    uuid.NAMESPACE_URL,
                    file_name + result["content"]["text"] + hashlib.md5(
                        result["content"]["image"].encode()
                        ).hexdigest(),
                    )
                )
    else:
        result['content'] = {"text": str(annot["contents"]).strip()}

        # create a reproducible uuid based on the filename and highlight content
        result["id #uuid"] = str(
                uuid.uuid3(
                    uuid.NAMESPACE_URL,
                    file_name + result["content"]["text"],
                    )
                )

    if annot["t"]:
        result["author"] = str(annot["t"]).strip()

    # add color
    if annot["c"]:
        try:
            colorname = getColorName(annot["c"])
        except Exception as err:
            print(f"Error when parsing color: '{err}'. Using yellow")
            colorname = "yellow"
        result["properties"] = {"color": colorname}


    return result

def getColorName(color):
    """
    Determine neartest color based on Delta-E difference between input and reference colors.
    Create sRGBColor object from input
    """
    try:
        annotationcolor = sRGBColor(color[0], color[1], color[2])
    except TypeError:
        # In case something goes wrong, return green
        return 'green'

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
        md_path: str = None,
        edn_path: str = None,
        keep_newlines: bool = True,
        ):
    """
    source: https://stackoverflow.com/questions/1106098/parse-annotations-from-a-pdf#12502560
    """

    reader = PdfReader(input_path)
    reader2 = fitz.open(input_path)  # separate reader that handles annotation text better

    file_name = Path(input_path).name

    annots = []
    for i, page in enumerate(reader.pages):
        if "/Annots" in page:
            page2 = reader2[i]
            annots2 = page2.annots()

            for ii, annot in enumerate(page["/Annots"]):
                obj = annot.get_object()
                new = {
                        k.replace("/", "").lower(): v
                        for k, v in obj.items()
                        }

                if new["subtype"] == "/Link":
                    continue

                # extract text using PyMuPDF
                annot2 = next(annots2)
                words = page2.get_text("words")
                text = _extract_annot(annot2, words, keep_newlines)
                new["contents"] = text

                new["pagesize"] = page2.bound()

                new["page"] = i

                new = annot_to_dict(file_name, new)
                annots.append(new)
                print(new)

    assert annots, "no annotation found"

    ids = [an["id #uuid"] for an in annots]
    assert len(ids) == len(set(ids)), "some annotations uuid were not unique!"

    annots = {
            "highlights": annots,
            }

    # create the md file alongside the annotations
    md = "file-path:: ../assets/" + Path(input_path).name + "\n"
    md += "diy_type:: [[Annotations_page]]\n\n"
    for an in annots["highlights"]:
        # if not "content" in an:
        #     print(f"No content in annotation: '{an}'")
        #     continue
        lines =  an["content"]["text"].split("\n")
        md += "- " + lines.pop(0) + "\n"
        if lines:
            md += textwrap.indent("\n".join(lines), " " * 2) + "\n"
        md += "  ls-type:: annotation\n"
        md += "  hl-page:: " + str(an["page"]) + "\n"
        md += "  hl-color:: " + str(an["properties"]["color"]) + "\n"
        md += "  id:: " + an["id #uuid"] + "\n"

    edn = json.dumps(annots, indent=2, use_decimal=True)

    for var in ["x1", "y1", "x2", "y2", "width", "height", "id #uuid",
                "page", "position", "content", "text", "properties",
                "color", "rects", "bounding", "highlights", "image",
                "author"]:
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
            edn_path = str(Path(input_path).absolute()).replace(".pdf", ".edn")
            print(f"Inferred edn_path: {edn_path}")
            with open(edn_path, "w") as f:
                f.write(edn)


if __name__ == "__main__":
    inst = fire.Fire(main)
