# GPL-2.0-or-later. Execute active upstream model with actual AGC jet latches.
set src [lindex $argv 0]
set f [open "$src/Contributed/LM_Simulator/lm_simulator.tcl" r]
set lines [split [read $f] "\n"]; close $f
eval [join [lrange $lines 123 240] "\n"]
source "$src/Contributed/LM_Simulator/modules/AGC_IMU.tcl"
source "$src/Contributed/LM_Simulator/modules/AGC_Simulation_Monitor_Control.tcl"
set gimbalLock 0
set bo(12,5) 0
proc write_socket {op address} {global packets; lappend packets [list $op $address]}
source {/Users/ggtrinkalipu/Documents/hacktoberfest-apollo/.build/phase7/runs/20261017T152845Z-71426fa6/integration/baseline-corrected-imu.tcl}
while {[gets stdin line] >= 0} {
 lassign $line dt jet5 jet6 zero blocked
 set packets {}
 set bo(12,5) $zero
 set j 0
 foreach name {Q4U Q4D Q3U Q3D Q2U Q2D Q1U Q1D} {
  set $name [expr {$blocked ? 0 : (($jet5 >> $j) & 1)}]; incr j
 }
 set j 0
 foreach name {Q3A Q4F Q1F Q2A Q2L Q3R Q4R Q1L} {
  set $name [expr {$blocked ? 0 : (($jet6 >> $j) & 1)}]; incr j
 }
 set Delta_Time2 0
 dynamic_simulation
 set Delta_Time $dt
 update_RCS
 set Delta_Time2 $dt
 dynamic_simulation
 puts "$Omega_Yaw $Omega_Pitch $Omega_Roll $IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE|$packets"
 flush stdout
}