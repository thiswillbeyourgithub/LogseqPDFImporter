# pdfannotations_to_logseq
Import pdf into logseq but also import annotations made from other softwares

## Status
* work in progress. The highlights don't appear at the right location on logseq but the pdf coordinates are very confusing (help welcome). But at least you can see them in the annotation panel and clicking on them leads you to the right page.

## Usage
* `python -m pip install -r requirements.txt`
* `python __init__.py path_to_pdf --md_path path_to_md --edn_path path_to_edn`

## TODO
* fix: the location of the highlights in logseq is wrong (meaning they don't appear at the right location in logseq's pdf reader)
* if ink annotation found: render an image and import it as a regular area highlight
* infer color via numpy instead of colormath (broken)


## credits
* [pdfannots](https://github.com/0xabu/pdfannots/)
