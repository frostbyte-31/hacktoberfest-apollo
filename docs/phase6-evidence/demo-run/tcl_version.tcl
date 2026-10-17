puts [info patchlevel]
if {[package vcompare [info patchlevel] 8.6] < 0} {exit 1}
