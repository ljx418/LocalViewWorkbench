from __future__ import annotations
import copy,random,threading
from io import BytesIO
from PIL import Image,ImageChops,ImageDraw
import pytest
from app.errors import AppError
from app.video_temporal import measure_video_evidence,temporal_summary,compose_video_spec
from test_video_appearance import appearance_envelope
from app.video_appearance import parse_appearance


def encode(image):
    stream=BytesIO();image.save(stream,format='PPM');return stream.getvalue()


def moving_background_fixed_chroma():
    rng=random.Random(612);background=Image.new('L',(96,72));background.putdata([rng.randrange(30,180) for _ in range(96*72)])
    result=[]
    for index in range(4):
        frame=ImageChops.offset(background,4*index,0).convert('RGB')
        ImageDraw.Draw(frame).rectangle((39,27,56,44),fill=(220,20,20));result.append(encode(frame))
    return result


def test_program_relative_change_is_measured_and_composition_never_rewrites_model_words():
    inputs=moving_background_fixed_chroma();before=inputs.copy();evidence=measure_video_evidence(inputs)
    assert inputs==before and len(evidence['pixel_pairs'])==len(evidence['alignment_pairs'])==3
    summary=temporal_summary(evidence);assert summary['kind']=='apparent_relative_horizontal'
    appearance=parse_appearance(appearance_envelope(),mode='realistic',frame_times=[1,3,5,7]);source=appearance.model_copy(deep=True)
    combined=compose_video_spec(appearance,evidence)
    assert appearance==source and combined.text_zh.startswith(source.text_zh)
    assert '横向相对' in combined.text_zh and 'lateral relative changes' in combined.text_en
    assert len(combined.domains.observation)==5 and combined.domains.inference
    assert 'unverified' in combined.technical.camera_motion and 'unverified' in combined.technical.subject_action
    wrong=source.model_copy(update={'template_id':'legacy-video'})
    with pytest.raises(AppError):compose_video_spec(wrong,evidence)
    with pytest.raises(AppError):compose_video_spec(combined,evidence)  # Never apply temporal evidence twice.


def test_identical_one_frame_and_illumination_do_not_become_physical_motion_claims():
    rng=random.Random(613);frame=Image.new('L',(64,48));frame.putdata([rng.randrange(30,180) for _ in range(64*48)])
    source=encode(frame.convert('RGB'))
    one=temporal_summary(measure_video_evidence([source]));assert one['kind']=='one_frame'
    identical=temporal_summary(measure_video_evidence([source]*4));assert identical['kind']=='identical_samples'
    assert 'unverified' in identical['summary_en'] and 'static video' not in identical['summary_en']
    brighter=encode(frame.point(lambda value:value+10).convert('RGB'))
    light=temporal_summary(measure_video_evidence([source,brighter]));assert light['kind']=='pixel_changes_unattributed'
    assert not light['inference_zh']


def test_noise_and_periodic_aliases_cannot_fake_confirmed_camera_motion():
    rng=random.Random(614)
    noise=[]
    for _ in range(2):
        image=Image.new('RGB',(64,48));image.putdata([tuple(rng.randrange(256) for _ in range(3)) for _ in range(64*48)])
        noise.append(encode(image))
    assert temporal_summary(measure_video_evidence(noise))['kind']=='pixel_changes_unattributed'
    stripes=Image.new('L',(64,48));stripes.putdata([200 if x%8<4 else 0 for y in range(48) for x in range(64)])
    evidence=measure_video_evidence([encode(stripes.convert('RGB')),encode(ImageChops.offset(stripes,2,0).convert('RGB'))])
    assert evidence['alignment_pairs'][0]['equally_best_offsets']>1
    assert temporal_summary(evidence)['kind']=='pixel_changes_unattributed'


def test_missing_pairs_or_wrong_source_identity_never_shrink_the_temporal_denominator():
    evidence=measure_video_evidence(moving_background_fixed_chroma())
    for key in ('pixel_pairs','alignment_pairs','source_frame_sha256'):
        changed=copy.deepcopy(evidence);changed[key].pop()
        with pytest.raises(AppError):temporal_summary(changed)
    changed=copy.deepcopy(evidence);changed['policy']['physical_motion_classifier']=True
    with pytest.raises(AppError):temporal_summary(changed)
    changed=copy.deepcopy(evidence);changed['pixel_pairs'][0]['to_frame']=3
    with pytest.raises(AppError):temporal_summary(changed)
    cancelled=threading.Event();cancelled.set()
    with pytest.raises(AppError) as caught:measure_video_evidence(moving_background_fixed_chroma(),cancelled)
    assert caught.value.code=='JOB_CANCELLED'
    with pytest.raises(AppError):measure_video_evidence([])
    with pytest.raises(AppError):measure_video_evidence(moving_background_fixed_chroma()+moving_background_fixed_chroma()[:1])


def test_fit_and_stable_error_exact_one_over_policy_edges():
    evidence=measure_video_evidence(moving_background_fixed_chroma()[:2]);pair=evidence['alignment_pairs'][0]
    pair['relative_error_reduction']=.5
    for component in pair['colour_components']:
        if component['usable']:
            component['error_reduction_percent']=0
            if component['offset_px']=={'x':0,'y':0}:component['zero_error']=1.0
    assert temporal_summary(evidence)['kind']=='apparent_relative_horizontal'
    pair['relative_error_reduction']=.499999
    assert temporal_summary(evidence)['kind']=='pixel_changes_unattributed'
    pair['relative_error_reduction']=.5
    for component in pair['colour_components']:
        if component['usable'] and component['offset_px']=={'x':0,'y':0}:component['zero_error']=1.000001
    assert temporal_summary(evidence)['kind']=='apparent_spatial_fit'
