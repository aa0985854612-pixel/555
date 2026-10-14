"""Synthetic worksheet; no customer farm data is included in the repository."""
import io
from datetime import date
from xml.sax.saxutils import escape
from zipfile import ZipFile

def workbook_fixture():
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    serial=lambda s:(date.fromisoformat(s)-date(1899,12,30)).days
    cells={'B1':serial('2026-10-14'),'R3':'進場頭數','S3':'存欄頭數','A6':'JD-TEST','C6':'第1.2棟','D6':serial('2026-07-01'),'E6':serial('2026-09-09'),'R6':100,'S6':90,'T6':5,'Z6':4,'AA6':1,'AB6':0,'AC6':'死亡','AC7':'賣汰','AC8':'售出','AF6':4,'AF7':1,'AF8':5,'I6':50,'H6':serial('2026-09-09')}
    for col,key in [('R','R6'),('S','S6'),('T','T6'),('Z','Z6'),('AA','AA6'),('AB','AB6')]:cells[col+'4']=cells[key]
    def cell(ref,value):
        if isinstance(value,str):return f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
        return f'<c r="{ref}"><v>{value}</v></c>'
    rows={}
    import re
    for ref,v in cells.items():rows.setdefault(int(re.search(r'\d+$',ref).group()),[]).append(cell(ref,v))
    sheet=f'<worksheet xmlns="{ns}"><sheetData>'+''.join(f'<row r="{r}">'+''.join(rows[r])+'</row>' for r in sorted(rows))+'</sheetData></worksheet>'
    comments={'AF6':'10/9-10/15\n10/11死1頭(1棟)\n10/13死1頭(2棟)\n10/14死2頭(2棟)','AF7':'10/9-10/15\n10/14淘汰1頭(1棟)','AF8':'10/9-10/15\n10/13出3頭\n10/14出2頭(1棟)'}
    out=io.BytesIO()
    with ZipFile(out,'w') as z:
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="肉豬各周存欄頭數  " sheetId="1" r:id="rId1"/><sheet name="肉豬各周存欄頭數(舊) " sheetId="2" r:id="rId2"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',sheet)
        z.writestr('xl/worksheets/sheet2.xml',f'<worksheet xmlns="{ns}"><sheetData><row r="1">'+cell('A1','HISTORICAL DATA PRESERVED')+cell('M1',500)+'</row></sheetData></worksheet>')
        z.writestr('xl/worksheets/_rels/sheet1.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="comment" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="../comments1.xml"/></Relationships>')
        z.writestr('xl/comments1.xml',f'<comments xmlns="{ns}"><commentList>'+''.join(f'<comment ref="{ref}"><text><t>{escape(text)}</t></text></comment>' for ref,text in comments.items())+'</commentList></comments>')
    return out.getvalue()
