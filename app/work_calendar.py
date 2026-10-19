"""Shared weekly work schedule; independent of livestock and feed accounting."""
import re
from datetime import timedelta
from .domain import day, Invalid


def validate_task(d):
    out=dict(d)
    for key,limit,required in [('title',120,True),('note',1000,False),('time',5,False)]:
        value=out.get(key,'')
        if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):
            raise Invalid('invalid_calendar_task')
        out[key]=value.strip()
    if out['time'] and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',out['time']):
        raise Invalid('invalid_calendar_task')
    if out.get('mode') not in ('weekly','once') or not isinstance(out.get('active',True),bool):
        raise Invalid('invalid_calendar_task')
    out['active']=out.get('active',True)
    if out['mode']=='weekly':
        if type(out.get('weekday')) is not int or not 0<=out['weekday']<=6:
            raise Invalid('invalid_calendar_task')
        out['start_date']=day(out.get('start_date')).isoformat()
        out['end_date']=day(out['end_date']).isoformat() if out.get('end_date') else ''
        if out['end_date'] and out['end_date']<out['start_date']:raise Invalid('invalid_period')
        out.pop('date',None)
    else:
        out['date']=day(out.get('date')).isoformat()
        for key in ('weekday','start_date','end_date'):out.pop(key,None)
    return out


def calendar_week(data, selected=None):
    from .review import farm_today
    selected=day(selected or farm_today())
    try:
        monday=selected-timedelta(days=selected.weekday())
        sunday=monday+timedelta(days=6)
    except OverflowError:raise Invalid('invalid_date')
    days=[]
    for index in range(7):
        date=(monday+timedelta(days=index)).isoformat()
        tasks=[]
        for task in data.get('work_tasks',[]):
            if not task.get('active',True):continue
            include=(task['mode']=='once' and task['date']==date) or (task['mode']=='weekly' and task['weekday']==index and task['start_date']<=date and (not task.get('end_date') or date<=task['end_date']))
            if include:tasks.append(dict(task))
        tasks.sort(key=lambda t:(t.get('time') or '99:99',t['title'],t['id']))
        days.append({'date':date,'weekday':index,'tasks':tasks})
    return {'from':monday.isoformat(),'to':sunday.isoformat(),'days':days}
