# Model specification

Companion to the README — written to be reviewed by an orbital-mechanics or
space-systems engineer. Every formula and constant is sourced, and every headline
number is reproduced by `node verify.mjs`.

---

## 0. Constants

| symbol | value | source |
|---|---|---|
| `μ` | 398 600.4418 km³/s² | EGM-96 |
| `Re` | 6 378.137 km | WGS-84 equatorial radius |
| `J2` | 1.082 626 68 × 10⁻³ | WGS-84 |
| `ω⊕` | 7.292 115 9 × 10⁻⁵ rad/s | IERS sidereal rate |
| sidereal day | 86 164.0905 s | IERS |
| tropical year | 365.242 189 7 d | — |

---

## 1. Orbit propagation

**Scope (disclosed):** circular orbits (`e = 0`), two-body motion plus the
*secular* J2 effect on the right ascension of the ascending node. No drag, SRP,
third-body, tesseral terms, manoeuvres or TLE ingest.

Mean motion and period:

$$n = \sqrt{\frac{\mu}{a^3}}, \qquad T = 2\pi\sqrt{\frac{a^3}{\mu}}$$

**J2 nodal precession** (circular orbit):

$$\dot\Omega = -\tfrac{3}{2}J_2\left(\frac{R_e}{a}\right)^2 n\cos i$$

A prograde orbit (`i < 90°`) regresses westward; a retrograde one advances
eastward. Both signs are asserted in the audit.

**Sun-synchronous condition.** An orbit is sun-synchronous when its nodal
precession matches Earth's mean motion about the Sun (`+360°` per tropical year
= `0.9856 °/day`):

$$\cos i_{\text{SSO}} = -\frac{2\pi/T_{\text{year}}}{\tfrac{3}{2}J_2 (R_e/a)^2 n}$$

*Verification:* 97.40° @ 500 km, 97.59° @ 550 km, 98.19° @ 700 km, 98.60° @
800 km — matching published SSO inclinations to better than 0.1°, and the
resulting drift reproduces 0.9856 °/day to four decimals. This is a strong
end-to-end check: it exercises `μ`, `Re`, `J2`, the mean motion and the
precession formula simultaneously.

**Position.** For argument of latitude `u = u₀ + n t` and node
`Ω = Ω₀ + Ω̇ t`:

$$\begin{aligned}
x &= a(\cos u\cos\Omega - \sin u\cos i\sin\Omega)\\
y &= a(\cos u\sin\Omega + \sin u\cos i\cos\Omega)\\
z &= a\sin u\sin i
\end{aligned}$$

The sub-satellite point is `lat = asin(z/r)`, `lon = atan2(y,x) − ω⊕ t`. We take
**GMST = 0 at t = 0**, so longitudes are epoch-relative, not absolute. Coverage
statistics are invariant to this choice.

*Verification:* at `t = 0` the ascending node lies exactly on the equator; a
quarter orbit reaches `|lat| = i`; the radius is constant to 10⁻⁹ km (confirming
the orbit really is circular); and a 53° shell never produces a sub-point above
53.00° latitude.

---

## 2. Footprint geometry

A satellite at altitude `h` is visible from a ground point when that point lies
within an Earth-central half-angle

$$\lambda = \arccos\!\left(\frac{R_e}{R_e+h}\cos\varepsilon\right) - \varepsilon$$

for minimum elevation angle `ε`. At `ε = 0` this reduces to the horizon limit
`arccos(Re/(Re+h))`, which the audit checks to machine precision. Ground radius
is `λ·Re`.

*Verification:* 550 km at a 25° mask gives a **941 km** ground radius, matching
the ≈940 km cell radius quoted for Starlink. Monotonicity in both arguments
(higher mask → smaller footprint; higher altitude → larger) is asserted.

---

## 3. Walker constellations

Walker notation `i: T/P/F` — `T` satellites, `P` planes, `F` phasing.

- **Delta**: `Ω_p = p·360°/P` — nodes spread over the full 360°. GPS, Galileo,
  Starlink.
- **Star**: `Ω_p = p·180°/P` — nodes over 180°, the near-polar arrangement.
  Iridium, OneWeb.

Within a plane, `u_{p,s} = s·360°/S + F·p·360°/T`.

*Verification:* Iridium builds 66 satellites with nodes at 0…150°; Starlink
shell 1 builds 1584 with nodes spanning 0…355°.

---

## 4. Coverage statistics

**Instantaneous global coverage.** An equal-angle lat/lon grid; a cell counts as
covered if any sub-point is within `λ`. Cells are **area-weighted by cos(lat)** —
an unweighted count over-credits the poles severely (a 2°×2° cell at 80°N has
~17% of the equatorial cell's area).

*Verification:* for a single satellite the covered fraction has the closed form
of a spherical cap,

$$f = \frac{1-\cos\lambda}{2}$$

The grid reproduces it to within 0.03% for a GPS-altitude footprint, and to
within 0.6% for a 30° cap centred on the pole — the latter being precisely the
case an unweighted grid would get badly wrong.

**Site revisit.** Propagating a site over 24 h at 30 s steps yields the fraction
of time with ≥1 satellite in view, the longest gap, the mean gap and the pass
count.

---

## 5. Reproduced system-level results

**Iridium NEXT** (66 sats, 6 planes, 780 km, 86.4°, 8.2° mask) reaches **≥99.2%
instantaneous global coverage at every sampled epoch**, with **zero gap** over
Paris and Svalbard — reproducing the system's continuous-coverage design claim
from published parameters alone.

**The equatorial seam (an honest finding).** In the idealised Star model,
Singapore sees a peak of **2** satellites against Svalbard's **10**, and a ~90 s
gap appears in 12 h (98.5% coverage). This is real geometry, not a modelling
error: Star-pattern planes converge at the poles and are furthest apart at the
equator, so equatorial overlap is minimal. The real system closes that seam with
in-orbit spares, station-keeping and slightly different phasing — none of which
are modelled. The audit therefore asserts the *physics* (thin equatorial seam,
polar overlap ≫ equatorial overlap) rather than the marketing claim.

**Starlink's 53° shell** (1584 sats, 550 km, 25° mask) gives 100% coverage in the
0–10° band and **0%** above 80° — and McMurdo (78°S) never acquires a satellite.
A shell cannot cover latitudes beyond roughly `i + λ`.

**Altitude trade.** Holding 48 satellites fixed at a 10° mask: 62.2% coverage at
600 km, 98.6% at 1200 km, 100% at 2000 km. Tightening the mask on a fixed 800 km
shell: 96.1% at 5°, 62.2% at 15°, 28.1% at 30°. Both monotonic, both asserted.

---

## 6. Known simplifications (disclosed)

- Circular orbits only; no eccentricity, no argument-of-perigee drift.
- Secular J2 only — no short-period terms, no J3+, no drag or SRP.
- Spherical Earth for coverage geometry (WGS-84 equatorial radius); no terrain
  masking or atmospheric refraction at low elevation.
- No link budget, spectrum, capacity, inter-satellite links or ground segment.
- No constellation maintenance, spares, or launch/deployment scheduling.

None of these change the qualitative trades the studio exists to show —
satellites vs altitude vs inclination vs elevation mask — which is the point.
