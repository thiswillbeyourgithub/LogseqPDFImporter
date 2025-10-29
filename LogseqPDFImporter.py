import time
import shutil
import textwrap
import hashlib
import simplejson as json  # only simplejson can dump decimal
from pathlib import Path
import sys
import uuid
import fire
import colour

import fitz


COLORS = {
        'yellow': (1.0, 0.78431372549, 0.196078431373),
        'red': (1.0, 0.0, 0.0),
        'green': (0.78431372549, 1, 0.392156862745),
        'blue': (0.294117647059, 0.688235294118, 1.0),
        'purple': (0.78431372549, 0.392156862745, 0.78431372549),
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

    # geometry page
    # more info: https://stackoverflow.com/questions/6230752/extracting-page-sizes-from-pdf-in-python/58288544#58288544
    px, py = annot["pagesize"].width, annot["pagesize"].height
    # px, py = annot["mediaboxsize"].width, annot["mediaboxsize"].height
    # px, py = annot["cropboxsize"].width, annot["cropboxsize"].height

    # turn the quadpoints into a list of rectangles. To make the
    # highlighted area in several parts
    # annot["boxes"] = []
    # if "quadpoints" in annot and len(annot["quadpoints"]) >= 8:
    #     while len(annot["quadpoints"]) >= 8:
    #         (x0, y0, x1, y1, x2, y2, x3, y3) = annot["quadpoints"][:8]
    #         annot["quadpoints"] = annot["quadpoints"][8:]
    #         xvals = [x0, x1, x2, x3]
    #         yvals = [y0, y1, y2, y3]
    #         box = {
    #                 "x0": min(xvals),
    #                 "y0": min(yvals),
    #                 "x1": max(xvals),
    #                 "y1": max(yvals)
    #                 }
    #         annot["boxes"].append(box)

    # annotation shape
    result['position'] = {
        "bounding": {
            "x1": annot["rect"].x0,
            "y1": annot["rect"].y0,
            "x2": annot["rect"].x1,
            "y2": annot["rect"].y1,
            "width": px,
            "height": py,
        },
        "rects": [
            {
                "x1": annot["rect"].x0,
                "y1": annot["rect"].y0,
                "x2": annot["rect"].x1,
                "y2": annot["rect"].y1,
                "width": px,
                "height": py,
            }  # for b in annot["boxes"]
        ],
        "page": int(result["page"]),
    }

    if annot["subtype"].lower() in ["square", "ink"]:
        # render image
        annot_irect = annot_fitz.get_pixmap().irect
        # create an image uuid that is deterministic
        image_uuid = str(
                uuid.uuid3(
                    uuid.NAMESPACE_URL,
                    file_name + str(result["page"]) + str(tuple(annot_irect)[0]) + str(tuple(annot_irect)[1]) + str(tuple(annot_irect)[2]) + str(tuple(annot_irect)[3])
                    )
                )
        image_id = str(result["page"]) + "_" + image_uuid
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
                    file_name + result["content"]["text"] + json.dumps(result["position"]),
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
    colorname = "yellow"
    try:
        if annot["color"]:
            colorname = getColorName(annot["color"])
    except Exception as err:
        print(f"Error when parsing color: '{err}'. Using {colorname}")
    result["properties"]["color"] = colorname

    if not result['content']["text"].strip():
        print(f"Warning: annotation with empty text:\n{result}")

    return result

def getColorName(color):
    """
    Determine nearest color based on Delta-E difference between input and reference colors.
    """
    color = colour.sRGB_to_XYZ(color)
    deltae = {}

    for colorname, referencecolor in COLORS.items():
        deltae[colorname] = colour.delta_E(color, referencecolor)

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
    text_boundary_threshold: float = 0.9,
    nonunique_uuid_do: str = "exit",
    handle_comments: str = "auto",
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
    nonunique_uuid_do: str, default 'exit'
        Set to 'remove' to automatically remove annotations that have a non unique
        UUID.
        Set to 'keep' to not even check for duplicate UUID and export them as usual.
        Leave to 'exit' to crash if there are non unique UUIDs.
        Note: The UUID for each block is a hash derived from its content so
        there really should be no reason to have duplicate UUIDs AFAIK.
nonunique_uuid_do: str, default 'auto'
        Set to 'auto' to add annotations from older apps to annotations from more recent apps.
        Set to 'replace' to automatically keep only annotations from older devices.
        Set to 'ignore' to not even check for other type of annotations.
    """
    assert nonunique_uuid_do in ["exit", "remove", "keep"], f"nonunique_uuid_do value is {nonunique_uuid_do}"

    readerfitz = fitz.open(input_path)  # separate reader that handles annotation text better

    file_name = Path(input_path).name

    assert handle_comments in ["auto", "replace", "ignore"], f"handle_comments value is {handle_comments}"

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
            content = None
            content = annot.info.get("content", "").strip()
            print(not content)
            if content and handle_comments == 'replace':
                text = content
            elif content and handle_comments == 'auto':
                text = _extract_annot(
                    annot,
                    words,
                    keep_newlines,
                    text_boundary_threshold)
                text = text + '\n' + content
            else:
                text = _extract_annot(
                    annot,
                    words,
                    keep_newlines,
                    text_boundary_threshold)
            annotdict["contents"] = text
            annotdict["color"] = annot.colors["fill"] if annot.colors["fill"] else annot.colors['stroke']
            annotdict["rect"] = annot.rect
            annotdict["quadpoints"] = []
            vertices = annot.vertices
            if vertices and len(vertices) % 2 == 0:
                if all(len(ver) == 2 for ver in vertices):
                    for iii in range(len(vertices)//2):
                        ver = vertices[iii*2:(iii+1)*2]
                        annotdict["quadpoints"].append(
                                {
                                    "x0": ver[0][0],
                                    "y0": ver[0][1],

                                    "x1": ver[1][0],
                                    "y1": ver[1][1],
                                    }
                                )

            annotdict["pagesize"] = page.rect
            annotdict["mediaboxsize"] = page.mediabox
            annotdict["cropboxsize"] = page.cropbox

            annotdict["page"] = i

            annotdict = annot_to_dict(file_name, annotdict, annot, page)
            annots.append(annotdict)
            print(annotdict)

    assert annots, "no annotation found"

    ids = [an["id #uuid"] for an in annots]
    if len(ids) != len(set(ids)):
        nonunique_ids = [one_id for one_id in ids if ids.count(one_id) > 1]
        assert nonunique_ids
        print("Non unique id for the following annotations:")
        for an in annots:
            if an["id #uuid"] in nonunique_ids:
                print(f"DUP: {an}")

        # sanity check: duplicate UUID are indeed identical
        for nid in nonunique_ids:
            for an in annots:
                if an["id #uuid"] == nid:
                    first_an = an
                    break
            for an in annots[annots.index(first_an)+1:]:
                if an["id #uuid"] == nid:
                    if an != first_an and json.dumps(an) != json.dumps(first_an):
                        print(
                            "Annotations with the same UUID are actually "
                            f"different: \n{an}\n{first_an}"
                            "\nPlease open an issue on github"
                            )

        if nonunique_uuid_do == "exit":
            raise Exception("Some annotations uuid were not unique! "
                            "The uuid is derived from the text content or "
                            "the image location.")
        elif nonunique_uuid_do == "remove":
            print("Removing annotations with non duplicate UUID")
            new_ids = []
            new_annots = []
            for an in annots:
                anid = an["id #uuid"]
                if anid in new_ids:
                    continue
                new_annots.append(an)
                new_ids.append(anid)
            assert len(new_annots) < len(annots)
            assert len(new_annots) == len(new_ids)
            annots = new_annots
            ids = new_ids
        elif nonunique_uuid_do == "keep":
            print("Keeping annotations with non duplicate UUID")
        else:
            raise ValueError(nonunique_ids)

    annots = {
            "highlights": annots,
            }

    if imgdir_path == "infer":
        imgdir_path = (Path(input_path).parent / Path(input_path).stem)
        imgdir_path.mkdir(exist_ok=True)
        imgdir_path = str(imgdir_path)

    filename = str(Path(input_path).name)

    # create the md file alongside the annotations
    md = "file-path:: ../assets/" + Path(input_path).name + "\n"
    md += "diy_type:: [[Annotations_page]]\n\n"
    for ia, an in enumerate(annots["highlights"]):
        # if not "content" in an:
        #     print(f"No content in annotation: '{an}'")
        #     continue
        text =  an["content"]["text"]
        if not text.strip():
            # text = f"Notext {ia + 1}"
            text = f"{filename} (empty annotation {ia + 1})"
        lines =  text.split("\n")
        md += "- " + lines.pop(0) + "\n"
        md += "  ls-type:: annotation\n"
        md += "  hl-page:: " + str(an["page"]) + "\n"
        md += "  hl-color:: " + str(an["properties"]["color"]) + "\n"
        md += "  id:: " + an["id #uuid"] + "\n"
        if "image_id" in an["content"] and imgdir_path:
            md += "  hl-type:: area\n"
            tstamp = an["content"]["image_id"].split("_")[-1]
            md += "  hl-stamp:: " + tstamp + "\n"
            # TODO: get the timestamp of the creation of the annot
            shutil.move(
                    "images_cache/" + an["content"]["image_id"] + ".png",
                    imgdir_path + "/" + an["content"]["image_id"] + ".png"
                    )
        if lines:
            md += textwrap.indent("\n".join(lines), " " * 2) + "\n"

    shutil.rmtree("images_cache")

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
            md_path = str(Path(input_path).parent.parent / "pages" / ("hls__" + filename).replace(".pdf", ".md"))
            print(f"Inferred md_path: {md_path}")
            with open(md_path, "w") as f:
                f.write(md)

    if edn_path:
        if edn_path != "infer":
            with open(edn_path, "w") as f:
                f.write(edn)
        else:
            edn_path = str(Path(input_path).parent / filename.replace(".pdf", ".edn"))
            print(f"Inferred edn_path: {edn_path}")
            with open(edn_path, "w") as f:
                f.write(edn)


if __name__ == "__main__":
    inst = fire.Fire(main)
