This is a bounded **modern synthetic rotational-model extension**, separate from original Luminary flight code and the pinned emulator. It reuses the existing packet-to-jet decode, `dynamic_simulation` mass-dependent perjet acceleration, `update_RCS` torque response and fuel accounting, and original gimbal quantizer. It replaces the old additive finite gimbal integration with a normalized quaternion and adds Euler angular-momentum coupling. It does not implement translation, gravity, PIPA feedback, descent propulsion or another controller.

`apply_physics.py` verifies the original module, initializer and dynamics SHA-256 values against the retained Phase 6 source inventory, and the Phase 5 server against the frozen prior inventory. It creates one derived Tcl file in new scratch; no original file changes. The generated file contains the complete original IMU module with three explicit signed-magnitude selector changes, plus `orientation.tcl`. The jet decode inside `phase7_step` is inserted verbatim from the retained server. Exact modified source, decode, hashes and selector diff are recorded in the audit. Original numerical dynamics and fuel procedures remain sourced from the unchanged original module.

The authoritative orientation convention is **VERIFIED** from the original source, rather than guessed from axis names:

\[
C_{body\to stable}=R_y(IG)R_z(MG)R_x(OG),\qquad
q=q_y(IG)\otimes q_z(MG)\otimes q_x(OG).
\]

The scalar-first quaternion represents body to stable rotation; body angular rate is ordered `(P,Q,R) = (Omega_Yaw, Omega_Pitch, Omega_Roll)` in the existing simulator. The sensor gimbals are `(OG,IG,MG) = (IMUX,IMUY,IMUZ)`, corresponding to CDU X/Y/Z. This ordering is supported by original Luminary's GPMATRIX and the retained simulator's FDAI/PIPA matrix; see the separate source mapping evidence. Its local differential is:

\[
P=\dot{OG}+\sin(MG)\dot{IG},\quad
Q=\cos(OG)\cos(MG)\dot{IG}+\sin(OG)\dot{MG},\quad
R=-\sin(OG)\cos(MG)\dot{IG}+\cos(OG)\dot{MG}.
\]

The extraction uses `MG=asin(C21)`, `OG=atan2(-C23,C22)` and `IG=atan2(-C31,C11)` on the branch with positive `cos(MG)`. A conservative `|MG| < 80°` bound rejects singularity approach; the original simulator's 85.1° gimbal-lock check remains intact. Angles returned to the existing quantizer are wrapped to `[0,360)` and changed by the shortest signed delta. Coupled yaw and pitch can produce nonzero body R and all three sensor gimbals, which are retained rather than suppressed.

The **ASSUMED** synthetic inertia and torque model is explicit. For each original perjet acceleration `alpha_i(m)` in degrees/s², define

\[
I_i(m)={445\,\mathrm{N}\times1\,\mathrm m\over\alpha_i(m)\pi/180}.
\]

The 1 m **component** arm is an assumed torque scale, not measured Apollo geometry. A vertical jet that contributes to two old angular components can contribute 445 Nm to each; this is not a claim that its total lever arm was 1 m. At the retained initial 15,364 kg configuration, the principal inertias are approximately `[20681.71127,20381.25550,20565.10208]` kg m². All must be positive and satisfy rigid-body triangle inequalities. The original decoder and `update_RCS` determine signed per-component torque by their actual rate increment, preserving the old perjet response and original propellant flow.

The rotational equation is

\[
I\dot\omega=\tau-\omega\times(I\omega).
\]

The model treats I as diagonal in fixed body principal axes and frozen over each interval; its next value follows the original fuel/mass update. It assumes ejected mass carries its corotating angular momentum, cancelling `I_dot*omega` with angular-momentum flux. This is an explicitly synthetic open-mass approximation, not a reconstruction of tank geometry or exhaust dynamics. Inertia before/after, mass before/after, fuel before/after, torque and resulting angular acceleration are available in telemetry.

An implicit midpoint iteration advances body rate, with absolute convergence tolerance `1e-14` rad/s and at most 20 iterations. Quaternion orientation then advances by the endpoint-rate exponential `q_new=q_old*exp(omega_new*dt/2)`, followed by normalization. Endpoint rate preserves the retained semi-implicit principal-axis cadence; it remains first order in orientation during changing rate. The fixed-inertia torque-free checks preserve body rotational energy and momentum magnitude to about `1e-14`, while inertial momentum **direction is only numerically approximated**: its relative error over 10 seconds is `1.66969e-4` at 2 ms and `8.34868e-5` at 1 ms. The roughly halved error establishes first-order convergence; exact inertial conservation is not claimed.

