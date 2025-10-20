## 20251019

- pymupdf4llm Markdown conversion is both agonizingly slow proportionate to number of pdf pages regardless of the size of specified subset in the pages argument, and also misses all the large text for some reason (to do with color or background maybe? ignoring opacity did not change output)
- The only property that can distinguish headings seems to be font size; doesn't seem to even distinguish the text that is obviously bolded

#### Current strategy
1. Find the page index of every page containing the link to the source WEG document. This gets the first page of every WEG entry.
2. Parse each entry's group of pages into an object
3. Extract text from each page (drop header and footer, already have working measurements for it) and mash text extract dicts together
4. Within each entry, grab the title line(s) (16pt font), section line(s) (12 pt font). Either need to group spans or one level up with parent lines (not sure if the line abstraction works for this)
5. Within section
    1. ~~Find each line with a colon~~
    2. ~~Group all text pre-colon and post-colon into key and value~~
    3. ~~If no colon, group all section text into "content"~~
    1. Find if first line has colon (possibly need to put a limit on number of words pre-colon)
    2. If true, process lines as attributes based on colons
    3. Otherwise, group all section text together under "content"