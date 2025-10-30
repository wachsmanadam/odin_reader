from line import CharacterizedLine, generate_attr_flatten

import pymupdf

from collections import OrderedDict, deque
from functools import reduce
from typing import Sequence
import json

def build_item_page_indices(doc:pymupdf.Document):
    item_indices = deque()
    for i, p in enumerate(doc.pages()):
        # Strategy: pick a search string that only ever appears on the first page of a WEG listing
        search_result = p.search_for('WEG Location:')
        if len(search_result) > 0:
            item_indices.append(i)
        i += 1
    return item_indices

class WegItem:
    CLIP = [0, 36, 800, 760]

    def __init__(self, doc:pymupdf.Document, start_index:int, stop_index:int = None):
        stop_index = stop_index if stop_index is not None else doc.page_count
        self.pages = doc[start_index:stop_index]
        self._all_extract_text = [p.get_textpage(clip = self.CLIP).extractDICT() for p in self.pages]
        self._all_raw_blocks = reduce(lambda x, y: x + y, [p['blocks'] for p in self._all_extract_text])
        self._all_raw_lines = reduce(generate_attr_flatten('lines'), self._all_raw_blocks, [])
        self._all_raw_spans = reduce(generate_attr_flatten('spans'), self._all_raw_lines, [])
        # Damn I didn't know list comprehension worked like this
        self._font_sizes = tuple(set(s.get('size') for s in self._all_raw_spans))

    def get_characterized_lines(self):
        # Seemed like the easiest way to make sure font sizes gets passed each time
        constructer_args_gen = ((l, self._font_sizes) for l in self._all_raw_lines)
        return tuple(map(lambda x: CharacterizedLine(x[0], x[1]), constructer_args_gen))

    def blocks_to_text(self):
        # Mostly added for debugging
        block_text = []
        for b in self._all_raw_blocks:
            line_text = []
            for l in b['lines']:
                span_text = []
                for s in l['spans']:
                    span_text.append(s.get('text', ''))
                line_text.append(''.join(span_text))
            block_text.append(' '.join(line_text))
        return block_text

    def _get_title_line_block_indices(self, characterized_lines:Sequence[CharacterizedLine]):
        title_indices = []
        found_first_title = False
        for i, l in enumerate(characterized_lines):
            # cycle through until finding title text. Theoretically this should be first iter basically every time tho
            if not found_first_title and not l.is_title_line:
                continue
            elif not found_first_title and l.is_title_line:
                title_indices.append(i)
                found_first_title = True
            elif found_first_title and l.is_title_line:
                title_indices.append(i)
            else:
                # Only want first contiguous block of title lines, assume anything flagged as title further on is a mistake
                break

        return title_indices

    def _organize_sections(self, char_lines:Sequence[CharacterizedLine], section_indices:Sequence[int]):
        section_heading_blocks = []

        section_heading_block = []
        prev_idx = None
        for idx in section_indices:
            if prev_idx is not None and (idx - 1 == prev_idx) and (char_lines[idx].section_depth == char_lines[prev_idx].section_depth):
                section_heading_block.append(idx)
            elif prev_idx is None:
                section_heading_block = [idx,]
            else:
                section_heading_blocks.append(section_heading_block)
                section_heading_block = [idx,]

            prev_idx = idx

        section_content_ranges = [(x[-1], y[0]) for x, y in zip(section_heading_blocks[0:-1], section_heading_blocks[1::])]
        # section_heading_text = []
        # for block in section_heading_blocks:
        #     # Inclusive range
        #     heading_slice = char_lines[block[0], block[-1]+1]
        #     section_heading_text.append(' '.join(map(lambda x: x.get_raw_text(), heading_slice)))

        return tuple(zip(section_heading_blocks, section_content_ranges))

    def _process_section_lines_as_block_text(self, section_lines_slice:Sequence[CharacterizedLine]):
        text = ' '.join([l.get_raw_text() for l in section_lines_slice])
        content_dict = OrderedDict()
        content_dict['content'] = text

        return content_dict

    def _process_section_lines_as_kv(self, section_lines_slice:Sequence[CharacterizedLine], splittable_lines = None):
        content_dict = OrderedDict()
        # Making it optional solely for the benefit of using this on title block tbh
        if splittable_lines is None:
            splittable_lines = tuple(filter(lambda x: x[1][1] is not None, enumerate(map(lambda y: y.get_key_val_split(), section_lines_slice))))
            splittable_indices = list(map(lambda x: x[0], splittable_lines))
        else:
            splittable_indices = list(map(lambda x: x[0], splittable_lines))
        # Ensure last bit always extends to the end of the slice
        if splittable_indices[-1] != len(section_lines_slice) - 1:
            splittable_indices.append(len(section_lines_slice))

        for chunk_start, chunk_end in zip(splittable_indices[0:-1], splittable_indices[1::]):
            key, start_text = section_lines_slice[chunk_start].get_key_val_split()
            remaining_text = ' '.join(map(lambda x: x.get_raw_text(), section_lines_slice[chunk_start+1:chunk_end]))
            if content_dict.get(key) is None:
                content_dict[key] = start_text + ' ' + remaining_text
            else:
                error_txt = "Conflicting keys within same text section"
                error_txt = error_txt + f'\nExisting key_val: {key}:{content_dict[key]}'
                error_txt = error_txt + f'\nAttempted key_val: {key}:{start_text + ' ' + remaining_text}'
                raise KeyError(error_txt)

        return content_dict

    def _process_section_content(self, section_lines_slice:Sequence[CharacterizedLine]):
        # Turn slice items into key_val_split results, enumerate that iterator, and then filter get the splits that don't have a null val
        splittable_lines = tuple(filter(lambda x: x[1][1] is not None, enumerate(map(lambda y: y.get_key_val_split(), section_lines_slice))))

        is_likely_block_text = (len(splittable_lines) / len(section_lines_slice)) < 0.2
        is_likely_block_text = is_likely_block_text & (splittable_lines[0][0] != 0) # Trying to avoid edge case of single key prior to large multiline block of text
        if len(splittable_lines) == 0 or not is_likely_block_text:
            return self._process_section_lines_as_kv(section_lines_slice, splittable_lines)
        else:
            return self._process_section_lines_as_block_text(section_lines_slice)

    def _process_sections(self, char_lines:Sequence[CharacterizedLine], section_indices:Sequence[int], title_text:str):
        out = OrderedDict()
        out['title'] = title_text

        root_start, root_end = section_indices[0], section_indices[1]
        title_content = self._process_section_content(char_lines[root_start+1:root_end])
        out.update(title_content)

        section_tups = self._organize_sections(char_lines, section_indices)

        current_section_dict = out
        current_depth = 0
        for section_title_block_idxs, (content_start_idx, content_end_idx) in section_tups:
            # join arbitrary amount of section heading text to string
            section_depth = char_lines[section_title_block_idxs[0]].section_depth
            if  section_depth == 0 or section_depth < current_depth:
                current_section_dict = out

            section_title = ' '.join(map(lambda x: char_lines[x].get_raw_text(), section_title_block_idxs))
            section_content = self._process_section_content(char_lines[content_start_idx:content_end_idx])
            current_section_dict[section_title] = section_content

            current_section_dict = section_content
            current_depth = section_depth

        return out

    def to_document_dict(self):
        char_lines = self.get_characterized_lines()
        # out = OrderedDict()
        title_indices = self._get_title_line_block_indices(char_lines)
        # Merge title text to a single string
        title_text = ' '.join([char_lines[i].get_raw_text() for i in title_indices])

        # Filter the tuples of enumerated CharacterizedLine by is_section_heading attribute, grab only the indices of the filtered tuples
        section_indices = list(map(lambda x: x[0], filter(lambda y: y[1].is_section_heading, enumerate(char_lines))))
        # Prepend the last index of title_indices because we will be operating on index ranges between section headings
        section_indices.insert(0, title_indices[-1])

        out = self._process_sections(char_lines, section_indices, title_text)

        return out
    
if __name__ == "__main__":
    from pathlib import Path

    docpath = Path(r'/workspaces/odin_reader/doc/tanksyourwelcome.pdf')
    doc = pymupdf.open(docpath)

    item_indices = build_item_page_indices(doc)
    index_pairs = [(item_indices[i], item_indices[i+1]) for i in range(len(item_indices) - 1)]
    index_pairs.append((item_indices[-1], doc.page_count))
    wegitems = []
    for st, ed in index_pairs:
        wegitems.append(WegItem(doc, st, ed))

    test_out = wegitems[0].to_document_dict()
    
    with open('out/output_example_20251028_1.json', 'w') as f:
        f.write(json.dumps(test_out))