Physical steps require `0 < dt <= 0.010001 s`, rates no greater than 60°/s per body component, no preexisting gimbal lock and no main-engine operation. Motion during IMU zeroing is rejected. These are fixture bounds, not flight software readiness changes. The native integration chooses a maximum 853 exact CPU-call interval, about 9.996 ms, and may subdivide at actual actuator changes.

Legacy translational jet combinations are observed explicitly: a replacement `modify_pipaXYZ` logs the requested body delta-V in `translation_suppressed_deltaV_body_m_s` and emits no PIPA packets. Translational state and PIPA counters are not integrated. This suppression is a disclosed boundary of a rotational diagnostic, not a claim about full vehicle dynamics.

The current selectors preserve the legacy body-component criterion using `abs(Omega_Yaw/Pitch/Roll)`, while `gimbal_rates_deg_s` records actual wrapped gimbal deltas divided by dt. Body angular components and gimbal speeds differ away from zero attitude. Consequently this is a modern bounded transport policy, **not a validation of hardware CDU timing**. The integration must measure resulting queues and delays; a mode selector alone cannot establish timely application or physical sensor fidelity.

The reusable API is `apply_physics(source_root, destination_tcl) -> audit_dict`. Source the derived module once after the original model initializer and modules, without the earlier Milestone 3 single-axis guard. The overlay exposes `phase7_step dt jet5 jet6 zero`. Its flat result is:

```text
omega_deg_s[3] gimbals_deg[3] quaternion_wxyz[4] alpha_rad_s2[3] torque_Nm[3]
```

The existing `write_socket` callback receives the original signed CDU operations and textual octal counter addresses. Additional Tcl dictionary telemetry is in `::phase7::last_telemetry`: quaternion, gimbals, body rates, gimbal rates, angular acceleration, torque, original perjet acceleration, inertias before/after, mass and fuel before/after, and suppressed translation requests. This is simulated/model telemetry, not authentic AGC output. Native actuator packets are recorded separately by the integration harness.

**VERIFIED component experiments:** eight quaternion/matrix/gimbal roundtrips, three local comparisons against the old gimbal Jacobian, constant principal torque, torque-free unequal inertias, yaw and pitch with both signs, simultaneous yaw/pitch torque, original-yaw comparison, no-PIPA translation control, three signed magnitude selectors and five bounded-error controls. The simultaneous one-second component case applies synthetic torque `[1780,1780,0]` Nm and ends at body rates approximately `[4.931411,5.004028,0.002094]`°/s with nonzero middle gimbal `0.055434°`; the third rate comes from angular-momentum coupling. This is prescribed jet activity in a component test, not evidence of multi-axis AGC control.

The one-second yaw comparison differs from the retained model by at most `7.99e-15`°/s and zero reported wrapped-angle difference. The original Jacobian/quaternion comparison differs by at most `5.68e-14` degrees for 1 μs local steps. Sixteen tests execute fresh locked Tcl once, independently extract/hash-check the retained source, and check physical/numerical invariants, source scope, signed physical sensor counters, rejection guards and adversarial evidence mutations.

From the repository root, after preparing the locked runtime:

```sh
python3 -B docs/phase7-evidence/physics/run_validation.py \
  --source .build/milestone3/pinned-source \
  --tcl .build/reproducibility/runtime/bin/tclsh8.6 \
  --output .build/phase7-physics/new-run
python3 -B -m unittest discover -s docs/phase7-evidence/physics -p 'test_*.py' -v
```

All generated results require new scratch destinations. Complete successful component output and the failed development probe are preserved separately under this directory. The first failed full component run expected a deliberately difficult 30 rad/s solver input to exhaust 20 iterations, but that case actually converged; a captured bounded search established that 35 rad/s exhausts the limit, and the negative control was corrected. No observed success, vehicle trajectory or historical log was fabricated.

Multi-axis authentic AGC control is evaluated only by the separate native integration evidence. This component does not establish sustained vehicle stability, historical inertia or geometry, actual IMU timing, physical calibration, mission initialization, powered descent or a landing.
