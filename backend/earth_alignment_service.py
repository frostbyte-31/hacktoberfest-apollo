"""Single-owner original CMC with explicitly modeled CSM alignment instruments.

This service owns a separate computer from the cold-start diagnostic and the LM
laboratories. It transports real controls and retains observations; it never
sets an Apollo alignment flag, supplies a DSKY result, or authorizes TLI.
"""
from copy import deepcopy
import math
from pathlib import Path
import secrets
import time

from backend.control_service import ControlError
from backend.earth_orbit_service import EarthOrbitService, KEYS

ROOT = Path(__file__).resolve().parents[1]
MODE = 'LIVE ORIGINAL CMC / MODELED INSTRUMENTS'
CONTROLS = ('power_imu', 'optics_mode', 'optics_slew', 'mark')
SCOPE = ('Original Comanche 055 with modeled CSM IMU and manual sextant controls. '
         'A disclosed P51 setup establishes the training reference through original software. '
         'P52 sightings and gyro corrections execute in the original CMC. This is a bounded '
         'alignment instrument fixture, not Apollo 11 flight telemetry, orbital dynamics or TLI.')


def task_definition():
    return [
        {'id': 'select-p52', 'title': 'Select original P52',
         'description': 'Press VERB 3 7 ENTR 5 2 ENTR. The original computer must display program 52.'},
        {'id': 'star-marks', 'title': 'Sight two catalog stars',
         'description': 'Select REFSMMAT option 3 at the original prompt. Follow the original star-code prompts, manually sight two stars with the sextant controls, and press MARK for each. Displayed target angles describe this modeled training attitude.'},
        {'id': 'star-angle', 'title': 'Review the measured star-angle difference',
         'description': 'Inspect the original VERB 06 NOUN 05 result. PRO accepts the measured star-angle difference; ENTR recycles the sightings.'},
        {'id': 'gyro-review', 'title': 'Review the gyro correction',
         'description': 'Inspect the original VERB 06 NOUN 93 torque angles. Press PRO to let original CMC gyro pulses correct the modeled IMU. Their resulting CDU feedback must be observed.'},
        {'id': 'alignment-return', 'title': 'Apply the correction and return to P00',
         'description': 'Wait for original VERB 50 NOUN 25 code 00014, then press VERB 3 7 ENTR 0 0 ENTR. Completion requires the original P52 result and applied physical instrument feedback, not just an entered key sequence.'},
    ]


def validate_control(control, value):
    """Reject unsupported or unbounded hardware requests before worker dispatch."""
    if not isinstance(control, str) or control not in CONTROLS:
        raise ControlError(400, 'Unsupported CSM instrument control.')
    if control == 'power_imu':
        valid = type(value) is bool
    elif control == 'optics_mode':
        valid = isinstance(value, str) and value in ('MANUAL', 'ZERO', 'CMC')
        if value == 'CMC':
            raise ControlError(400, 'Automatic CMC optical motor drive is unavailable in this manual alignment fixture.')
    elif control == 'mark':
        valid = isinstance(value, str) and value in ('MARK', 'REJECT')
    else:
        valid = (isinstance(value, dict) and set(value) == {'shaft', 'trunnion', 'rate', 'seconds'}
                 and isinstance(value['rate'], str) and value['rate'] in ('LOW', 'HIGH'))
        if valid:
            valid = all(type(value[name]) in (int, float) and math.isfinite(value[name])
                        and low <= value[name] <= high
                        for name, low, high in [('shaft', -1, 1), ('trunnion', -1, 1), ('seconds', 0, 1)])
            valid = valid and value['seconds'] > 0
    if not valid:
        raise ControlError(400, 'Invalid or unbounded CSM instrument control value.')


