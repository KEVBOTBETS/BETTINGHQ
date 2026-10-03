import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

VERSION = 'research-2026-10-v1'

def instant(value):
    try:
        x = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return x.astimezone(timezone.utc) if x.tzinfo else None
    except (ValueError, TypeError):
        return None

def number(value):
    if value is None or isinstance(value, bool): return None
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError): return None

def read(path, default):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default

def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False)+'\n')
    temp.replace(path)

def seed(value):
    return int(hashlib.sha256(str(value).encode()).hexdigest()[:8], 16)

def decimal(price):
    p = number(price)
    return 1+p/100 if p is not None and p>=100 else 1+100/abs(p) if p is not None and p<=-100 else None

def team(game, side):
    x = game.get(side)
    return x.get('abbr') if isinstance(x, dict) else x

def key_team(x):
    return {'WAS':'WSH','LA':'LAR','OAK':'LV','SD':'LAC'}.get(x, x)

def margin_distribution(mean, sd, residuals=()):
    """Discrete residual mixture; smooth with a normal prior when evidence is thin."""
    sd=max(1.,float(sd)); mean=float(mean)
    support=range(-100,101)
    base={k:math.exp(-.5*((k-mean)/sd)**2) for k in support}
    norm=sum(base.values()); base={k:v/norm for k,v in base.items()}
    samples=[x for x in residuals if number(x) is not None]
    if len(samples)>=40:
        center=sum(samples)/len(samples);samples=[x-center for x in samples]
        empirical={k:sum(math.exp(-.5*((k-mean-r)/2)**2) for r in samples) for k in support}
        norm=sum(empirical.values()); w=min(.7,len(samples)/(len(samples)+100))
        base={k:(1-w)*base[k]+w*empirical[k]/norm for k in support}
    return base

def cover(dist, line):
    return {s:sum(p for k,p in dist.items() if (k+line>1e-9 if s=='win' else abs(k+line)<=1e-9 if s=='push' else k+line< -1e-9)) for s in ['win','push','loss']}

def summary(dist):
    def quantile(q):
        total=0
        for k,p in sorted(dist.items()):
            total+=p
            if total>=q:return k
        return max(dist)
    return {'mean':sum(k*p for k,p in dist.items()),'low':quantile(.1),'high':quantile(.9),'p_home':sum(p for k,p in dist.items() if k>0)+.5*dist.get(0,0)}
