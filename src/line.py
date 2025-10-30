from functools import reduce
from typing import Dict

class CharacterizedLine:

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

