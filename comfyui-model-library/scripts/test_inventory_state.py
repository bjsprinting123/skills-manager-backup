import json
from pathlib import Path
import tempfile
import unittest
import inventory_state as inv

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'library';self.models=Path(self.temp.name)/'models';self.quarantine=Path(self.temp.name)/'quarantine'
        (self.root/'索引数据').mkdir(parents=True);self.models.mkdir();self.quarantine.mkdir()
    def cards(self, specs):
        rows=[]
        for mid,paths in specs.items():
            file=self.root/(mid+'.json');file.write_text(json.dumps({'contribution':{'model':{'model_id':mid,'sha256':mid,'local_files':[{'path':str(p)} for p in paths]}}}),'utf-8')
            rows.append({'model_id':mid,'current_revision':'r-1','paths':[file.name]})
        (self.root/'索引数据/model-index.json').write_text(json.dumps({'models':rows}),'utf-8')
    def test_local_remote_and_quarantine_are_distinct(self):
        p=self.models/'a.safetensors';p.write_bytes(b'fixture');q=self.quarantine/'q.safetensors';q.write_bytes(b'fixture')
        self.cards({'local':[p],'remote':[],'quarantine':[q]});inv.refresh(self.root,self.models,[self.quarantine]);d=inv.read_state(self.root)
        self.assertTrue(d['fresh']);self.assertTrue(d['records']['local']['is_local_unique'])
        self.assertFalse(d['records']['remote']['eligible_for_local_cleanup']);self.assertEqual(d['records']['quarantine']['status'],'quarantined')
    def test_two_paths_are_not_unique(self):
        ps=[self.models/'a.safetensors',self.models/'b.safetensors']
        for p in ps:p.write_bytes(b'fixture')
        self.cards({'one':ps});inv.refresh(self.root,self.models);r=inv.read_state(self.root)['records']['one']
        self.assertEqual(r['status'],'local_multiple');self.assertFalse(r['is_local_unique'])
    def test_delete_or_new_file_invalidates_snapshot_without_writing(self):
        p=self.models/'a.safetensors';p.write_bytes(b'fixture');self.cards({'one':[p]});inv.refresh(self.root,self.models)
        snapshot=(self.root/inv.RELATIVE_PATH).read_bytes();p.unlink();d=inv.read_state(self.root)
        self.assertFalse(d['fresh']);self.assertFalse(d['records']['one']['is_local']);self.assertEqual(snapshot,(self.root/inv.RELATIVE_PATH).read_bytes())
        inv.refresh(self.root,self.models);self.assertEqual(inv.read_state(self.root)['records']['one']['status'],'path_missing')
        (self.models/'new.safetensors').write_bytes(b'new');self.assertFalse(inv.read_state(self.root)['fresh'])
    def test_changed_card_index_invalidates_and_missing_snapshot_is_unknown(self):
        self.cards({'remote':[]});self.assertEqual(inv.read_state(self.root)['status'],'unknown');inv.refresh(self.root,self.models)
        p=self.root/'索引数据/model-index.json';d=json.loads(p.read_text());d['models'][0]['current_revision']='r-2';p.write_text(json.dumps(d))
        self.assertFalse(inv.read_state(self.root)['fresh'])

if __name__=='__main__':unittest.main()
