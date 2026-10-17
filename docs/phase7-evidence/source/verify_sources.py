#!/usr/bin/env python3
"""Read-only, offline source and interface checks for Phase 7 evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(primary_pdf=None):
    manifest = json.loads((HERE / 'manifest.json').read_text())
    mapping = json.loads((HERE / 'mappings.json').read_text())
    checked = []
    for name, row in manifest['remote_files'].items():
        if digest(HERE / name) != row['sha256']:
            raise ValueError('Fetched source changed: ' + name)
        checked.append(name)
    for name, expected in manifest.get('derived_notes',{}).items():
        if digest(HERE / name) != expected:
            raise ValueError('Source note or checker changed: ' + name)
    for name, expected in manifest['retained_dependencies'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Retained dependency changed: ' + name)
        checked.append(name)
    for name, row in manifest['primary_document']['extracts'].items():
        if digest(HERE / name) != row['sha256']:
            raise ValueError('Primary-document extract changed: ' + name)
        checked.append(name)
    if primary_pdf is not None and digest(primary_pdf) != manifest['primary_document']['original_sha256']:
        raise ValueError('Original primary PDF hash mismatch')
    for table in mapping['channels'].values():
        if [row['bit'] for row in table] != list(range(1,9)) or any(row['mask'] != 1 << (row['bit']-1) for row in table):
            raise ValueError('Invalid channel bit numbering')
    masks = {sign: sum(row['mask'] for row in mapping['channels']['005'] if row['rotation'] == sign)
             for sign in ('-U','-V','+U','+V')}
    qr = (HERE / 'upstream/Luminary099/Q,R-AXES_RCS_AUTOPILOT.agc').read_text()
    qr_table = re.search(r'(?ms)^ALLJETS\s+OCT.*?(?=^TYPEPOLY\s+OCT)',qr).group()
    qr_values = [int(value,8) for value in re.findall(r'\bOCT\s+([0-7]+)',qr_table)]
    if list(masks.values()) != qr_values:
        raise ValueError('Ch005 bit map differs from original Q/R ALLJETS table')
    p = (HERE / 'upstream/Luminary099/P-AXIS_RCS_AUTOPILOT.agc').read_text()
    p_table = re.search(r'(?ms)^JETSALL\s+OCT.*?(?=^TYPEP\s+OCT)',p).group()
    p_values = [int(value,8) for value in re.findall(r'\bOCT\s+([0-7]+)',p_table)]
    for index, sign in enumerate(('-P','+P')):
        if sum(row['mask'] for row in mapping['channels']['006'] if row['rotation']==sign) != p_values[index]:
            raise ValueError('Ch006 bit map differs from original P JETSALL table')
    t4 = (ROOT / 'docs/milestone2-evidence/startup/source/T4RUPT_PROGRAM.agc').read_text()
    if 'AOG = CDUX, AIG = CDUY, AMG = CDUZ' not in t4:
        raise ValueError('Original OIM=XYZ gimbal mapping missing')
    crew = (HERE / 'upstream/Contributed/LM_Simulator/modules/AGC_Crew_Inputs.tcl').read_text()
    for axis, word in (('Pitch','166'),('Yaw','167'),('Roll','170')):
        lower = axis.lower()
        block = crew[crew.index('# ---- '+axis+' ----'):]
        if 'set wdata('+word+') $'+lower not in block or 'set '+lower+' [expr $RHC'+axis+' + 63]' not in block:
            raise ValueError('RHC port/sign source differs: '+axis)
    neutral = mapping['words']['neutral']
    expected_words = {'pitch_plus':neutral & ~(16384|1),'pitch_minus':neutral & ~(16384|2),
        'yaw_minus':neutral & ~(16384|8),'yaw_minus_pitch_plus':neutral & ~(16384|8|1),
        'yaw_minus_pitch_minus':neutral & ~(16384|8|2)}
    if any(mapping['words'][name] != value for name,value in expected_words.items()):
        raise ValueError('RHC discrete word does not match source-defined active-low bits')
    if mapping['signed_20']['minus_ones_complement'] != 32767 - 20:
        raise ValueError('Invalid signed RHC encoding')
    # Original numeric allocation gives STATE at074, independently of old probes.
    address = None
    erasable = (ROOT / 'docs/milestone2-evidence/startup/source/ERASABLE_ASSIGNMENTS.agc').read_text()
    for line in erasable.splitlines():
        line = line.split('#',1)[0]
        match = re.match(r'^\s*SETLOC\s+([0-7]+)\s*$',line)
        if match:
            address = int(match[1],8)
        match = re.match(r'^\s*(?:(\S+)\s+)?ERASE(?:\s+([^\s]+))?',line)
        if not match:
            continue
        label, extent = match.groups()
        if label == 'STATE':
            break
        count = 1
        if extent:
            value = extent[1:]
            count += int(value[:-1],10) if value.endswith('D') else int(value,8)
        address += count
    flags = (HERE / 'upstream/Luminary099/FLAGWORD_ASSIGNMENTS.agc').read_text()
    if address != 0o74 or address+13 != int(mapping['readiness']['dapbools_address_octal'],8):
        raise ValueError('DAPBOOLS erasable address does not resolve')
    for expression in (r'DAPBOOLS\s+EQUALS\s+FLGWRD13',r'FLGWRD13\s+=\s+STATE \+13D',r'ACCSOKAY\s+=\s+BIT3',r'PULSES\s+=\s+BIT15'):
        if not re.search(expression,flags):
            raise ValueError('Readiness flag source definition missing')
    return {'status':'VERIFIED source checks','revision':manifest['revision'],'files_checked':len(checked),
        'channel005_masks_octal':{name:f'{value:05o}' for name,value in masks.items()},
        'gimbal_order':'OIM=XYZ','dapbools_address_octal':f'{address+13:04o}',
        'primary_full_pdf_checked':primary_pdf is not None,
        'coupled_execution':'NOT RUN by this source checker; inspect separate integration evidence'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--primary-pdf',type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.primary_pdf),indent=2))
