# pdfannotations_to_logseq
Import pdf into logseq but also import annotations made from other softwares

## status
* work in progress. The highlights don't appear at the right location on logseq but the pdf coordinates are very confusing (help welcome). But at least you can see them in the annotation panel and clicking on them leads you to the right page.

## usage
* `python __init__.py path_to_pdf --md_path path_to_md --edn_path path_to_edn`

## TODO
* if ink annotation found: take an image
* infer color via numpy instead of colormath (broken)


## credits
* [pdfannots](https://github.com/0xabu/pdfannots/)
