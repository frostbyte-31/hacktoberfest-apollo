# GPL-2.0-or-later. Bounded synthetic rotational extension of the retained model.
# q is scalar first; C(body->stable)=Ry(IGA)*Rz(MGA)*Rx(OGA).
namespace eval ::phase7 {
    variable q {1.0 0.0 0.0 0.0}
    variable last_telemetry {}
    variable translations {}
    variable arm_m 1.0
    variable max_middle_deg 80.0
}

proc ::phase7::cross {a b} {
    lassign $a x y z
    lassign $b u v w
    return [list [expr {$y*$w-$z*$v}] [expr {$z*$u-$x*$w}] [expr {$x*$v-$y*$u}]]
}

proc ::phase7::qmul {a b} {
    lassign $a w x y z
    lassign $b s u v t
    return [list [expr {$w*$s-$x*$u-$y*$v-$z*$t}] \
        [expr {$w*$u+$x*$s+$y*$t-$z*$v}] \
        [expr {$w*$v-$x*$t+$y*$s+$z*$u}] \
        [expr {$w*$t+$x*$v-$y*$u+$z*$s}]]
}

proc ::phase7::qnormalize {quat} {
    set n2 0.0
    foreach value $quat {set n2 [expr {$n2+$value*$value}]}
    if {$n2 < 1e-20 || $n2 > 1e20} {error {Invalid quaternion norm}}
    set normalized {}
    foreach value $quat {lappend normalized [expr {$value/sqrt($n2)}]}
    return $normalized
}

proc ::phase7::from_gimbals {angles} {
    global DEG_TO_RAD
    lassign $angles o i m
    set o [expr {$o*$DEG_TO_RAD/2.0}]
    set i [expr {$i*$DEG_TO_RAD/2.0}]
    set m [expr {$m*$DEG_TO_RAD/2.0}]
    set qo [list [expr {cos($o)}] [expr {sin($o)}] 0.0 0.0]
    set qi [list [expr {cos($i)}] 0.0 [expr {sin($i)}] 0.0]
    set qm [list [expr {cos($m)}] 0.0 0.0 [expr {sin($m)}]]
    return [qnormalize [qmul [qmul $qi $qm] $qo]]
}

proc ::phase7::matrix {quat} {
    lassign [qnormalize $quat] w x y z
    return [list [expr {1-2*($y*$y+$z*$z)}] [expr {2*($x*$y-$w*$z)}] [expr {2*($x*$z+$w*$y)}] \
        [expr {2*($x*$y+$w*$z)}] [expr {1-2*($x*$x+$z*$z)}] [expr {2*($y*$z-$w*$x)}] \
        [expr {2*($x*$z-$w*$y)}] [expr {2*($y*$z+$w*$x)}] [expr {1-2*($x*$x+$y*$y)}]]
}

proc ::phase7::gimbals {quat} {
    global RAD_TO_DEG
    variable max_middle_deg
    set c [matrix $quat]
    set sine [lindex $c 3]
    if {abs($sine) > 1.000000000001} {error {Invalid rotation matrix}}
    set sine [expr {max(-1.0,min(1.0,$sine))}]
    set m [expr {asin($sine)*$RAD_TO_DEG}]
    if {abs($m) >= $max_middle_deg-1e-10} {error {Unsupported middle-gimbal singularity approach (80 degrees)}}
    set o [expr {atan2(-[lindex $c 5],[lindex $c 4])*$RAD_TO_DEG}]
    set i [expr {atan2(-[lindex $c 6],[lindex $c 0])*$RAD_TO_DEG}]
    set angles {}
    foreach angle [list $o $i $m] {lappend angles [expr {$angle < 0 ? $angle+360.0 : $angle}]}
    return $angles
}

proc ::phase7::advance_q {quat omega dt} {
    set speed2 0.0
    foreach value $omega {set speed2 [expr {$speed2+$value*$value}]}
    set speed [expr {sqrt($speed2)}]
    if {$speed < 1e-20} {return [qnormalize $quat]}
    set h [expr {$speed*$dt/2.0}]
    set increment [list [expr {cos($h)}]]
    foreach value $omega {lappend increment [expr {$value*sin($h)/$speed}]}
    return [qnormalize [qmul $quat $increment]]
}

proc ::phase7::omega_step {old acceleration inertia dt} {
    if {$dt <= 0 || $dt > 0.010001} {error {Unsupported rotational integration step}}
    foreach value $inertia {if {$value <= 0} {error {Nonpositive synthetic principal inertia}}}
    set guess {}
    foreach value $old a $acceleration {lappend guess [expr {$value+$a*$dt}]}
    for {set iteration 0} {$iteration < 20} {incr iteration} {
        set midpoint {}; set momentum {}
        foreach previous $old current $guess moment $inertia {
            set mid [expr {($previous+$current)/2.0}]
            lappend midpoint $mid
            lappend momentum [expr {$moment*$mid}]
        }
        set gyroscopic [cross $midpoint $momentum]
        set next {}; set error 0.0
        foreach previous $old a $acceleration gyro $gyroscopic moment $inertia current $guess {
            set value [expr {$previous+$dt*($a-$gyro/$moment)}]
            lappend next $value
            set error [expr {max($error,abs($value-$current))}]
        }
        set guess $next
        if {$error < 1e-14} {return $guess}
    }
    error {Euler angular-momentum implicit midpoint did not converge in20 iterations}
}

# Do not fabricate PIPA feedback for intentionally excluded translation.
rename modify_pipaXYZ ::phase7::upstream_modify_pipaXYZ
proc modify_pipaXYZ {x y z} {
    lappend ::phase7::translations [list $x $y $z]
}

