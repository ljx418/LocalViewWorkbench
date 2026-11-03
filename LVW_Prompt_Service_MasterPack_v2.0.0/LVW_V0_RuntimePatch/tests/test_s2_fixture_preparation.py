"""Offline fixture authority and oracle tests; no actual media generation."""
import copy
import hashlib
from fractions import Fraction
import unittest

from tools.v0_s2_fixtures import authority,BUDGET,RECIPES,MARKER,recipe_hash,png_bytes,generate_argv,structural_oracle


def probe(kind):
    pts=list(range(8));hashes=['a'*64]*8
    if kind=='tracking':hashes=[str(i)*64 for i in range(8)]
    if kind=='fast-cut':hashes=[str(i//2)*64 for i in range(8)]
    if kind=='vfr':pts=[0,1,3,5,7,9,11,14];hashes=[str(i)*64 for i in range(8)]
    basis=Fraction(1,2) if kind=='vfr' else Fraction(1)
    value={'streams':[{'codec_type':'video','codec_name':'h264','width':320,'height':192,'time_base':str(basis)}],
        'format':{'duration':'8','nb_streams':1,'format_name':'mov,mp4','tags':{'comment':MARKER}},
        'frames':[{'pts':p} for p in pts]}
    raw='#tb 0: '+str(basis)+'\n'+''.join(f'0, {p}, {p}, 1, 100, {h}\n' for p,h in zip(pts,hashes))
    # Fraction(1) renders as "1"; actual FFmpeg always prints rational form.
    raw=raw.replace('#tb 0: 1\n','#tb 0: 1/1\n')
    return value,raw


class FixtureTests(unittest.TestCase):
    def auth(self):
        program={'status':'ACTIVE','authorization_id':'AUTH-PROGRAM-V1-LOCAL-01','stages':['V0-S2']}
        auth={'status':'ACTIVE_ONE_SHOT','stage_id':'V0-S2','workpack_id':'WP-S2-04-FIXTURE-PREPARATION',
              'source_program_authorization':program['authorization_id'],'scope':'CPU_FIXED_FIXTURE_PREPARATION_ONLY',
              'budget':BUDGET.copy(),'run_id':'fixture-preparation-01','recipe_sha256':recipe_hash(),'ports':[],
              'generated_png_sha256':hashlib.sha256(png_bytes()).hexdigest()}
        return auth,program
    def test_authority_binds_recipe_generated_bytes_scope_and_zero_external_actions(self):
        auth,program=self.auth();authority(auth,program)
        for key in ('provider_calls','service_starts','gpu_probes','browser_runs','downloads','cloud_calls','stage_checkpoints'):
            value=copy.deepcopy(auth);value['budget'][key]=1
            with self.subTest(key=key),self.assertRaises(ValueError):authority(value,program)
        for key,value in [('status','EXPIRED'),('recipe_sha256','a'*64),('generated_png_sha256','b'*64),
                          ('run_id','fixture-preparation-03'),('ports',[8191]),('workpack_id','other')]:
            with self.subTest(key=key),self.assertRaises(ValueError):authority({**auth,key:value},program)
        with self.assertRaises(ValueError):authority(auth,{**program,'status':'REVOKED'})

    def test_actual_pts_and_decoded_hashes_establish_four_categories(self):
        for category in ('static','tracking','fast-cut','vfr'):
            value,raw=probe(category);result=structural_oracle(category,value,raw)
            self.assertTrue(result['synthetic_structural_only']);self.assertEqual(8,result['frames'])
        value={'streams':[{'codec_type':'video','codec_name':'h264','width':64,'height':64,'time_base':'1/1'}],
            'frames':[{'pts':i} for i in range(61)],'format':{'duration':'61','nb_streams':1,'format_name':'mov,mp4'}}
        self.assertTrue(structural_oracle('over-duration',value,'')['expected_product_rejection'])
        value['format']['duration']='60'
        with self.assertRaises(ValueError):structural_oracle('over-duration',value,'')

    def test_category_labels_without_actual_frame_evidence_fail(self):
        for case in ('static-changed','tracking-unchanged','only-three-cuts','cfr-labelled-vfr','wrong-timestamp',
                     'duplicate-pts','fake-codec','missing-canary','fake-duration-gap','fake-container'):
            category='static'
            if case=='tracking-unchanged':category='tracking'
            if case=='only-three-cuts':category='fast-cut'
            if case=='cfr-labelled-vfr':category='vfr'
            value,raw=probe(category)
            if case=='static-changed':raw=raw.replace('a'*64,'b'*64,1)
            if case=='tracking-unchanged':raw=raw.replace('1'*64,'0'*64).replace('2'*64,'0'*64).replace('3'*64,'0'*64).replace('4'*64,'0'*64).replace('5'*64,'0'*64).replace('6'*64,'0'*64).replace('7'*64,'0'*64)
            if case=='only-three-cuts':raw=raw.replace('3'*64,'2'*64)
            if case=='cfr-labelled-vfr':
                value['streams'][0]['time_base']='1';value['frames']=[{'pts':i} for i in range(8)]
                raw='#tb 0: 1/1\n'
                raw+=''.join(f'0, {i}, {i}, 1, 100, '+str(i)*64+'\n' for i in range(8))
            if case=='wrong-timestamp':raw=raw.replace('0, 1, 1,','0, 1, 2,')
            if case=='duplicate-pts':value['frames'][1]['pts']=0
            if case=='fake-codec':value['streams'][0]['codec_name']='png'
            if case=='missing-canary':value['format']['tags']={}
            if case=='fake-duration-gap':value['format']['duration']='9'
            if case=='fake-container':value['format']['format_name']='image2'
            with self.subTest(case=case),self.assertRaises(ValueError):structural_oracle(category,value,raw)

    def test_generation_is_cpu_only_fixed_recipe_without_overwrite_or_shell(self):
        for kind,recipe in RECIPES.items():
            argv=generate_argv(kind,'OWNED/'+recipe['file'])
            self.assertIn('-n',argv);self.assertIn('none',argv);self.assertEqual('libx264',argv[argv.index('-c:v')+1])
            self.assertEqual('1',argv[argv.index('-threads')+1]);self.assertNotIn('-y',argv)
            self.assertNotIn('http',str(argv));self.assertNotIn('cuda',str(argv))


if __name__=='__main__':unittest.main()
