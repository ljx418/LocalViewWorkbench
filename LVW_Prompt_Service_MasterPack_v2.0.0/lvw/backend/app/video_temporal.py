"""CPU pixel measurements and conservative sampled temporal evidence; no physical classifier."""
from __future__ import annotations
from io import BytesIO
import hashlib
from PIL import Image,ImageChops,ImageStat
from .errors import AppError

POLICY_VERSION='lvw.temporal-evidence/1'
FIT_REDUCTION_MIN=.5
STABLE_COMPONENT_ERROR_MAX=1.0


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise AppError('JOB_CANCELLED','视频计量已取消',status_code=503)


def temporal_pixel_measurements(images: list[bytes], cancel=None) -> list[dict]:
    """Measured metadata only: no motion direction/class or sample-specific answers."""
    decoded=[]
    for payload in images:
        _check_cancel(cancel)
        with Image.open(BytesIO(payload)) as image:
            decoded.append(image.convert('RGB'))
    result=[]
    for index,(left,right) in enumerate(zip(decoded,decoded[1:]),1):
        _check_cancel(cancel)
        if left.size != right.size:
            raise AppError('PARSE_PARTIAL','视频采样帧尺寸不一致',status_code=503)
        difference=ImageChops.difference(left,right)
        red,green,blue=difference.split()
        nonzero=ImageChops.lighter(ImageChops.lighter(red,green),blue)
        changed=left.width*left.height-nonzero.histogram()[0]
        result.append({'from_frame':index,'to_frame':index+1,
            'changed_pixel_count':changed,'frame_pixel_count':left.width*left.height,
            'different_pixel_percent':round(100*changed/(left.width*left.height),4),
            'mean_absolute_rgb_delta':round(sum(ImageStat.Stat(difference).mean)/3,6)})
    return result


