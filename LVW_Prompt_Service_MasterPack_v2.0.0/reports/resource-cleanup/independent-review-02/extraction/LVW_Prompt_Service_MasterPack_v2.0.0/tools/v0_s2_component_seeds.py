"""Preserve frozen seed identities while explicitly scoping dependency trees."""
from pathlib import PurePosixPath
from tools import v0_s2_stage_checkpoint as cp
from tools.v0_s2_execution_bindings import plain


def add_native_seed_files(files,paths,seeds):
    result=dict(files);aliases={}
    for index,row in enumerate(seeds['packages']['native_decoder_packages']['files']):
        prefix='COMFY_PYTHON_HOME/'
        if not row['alias'].startswith(prefix):raise ValueError('unknown native seed alias')
        relative=PurePosixPath(row['alias'][len(prefix):])
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('native seed path escapes declared dependency root')
        key=f'COMPONENT_SEED_{index:03}';result[key]=plain(paths['comfy_python'].parent/relative)
        aliases[key]=row['alias']
    return result,aliases


def verify_seed_identities(snapshot,seeds,metadata,aliases):
    observed={};original={row['alias']:row for row in snapshot['files']}
    for row in snapshot['files']:
        alias=aliases.get(row['alias'],row['alias'])
        for source,target in [('COMPONENT_FRONTEND/','COMFY_PYTHON_HOME/Lib/site-packages/comfyui_frontend_package/static/'),
                ('COMPONENT_AV/','COMFY_PYTHON_HOME/Lib/site-packages/av/'),('COMPONENT_PIL/','COMFY_PYTHON_HOME/Lib/site-packages/PIL/')]:
            if alias.startswith(source):alias=target+alias[len(source):];break
        canonical={**row,'alias':alias}
        if alias in observed and observed[alias]!=canonical:raise ValueError('inconsistent duplicate dependency identity')
        observed[alias]=canonical
    # Lookup aliases only. This is not a replacement execution manifest and
    # does not claim that the excluded whole Python/Ollama trees were sealed.
    cp.verify_observations({'files':list(observed.values())},seeds)
    if (len(metadata)!=2 or metadata[0].get('executable_sha256')!=original['NODE_EXECUTABLE']['sha256']
            or metadata[1].get('executable_sha256')!=original['POWERSHELL']['sha256']
            or any(r.get('command_terminal') is not True or type(r.get('exit_code')) is not int or r.get('exit_code')!=0 for r in metadata)):
        raise ValueError('metadata executed tools differ from captured component tools')
    return {'kind':'FROZEN_SEED_SUBSET_IDENTITIES_VERIFIED_NOT_STAGE_ACCEPTANCE',
        'native_seed_files':len(seeds['packages']['native_decoder_packages']['files']),
        'sdk_seed_files':len(seeds['frontend']['sdk']['files'])}
