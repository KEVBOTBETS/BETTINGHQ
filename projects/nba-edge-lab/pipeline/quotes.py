"""Only paired, named-book current prices; no default juice or opener fallback."""
from .model import number

def parse_espn(rows, observed):
    output=[]
    for row in rows:
        book=(row.get('provider') or {}).get('name')
        if not book or any(x in book.lower() for x in ('consensus','opening')):continue
        for market,key,sides in [('ML','moneyline',('home','away')),('ATS','pointSpread',('home','away')),('TOTAL','total',('over','under'))]:
            values=[]
            for side in sides:
                block=(row.get(key) or {}).get(side) or {}
                current=block.get('current') or block.get('close') or (block if 'open' not in block else {})
                price=number(current.get('odds',current.get('american')))
                line=number(current.get('line',current.get('pointSpread')))
                if market=='TOTAL' and line is None:line=number(row.get('overUnder'))
                if price is None or not 100<=abs(price)<=100000 or (market!='ML' and line is None):break
                values.append({'market':market,'side':side,'line':line if market!='ML' else None,'price':price,'book':book,'observed_at':observed,'source':'ESPN public odds','source_url':'https://www.espn.com/nba/odds'})
            if len(values)!=2:continue
            if market=='ATS' and abs(values[0]['line']+values[1]['line'])>1e-8:continue
            if market=='TOTAL' and values[0]['line']!=values[1]['line']:continue
            for i,q in enumerate(values):q['opposite_price']=values[1-i]['price']
            output.extend(values)
    return output
