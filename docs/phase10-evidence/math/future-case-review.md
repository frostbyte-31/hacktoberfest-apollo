# Independent review of the angle-0.4 native case

The independent scripts were frozen before the final repeated native validation.
`source-freeze.json` fingerprints them. No earlier candidate or captured run was
changed in response to these calculations.

```sh
python3 -B docs/phase10-evidence/math/inspect_native.py \
  --run .build/phase10/future-15km-01 \
  --output .build/phase10-future-independent-review.json
```

`native-future-15km-01.json` retains the actual independent inspection and the
hashes of the raw trace, observer map and input configuration. It records nine
original ROOTPSRS entries and nine original normal-return observations. These
are observations of the actual AGC-computed root, not a modern root solution.

Signed root times, in order:

```
-847.23549805  -849.03689941  -849.03705566
-585.82227539  -585.83947266  -585.83930176
-582.79771973  -582.79703125  -582.79703125 seconds
```

The four original coefficients agree with independently evaluated operations on
the actual observed operands within 0.875 DP LSB. All observed polynomials are
nondegenerate, all observed derivative coefficients meet original ROOTPSRS's
`abs(i*Ai)<1` requirement, and the derivatives at the observed roots are nonzero.
Maximum fractional residual is `3.497e-8`; maximum relative residual is
`1.651e-6`. These checks support meaningful original numerical progression in
the explicitly synthetic geometry. They do not establish flight convergence.

The independent frame comparisons use the actual native REFSMMAT and CG:

| Check over nine passes | Maximum observed difference |
|---|---:|
| LAND versus independent original lunar orientation at **TPIP**, not TLAND | 0.525 m norm |
| First LAND versus original TTFINCR transport formula using actual WM | 0.190 m norm |
| R versus physical REFSMMAT × original RATT1 | 0.061 m/component |
| RGU versus physical CG × (R−LAND) | 0.124 m/component |
| VGU versus physical CG × (V−omega×R) | 0.000373 m/s/component |
| CG row orthogonality | `1.253e-7` maximum absolute error |

The position differences are compatible with the explicitly retained original
fixed-point rounding. The lunar matrix comparison also includes the original
first-order transport approximation and independently decoded angle/rate
constants. Initial CG is identity; subsequent matrices remain proper rotations.

The earlier angle-0.15 runs reached meaningful roots but selected a past
ignition epoch by the time data entry finished. The angle-0.4 configuration
addresses this by moving the **initialized spacecraft orbital phase** earlier,
preserving the clock, epochs, guidance equations and existing results. Actual
future ignition timing and V06N61 display are validated by the native-driver
analysis elsewhere in Phase 10. This arithmetic inspection makes no separate
engine-response or powered-descent claim.
