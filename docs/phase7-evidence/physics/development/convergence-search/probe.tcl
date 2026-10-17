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
foreach speed {35 40 50 60 80 100} {
 set code [catch {::phase7::omega_step [list $speed $speed $speed] {0 0 0} {1 2 2.9} 0.01} msg]
 puts "$speed|$code|$msg"
}
puts {CONVERGENCE_SEARCH_COMPLETE}
