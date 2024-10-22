# LogseqPDFImporter
Import PDF into [logseq](https://github.com/logseq/logseq/) but also import annotations made from other software.

## Status
* *Not feature complete but I've used it successfuly several times*
* The text highlights are correctly parsed.
* Other type of annotation (lines, shapes, rectangles, etc) are parsed as "area highlight" (open an issue if something goes wrong). The area is currently only one rectangle that surrounds the whole area, I have yet to code the exact rectangle geometry extractions (help welcome!)
* Colors are correctly matched to logseq's available colors.
* Creates both the .md and .edn files, as well as images of area highlights.

### PDF reader compatibility
- I use [Okular](https://okular.kde.org/) from KDE software on my computers and [Xodo](https://xodo.com/) on android. Both use annotations that are fully compatible by the way!
- I assume it works out of the box with other readers minus some quirks. Notably related to freehand movement I'm sure.
- **Tell me if you tested it on other software!**

### TODO (please help)
* fix the text annotation by using small rectangles that cover exactly the text instead of one large overlapping area over the whole text

## Usage
* `python -m pip install -r requirements.txt`
* `python LogseqPDFImporter.py path_to_pdf --md_path path_to_md --edn_path path_to_edn`

## Example
### 1
<img src="https://github.com/thiswillbeyourgithub/LogseqPDFImporter/blob/main/docs/normal_1.png" width=300/> <img src="https://github.com/thiswillbeyourgithub/LogseqPDFImporter/blob/main/docs/logseq_1.png" width=300/>

### 2
<img src="https://github.com/thiswillbeyourgithub/LogseqPDFImporter/blob/main/docs/normal_2.png" width=300/> <img src="https://github.com/thiswillbeyourgithub/LogseqPDFImporter/blob/main/docs/logseq_2.png" width=300/>



## credits
* [user e-zz who was indispensable in getting the annotation locations right](https://github.com/e-zz/logseq-pdf-extract/discussions/3#discussioncomment-7902471)
* [pdfannots](https://github.com/0xabu/pdfannots/)