proc phase7_step {dt jet5 jet6 zero} {
    global bo Delta_Time Delta_Time2 Omega_Yaw Omega_Pitch Omega_Roll
    global Alpha_Yaw Alpha_Pitch Alpha_Roll DEG_TO_RAD RAD_TO_DEG
    global IMUX_ANGLE IMUY_ANGLE IMUZ_ANGLE RCS_Thrust_N
    global DESCENT_ENGINE_FLAG ASCENT_ENGINE_FLAG RCS_Propellant_Mass_KG
    global gimbalLock
    global LM_Weight_Ascent_KG LM_Weight_Descent_KG
    global Q4U Q4D Q3U Q3D Q2U Q2D Q1U Q1D
    global Q3A Q4F Q1F Q2A Q2L Q3R Q4R Q1L
    foreach value [list $dt $jet5 $jet6 $zero] {
        if {![string is double -strict $value]} {error {Nonnumeric phase7 input}}
    }
    if {$dt <= 0 || $dt > 0.010001 || $jet5 < 0 || $jet5 > 255 || $jet6 < 0 || $jet6 > 255 || $zero ni {0 1}} {
        error {Unsupported phase7 interval, jet word or zeroing state}
    }
    if {$DESCENT_ENGINE_FLAG || $ASCENT_ENGINE_FLAG} {error {Main propulsion is outside rotational fixture}}
    if {$gimbalLock} {error {Existing gimbal lock is outside rotational fixture}}
    if {$zero && ($Omega_Yaw != 0 || $Omega_Pitch != 0 || $Omega_Roll != 0 || $jet5 || $jet6)} {
        error {Moving vehicle during IMU zeroing is outside this fixture}
    }
    set old [list $Omega_Yaw $Omega_Pitch $Omega_Roll]
    set old_mass [expr {$LM_Weight_Ascent_KG+$LM_Weight_Descent_KG}]
    set old_fuel $RCS_Propellant_Mass_KG
    set ::phase7::translations {}
    set bo(12,5) $zero
    set blocked 0
@LEGACY_JET_DECODE@
    set Delta_Time2 0
    dynamic_simulation
    set legacy_alpha [list $Alpha_Yaw $Alpha_Pitch $Alpha_Roll]
    set inertia {}
    foreach a $legacy_alpha {
        if {$a <= 0} {error {Nonpositive legacy perjet acceleration}}
        lappend inertia [expr {$RCS_Thrust_N*$::phase7::arm_m/($a*$DEG_TO_RAD)}]
    }
    lassign $inertia ix iy iz
    if {$ix+$iy <= $iz || $ix+$iz <= $iy || $iy+$iz <= $ix} {error {Synthetic inertias violate physical triangle inequalities}}
    set Delta_Time $dt
    update_RCS
    set legacy [list $Omega_Yaw $Omega_Pitch $Omega_Roll]
    set old_rad {}; set acceleration {}; set torque {}
    foreach previous $old current $legacy moment $inertia {
        set a [expr {($current-$previous)*$DEG_TO_RAD/$dt}]
        lappend old_rad [expr {$previous*$DEG_TO_RAD}]
        lappend acceleration $a
        lappend torque [expr {$moment*$a}]
    }
    set now [::phase7::omega_step $old_rad $acceleration $inertia $dt]
    set total_alpha {}; set omega_deg {}
    foreach previous $old_rad current $now {
        if {abs($current*$RAD_TO_DEG) > 60} {error {Rate beyond bounded60 degree/second fixture}}
        lappend total_alpha [expr {($current-$previous)/$dt}]
        lappend omega_deg [expr {$current*$RAD_TO_DEG}]
    }
    # Endpoint-rate exponential orientation retains legacy semi-implicit cadence.
    set next_q [::phase7::advance_q $::phase7::q $now $dt]
    set angles [::phase7::gimbals $next_q]
    set deltas {}
    foreach target $angles previous [list $IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE] {
        set delta [expr {$target-$previous}]
        if {$delta < -180} {set delta [expr {$delta+360}]}
        if {$delta > 180} {set delta [expr {$delta-360}]}
        lappend deltas $delta
    }
    set gimbal_rates {}
    foreach delta $deltas {lappend gimbal_rates [expr {$delta/$dt}]}
    lassign $omega_deg Omega_Yaw Omega_Pitch Omega_Roll
    modify_gimbal_angle {*}$deltas
    set ::phase7::q $next_q
    # Reuse original alpha/mass computation at zero elapsed time for after-I.
    set Delta_Time2 0
    dynamic_simulation
    set inertia_after {}
    foreach a [list $Alpha_Yaw $Alpha_Pitch $Alpha_Roll] {
        lappend inertia_after [expr {$RCS_Thrust_N*$::phase7::arm_m/($a*$DEG_TO_RAD)}]
    }
    set ::phase7::last_telemetry [dict create omega_deg_s $omega_deg quaternion $next_q \
        gimbals_deg [list $IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE] alpha_rad_s2 $total_alpha \
        gimbal_rates_deg_s $gimbal_rates \
        torque_Nm $torque legacy_perjet_alpha_deg_s2 $legacy_alpha inertia_before_kgm2 $inertia \
        inertia_after_kgm2 $inertia_after mass_before_kg $old_mass \
        mass_after_kg [expr {$LM_Weight_Ascent_KG+$LM_Weight_Descent_KG}] \
        fuel_before_kg $old_fuel fuel_after_kg $RCS_Propellant_Mass_KG \
        translation_suppressed_deltaV_body_m_s $::phase7::translations]
    return [concat $omega_deg [list $IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE] $next_q $total_alpha $torque]
}

# Instrument angles are model state, not writes to the AGC or its counters.
set ::phase7::q [::phase7::from_gimbals [list $IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE]]
