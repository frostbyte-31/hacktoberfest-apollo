#!/usr/bin/env python3
"""GPL-2.0-or-later. Independent inspection of actual Phase 9 native traces.

This module does not drive the CPU, synthesize measurements or repair traces.
It requires complete native runs and reports each causal assertion separately.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REFSMBIT=0o10000
MARK_COMPLETE=0o23000
KEYS={**{str(i):i for i in range(1,10)},'0':16,'V':17,'N':31,'E':28,'+':26,'-':27}
KEY_INTERVAL=21333
ROPE_SHA='1f5326e038de5b741b2f27b01ec949dbd688cf1906994e997402587c8628f40e'

def raw(path):
    path=Path(path)
    if not path.exists():path=path.with_name(path.name+'.gz')
    data=path.read_bytes()
    return gzip.decompress(data) if path.suffix=='.gz' else data

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key: '+key)
        result[key]=value
    return result

def load_trace(path):
    data=raw(path)
    try:
        rows=[json.loads(line,object_pairs_hook=unique_object,
                         parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Non-finite JSON')))
              for line in data.splitlines()]
    except (json.JSONDecodeError,UnicodeDecodeError) as error:
        raise ValueError('Malformed trace') from error
    if not rows or rows[0].get('ev')!='initial' or rows[-1].get('ev')!='finish':
        raise ValueError('Incomplete trace: initial/finish boundaries required')
    previous=-1
    for row in rows:
        cycle=row.get('cycle')
        if type(cycle) is not int or cycle<previous:raise ValueError('Invalid or out-of-order CPU call')
        previous=cycle
        if row.get('ev') in ('failure','wait_timeout'):raise ValueError('Failed native run retained in trace')
        if row.get('ev') in ('input','output'):
            for field in ('channel','value'):
                if type(row.get(field)) is not int:raise ValueError('Non-integer packet')
            if not 0<=row['channel']<=255 or not 0<=row['value']<=0o77777:
                raise ValueError('Packet outside original interface width')
        if row.get('ev') in ('checkpoint','transition'):
            words=row.get('snapshot_words')
            if not isinstance(words,list) or any(type(word) is not int or not 0<=word<=0o177777 for word in words):
                raise ValueError('Invalid native observer snapshot')
    return rows

def load_run(directory):
    directory=Path(directory)
    data=raw(directory/'trace.jsonl')
    rows=load_trace(directory/'trace.jsonl')
    mapping=json.loads((directory/'observer-map.json').read_text())
    count=len(mapping['snapshot_addresses'])
    if any(len(r['snapshot_words'])!=count for r in rows if 'snapshot_words' in r):
        raise ValueError('Observer snapshot/map width mismatch')
    return {'directory':directory,'rows':rows,'mapping':mapping,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}

def words_for(row,mapping,name,count=1):
    address=mapping['addresses'][name]
    indices=mapping['snapshot_addresses']
    try:return [row['snapshot_words'][indices.index(address+i)] for i in range(count)]
    except (KeyError,ValueError) as error:raise ValueError('Observer does not capture '+name) from error

def native_display_agrees(rows):
    """Reconstruct from actual output packets using the retained Phase 1 decoder."""
    spec=importlib.util.spec_from_file_location('phase9_independent_display',ROOT/'docs/phase1-evidence/m2_dsky_client.py')
    decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)
    for row in rows:
        if row['ev']=='output' and row['channel']==0o10:
            decoder.apply010(row['value'])
            if row.get('display')!=decoder.snapshot():return False
        elif 'display' in row and row['display']!=decoder.snapshot():return False
        elif isinstance(row.get('state'),dict) and row['state'].get('display')!=decoder.snapshot():return False
    return True

def source_keys_agree(rows):
    """Check every logged sequence against real queued MNKEYIN packets."""
    sequences=[(i,row) for i,row in enumerate(rows) if row['ev']=='key_sequence']
    for j,(index,row) in enumerate(sequences):
        end=sequences[j+1][0] if j+1<len(sequences) else len(rows)
        packets=[r for r in rows[index+1:end] if r['ev']=='input' and r['channel']==0o15]
        try:expected=[(row['cycle']+i*KEY_INTERVAL,KEYS[key]) for i,key in enumerate(row['text'])]
        except KeyError:return False
        if [(r['cycle'],r['value']) for r in packets]!=expected:return False
    return True

def load_sequencing_agrees(rows,negative=False):
    sequences=[r for r in rows if r['ev']=='key_sequence']
    plans=[r for r in rows if r['ev']=='synthetic_star_plan']
    if len(plans)!=(1 if negative else 2):return False
    for plan in plans:
        following=[r for r in sequences if r['cycle']>=plan['cycle']]
        code=plan['code'];az=plan['azimuth_field'];el=plan['elevation_field']
        if not re.fullmatch(r'[0-7]{5}',code) or not all(re.fullmatch(r'[+-][0-9]{5}',v) for v in (az,el)):
            return False
        required=[('V21N71E','01','71'),(code+'E','21','71'),('V33E','01','71'),
                  ('V24N87E','06','87'),(az+'E','21','87'),(el+'E','22','87'),('V33E','06','87')]
        if len(following)<len(required):return False
        for row,(text,verb,noun) in zip(following,required):
            if row['text']!=text or (row['display']['VERB'],row['display']['NOUN'])!=(verb,noun):return False
    return True

def analyze_run(run,negative=False):
    rows,mapping=run['rows'],run['mapping'];addresses=mapping['addresses']
    startup=next((r for r in rows if r['ev']=='startup_complete'),None)
    if startup is None:raise ValueError('Missing startup observation')
    state=startup['state']
    original=[list(map(int,line.split())) for line in (ROOT/'docs/phase5-evidence/operate_inputs.txt').read_text().splitlines()[1:]]
    prefix=[tuple(row) for row in original if row[0]<2200000]
    inputs=[r for r in rows if r['ev']=='input']
    startup_inputs=[(r['cycle'],r['channel'],r['value']) for r in inputs if r['cycle']<2200000]
    checkpoints=[r for r in rows if r['ev']=='checkpoint']
    routine=lambda name:[r for r in checkpoints if r['routine']==name]
    transitions=[r for r in rows if r['ev']=='transition']
    flag_rows=[r for r in transitions if r['address']==addresses['FLAGWRD3'] and r['value']&REFSMBIT]
    matrix_rows=[r for r in transitions if addresses['REFSMMAT']<=r['address']<addresses['REFSMMAT']+18]
    irqs=[r for r in rows if r['ev']=='hardware_interrupt']
    marks=[r for r in inputs if r['channel']==0o16 and r['value']]
    pair_rows=[r for r in rows if r['ev']=='mark_pair_result']
    alignment=next((r for r in rows if r['ev']=='alignment_result'),None)
    p63=next((r for r in rows if r['ev']=='p63_result'),None)
    before_p63=next((r['cycle'] for r in rows if r['ev']=='key_sequence' and r['text']=='V37E63E'),None)
    frozen_baseline=[json.loads(line) for line in raw(ROOT/'docs/phase8-evidence/runs/attempt-03/baseline.stdout').splitlines()]
    output_projection=lambda records:[(r['cycle'],r['channel'],r['value']) for r in records
                                       if r['ev']=='output' and r['cycle']<=2200000]
    valid_snapshots=all(r['value']==r['snapshot_words'][mapping['snapshot_addresses'].index(r['address'])]
                        for r in transitions if r['address'] in mapping['snapshot_addresses'])
    checks={
        'fresh_unmodified_rope_no_flight_memory_writes':rows[0].get('original_ram_writes')==0 and rows[0].get('rope_sha256')==ROPE_SHA,
        'exact_phase5_startup_packets':startup_inputs==prefix and startup['cycle']==2200000,
        'phase5_startup_actual_outputs_match_phase8':output_projection(rows)==output_projection(frozen_baseline),
        'startup_is_legacy_unaligned_operate_state':state['modreg']==0o77777 and not state['refsmflg']
            and not state['flagword3']&REFSMBIT and not any(state['refsmmat'])
            and state['failreg']==[0o1520,0,0] and not state['imodes33']&32,
        'only_supported_accepted_hardware_packets':all(r['accepted_bytes']>0 and r['channel'] in (0o15,0o16,0o30,0o31) for r in inputs)
            and all(r['channel'] in (0o15,0o16) for r in inputs if r['cycle']>=2200000),
        'dsky_sequence_packets_match_logged_keys_and_cpu_timing':source_keys_agree(rows),
        'dsky_display_reconstructed_from_actual_output':native_display_agrees(rows),
        'octal_five_digit_code_and_signed_decimal_field_loads':load_sequencing_agrees(rows,negative),
        'native_transition_snapshots_agree_with_actual_values':valid_snapshots,
        'stationary_cdu_fixture_without_counter_feedback':all(r['snapshot_words'][7:10]==[0,0,0] for r in transitions+checkpoints)
            and all(not r['channel']&128 for r in inputs),
    }
    if negative:
        end=rows[-1]['state']
        checks.update({
            'negative_control_sends_actual_mark_packets':len(marks)==2 and [r['value'] for r in marks]==[4,8],
            'no_external_mark_irq_or_original_markrupt':not irqs and not routine('MARKRUPT'),
            'original_mark_pair_not_completed':bool(pair_rows) and all(r['after']&MARK_COMPLETE!=MARK_COMPLETE for r in pair_rows),
            'no_native_matrix_population_or_refsm_flag':not matrix_rows and not flag_rows
                and not end['refsmflg'] and not any(end['refsmmat']),
            'no_synthetic_alignment_or_p63_substitution':alignment is None and p63 is None
                and before_p63 is None and any(r['ev']=='negative_control_complete' for r in rows),
        })
    else:
        # Every interrupt must follow consumption of its real hardware input;
        # original MARKRUPT must then execute before the next release packet.
        mark_causes=[]
        for mark,irq,entry in zip(marks,irqs,routine('MARKRUPT')):
            mark_causes.append(mark['value']==irq.get('readback') and irq.get('channel')==0o16
                and irq.get('interrupt')==6 and irq.get('accepted')==1
                and mark['cycle']<irq['cycle']<entry['cycle'])
        first_flag=flag_rows[0] if flag_rows else None
        flag_matrix=words_for(first_flag,mapping,'REFSMMAT',18) if first_flag else []
        interpreted={name:words_for(first_flag,mapping,name)[0] for name in ('LOC','BANKSET','POLISH','SWBIT','SWWORD')
                     if first_flag is not None and name in addresses}
        checks.update({
            'four_documented_mark_inputs_irqs_and_original_markrupts':len(marks)==len(irqs)==len(routine('MARKRUPT'))==4
                and [r['value'] for r in marks]==[4,8,4,8] and all(mark_causes),
            'two_real_star_pairs_complete_in_original_markstat':len(pair_rows)==2
                and all(r['after']&MARK_COMPLETE==MARK_COMPLETE and r['before']&MARK_COMPLETE!=MARK_COMPLETE for r in pair_rows)
                and len(routine('MARKCHEX'))==2 and len(routine('AVESTAR'))==2,
            'matrix_native_stores_precede_original_flag_set':bool(first_flag) and bool(matrix_rows) and len(set(r['address'] for r in matrix_rows))>=9
                and all(pair_rows[-1]['cycle']<r['cycle']<first_flag['cycle'] for r in matrix_rows)
                and first_flag['pre_bank']==1 and first_flag['pre_z']==0o2554
                and any(flag_matrix) and all(r['pre_bank']==3 for r in matrix_rows),
            'alignment_result_matches_native_matrix_and_flag':alignment is not None and first_flag is not None
                and alignment['state']['refsmflg'] and alignment['state']['flagword3']&REFSMBIT!=0
                and alignment['state']['refsmmat']==flag_matrix and first_flag['cycle']<=alignment['cycle'],
            'original_p51g_set_refsmflag_operand_observed':interpreted.get('LOC')==0o3562
                and interpreted.get('BANKSET',0)>>10&0o37==0o14 and interpreted.get('POLISH')==0o1462
                and interpreted.get('SWBIT')==REFSMBIT and interpreted.get('SWWORD')==3,
            'alignment_precedes_normal_p63_selection':alignment is not None and before_p63 is not None
                and alignment['cycle']<=before_p63 and routine('P51E') and routine('P63LM'),
            'original_r02_with_valid_refsm_returns_to_p63':bool(routine('R02BOTH')) and bool(routine('P63_AFTER_R02'))
                and words_for(routine('R02BOTH')[0],mapping,'FLAGWRD3')[0]&REFSMBIT!=0
                and routine('R02BOTH')[0]['cycle']<routine('P63_AFTER_R02')[0]['cycle'],
            'next_observed_alarm_is_01406_not_00220':p63 is not None and p63['state']['modreg']==63
                and p63['state']['failreg']==[0o1520,0o1406,0] and p63['state']['refsmflg']
                and not any(0o220 in words_for(r,mapping,'FAILREG',3) for r in transitions),
            'root_failure_original_routines_observed':bool(routine('ROOTPSRS')) and bool(routine('BADROOT')) and bool(routine('1406POO'))
                and routine('ROOTPSRS')[0]['cycle']<routine('BADROOT')[0]['cycle']<routine('1406POO')[0]['cycle'],
            'no_engine_on_output_after_alignment_request':before_p63 is not None and not any(r['ev']=='output' and r['channel']==0o11
                and r['cycle']>=before_p63 and r['value']&0o10000 for r in rows),
        })
    checks={name:bool(value) for name,value in checks.items()}
    details={'classification':'VERIFIED' if all(checks.values()) else 'UNRESOLVED',
             'negative_control':negative,'raw_sha256':run['sha256'],'raw_bytes':run['bytes'],
             'checks':checks,'all_pass':all(checks.values()),'native_markrupt_entries':len(routine('MARKRUPT')),
             'external_mark_irq_assertions':len(irqs),'original_mark_pairs':len(pair_rows),
             'matrix_write_observations':len(matrix_rows),'final_state':rows[-1]['state'],
             'first_refsm_flag_set_cpu_call':flag_rows[0]['cycle'] if flag_rows else None,
             'flag_set_interpreter':interpreted if not negative else None,
             'first_p63_after_r02_cpu_call':routine('P63_AFTER_R02')[0]['cycle'] if routine('P63_AFTER_R02') else None,
             'root_failure_checkpoints':[]}
    for row in routine('BADROOT'):
        observed={'cycle':row['cycle'],'pre_bank':row['pre_bank'],'pre_z':row['pre_z']}
        for name,count in [('MODE',1),('RETROOT',1),('MPAC',7),('TABLTTF',10),('TTF/8',2),('WCHPHASE',1),
                           ('RLS',6),('TLAND',2),('RN',6),('VN',6),('RGU',6),('VGU',6),('ROOTPS',2),('DXCRIT',2),('LOC',1)]:
            if name in addresses:observed[name]=words_for(row,mapping,name,count)
        details['root_failure_checkpoints'].append(observed)
    return details

def analyze_experiment(run,repeat,negative):
    final=analyze_run(run);replayed=analyze_run(repeat);control=analyze_run(negative,True)
    comparisons={'fresh_repeat_trace_byte_identical':raw(run['directory']/'trace.jsonl')==raw(repeat['directory']/'trace.jsonl'),
                 'negative_control_removes_native_alignment':final['all_pass'] and control['all_pass']
                    and final['first_refsm_flag_set_cpu_call'] is not None and control['first_refsm_flag_set_cpu_call'] is None}
    return {'run':final,'repeat':replayed,'negative':control,'comparisons':comparisons,
            'all_pass':all(item['all_pass'] for item in (final,replayed,control)) and all(comparisons.values()),
            'scope':'Authentic P51 synthetic stationary geometry and P63 readiness feasibility; no powered descent/engine plant'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--repeat',required=True,type=Path)
    parser.add_argument('--negative',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Refusing to overwrite prior analysis')
    result=analyze_experiment(*(load_run(path) for path in (args.run,args.repeat,args.negative)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'all_pass':result['all_pass'],'comparisons':result['comparisons'],
                     'failed_checks':{name:[k for k,v in result[name]['checks'].items() if not v] for name in ('run','repeat','negative')}},indent=2))
    if not result['all_pass']:raise SystemExit(1)

if __name__=='__main__':main()