def _register_component(previous: Image.Image, next_image: Image.Image, cancel=None) -> dict:
    """Same bounded, fixed-area registration for any scalar pixel component."""
    width,height=previous.size
    radius=min(10,(min(width,height)-1)//4)
    if radius<1:
        return {'usable':False,'reason':'analysis_too_narrow'}
    window=(radius,radius,width-radius,height-radius)
    reference=previous.crop(window)
    if ImageStat.Stat(reference).stddev[0]==0:
        return {'usable':False,'reason':'reference_has_no_texture'}
    scores=[]
    for dy in range(-radius,radius+1):
        _check_cancel(cancel)
        for dx in range(-radius,radius+1):
            shifted=next_image.crop((window[0]-dx,window[1]-dy,window[2]-dx,window[3]-dy))
            error=int(ImageStat.Stat(ImageChops.difference(reference,shifted)).sum[0])
            scores.append((error,dx*dx+dy*dy,dy,dx))
    best=min(scores)
    unaligned=next(value[0] for value in scores if value[2]==0 and value[3]==0)
    area=reference.width*reference.height
    return {'usable':True,'analysis_size':[width,height],'search_radius_px':radius,
        'next_to_previous_alignment_offset_px':{'x':best[3],'y':best[2]},
        'unaligned_mean_luma_error':round(unaligned/area,6),
        'best_aligned_mean_luma_error':round(best[0]/area,6),
        'relative_error_reduction':round((unaligned-best[0])/unaligned,6) if unaligned else 0,
        'equally_best_offsets':sum(value[0]==best[0] for value in scores)}


def temporal_alignment_measurements(images: list[bytes], cancel=None) -> list[dict]:
    """Generic luma + colour-component registration, never object/camera labels.

    Opponent components are (first-second)/2+128, truncated/clamped by Pillow.
    Thumbnail filtering, central-window/search limits and aliases apply to all.
    Component differences do not identify semantic regions or physical causes.
    """
    decoded=[]
    original_size=None
    for payload in images:
        _check_cancel(cancel)
        with Image.open(BytesIO(payload)) as source:
            if original_size is not None and source.size!=original_size:
                raise AppError('PARSE_PARTIAL','视频采样帧尺寸不一致',status_code=503)
            original_size=source.size
            # Preserve the previous luma calculation exactly; colour is additional evidence.
            luma=source.convert('L')
            luma.thumbnail((128,128),Image.Resampling.LANCZOS)
            rgb=source.convert('RGB')
            rgb.thumbnail((128,128),Image.Resampling.LANCZOS)
            red,green,blue=rgb.split()
            decoded.append((luma,[ImageChops.subtract(first,second,scale=2,offset=128)
                for first,second in [(red,green),(green,blue),(blue,red)]]))
    result=[]
    for index,((previous,previous_colour),(next_image,next_colour)) in enumerate(zip(decoded,decoded[1:]),1):
        _check_cancel(cancel)
        measurement={'from_frame':index,'to_frame':index+1,**_register_component(previous,next_image,cancel)}
        components=[]
        for name,left,right in zip(('R-G','G-B','B-R'),previous_colour,next_colour):
            registered=_register_component(left,right,cancel)
            component={'component':name,'usable':registered['usable']}
            if registered['usable']:
                component.update(offset_px=registered['next_to_previous_alignment_offset_px'],
                    zero_error=registered['unaligned_mean_luma_error'],
                    best_error=registered['best_aligned_mean_luma_error'],
                    error_reduction_percent=round(100*registered['relative_error_reduction'],4),
                    equally_best_offsets=registered['equally_best_offsets'])
            else:
                component['reason']=registered['reason']
            components.append(component)
        measurement['colour_components']=components
        result.append(measurement)
    return result




def measure_video_evidence(images: list[bytes], cancel=None) -> dict:
    if not 1<=len(images)<=4:
        raise AppError('PARSE_PARTIAL','实际视频帧数量无效',status_code=503)
    pixels=temporal_pixel_measurements(images,cancel)
    alignment=temporal_alignment_measurements(images,cancel)
    _check_cancel(cancel)
    return {'policy_version':POLICY_VERSION,'source_frame_sha256':[hashlib.sha256(value).hexdigest() for value in images],
        'frame_count':len(images),'pixel_pairs':pixels,'alignment_pairs':alignment,
        'policy':{'fit_reduction_min':FIT_REDUCTION_MIN,'stable_component_error_max':STABLE_COMPONENT_ERROR_MAX,
            'unique_local_fit_required':True,'physical_motion_classifier':False}}


def _pair_spatial_evidence(pair):
    """Report local fit features; never classify camera or name semantic objects."""
    moving=[];stable=False
    if pair.get('usable'):
        offset=pair['next_to_previous_alignment_offset_px']
        if (pair['equally_best_offsets']==1 and pair['relative_error_reduction']>=FIT_REDUCTION_MIN
                and (offset['x'] or offset['y'])):
            moving.append((offset['x'],offset['y']))
    for item in pair['colour_components']:
        if not item['usable'] or item['equally_best_offsets']!=1:continue
        offset=item['offset_px'];vector=(offset['x'],offset['y'])
        if vector==(0,0) and item['zero_error']<=STABLE_COMPONENT_ERROR_MAX:stable=True
        elif vector!=(0,0) and item['error_reduction_percent']>=100*FIT_REDUCTION_MIN:moving.append(vector)
    axis='horizontal' if moving and all(x and not y for x,y in moving) else 'vertical' if moving and all(y and not x for x,y in moving) else 'spatial' if moving else None
    return {'axis':axis,'relative':bool(moving and stable),'local_offsets':moving}


def temporal_summary(evidence: dict) -> dict:
    expected_policy={'fit_reduction_min':FIT_REDUCTION_MIN,'stable_component_error_max':STABLE_COMPONENT_ERROR_MAX,
        'unique_local_fit_required':True,'physical_motion_classifier':False}
    if evidence.get('policy_version')!=POLICY_VERSION or evidence.get('policy')!=expected_policy:
        raise AppError('PARSE_PARTIAL','时序计量规则版本不匹配',status_code=503)
    count=evidence['frame_count'];pairs=evidence['pixel_pairs']
    alignment=evidence['alignment_pairs']
    if (type(count) is not int or not 1<=count<=4 or len(evidence['source_frame_sha256'])!=count
            or len(pairs)!=count-1 or len(alignment)!=count-1):
        raise AppError('PARSE_PARTIAL','时序证据固定帧对分母不完整',status_code=503)
    for index,(pixels,fit) in enumerate(zip(pairs,alignment,strict=True),1):
        if (pixels['from_frame']!=index or pixels['to_frame']!=index+1
                or fit['from_frame']!=index or fit['to_frame']!=index+1
                or type(pixels['changed_pixel_count']) is not int
                or not 0<=pixels['changed_pixel_count']<=pixels['frame_pixel_count']
                or pixels['frame_pixel_count']<=0):
            raise AppError('PARSE_PARTIAL','时序证据帧身份或像素分母无效',status_code=503)
    if count==1:
        return {'kind':'one_frame','observation_zh':'程序测量：只有一个实际采样帧，无法比较跨帧变化。',
            'inference_zh':'','summary_zh':'仅有单帧外观，跨帧变化未确认。',
            'summary_en':'Only one sampled appearance is available; temporal changes are unverified.'}
    changed=any(item['changed_pixel_count']>0 for item in pairs)
    if not changed:
        return {'kind':'identical_samples','observation_zh':'程序测量：所取样帧的RGB像素相同；帧间过程未经验证。',
            'inference_zh':'','summary_zh':'已采样画面像素一致，帧间过程和连续动作未确认。',
            'summary_en':'The sampled images have identical RGB pixels; intervening events and continuous action are unverified.'}
    spatial=[_pair_spatial_evidence(pair) for pair in evidence['alignment_pairs']]
    observation='程序测量：相邻采样帧存在RGB像素差异；像素差异本身不证明物理运动。'
    if spatial and all(item['relative'] and item['axis']=='horizontal' for item in spatial):
        return {'kind':'apparent_relative_horizontal','observation_zh':observation,
            'inference_zh':'程序配准推断：部分颜色结构近似保持屏幕位置，其他可比较结构呈横向相对位移特征；具体物体与物理原因未确认。',
            'summary_zh':'采样画面中部分结构近似保持位置，其他结构呈横向相对变化迹象；真实镜头、主体动作及连续轨迹未确认。',
            'summary_en':'Across the sampled images, some structures remain approximately positioned while others show apparent lateral relative changes; physical camera motion, subject action and continuous trajectories are unverified.'}
    if spatial and all(item['axis'] for item in spatial):
        return {'kind':'apparent_spatial_fit','observation_zh':observation,
            'inference_zh':'程序配准推断：采样结构呈现平移拟合特征；这不等于已确认的物理镜头或主体运动。',
            'summary_zh':'采样画面呈空间配准变化特征，物理镜头与主体运动原因未确认。',
            'summary_en':'The sampled structures exhibit apparent spatial registration changes; physical camera or subject motion and its cause are unverified.'}
    return {'kind':'pixel_changes_unattributed','observation_zh':observation,'inference_zh':'',
        'summary_zh':'采样画面像素发生变化，可靠的位移特征与成因尚未确认。',
        'summary_en':'Pixels differ between the samples; reliable displacement and its cause remain unverified.'}


def compose_video_spec(appearance, evidence: dict):
    """Append separately attributed program evidence; never mutate model/raw words."""
    from .video_appearance import TEMPLATE_ID,TEMPLATE_VERSION
    if appearance.template_id!=TEMPLATE_ID or appearance.template_version!=TEMPLATE_VERSION:
        raise AppError('PARSE_PARTIAL','视频外观来源版本不匹配，未组合建议',status_code=503)
    if (len(appearance.domains.observation)!=evidence['frame_count']
            or any(not text.startswith(f'F{index} @ ') for index,text in enumerate(appearance.domains.observation,1))):
        raise AppError('PARSE_PARTIAL','逐帧外观分母与时序源不一致',status_code=503)
    result=appearance.model_copy(deep=True);summary=temporal_summary(evidence)
    result.domains.observation.append(summary['observation_zh'])
    if summary['inference_zh']:result.domains.inference.append(summary['inference_zh'])
    result.domains.unknowns.extend(['图像配准仅比较有界窗口，周期纹理可能产生多解；不能据此确定真实运镜、完整位移量或主体连续动作。'])
    result.text_zh=appearance.text_zh+'\n\n采样时序证据：'+summary['summary_zh']
    result.text_en=appearance.text_en+'\n\nSampled temporal evidence: '+summary['summary_en']
    result.technical.camera_motion='Physical camera motion unverified; use the separately attributed sampled temporal evidence.'
    result.technical.subject_action='Continuous subject action unverified; appearance descriptions refer only to the sampled instants.'
    return result
