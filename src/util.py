from collections import deque
from functools import reduce

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