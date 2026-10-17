"""GPL-2.0-or-later. Native P51 evidence, causal controls and fail-closed inspection.

Captured-evidence assertions are distinct from parser/bridge-contract tests.
No test starts the native AGC or manufactures retained execution evidence.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('phase9_evidence_analysis',HERE/'analyze.py')
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)

def configured_runs():
    config_path=Path(os.environ.get('APOLLO_PHASE9_VALIDATION_CONFIG',HERE/'validation-config.json'))
    config=json.loads(config_path.read_text()) if config_path.exists() else {
        'run':'runs/final','repeat':'runs/repeat','negative':'runs/mark-irq-off'}
    return {name:analysis.load_run(Path(value) if Path(value).is_absolute() else HERE/value)
            for name,value in config.items() if name in ('run','repeat','negative')}

class NativeAlignmentEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs=configured_runs()
        cls.result=analysis.analyze_experiment(cls.runs['run'],cls.runs['repeat'],cls.runs['negative'])
        cls.final=cls.runs['run'];cls.rows=cls.final['rows'];cls.mapping=cls.final['mapping']

    def test_actual_phase5_startup_packets_and_outputs_preserved(self):
        checks=self.result['run']['checks']
        for name in ('exact_phase5_startup_packets','phase5_startup_actual_outputs_match_phase8',
                     'startup_is_legacy_unaligned_operate_state'):
            self.assertTrue(checks[name],name)

    def test_authentic_dsky_packets_field_widths_and_load_order(self):
        checks=self.result['run']['checks']
        self.assertTrue(checks['dsky_sequence_packets_match_logged_keys_and_cpu_timing'])
        self.assertTrue(checks['dsky_display_reconstructed_from_actual_output'])
        self.assertTrue(checks['octal_five_digit_code_and_signed_decimal_field_loads'])
        load_starts=[r for r in self.rows if r['ev']=='key_sequence' and r['text']=='V24N87E']
        self.assertEqual(len(load_starts),2)
        azimuths=[r for r in self.rows if r['ev']=='key_sequence' and r['text'].startswith('+')]
        self.assertEqual([r['display']['VERB'] for r in azimuths],['21','22','21','22'])

    def test_real_external_marks_trigger_original_markrupt_and_pairs(self):
        item=self.result['run']
        self.assertEqual(item['external_mark_irq_assertions'],4)
        self.assertEqual(item['native_markrupt_entries'],4)
        self.assertEqual(item['original_mark_pairs'],2)
        self.assertTrue(item['checks']['four_documented_mark_inputs_irqs_and_original_markrupts'])
        self.assertTrue(item['checks']['two_real_star_pairs_complete_in_original_markstat'])

    def test_matrix_and_flag_are_native_stores_after_original_sightings(self):
        item=self.result['run']
        self.assertTrue(item['checks']['matrix_native_stores_precede_original_flag_set'])
        self.assertTrue(item['checks']['alignment_result_matches_native_matrix_and_flag'])
        self.assertTrue(item['checks']['original_p51g_set_refsmflag_operand_observed'])
        context=item['flag_set_interpreter']
        self.assertEqual((context['LOC'],context['BANKSET']>>10&0o37),(0o3562,0o14))
        self.assertEqual((context['POLISH'],context['SWBIT'],context['SWWORD']),(0o1462,0o10000,3))

    def test_original_r02_accepts_then_p63_reaches_genuine_01406_path(self):
        item=self.result['run']
        for name in ('alignment_precedes_normal_p63_selection','original_r02_with_valid_refsm_returns_to_p63',
                     'next_observed_alarm_is_01406_not_00220','root_failure_original_routines_observed'):
            self.assertTrue(item['checks'][name],name)
        self.assertGreater(item['first_p63_after_r02_cpu_call'],item['first_refsm_flag_set_cpu_call'])
        self.assertEqual(item['final_state']['failreg'],[0o1520,0o1406,0])

    def test_root_limit_and_uninitialized_navigation_are_observations(self):
        failures=self.result['run']['root_failure_checkpoints']
        self.assertEqual(len(failures),1)
        actual=failures[0]
        self.assertEqual(actual['MODE'],[8])
        self.assertEqual(actual['WCHPHASE'],[0o77776])
        self.assertEqual(actual['TABLTTF'][:8],[0]*8)
        self.assertEqual(actual['RLS'],[0]*6)
        self.assertEqual(actual['TLAND'],[0]*2)
        self.assertEqual(actual['RN'],[0]*6)
        self.assertEqual(actual['VN'],[0]*6)
        loops=[r for r in self.rows if r['ev']=='checkpoint' and r['routine']=='ROOTLOOP']
        self.assertEqual([analysis.words_for(r,self.mapping,'MODE')[0] for r in loops],list(range(9)))

    def test_stationary_scope_and_no_engine_on_are_explicit(self):
        checks=self.result['run']['checks']
        self.assertTrue(checks['stationary_cdu_fixture_without_counter_feedback'])
        self.assertTrue(checks['no_engine_on_output_after_alignment_request'])
        self.assertTrue(checks['only_supported_accepted_hardware_packets'])

    def test_identical_fresh_runs_have_exact_raw_bytes(self):
        self.assertTrue(self.result['comparisons']['fresh_repeat_trace_byte_identical'])
        self.assertEqual(self.runs['run']['sha256'],self.runs['repeat']['sha256'])
        self.assertTrue(self.result['repeat']['all_pass'])

    def test_packet_only_negative_control_cannot_align(self):
        negative=self.result['negative']
        self.assertTrue(negative['all_pass'])
        self.assertEqual(negative['external_mark_irq_assertions'],0)
        self.assertEqual(negative['native_markrupt_entries'],0)
        self.assertIsNone(negative['first_refsm_flag_set_cpu_call'])
        self.assertFalse(negative['final_state']['refsmflg'])
        self.assertEqual(negative['final_state']['refsmmat'],[0]*18)
        self.assertTrue(self.result['comparisons']['negative_control_removes_native_alignment'])

    def test_executed_bridge_provenance_is_separate_from_flight_execution(self):
        directory=self.final['directory'];execution=json.loads((directory/'execution.json').read_text())
        hashes=execution['input_sha256']
        for name in ('hardware_bridge.c','run_alignment.py'):
            executed=(directory/('executed-'+name)).read_bytes()
            matching=[value for key,value in hashes.items() if Path(key).name==name]
            self.assertEqual(len(matching),1,name)
            self.assertEqual(hashlib.sha256(executed).hexdigest(),matching[0],name)
        bridge=(directory/'executed-hardware_bridge.c').read_text()
        self.assertNotIn('State.Erasable',bridge)
        self.assertEqual(len(re.findall(r'State\.InterruptRequests\[6\]\s*=\s*1',bridge)),1)
        self.assertNotRegex(bridge,r'(?i)(set_ram|write_ram|force_flag)\s*\(')

    def test_missing_original_markrupt_is_not_replaced_by_success_metadata(self):
        changed=copy.deepcopy(self.final)
        changed['rows']=[r for r in changed['rows'] if not(r['ev']=='checkpoint' and r['routine']=='MARKRUPT')]
        result=analysis.analyze_run(changed)
        self.assertFalse(result['all_pass'])
        self.assertFalse(result['checks']['four_documented_mark_inputs_irqs_and_original_markrupts'])

    def test_success_metadata_cannot_substitute_for_native_matrix(self):
        changed=copy.deepcopy(self.final)
        record=next(r for r in changed['rows'] if r['ev']=='alignment_result')
        record['state']['refsmmat'][0]^=1
        result=analysis.analyze_run(changed)
        self.assertFalse(result['checks']['alignment_result_matches_native_matrix_and_flag'])

    def test_early_matrix_substitution_fails_causal_order_check(self):
        changed=copy.deepcopy(self.final)
        start=changed['mapping']['addresses']['REFSMMAT']
        record=next(r for r in changed['rows'] if r['ev']=='transition' and start<=r['address']<start+18)
        record['cycle']=2200001
        result=analysis.analyze_run(changed)
        self.assertFalse(result['checks']['matrix_native_stores_precede_original_flag_set'])

    def test_short_numeric_load_and_wrong_gate_are_rejected(self):
        changed=copy.deepcopy(self.final)
        record=next(r for r in changed['rows'] if r['ev']=='key_sequence' and r['text'].startswith('+'))
        record['text']=record['text'][0]+record['text'][2:]
        record['display']['VERB']='24'
        result=analysis.analyze_run(changed)
        self.assertFalse(result['checks']['dsky_sequence_packets_match_logged_keys_and_cpu_timing'])
        self.assertFalse(result['checks']['octal_five_digit_code_and_signed_decimal_field_loads'])
        self.assertFalse(result['checks']['dsky_display_reconstructed_from_actual_output'])


class TraceInspectionTests(unittest.TestCase):
    def check_invalid(self,data,message):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'trace.jsonl';path.write_bytes(data)
            with self.assertRaisesRegex(ValueError,message):analysis.load_trace(path)

    def test_truncated_trace_is_rejected(self):
        self.check_invalid(b'{"ev":"initial","cycle":0}\n','Incomplete')

    def test_nonfinite_and_duplicate_json_are_rejected(self):
        self.check_invalid(b'{"ev":"initial","cycle":NaN}\n{"ev":"finish","cycle":1}\n','Non-finite')
        self.check_invalid(b'{"ev":"initial","ev":"initial","cycle":0}\n{"ev":"finish","cycle":1}\n','Duplicate')

    def test_noninteger_and_out_of_order_cpu_calls_are_rejected(self):
        self.check_invalid(b'{"ev":"initial","cycle":true}\n{"ev":"finish","cycle":1}\n','CPU call')
        self.check_invalid(b'{"ev":"initial","cycle":2}\n{"ev":"finish","cycle":1}\n','CPU call')

    def test_packet_width_and_native_failure_are_rejected(self):
        self.check_invalid(b'{"ev":"initial","cycle":0}\n{"ev":"input","cycle":1,"channel":13,"value":65535}\n{"ev":"finish","cycle":2}\n','interface width')
        self.check_invalid(b'{"ev":"initial","cycle":0}\n{"ev":"failure","cycle":1}\n{"ev":"finish","cycle":2}\n','Failed native')

    def test_snapshot_map_width_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            rows=[{'ev':'initial','cycle':0},{'ev':'checkpoint','cycle':1,'snapshot_words':[0]},
                  {'ev':'finish','cycle':2}]
            (path/'trace.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
            (path/'observer-map.json').write_text(json.dumps({'snapshot_addresses':[63,521]}))
            with self.assertRaisesRegex(ValueError,'width mismatch'):analysis.load_run(path)

if __name__=='__main__':unittest.main()
