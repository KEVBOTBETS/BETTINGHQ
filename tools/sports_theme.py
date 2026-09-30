"""Apply the shared sports presentation after generated pages are staged.

Models, IDs, controls and saved state are untouched. One stylesheet means a
scheduled rebuild cannot silently revert the visual design of one league.
"""
import os
import re

SPORTS = {'bet-ledger-hq': 'hq', 'nfl-edge-lab': 'nfl', 'ncaaf-edge-lab': 'ncaaf',
          'mlb-edge': 'mlb', 'wnba-edge-lab': 'wnba', 'nhl-edge-lab': 'nhl',
          'props-edge': 'props', 'ladderbet': 'ladder'}

def apply(root):
    css = root/'bet-ledger-hq/sports-theme.css'
    for directory, sport in SPORTS.items():
        for page in (root/directory).glob('*.html'):
            source = page.read_text()
            if not re.search(r'</head>', source, re.I): continue  # Redirect-only aliases.
            identity = sport if sport != 'hq' else page.stem
            light = ' data-kb-light="true"' if sport in ('nfl','ncaaf','mlb','wnba') or identity == 'ledger' else ''
            source = re.sub(r'<html\b', '<html data-kb-sport="'+sport+'" data-kb-page="'+identity+'"'+light, source, count=1, flags=re.I)
            href = os.path.relpath(css, page.parent).replace(os.sep, '/')
            source = re.sub(r'</head>', '<link rel="stylesheet" href="'+href+'">\n</head>', source, count=1, flags=re.I)
            page.write_text(source)
