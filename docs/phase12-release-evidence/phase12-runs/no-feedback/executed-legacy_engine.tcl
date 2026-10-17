# GPL-2.0-or-later. Headless adapter around the unchanged pinned LM plant.
# Python validates original source hashes and the Tcl runtime before launch.
# The existing proc supplies thrust/mass, fuel depletion and body delta-v.
# This adapter captures that delta-v; Phase 11 owns actual PIPA quantization.
if {[llength $argv] != 5} {error {Expected source root, Phase7 overlay, mass, fuel and ascent mass}}
lassign $argv src phase7 total_mass fuel ascent_mass
set stream [open "$src/Contributed/LM_Simulator/lm_simulator.tcl" r]
set text [read $stream]
close $stream
# Exact retained initialization slice already used by Phase5 plant_server.tcl.
eval [join [lrange [split $text "\n"] 123 240] "\n"]
source "$src/Contributed/LM_Simulator/modules/AGC_Simulation_Monitor_Control.tcl"
proc modify_pipaXYZ {x y z} {error {Phase7 capture must replace this stub}}
proc Transform_BodyAxes_StableMember {x y z} {
    if {$x != 0 || $y != 0 || $z != 0} {
        error {Nonzero angular motion is outside the fixed-attitude propulsion fixture}
    }
}
# Defines exact existing quaternion conversion/matrix operations and its capture
# of upstream body delta-v. phase7_step is never called: RCS remains disconnected.
source $phase7
set LM_Weight_Ascent_KG $ascent_mass
set LM_Weight_Descent_KG [expr {$total_mass-$ascent_mass}]
set Descent_Propellant_Mass_KG $fuel
set DESCENT_ENGINE_FLAG 0
set ASCENT_ENGINE_FLAG 0
puts READY
flush stdout
while {[gets stdin line] >= 0} {
    if {[llength $line] != 7} {error {Invalid step field count}}
    lassign $line dt enabled thrust qw qx qy qz
    foreach value $line {
        if {![string is double -strict $value]} {error {Nonnumeric plant input}}
    }
    if {$dt <= 0 || $dt > 0.010001 || $enabled ni {0 1} || $thrust < 0 || $thrust > $Descent_Propulsion_Max_N} {
        error {Outside bounded propulsion fixture}
    }
    set before [expr {$LM_Weight_Ascent_KG+$LM_Weight_Descent_KG}]
    set before_fuel $Descent_Propellant_Mass_KG
    if {$enabled && $thrust*$dt/$Descent_Specific_Impulse_MS > $before_fuel} {
        error {Fuel-exhaustion transient is outside the bounded fixture}
    }
    set DESCENT_ENGINE_FLAG $enabled
    set Descent_Propulsion_N $thrust
    set Delta_Time2 $dt
    set ::phase7::translations {}
    # This is the original upstream procedure, with no body rewrite.
    dynamic_simulation
    set dv {0.0 0.0 0.0}
    foreach increment $::phase7::translations {
        set next {}
        foreach old $dv added $increment {lappend next [expr {$old+$added}]}
        set dv $next
    }
    set matrix [::phase7::matrix [list $qw $qx $qy $qz]]
    puts [concat [list $before [expr {$LM_Weight_Ascent_KG+$LM_Weight_Descent_KG}] \
        $before_fuel $Descent_Propellant_Mass_KG $Descent_Acceleration \
        $Descent_Fuel_Flow_SEC $DESCENT_ENGINE_FLAG] $dv $matrix]
    flush stdout
}
