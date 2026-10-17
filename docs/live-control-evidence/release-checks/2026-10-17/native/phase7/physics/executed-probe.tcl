# GPL-2.0-or-later. Component mechanics/coordinate tests, not AGC execution.
set src [lindex $argv 0]
set f [open "$src/Contributed/LM_Simulator/lm_simulator.tcl" r]
set ::initialization [join [lrange [split [read $f] "\n"] 123 240] "\n"]
close $f
eval $::initialization
source "$src/Contributed/LM_Simulator/modules/AGC_IMU.tcl"
source "$src/Contributed/LM_Simulator/modules/AGC_Simulation_Monitor_Control.tcl"
set gimbalLock 0
set bo(12,5) 0
proc write_socket {op address} {lappend ::packets [list $op $address]}
source [lindex $argv 1]
proc reset_model {} {
    uplevel #0 $::initialization
    set ::gimbalLock 0
    set ::bo(12,5) 0
    set ::phase7::q {1.0 0.0 0.0 0.0}
    set ::packets {}
}
puts "TCL|[info patchlevel]"
foreach angles {{0 0 0} {17 -23 31} {120 42 -45} {-170 -166 70} {11 73 -79} {-33 0 0} {0 -44 0} {0 0 55}} {
    set q [::phase7::from_gimbals $angles]
    puts "roundtrip|$angles|[::phase7::gimbals $q]|$q|[::phase7::matrix $q]"
}
# Validate old Transform's local gimbal Jacobian against the SO(3) update.
foreach angles {{0 0 0} {17 -23 31} {120 42 -45}} {
    reset_model
    lassign $angles ::IMUX_ANGLE ::IMUY_ANGLE ::IMUZ_ANGLE
    set ::PIMUX $::IMUX_ANGLE; set ::PIMUY $::IMUY_ANGLE; set ::PIMUZ $::IMUZ_ANGLE
    set ::Omega_Yaw 0.7; set ::Omega_Pitch -0.4; set ::Omega_Roll 0.3
    set q [::phase7::from_gimbals $angles]
    set dt 0.000001
    Transform_BodyAxes_StableMember [expr {0.7*$dt}] [expr {-0.4*$dt}] [expr {0.3*$dt}]
    set small [::phase7::advance_q $q [list [expr {0.7*$DEG_TO_RAD}] [expr {-0.4*$DEG_TO_RAD}] [expr {0.3*$DEG_TO_RAD}]] $dt]
    puts "jacobian|$angles|$IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE|[::phase7::gimbals $small]"
}
# Constant principal torque oracle: fixed unequal I, angular acceleration0.2rad/s².
set omega {0.0 0.0 0.0}; set quat {1.0 0.0 0.0 0.0}
for {set j 0} {$j < 1000} {incr j} {
    set omega [::phase7::omega_step $omega {0.2 0.0 0.0} {2.0 3.0 4.0} 0.001]
    set quat [::phase7::advance_q $quat $omega 0.001]
}
puts "constant_torque|$omega|$quat|[::phase7::matrix $quat]"
# Unequal-inertia torque-free energy/|L| and inertial momentum convergence.
foreach dt {0.002 0.001} {
    set omega {0.2 0.3 0.4}; set quat {1.0 0.0 0.0 0.0}
    set steps [expr {int(round(10.0/$dt))}]
    for {set j 0} {$j < $steps} {incr j} {
        set omega [::phase7::omega_step $omega {0.0 0.0 0.0} {2.0 3.0 4.0} $dt]
        set quat [::phase7::advance_q $quat $omega $dt]
    }
    puts "free|$dt|$omega|$quat|[::phase7::matrix $quat]"
}
foreach spec {{yaw 0 85} {pitch 150 0} {coupled 150 85} {yaw_negative 0 170} {pitch_negative 105 0}} {
    reset_model
    lassign $spec name jet5 jet6
    set pulses {}
    for {set j 0} {$j < 100} {incr j} {
        set ::packets {}
        set values [phase7_step 0.01 $jet5 $jet6 0]
        foreach packet $::packets {lappend pulses $packet}
        if {$j == 0 || $j == 99} {
            puts "vehicle|$name|$j|$values|[dict get $::phase7::last_telemetry inertia_before_kgm2]|[dict get $::phase7::last_telemetry inertia_after_kgm2]|[dict get $::phase7::last_telemetry mass_before_kg]|[dict get $::phase7::last_telemetry mass_after_kg]"
        }
    }
    puts "packets|$name|$pulses"
}
reset_model
set values [phase7_step 0.01 0 192 0]
puts "translation|$values|$::phase7::translations|$::packets|$xVelocity $yVelocity $zVelocity"
foreach rate {-8 8} {
    foreach counter {32 33 34} delta {{0.03 0 0} {0 0.03 0} {0 0 0.03}} {
        reset_model
        set Omega_Yaw $rate; set Omega_Pitch $rate; set Omega_Roll $rate
        modify_gimbal_angle {*}$delta
        puts "selector|$rate|$counter|$::packets"
    }
}
foreach spec {
    {negative_dt {phase7_step -0.01 0 0 0}}
    {too_large_dt {phase7_step 0.1 0 0 0}}
    {nonpositive_inertia {::phase7::omega_step {0 0 0} {0 0 0} {0 3 4} 0.001}}
    {singularity {::phase7::gimbals [::phase7::from_gimbals {0 0 80}]}}
    {nonconvergence {::phase7::omega_step {35 35 35} {0 0 0} {1 2 2.9} 0.01}}
} {
    lassign $spec name command
    set status [catch {eval $command} message]
    if {$status != 1} {error "Missing expected rejection $name"}
    puts "rejection|$name|$message"
}
puts {PHASE7_PHYSICS_COMPONENT_COMPLETE}
