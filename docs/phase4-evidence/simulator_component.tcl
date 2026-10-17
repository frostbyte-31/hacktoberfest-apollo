# GPL-2.0-or-later. Execute active upstream model; no emulator/guidance substitute.
set src [lindex $argv 0]
set f [open "$src/Contributed/LM_Simulator/lm_simulator.tcl" r]
set lines [split [read $f] "\n"]; close $f
# Execute only literal upstream initialization, no GUI/socket startup.
eval [join [lrange $lines 123 240] "\n"]
source "$src/Contributed/LM_Simulator/modules/AGC_IMU.tcl"
source "$src/Contributed/LM_Simulator/modules/AGC_Simulation_Monitor_Control.tcl"
proc write_socket {op address} {global packets; lappend packets [list $op $address]}
foreach mode {positive negative blocked} {
 eval [join [lrange $lines 123 240] "\n"]
 set bo(12,5) 0; set packets {}; set gimbalLock 0
 set Delta_Time2 0.026
 dynamic_simulation
 set Delta_Time 0.1
 if {$mode=="positive"} {set Q3A 1;set Q1F 1;set Q2L 1;set Q4R 1}
 if {$mode=="negative"} {set Q4F 1;set Q2A 1;set Q3R 1;set Q1L 1}
 update_RCS
 set Delta_Time2 0.1
 dynamic_simulation
 puts "MODE=$mode ALPHA_YAW=$Alpha_Yaw OMEGA_YAW=$Omega_Yaw IMUX=$IMUX_ANGLE IMUY=$IMUY_ANGLE IMUZ=$IMUZ_ANGLE PACKETS=[llength $packets] FIRST=[lindex $packets 0] LAST=[lindex $packets end]"
}