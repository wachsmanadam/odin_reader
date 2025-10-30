## 20251028

We've got output! And while, structurally, it's fairly jacked up, the extracted text itself has fewer problems than I expected. The hierarchy isn't working and text from the title block is getting repeated under title text (luckily the example has multiple lines so it's a more obvious bug). Also the Tiers attribute is getting subsumed into the attribute above it, may just do a hardcoded patch clause to fix that one honestly.

## 20251020

It occurs to me that having multiple levels of hierarchy in output isn't that useful and is a pain, so instead I'm just outputting to OrderedDict so that one can just inference that adjacent sections may relate to each other. Oh now I remember it's because there's multiple cases of key collision if I had everything flat.

## 20251019
Font size strategy for title and section heads seems to be working, now relative since values seem to vary between WEG items for whatever reason. Annoyingly, I found an instance of the title being split across consecutive lines, so I'm going to have to have the algorithm merge is_title_line matches first thing. Will also need to compare section heads with subsequent sections to decide whether the subsequent is a subsection of the above, or a new section at the same document level. Still, I'm used to way more headaches at this stage so I'll take my wins where I can get em.

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