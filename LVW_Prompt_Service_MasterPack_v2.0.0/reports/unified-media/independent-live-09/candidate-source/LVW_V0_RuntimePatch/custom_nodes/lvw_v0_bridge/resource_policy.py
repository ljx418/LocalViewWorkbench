"""Shared approved GPU admission v2; CPU-only policy, no resource queries.

The observed single-image profile permits monitored trials, not a claim that
all video/benchmark workloads have already met the unchanged runtime cap.
"""
POLICY_VERSION='lvw.gpu-admission/2'
MODEL_TAG='gemma4:26b'
MODEL_DIGEST='5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251'
HARD_PEAK_MIB=23552
OBSERVED_INCREMENT_MIB=18535
FREE_RESERVE_MIB=512
REQUIRED_FREE_MIB=OBSERVED_INCREMENT_MIB+FREE_RESERVE_MIB


class PolicyError(ValueError):
    def __init__(self,reason,evidence=None):
        super().__init__(reason);self.reason=reason;self.evidence=evidence or {}


def profile(model=MODEL_TAG,digest=MODEL_DIGEST,num_ctx=2048,max_parallel=1,image_long_edge=1024,video_frame_long_edge=768):
    if any(type(x) is not int for x in (num_ctx,max_parallel,image_long_edge,video_frame_long_edge)):
        raise PolicyError('GPU_MODEL_PROFILE_UNVERIFIED')
    if (model,digest,num_ctx,max_parallel,image_long_edge,video_frame_long_edge)!=(MODEL_TAG,MODEL_DIGEST,2048,1,1024,768):
        raise PolicyError('GPU_MODEL_PROFILE_UNVERIFIED')
    return {'version':POLICY_VERSION,'model':MODEL_TAG,'model_digest':MODEL_DIGEST,'num_ctx':2048,'num_predict':768,'max_parallel':1,
        'image_long_edge':1024,'video_frame_long_edge':768,'observed_increment_mib':OBSERVED_INCREMENT_MIB,
        'minimum_free_reserve_mib':FREE_RESERVE_MIB,'required_free_mib':REQUIRED_FREE_MIB,
        'hard_peak_mib_exclusive':HARD_PEAK_MIB,'calibration':'observed_single_image_monitored_trial'}


def valid_baseline(value):
    return type(value) is int and 0<=value<HARD_PEAK_MIB


def admit(native,wsl=None,*,warm=False):
    if type(warm) is not bool:raise PolicyError('RESOURCE_TELEMETRY_INVALID')
    if wsl is None:wsl=native
    if (not isinstance(native,list) or not isinstance(wsl,list) or len(native)!=1 or len(wsl)!=1):
        raise PolicyError('RESOURCE_TELEMETRY_INVALID')
    rows=[native[0],wsl[0]]
    for row in rows:
        if (not isinstance(row,list) or len(row)!=4 or any(type(x) is not int or x<0 for x in row)
                or row[1]<=0 or row[2]+row[3]>row[1]):raise PolicyError('RESOURCE_TELEMETRY_INVALID')
    if rows[0][:2]!=rows[1][:2]:raise PolicyError('RESOURCE_DEVICE_MISMATCH')
    total=rows[0][1];used=max(row[2] for row in rows);free=min(row[3] for row in rows)
    evidence={'policy':profile(),'gpu_count':1,'gpu_total_mib':total,'max_used_mib':used,'min_free_mib':free,
        'reserved_mib':[row[1]-row[2]-row[3] for row in rows],
        'native_wsl_difference_mib':abs(rows[0][2]-rows[1][2]),'warm':warm}
    if total<HARD_PEAK_MIB:raise PolicyError('GPU_CAPACITY_INSUFFICIENT',evidence)
    if warm:
        if used>=HARD_PEAK_MIB:raise PolicyError('GPU_RUNTIME_PEAK_EXCEEDED',evidence)
    else:
        evidence['projected_total_used_mib']=used+OBSERVED_INCREMENT_MIB
        if free<REQUIRED_FREE_MIB or evidence['projected_total_used_mib']>=HARD_PEAK_MIB:
            raise PolicyError('GPU_MEMORY_HEADROOM_INSUFFICIENT',evidence)
    return evidence
