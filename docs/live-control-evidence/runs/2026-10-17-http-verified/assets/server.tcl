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

source [lindex $argv 1]
while {[gets stdin line] >= 0} {
 lassign $line dt jet5 jet6 zero
 set packets {}
 set values [phase7_step $dt $jet5 $jet6 $zero]
 set extra {}
 foreach key {inertia_before_kgm2 inertia_after_kgm2 mass_before_kg mass_after_kg fuel_before_kg fuel_after_kg legacy_perjet_alpha_deg_s2 gimbal_rates_deg_s} {
  lappend extra {*}[dict get $::phase7::last_telemetry $key]
 }
 lappend extra [llength [dict get $::phase7::last_telemetry translation_suppressed_deltaV_body_m_s]]
 puts "[join $values { }]|$packets|[join $extra { }]"
 flush stdout
}
