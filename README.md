# LogseqPDFImporter
Import pdf into logseq but also import annotations made from other softwares

## Status
* *work in progress*
* The text highlights are correctly parsed.
* Other type of annotation (lines, shapes, rectangles, etc) are parsed as "area highlight" (open an issue if something goes wrong). The area is currently only one rectangle that surrounds the whole area, I have yet to code the exact rectangle geometry extractions (help welcome!)
* Colors are correctly matched to logseq's available colors.
* Creates both the .md and .edn files, as well as images of area highlights.

## Usage
* `python -m pip install -r requirements.txt`
* `python LogseqPDFImporter.py path_to_pdf --md_path path_to_md --edn_path path_to_edn`

## Example
### 1
<img src="https://github.com/thiswillbeyourgithub/LogseqPDFImporter/blob/main/docs/normal_1.png" width=300/> <img src="https://github.com/thiswillbeyourgithub/LogseqPDFImporter/blob/main/docs/logseq_1.png" width=300/>

### 2
<img src="https://github.com/thiswillbeyourgithub/LogseqPDFImporter/blob/main/docs/normal_2.png" width=300/> <img src="https://github.com/thiswillbeyourgithub/LogseqPDFImporter/blob/main/docs/logseq_2.png" width=300/>

## TODO
* fix the text annotation by using small rectangles that cover exactly the text instead of one large overlapping area over the whole text



## credits
* [user e-zz who was indispensable in getting the annotation locations right](https://github.com/e-zz/logseq-pdf-extract/discussions/3#discussioncomment-7902471)
* [pdfannots](https://github.com/0xabu/pdfannots/)
