from abc import ABC, abstractmethod
import pypdf
import pymupdf
from functools import reduce
from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, Sequence
from collections import OrderedDict

from pprint import pprint

def build_item_page_indices(doc:pymupdf.Document):
    item_indices = deque()
    for i, p in enumerate(doc.pages()):
        # Strategy: pick a search string that only ever appears on the first page of a WEG listing
        search_result = p.search_for('WEG Location:')
        if len(search_result) > 0:
            item_indices.append(i)
        i += 1
    return item_indices

def build_heading_span_indices(spans):
    heading_indices = deque()
    for i, s in enumerate(spans):
        # Strategy: Font size seems to be the only marker that can be counted on
        if s.get('size', 0.0) >= 12.0:
            # Note: Every word of a heading will be added individually, must group consecutives downstream
            heading_indices.append(i)
    return heading_indices

def debug_iter_print(iter, firstline = ''):
    print('=======')
    print(firstline)
    for x in iter:
        print(x)
    print('=======')

def generate_attr_flatten(key):

    def attr_flatten(x, y):
        return x + y.get(key, [])
    
    return attr_flatten

def flatten_to_spans(page:dict):
    out = reduce(generate_attr_flatten('lines'), page['blocks'], [])
    out = reduce(generate_attr_flatten('spans'), out, [])
    return tuple(out)

# @dataclass
# class SpanFilter:
#     key:str
#     filter_func:Callable # span[key] -> bool

#     def to_func(self):
#         def span_filter(span:Dict):
#             val = span.get(self.key)
#             if val is not None and self.filter_func(val):
#                 return True
#             else:
#                 return False
#         return span_filter

class CharacterizedLine:

    # @staticmethod
    # def _is_title_span(span:Dict):
    #     span_size = span.get('size', 0)
    #     out = span_size >= 16.0
    #     return out
    
    # @staticmethod
    # def _is_section_heading_span(span:Dict):
    #     span_size = span.get('size', 0)
    #     out = (span_size >= 12.0) & (span_size < 16.0)
    #     return out

    def __init__(self, raw_line:Dict, font_sizes = [8.0, 12.0, 16.0]):
        # Uses approximate logic based on contained spans to infer function of given lineS
        assert len(font_sizes) >= 3, "Must have at least 3 font sizes to distinguish title, section, and body"
        self.font_sizes = sorted(font_sizes)
        self._raw_line = raw_line
        self._raw_text = self._gen_raw_text()
        self._is_title_span, self._is_section_heading_span = self._build_span_funcs()
        
        self.is_title_line = self._check_is_title()
        self.is_section_heading = self._check_is_section_heading()
        self.is_attribute_start = self._check_is_attribute_start()
        self._enforce_logical_precedence()
        self.section_depth = self._calc_section_depth()

    def _build_span_funcs(self):
        
        def _is_title_span(span:Dict) -> bool:
            span_size = span.get('size', self.font_sizes[0])
            return span_size >= self.font_sizes[-1]
        
        def _is_section_heading_span(span:Dict) -> bool:
            span_size = span.get('size', self.font_sizes[0])
            return (span_size > self.font_sizes[0]) & (span_size < self.font_sizes[-1])
        
        return _is_title_span, _is_section_heading_span

    def _gen_raw_text(self):
        return reduce(lambda x, y: x + y.get('text', ''), self._raw_line['spans'], '')
    
    def get_raw_text(self):
        return self._raw_text

    def get_key_val_split(self):
        key_val_split = self._raw_text.split(': ', maxsplit=1)
        if len(key_val_split) < 2:
            key, val = key_val_split, None
        else:
            key, val = key_val_split
        return key, val

    def _check_is_title(self):
        # Just check if it has largest font
        spans = self._raw_line['spans']
        title_sized = tuple(filter(self._is_title_span, spans))
        return len(title_sized) > 0   
     
    def _check_is_section_heading(self):
        # Just check if it has larger font but not largest
        spans = self._raw_line['spans']
        section_sized = tuple(filter(self._is_section_heading_span, spans))
        return len(section_sized) > 0
    
    def _check_is_attribute_start(self):
        # Just check if it has a colon
        if ':' in self._raw_text:
            return True
        else:
            return False
        
    def _enforce_logical_precedence(self):
        if self.is_title_line:
            self.is_attribute_start = False
            self.is_section_heading = False
        elif self.is_section_heading:
            self.is_attribute_start = False
        else:
            pass

    def _calc_section_depth(self):
        if self.is_title_line or len(self.font_sizes) <= 3:
            return 0
        
        max_span_size = max(tuple(s['size'] for s in self._raw_line['spans']))
        # Only need to iterate over middle sizes
        for i, size in enumerate(sorted(self.font_sizes[1:-1], reverse = True)):
            if max_span_size <= size:
                return i
            
        # All else fails
        return 0

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
        else:
            splittable_indices = list(map(lambda x: x[0], splittable_lines))
        # Ensure last bit always extends to the end of the slice
        if splittable_indices[-1] != len(section_lines_slice) - 1:
            splittable_lines.append(len(section_lines_slice))

        for chunk_start, chunk_end in zip(splittable_indices[0:-1], splittable_indices[1::]):
            key, start_text = section_lines_slice[chunk_start].get_key_val_split()
            remaining_text = ' '.join(section_lines_slice[chunk_start+1:chunk_end])
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
        # Below title is always WEG Location, Tier, etc. so this doesn't need to be as robust
        for l in char_lines[root_start+1:root_end]:
            try:
                key, val = l.get_key_val_split()
                out[key] = val
            except ValueError:
                # key = l._raw_text.split(': ', maxsplit=1)
                out[key] = None
        
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

            current_section_dict = section_content
            current_depth = section_depth

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

# t['blocks']
# block['lines']
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

    wegitems[0].to_document_dict()
    # for i in range(1):
        # p = doc.load_page(i)
        # t = p.get_text('dict', clip = [0, 36, 800, 760])
        # all_spans = flatten_to_spans(t)

        # sizes = set()
        # flags = set()
        # charflags = set()
        # colors = set()
        # fonts = set()
        # alphas = set()
        # for s in all_spans:
        #     sizes.add(s.get('size', -1))
        #     flags.add(s.get('flags', -1))
        #     charflags.add(s.get('char_flags', -1))
        #     colors.add(s.get('color', -1))
        #     fonts.add(s.get('font', ''))
        #     alphas.add(s.get('alpha', -1))

        # debug_iter_print(sorted(sizes), 'Sizes')
        # debug_iter_print(sorted(flags), 'Flags')
        # debug_iter_print(sorted(charflags), 'Char Flags')
        # debug_iter_print(sorted(colors), 'Colors')
        # debug_iter_print(sorted(fonts), 'Fonts')
        # debug_iter_print(sorted(alphas), 'Opacities')

        # pprint(tuple(filter(lambda x: x.get('size', 0.0) > 8.0, all_spans)))