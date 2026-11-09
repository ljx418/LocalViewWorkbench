"""Offline synthetic fixtures for native multi-image visibility, not video quality."""
from pathlib import Path
import hashlib,json
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/unified-media/protocol-witness-fixtures-04'
if __name__=='__main__':
    OUT.mkdir(exist_ok=False)
    definitions=[('#e7cc34','yellow','purple filled circle on left'),
        ('#183b62','navy blue','orange filled triangle on right'),
        ('#f1eee7','ivory white','black diagonal stripe'),
        ('#9be0c7','mint green','magenta outline square in center')]
    items=[]
    for index,(color,background,shape) in enumerate(definitions):
        image=Image.new('RGB',(256,192),color);draw=ImageDraw.Draw(image)
        if index==0:draw.ellipse((24,64,88,128),fill='#8036a8')
        elif index==1:draw.polygon([(175,36),(235,148),(112,148)],fill='#f47c22')
        elif index==2:draw.line((30,164,222,22),fill='#101010',width=18)
        else:draw.rectangle((72,40,184,152),outline='#ba237d',width=8)
        path=OUT/f'frame-{index}.ppm';image.save(path,format='PPM')
        items.append({'index':index+1,'path':str(path.relative_to(ROOT)),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size':[256,192],
            'expected_background':background,'expected_shape':shape})
    (OUT/'receipt.json').write_text(json.dumps({'kind':'OFFLINE_SYNTHETIC_PROTOCOL_FIXTURES_NOT_VIDEO_QUALITY',
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'items':items,
        'model_calls':0,'existing_media_reads':0,'source_video_present':False,
        'holdouts_used':False,'not_a_replacement_for_tracking_fixed_quality_sample':True,
        'stage_pass_claim':False},indent=2)+'\n')
    print('Created4 synthetic protocol frames; no model, sourcevideo or human holdout used.')
