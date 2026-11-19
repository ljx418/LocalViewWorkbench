"""Metadata-only subprocess entrypoint; no Comfy, Torch or model imports."""
from fractions import Fraction
import json
import sys


def probe_document(path, *, av_module=None):
    if av_module is None:
        import av as av_module
    with av_module.open(path,mode='r',format='mov',options={
            'protocol_whitelist':'file,pipe','enable_drefs':'0'}) as container:
        if len(container.streams)>64:raise ValueError('stream limit')
        rows=[]
        for stream in container.streams:
            disposition=getattr(stream.disposition,'value',stream.disposition)
            row={'index':stream.index,'codec_type':stream.type,
                 'disposition':{'attached_pic':int(bool(int(disposition)&0x400))}}
            if stream.type=='video':
                row.update(width=stream.codec_context.width,height=stream.codec_context.height,
                    time_base=str(stream.time_base) if stream.time_base is not None else None,
                    start_pts=stream.start_time)
                if stream.duration is not None and stream.time_base is not None:
                    row['duration']=str(Fraction(stream.duration)*stream.time_base)
            rows.append(row)
        duration=None if container.duration is None else str(Fraction(container.duration,int(av_module.time_base)))
        return {'format':{'format_name':container.format.name,'duration':duration},
                'streams':rows,'probe_backend':'native-pyav'}


if __name__=='__main__':
    try:
        if len(sys.argv)!=2:raise ValueError('one owned snapshot required')
        result=probe_document(sys.argv[1])
        sys.stdout.buffer.write(json.dumps(result,ensure_ascii=True,allow_nan=False).encode('ascii'))
    except Exception as exc:
        sys.stderr.write(json.dumps({'code':'VIDEO_PROBE_FAILED','error_type':type(exc).__name__}))
        raise SystemExit(2)
