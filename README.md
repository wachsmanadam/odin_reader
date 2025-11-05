# Odin Reader
This is a script utility for reading PDFs using pymupdf generated from OE Data Integration Network (ODIN)'s Worldwide Equipment Guide (WEG) into semi-structured JSON documents. 

## Dependencies
Python 3.12 and pymupdf  

Recommend using uv for initializing
  
## Process
Since WEG has a very handy PDF mass-export feature, I designed this around reading from those.  
  
The first step was to split exports into individual WEG entries. My strategy was simply to find every instance of "WEG Location:" since it was guaranteed on the first page of each entry and unlikely to appear anywhere else.  
  
Next, per WEG entry, subdivide into the title, section headings, and content. After a fair amount of poking around, it appeared that the only formatting Pymupdf picked up which could discern these was font size. To further complicate matters, the absolute font size values did not seem to be guaranteed consistent. Based on these observations, I decided to get all unique font size values per WEG entry, treat the largest size as title size, the smallest as content, and any size in between as levels of heading hierarchy.  
  
With a list of categorized line objects, the indices of multi-line blocks of title text and section headers are collected. Then it's simply a matter of processing joining those lines into single strings and processing the subsequent blocks of non-header text into key-value pairs underneath the preceding header (except for the content between the title block and the first section header block).

### Why?
This was an idea I had while using WEG as a potential data source for lower-echelon military modeling, but never wound up needing to devote the labor to during the day. I decided it would be a nice exercise to see it through on my own, and perhaps somebody in a similar position might find it useful. Plus nearly all of my years of work in this domain are not on public repositories for bureaucratic reasons and I hear it's a good thing to have a portfolio. 