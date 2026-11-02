---
name: make-fixture-comic
description: Build the duck fixture comic end to end with fake LLM, fake vision, and mock image backend.
---
Run `./run.sh`. Passes when the PDF has the expected page count and the web export folder
contains index.html with data-narrate markup. Until the export sprint lands, the script runs the
stages that exist and reports which stages are not implemented yet.