class EarthAlignmentService(EarthOrbitService):
    """Reuse the proven bounded owner queue, lifecycle and real DSKY transport."""
    def __init__(self, factory=None, discovery=None, output_root=None, pace=True,
                 idle_timeout=600, enabled=True):
        super().__init__(factory=factory, discovery=discovery,
                         output_root=output_root or ROOT/'.build/earth-alignment/sessions',
                         pace=pace, idle_timeout=idle_timeout, enabled=enabled)
        self.state['mode'] = MODE
        self.observed = {}

    def capabilities(self):
        if not self.enabled:
            data = {'available': False, 'unavailableReason': 'Live CMC instruments are disabled in recorded-only mode.'}
        elif self.discovery:
            data = self.discovery()
        else:
            try:
                from backend.cmc_alignment import alignment_availability
                data = alignment_availability()
            except Exception as error:
                data = {'available': False, 'unavailableReason': str(error)}
        return {**data, 'mode': MODE, 'software': 'Comanche055', 'scope': SCOPE,
                'supportedKeys': list(KEYS) if data.get('available') is True else [],
                'supportedControls': list(CONTROLS) if data.get('available') is True else [],
                'flightExecuted': False, 'translunarInjection': False}

    def instrument(self, sessionId, sequence, control, value):
        if type(sequence) is not int or not 0 <= sequence <= 2**31-1:
            raise ControlError(400, 'CMC sequence must be a nonnegative integer.')
        validate_control(control, value)
        return self._call('instrument', sessionId, sequence, control, deepcopy(value))

    def _task(self):
        steps = task_definition()
        computer = self.state['computer'] or {}
        alignment = computer.get('instruments', {}).get('alignment', {})
        complete = bool(alignment.get('p52Complete') is True
                        and all(item['id'] in self.observed for item in steps)
                        and computer.get('dsky', {}).get('PROG') == '00')
        active_assigned = False
        for item in steps:
            item['complete'] = item['id'] in self.observed
            item['active'] = not item['complete'] and not active_assigned
            active_assigned = active_assigned or item['active']
        pending = next((item['description'] for item in steps if not item['complete']), '')
        pending = self._next_instruction(computer, pending)
        return {'id': 'original-p52-alignment', 'title': 'Columbia P52 instrument alignment',
                'complete': complete, 'alignmentCompleted': complete, 'flightExecuted': False,
                'scope': SCOPE, 'steps': steps,
                'nextInstruction': ('P52 alignment is complete in the modeled instrument fixture. '
                    'Original Apollo 11 launch-vehicle execution and an S-IVB flight model are still '
                    'required for TLI; this alignment does not simulate leaving Earth orbit.' if complete else pending),
                'checkpoints': deepcopy(list(self.observed.values()))}

    def _next_instruction(self, computer, fallback):
        instruments = computer.get('instruments', {})
        if instruments.get('imuPowered') is False:
            return 'The modeled IMU is OFF. Restart this training fixture to reestablish its original P51 reference before repeating P52.'
        d = computer.get('dsky', {})
        if d.get('PROG') != '52':
            return fallback
        verb, noun = d.get('VERB'), d.get('NOUN')
        if verb == '04' and noun == '06':
            return 'Select P52 REFSMMAT option 3: press VERB 2 2 ENTR 0 0 0 0 3 ENTR, then PRO. This preserves the reference initialized by the disclosed P51 setup.'
        if verb == '50' and noun == '25':
            if d.get('R1') == '00015':
                return 'Original request 00015 offers star selection. Press ENTR to choose the two training stars manually.'
            if d.get('R1') == '00016':
                return 'The original computer has recorded an optical MARK. Press PRO to review the marked star identity.'
            if d.get('R1') == '00014':
                return 'Original P52 returned request 00014. Press VERB 3 7 ENTR 0 0 ENTR, then wait for observed program 00 and verified alignment completion.'
        marks = instruments.get('alignment', {}).get('p52Marks', 0)
        target = '30 (Menkent)' if marks == 0 else '37 (Nunki)'
        if verb == '01' and noun == '70':
            code = '3 0' if marks == 0 else '3 7'
            return ('Select catalog star '+target+': press VERB 2 1 ENTR 0 0 0 '+code+
                    ' ENTR, then PRO. Wait for the original flashing VERB 51 before pressing MARK.')
        if verb == '51':
            return ('Use the DIRECT optics hand controller to center star '+target+
                    ' in the sextant. The star cards show this fixed training attitude’s target angles. '
                    'Fine-tune at LOW rate, then press the physical MARK control.')
        if verb == '01' and noun == '71':
            return 'Review the original marked-star code. Press PRO to accept its identity and continue.'
        if verb == '06' and noun == '05':
            if d.get('R1', '').isdigit() and int(d['R1']) > 5:
                return 'The original star-angle difference exceeds this training fixture’s 0.05° acceptance limit. Restart and improve both optical sightings; accepting this result will not complete the task.'
            return 'Review original NOUN 05: the measured star-angle difference is in hundredths of a degree. Press PRO to accept this pair and calculate the gyro correction.'
        if verb == '06' and noun == '93':
            return 'Review the original NOUN 93 gyro torque angles. Press PRO to apply the CMC’s real gyro-pulse outputs to the modeled IMU; wait for its sensor feedback and request 00014.'
        return fallback

    def _record_checkpoint(self, name, computer):
        if name in self.observed:
            return
        value = {'id': name, 'cycle': computer['cycle'], 'dsky': deepcopy(computer['dsky']),
                 'dskySource': deepcopy(computer.get('dskySource'))}
        self.observed[name] = value
        self._event('original_alignment_checkpoint', **value)

    def _observe(self, computer):
        if (not isinstance(computer, dict) or computer.get('software') != 'Comanche055'
                or type(computer.get('cycle')) is not int or computer['cycle'] < 0
                or not isinstance(computer.get('dsky'), dict)):
            raise ValueError('Original alignment observer returned an invalid computer frame.')
        dsky = computer['dsky']
        for name, width in [('PROG', 2), ('VERB', 2), ('NOUN', 2), ('R1', 5), ('R2', 5), ('R3', 5)]:
            value = dsky.get(name)
            if not isinstance(value, str) or len(value) != width or any(c not in ' 0123456789?' for c in value):
                raise ValueError('Original alignment observer returned an invalid DSKY digit field.')
        instruments = computer.get('instruments')
        if (not isinstance(instruments, dict) or instruments.get('mode') != 'MODELED CSM INSTRUMENTS'
                or type(instruments.get('imuPowered')) is not bool
                or instruments.get('opticsMode') not in ('MANUAL', 'ZERO', 'CMC')
                or not isinstance(instruments.get('alignment'), dict)):
            raise ValueError('Modeled CSM instrument observation is invalid.')
        for field in ('shaftDeg', 'trunnionDeg', 'mechanicalTrunnionDeg'):
            if type(instruments.get(field)) not in (int, float) or not math.isfinite(instruments[field]):
                raise ValueError('Modeled optics must report finite physical angles.')
        if self.state['computer'] and computer['cycle'] < self.state['computer']['cycle']:
            raise ValueError('Original CMC clock moved backwards.')
        previous_program = (self.state['computer'] or {}).get('dsky', {}).get('PROG')
        if dsky['PROG'] == '52' and previous_program != '52':
            # Selecting P52 again starts a fresh sighting attempt. Retained
            # checkpoints from a previous attempt must not mark new work done.
            self.observed = {}
        last_key = self.state['computer'].get('lastKey') if self.state['computer'] else None
        last_control = self.state['computer'].get('lastControl') if self.state['computer'] else None
        self.state['computer'] = deepcopy(computer)
        self.state['computer'].update(lastKey=last_key, lastControl=last_control)
        alignment = instruments['alignment']
        if (dsky['PROG'] == '52'
                and self._command_seen(['VERB', '3', '7', 'ENTR', '5', '2', 'ENTR'])):
            self._record_checkpoint('select-p52', computer)
        if 'select-p52' not in self.observed or dsky['PROG'] != '52':
            return self._observe_return(computer, alignment)
        since = self.observed['select-p52']['cycle']
        marks = [row for row in self.history if row.get('control') == 'mark'
                 and row.get('value') == 'MARK' and row['queuedAtCycle'] >= since]
        if (type(alignment.get('p52Marks')) is int and alignment['p52Marks'] >= 2 and len(marks) >= 2):
            self._record_checkpoint('star-marks', computer)
        if ('star-marks' in self.observed and dsky['VERB'] == '06' and dsky['NOUN'] == '05'
                and all(dsky[name].isdigit() for name in ('R1',))):
            self._record_checkpoint('star-angle', computer)
        if ('star-angle' in self.observed and dsky['VERB'] == '06' and dsky['NOUN'] == '93'
                and all(dsky[name].isdigit() for name in ('R1', 'R2', 'R3'))):
            self._record_checkpoint('gyro-review', computer)
        self._observe_return(computer, alignment)

    def _observe_return(self, computer, alignment):
        dsky = computer['dsky']
        if ('gyro-review' in self.observed and dsky['VERB'] == '50' and dsky['NOUN'] == '25'
                and dsky['R1'] == '00014' and alignment.get('torqueApproved') is True
                and type(alignment.get('torqueOutputCount')) is int and alignment['torqueOutputCount'] > 0
                and type(alignment.get('gyroSensorFeedbackOperations')) is int
                and alignment['gyroSensorFeedbackOperations'] > 0
                and alignment.get('p52Complete') is True):
            self._record_checkpoint('completion-display', computer)
        if ('completion-display' in self.observed and dsky['PROG'] == '00'
                and alignment.get('p52Complete') is True
                and alignment.get('referenceInitialized') is True
                and type(alignment.get('completionCycle')) is int
                and 0 <= alignment['completionCycle'] <= computer['cycle']
                and self._command_seen(['VERB', '3', '7', 'ENTR', '0', '0', 'ENTR'],
                                       self.observed['completion-display']['cycle'])):
            self._record_checkpoint('alignment-return', computer)

    def _command_seen(self, sequence, since=0):
        # Instrument controls share the sequence but are never DSKY keys.
        keys = [row['key'] for row in self.history if 'key' in row and row['queuedAtCycle'] >= since]
        return any(keys[index:index+len(sequence)] == sequence for index in range(len(keys)-len(sequence)+1))

    def _start(self):
        discovery = self.capabilities()
        if discovery['available'] is not True:
            raise ControlError(503, 'Original CMC alignment instruments are unavailable. '+str(discovery.get('unavailableReason', '')))
        if self.engine:
            self.engine.close()
            self.engine = None
        self.marks, self.history, self.observed = [], [], {}
        identity = secrets.token_hex(16)
        folder = self.output_root/identity
        folder.mkdir(parents=True, exist_ok=False)
        self.log = folder/'console.jsonl'
        self.state.update(status='idle', sessionId=identity, revision=0, nextSequence=0,
                          computer=None, inputs=[], error=None)
        self._event('start', sessionId=identity, mode=MODE, scope=SCOPE)
        if self.factory:
            self.engine = self.factory()
        else:
            from backend.cmc_alignment import CmcAlignmentProcess, prepare_alignment_assets
            self.engine = CmcAlignmentProcess(prepare_alignment_assets())
        self._observe(self.engine.boot())
        self.state['status'] = 'ready'
        self.last_activity = time.monotonic()
        return self.snapshot()

    def _instrument(self, identity, sequence, control, value):
        self._check_id(identity)
        if self.state['status'] != 'ready' or not self.engine:
            raise ControlError(409, 'Start the original CMC instruments before operating a control.')
        if sequence != self.state['nextSequence']:
            raise ControlError(409, 'Stale, repeated or skipped instrument sequence. Refresh status; input was not repeated.')
        if (control == 'optics_slew'
                and self.state['computer']['instruments']['opticsMode'] != 'MANUAL'):
            raise ControlError(409, 'Set the optics mode to MANUAL before using its hand controller.')
        response = self.engine.instrument(control, value)
        packet, computer = deepcopy(response['ackpacket']), response['computer']
        # The native peripheral calls this an action; the HTTP domain contract
        # calls it a control. Keep the native field as provenance too.
        if 'control' not in packet:
            packet['control'] = packet.get('action')
        if (packet.get('control') != control or packet.get('value') != value
                or type(packet.get('queuedAtCycle')) is not int or packet['queuedAtCycle'] < 0
                or type(packet.get('afterCycle')) is not int or packet['afterCycle'] < packet['queuedAtCycle']):
            raise ValueError('CSM instrument acknowledgment is invalid.')
        row = {**deepcopy(packet), 'sequence': sequence}
        self.history.append(row)
        self.state.update(nextSequence=sequence+1, revision=self.state['revision']+1,
                          inputs=deepcopy(self.history[-30:]))
        self._observe(computer)
        self.state['computer']['lastControl'] = {'control': control, 'value': deepcopy(value),
            'cycle': packet['queuedAtCycle'], 'sequence': sequence}
        self.last_activity = time.monotonic()
        self._event('instrument_control', **row)
        result = self.snapshot()
        result['ack'] = {**deepcopy(packet), 'sessionId': identity, 'sequence': sequence}
        return result
