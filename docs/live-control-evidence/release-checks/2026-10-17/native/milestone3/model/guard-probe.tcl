set src [lindex $argv 0]
set f [open "$src/Contributed/LM_Simulator/lm_simulator.tcl" r]
set initialization [join [lrange [split [read $f] "\n"] 123 240] "\n"]
close $f
source [lindex $argv 1]
proc write_socket {op address} {global packets; lappend packets [list $op $address]}
foreach control {{Y 0.1 0.01 0 0 0} {Z 0.1 0 -0.01 0 0} {ZERO 0.1 0.01 0 1 0} {LOCKED 0.1 0 -0.01 0 1}} {
    eval $initialization
    lassign $control id dx dy dz zero locked
    set bo(12,5) $zero
    set gimbalLock $locked
    set packets {}
    set before [list $IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE $PIMUX $PIMUY $PIMUZ $packets]
    set code [catch {modify_gimbal_angle $dx $dy $dz} message options]
    set after [list $IMUX_ANGLE $IMUY_ANGLE $IMUZ_ANGLE $PIMUX $PIMUY $PIMUZ $packets]
    if {$code != 1 || [dict get $options -errorcode] ne {APOLLO MILESTONE3 UNSUPPORTED_AXIS} || $before ne $after} {
        error "Unsupported-axis guard failed for $id"
    }
    puts "$id\t$code\t[dict get $options -errorcode]\tUNCHANGED"
}
puts {AXIS_GUARD_COMPLETE}
