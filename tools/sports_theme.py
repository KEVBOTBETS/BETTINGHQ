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
            source=re.sub(r'<(?:link|script)\b[^>]*data-kb-shared="true"[^>]*>(?:</script>)?\s*','',source,flags=re.I)
            # Reapplying presentation must not duplicate the network navigation.
            source = re.sub(r'\s+data-kb-(?:sport|page|light)="[^"]*"', '', source)
            source = re.sub(r'<link\b[^>]*href="[^"]*sports-theme\.css"[^>]*>\s*', '', source, flags=re.I)
            source = re.sub(r'<nav\b[^>]*class="kb-network"[^>]*>.*?</nav>', '', source, flags=re.I|re.S)
            identity = sport if sport != 'hq' else page.stem
            light = ' data-kb-light="true"' if sport in ('nfl','ncaaf','mlb','wnba') or identity == 'ledger' else ''
            source = re.sub(r'<html\b', '<html data-kb-sport="'+sport+'" data-kb-page="'+identity+'"'+light, source, count=1, flags=re.I)
            href = os.path.relpath(css, page.parent).replace(os.sep, '/')
            source = re.sub(r'</head>', '<link rel="stylesheet" href="'+href+'">\n</head>', source, count=1, flags=re.I)
            # The same controls reach every generated board on every rebuild.
            # Never inject twice, and retain the existing board's own scripts.
            shared=['value-core.js','execution-core.js','betsync.js','site-tools-core.js','parlay-removal-core.js','site-tools.js']
            if identity in ('accuracy','ledger'): shared.append('receipt-audit.js')
            snippets=[]
            shared_css=os.path.relpath(root/'bet-ledger-hq/site-tools.css',page.parent).replace(os.sep,'/')
            if 'site-tools.css' not in source: snippets.append('<link data-kb-shared="true" rel="stylesheet" href="'+shared_css+'">')
            for name in shared:
                if re.search(r'<script\b[^>]*src="[^"]*(?:/|^)'+re.escape(name)+'"',source):continue
                if 'src="'+name+'"' in source:continue
                src=os.path.relpath(root/'bet-ledger-hq'/name,page.parent).replace(os.sep,'/')
                snippets.append('<script data-kb-shared="true" src="'+src+'" defer></script>')
            source=re.sub(r'</head>', '\n'.join(snippets)+'\n</head>',source,count=1,flags=re.I)
            if sport != 'hq':
                home = os.path.relpath(root/'bet-ledger-hq/index.html', page.parent).replace(os.sep, '/')
                desk = os.path.relpath(root/'bet-ledger-hq/sports-desk.html', page.parent).replace(os.sep, '/')
                league = sport if sport in ('nfl','ncaaf','mlb','nhl','wnba') else 'nfl'
                parlay_link=f'<a href="{home}#ncaaf-parlays" target="_top">GAME PARLAYS ↗</a>' if sport=='ncaaf' else ''
                nav = f'<nav class="kb-network" aria-label="Matchday network"><a href="{home}#today" target="_top">KB / {sport.upper()} LAB</a><a href="{desk}?sport={league}">SPORTS DESK ↗</a><a href="{home}#accuracy" target="_top">PERFORMANCE ↗</a>{parlay_link}</nav>'
                source = re.sub(r'(<body\b[^>]*>)', lambda m:m[0]+nav, source, count=1, flags=re.I)
            page.write_text(source)
