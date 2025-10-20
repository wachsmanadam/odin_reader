from abc import ABC, abstractmethod
import pypdf
import pymupdf
from functools import reduce
from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict

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

class CharacterizedLine:

    @staticmethod
    def _is_title_span(span:Dict):
        span_size = span.get('size', 0)
        out = span_size >= 16.0
        return out
    
    @staticmethod
    def _is_section_heading_span(span:Dict):
        span_size = span.get('size', 0)
        out = (span_size >= 12.0) & (span_size < 16.0)
        return out

    def __init__(self, raw_line:Dict):
        self._raw_line = raw_line
        self._raw_text = self.get_raw_text()
        self.is_title_line = self._check_is_title()
        self.is_section_heading = self._check_is_section_heading()
        self.is_attribute_start = self._check_is_attribute_start()
        self._enforce_logical_precedence()

    def get_raw_text(self):
        return reduce(lambda x, y: x + y.get('text', ''), self._raw_line['spans'], '')

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

class WegItem:
    CLIP = [0, 36, 800, 760]
    def __init__(self, doc:pymupdf.Document, start_index:int, stop_index:int = None):
        stop_index = stop_index if stop_index is not None else doc.page_count - 1
        self.pages = doc.pages[start_index:stop_index]

# t['blocks']
# block['lines']
if __name__ == "__main__":
    from pathlib import Path

    docpath = Path(r'/workspaces/odin_reader/doc/fullwegexportcompressed.pdf')
    doc = pymupdf.open(docpath)

    for i in range(1):
        p = doc.load_page(i)
        t = p.get_text('dict', clip = [0, 36, 800, 760])
        all_spans = flatten_to_spans(t)

        sizes = set()
        flags = set()
        charflags = set()
        colors = set()
        fonts = set()
        alphas = set()
        for s in all_spans:
            sizes.add(s.get('size', -1))
            flags.add(s.get('flags', -1))
            charflags.add(s.get('char_flags', -1))
            colors.add(s.get('color', -1))
            fonts.add(s.get('font', ''))
            alphas.add(s.get('alpha', -1))

        # debug_iter_print(sorted(sizes), 'Sizes')
        # debug_iter_print(sorted(flags), 'Flags')
        # debug_iter_print(sorted(charflags), 'Char Flags')
        # debug_iter_print(sorted(colors), 'Colors')
        # debug_iter_print(sorted(fonts), 'Fonts')
        # debug_iter_print(sorted(alphas), 'Opacities')

        pprint(tuple(filter(lambda x: x.get('size', 0.0) > 8.0, all_spans)))
    # reader = pypdf.PdfReader(docpath)

    # def test_visitor(text, user_matrix, tm_matrix, font_dictionary, font_size):
    #     if font_dictionary is not None and not text.isspace() and font_size >= 12:
    #         print("========")
    #         print(text)
    #         # print(user_matrix)
    #         # print(tm_matrix)
    #         print(font_dictionary)
    #         print(font_size)
    #         print("========")

    # for i in range(10):
    #     page = reader.get_page(i)
    #     page.extract_text(visitor_text=test_visitor)


#    {'alpha': 0,
#   'ascender': 0.9000000357627869,
#   'bbox': (10.75, 135.3000030517578, 42.28129959106445, 144.2519989013672),
#   'bidi': 0,
#   'char_flags': 0,
#   'color': 0,
#   'descender': -0.21900001168251038,
#   'flags': 0,
#   'font': 'Unnamed-T3',
#   'origin': (10.75, 142.5),
#   'size': 8.0,
#   'text': 'Domain:'},
#    {'alpha': 0,
#   'ascender': 0.9000000357627869,
#   'bbox': (44.5078010559082,
#            135.3000030517578,
#            56.491798400878906,
#            144.24400329589844),
#   'bidi': 0,
#   'char_flags': 0,
#   'color': 0,
#   'descender': -0.21800000965595245,
#   'flags': 0,
#   'font': 'Unnamed-T3',
#   'origin': (44.5078010559082, 142.5),
#   'size': 8.0,
#   'text': 'Air,'},