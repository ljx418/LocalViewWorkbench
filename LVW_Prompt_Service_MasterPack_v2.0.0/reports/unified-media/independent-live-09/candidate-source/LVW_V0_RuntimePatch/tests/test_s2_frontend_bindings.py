import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.v0_s2_frontend_bindings import snapshot_sources,sdk_snapshot,registry_directories


class FrontendBindingTests(unittest.TestCase):
    def test_public_module_imports_and_marker_evidence_are_hashed_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'scripts').mkdir();(root/'assets').mkdir()
            (root/'scripts/api.js').write_text("export {api} from '../assets/api.js';")
            raw=b"export const api={apiURL:(x)=>'/api'+x,fetchApi(){}};"
            (root/'assets/api.js').write_bytes(raw)
            value=snapshot_sources([('WEB/scripts/api.js',root/'scripts/api.js')],{'WEB':root})
            self.assertEqual(2,len(value['files']));self.assertEqual(hashlib.sha256(raw).hexdigest(),value['files'][1]['sha256'])
            self.assertIn('apiURL',[v['marker'] for v in value['files'][1]['snippets']])

    def test_source_symlink_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'outside').write_text('not library');(root/'web').mkdir()
            (root/'web/api.js').symlink_to(root/'outside')
            with self.assertRaises(ValueError):snapshot_sources([('WEB/api.js',root/'web/api.js')],{'WEB':root/'web'})

    def test_sdk_code_manifest_is_exact_and_excludes_profile_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'lib').mkdir();(root/'lib/api.js').write_text('module.exports={};')
            (root/'package.json').write_text(json.dumps({'version':'synthetic'}));(root/'profile').mkdir()
            (root/'profile/cookies').write_text('never hashed')
            value=sdk_snapshot({'SDK':root});self.assertEqual(2,len(value['files']))
            self.assertFalse(any('profile' in v['alias'] for v in value['files']))
            before=value['manifest_sha256'];(root/'lib/api.js').write_text('module.exports={changed:true};')
            self.assertNotEqual(before,sdk_snapshot({'SDK':root})['manifest_sha256'])

    def test_sdk_registry_selects_exact_revisions_without_unrelated_cached_fallback(self):
        value={'browsers':[{'name':'chromium','revision':'123'},{'name':'chromium-headless-shell','revision':'124'},
                           {'name':'firefox','revision':'999'}]}
        self.assertEqual(['chromium-123','chromium_headless_shell-124'],registry_directories(value))
        for bad in ({'browsers':[]},{'browsers':value['browsers']+[value['browsers'][0]]}):
            with self.assertRaises(ValueError):registry_directories(bad)


if __name__=='__main__':unittest.main()
