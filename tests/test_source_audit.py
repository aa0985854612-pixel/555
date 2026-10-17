"""Archived vaccine dates are metadata, and old cohorts need no active IDs."""
import unittest,copy,base64,io,tempfile,json,uuid
from pathlib import Path
from zipfile import ZipFile
from datetime import date
from app.legacy import archive_review,archive_history_row,archive_movement_cell,history_report,review
from app.history import source_history
from app.review import data_quality
from app.store import Store
from legacy_fixture import workbook_fixture

def archive_fixture():
 raw=workbook_fixture();out=io.BytesIO()
 ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
 sheet=f'''<worksheet xmlns="{ns}"><sheetData><row r="3"><c r="AU3" t="inlineStr"><is><t>34W</t></is></c><c r="AV3" t="inlineStr"><is><t>APP+PR</t></is></c></row><row r="5"><c r="A5" t="inlineStr"><is><t>JD-OLD</t></is></c><c r="B5"><v>45000</v></c><c r="C5"><v>45070</v></c><c r="R5" t="inlineStr"><is><t>9棟</t></is></c><c r="V5" t="inlineStr"><is><t>死亡</t></is></c><c r="AU5"><v>2</v></c><c r="AV5"><v>45677</v></c><c r="AW5"><v>10</v></c></row></sheetData></worksheet>'''
 with ZipFile(io.BytesIO(raw)) as old,ZipFile(out,'w') as new:
  for name in old.namelist():new.writestr(name,sheet if name=='xl/worksheets/sheet2.xml' else old.read(name))
 return out.getvalue()

class SourceAuditTests(unittest.TestCase):
 def data(self):
  row={'key':'5','name':'JD-OLD','entry_date':'2024-01-01','barns':[9],'sheet':'肉豬各周存欄頭數(舊)','weights':[],'unresolved_cells':[],'events':[{'date':'2024-02-01','type':'death','quantity':1,'cell':'X5','text':'2/1死1頭','allocations':[]}]}
  book={'id':'book','report':{'rows':[],'archive_rows':[row],'sheet':'current'}}
  return {'barns':[{'id':'barn9','name':'9棟'}],'batches':[],'workbooks':[book],'movements':[],'weights':[],'source_voids':[],'feed_orders':[]}
 def test_only_week_columns_are_movements_not_vaccine_dates(self):
  r=review(archive_fixture());cells=r['archive_rows'][0]['unresolved_cells'];self.assertEqual([c['cell'] for c in cells],['AU5']);self.assertEqual(cells[0]['quantity'],2)
  self.assertTrue(archive_movement_cell('W5'));self.assertTrue(archive_movement_cell('AU5'));self.assertFalse(archive_movement_cell('AV5'));self.assertFalse(archive_movement_cell('AW5'))
 def test_cached_vaccine_cell_filtered_without_changing_report_or_ids(self):
  data=self.data();row=data['workbooks'][0]['report']['archive_rows'][0];row['unresolved_cells']=[{'cell':'AV5','type':'death','quantity':45677,'comment':'APP+PR'}];original=copy.deepcopy(data);before=source_history(data)
  self.assertEqual(len(before),1);self.assertEqual(before[0]['quantity'],1);self.assertEqual(data,original);self.assertEqual(source_history(data),before)
 def test_known_archive_barn_and_date_not_missing_active_batch(self):
  q=data_quality(self.data(),'2026-10-17');self.assertEqual(q['count'],0)
 def test_undated_archive_retains_missing_date_with_known_barn(self):
  data=self.data();data['workbooks'][0]['report']['archive_rows'][0]['events'][0]['date']=None
  q=data_quality(data,'2026-10-17');self.assertEqual(q['items'][0]['fields'],['missing_date'])
 def test_multi_barn_archive_still_needs_distribution(self):
  data=self.data();data['workbooks'][0]['report']['archive_rows'][0]['barns']=[9,10]
  q=data_quality(data,'2026-10-17');self.assertEqual(q['items'][0]['fields'],['missing_barn_allocation'])
 def test_source_mean_without_samples_is_still_marked(self):
  data=self.data();data['workbooks'][0]['report']['archive_rows'][0]['weights']=[{'date':'2024-02-01','mean_kg':50,'cell':'G5'}]
  q=data_quality(data,'2026-10-17');self.assertEqual(q['items'][0]['fields'],['source_mean_only'])
 def test_old_backup_cached_metadata_is_accepted_and_preserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(Path(tmp)/'db');user=s.create_user('owner','83000011');s.import_workbook(user,{'filename':'test.xlsx','base64':base64.b64encode(archive_fixture()).decode(),'counts_as_of':'2026-10-12','counts_text':'1/49\n2/50'},str(uuid.uuid4()));doc=s.export_backup()
   book=next(r for r in doc['records'] if r['kind']=='workbooks');b=json.loads(book['data']);b['report']['archive_rows'][0]['unresolved_cells'].append({'cell':'AV5','type':'death','quantity':45677,'unresolved_quantity':45677,'comment':'APP+PR'});book['data']=json.dumps(b)
   restored=Store(Path(tmp)/'restored');restored.import_backup(user,doc);restored.import_backup(user,doc);raw=restored.export_backup()['records'];stored=json.loads(next(r for r in raw if r['kind']=='workbooks')['data']);self.assertEqual(stored['report'],b['report']);self.assertNotIn(45677,[r['quantity'] for r in source_history(restored.snapshot())]);self.assertTrue(any(r['quantity']==2 for r in source_history(restored.snapshot())))
