"""Pure frozen identity negative cases; no installed tool/media access."""
import copy
import unittest
from tools.v0_s2_component_seeds import verify_seed_identities


class ComponentSeedTests(unittest.TestCase):
    def fixture(self):
        def row(alias,sha='a',size=1):return {'alias':alias,'sha256':sha*64,'bytes':size}
        targets={name:row(name) for name in ['COMFY_MAIN','COMFY_PYTHON','OLLAMA_EXE']}
        decoder=row('COMFY_PYTHON_HOME/Lib/site-packages/av/__init__.py','b')
        sdk=row('PLAYWRIGHT/index.js','c');frontend={**row('FRONTEND_PACKAGE/app.js','d'),'status':'HASHED'}
        browser=row('BROWSER_CACHE/chromium-test/chrome','e')
        seeds={'targets':{'executables':targets},'packages':{'native_decoder_packages':{'files':[decoder]}},
            'frontend':{'sdk':{'files':[sdk]},'frontend':{'files':[frontend]},'browser_binaries':[browser]}}
        snapshot={'files':copy.deepcopy([ *targets.values(),row('COMPONENT_SEED_000','b'),sdk,row('COMPONENT_FRONTEND/app.js','d'),
            row('BROWSER_EXECUTABLE','e'),row('NODE_EXECUTABLE','f'),row('POWERSHELL','1')])}
        metadata=[{'executable_sha256':c*64,'command_terminal':True,'exit_code':0} for c in ['f','1']]
        aliases={'COMPONENT_SEED_000':decoder['alias']}
        return snapshot,seeds,metadata,aliases

    def test_retained_seed_aliases_and_actual_executed_metadata_tool_must_match(self):
        values=self.fixture();verify_seed_identities(*values)
        for alias in ['COMFY_MAIN','COMFY_PYTHON','OLLAMA_EXE','COMPONENT_SEED_000','PLAYWRIGHT/index.js','COMPONENT_FRONTEND/app.js','BROWSER_EXECUTABLE']:
            snapshot,seeds,metadata,aliases=copy.deepcopy(values)
            next(r for r in snapshot['files'] if r['alias']==alias)['sha256']='9'*64
            with self.subTest(alias=alias),self.assertRaises(ValueError):verify_seed_identities(snapshot,seeds,metadata,aliases)
        snapshot,seeds,metadata,aliases=copy.deepcopy(values);metadata[0]['executable_sha256']='9'*64
        with self.assertRaises(ValueError):verify_seed_identities(snapshot,seeds,metadata,aliases)

    def test_missing_codec_and_conflicting_alias_cannot_be_hidden_by_smaller_tree(self):
        snapshot,seeds,metadata,aliases=self.fixture()
        snapshot['files']=[r for r in snapshot['files'] if r['alias']!='COMPONENT_SEED_000']
        with self.assertRaises(ValueError):verify_seed_identities(snapshot,seeds,metadata,aliases)
        snapshot,seeds,metadata,aliases=self.fixture()
        snapshot['files'].append({'alias':'COMPONENT_AV/__init__.py','sha256':'9'*64,'bytes':1})
        with self.assertRaises(ValueError):verify_seed_identities(snapshot,seeds,metadata,aliases)
