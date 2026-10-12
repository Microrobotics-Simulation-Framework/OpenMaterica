# Mixing rules

Schema 0.1.0, draft. Conventions, profiles and case numbers: `README.md`. Rationale: AD 3.5 (rule 3) and 4.12.
The mixing profile (MX) is optional in 0.1.0.

A cell that holds more than one material needs one value per property for a consumer whose grid cannot
resolve them. Some rules are identities, fixed by physics; the rest depend on how the materials are arranged
and on the regime, so the consumer picks one and the material input sheet records the pick.

## 1. General rules

1. Mixing happens inside a domain only. At a domain's edge a model gets geometry (a distance function, an
   interface record), never an average of the materials on either side (`geometry.md`). [MX-001]
2. The fractions are volume fractions `phi_i` of the materials in the cell, each in [0, 1] and summing to one
   within 1e-9. A declared background is inside every domain that requires it, so it counts as a material
   where it fills part of a cell. A consumer refuses fractions that do not sum to one. [MX-002]
3. The consumer declares the rule per model and field (`declarations.md`, `mixing`). A field's identity, where
   it has one, is used without a declaration. A field with no identity and no declared rule is refused.
   [MX-003]
4. A field with no general rule refuses to mix whatever is declared (section 4). [MX-004]
5. Consumers write the rules in their own code (constraint 26 of `DOCUMENTATION_ARCHITECTURE.md`); the numpy
   forms below are the reference against which they are verified. Vesalius's code never runs inside a
   consumer's computation. [not yet covered]
6. A consumer's soft fractions at a moving body's edge are its own declared discretisation, tested for
   convergence (AD 3.5, rule 3); they are not a mixing rule.

## 2. Identities

| Field | Identity | Holds for |
|---|---|---|
| `bulk.density` | `rho = sum_i phi_i * rho_i` | materials side by side in a cell (spatial mixing); never a solution, such as a contrast agent dissolved in blood, whose density is measured or derived as its own value [MX-005] |
| `bulk.elemental_composition` | `w_e = sum_i m_i * w_{i,e}`, with mass shares `m_i = phi_i * rho_i / rho` | spatial mixing, compositions by mass fraction [MX-006] |
| mass attenuation (radiological section, from 0.2) | `(mu/rho) = sum_i m_i * (mu/rho)_i`, so linear attenuation `mu = sum_i phi_i * mu_i` | photon attenuation by additivity of its elements (recalled: Bragg additivity) [MX-007] |

```python
import numpy as np

def density(phi, rho):                      # spatial mixing only
    return np.sum(phi * rho, axis=-1)

def mass_shares(phi, rho):
    return phi * rho / np.sum(phi * rho, axis=-1, keepdims=True)

def composition(phi, rho, w):               # w[..., i, e]: mass fraction of element e in material i
    return np.sum(mass_shares(phi, rho)[..., :, None] * w, axis=-2)
```

## 3. Named rules

Each rule states its assumptions; the consumer's pick declares that they hold in its cell. [MX-008]

| Rule | Equation | Assumptions |
|---|---|---|
| `arithmetic` | `p = sum_i phi_i * p_i` | the property adds by volume: materials side by side along the direction that matters (an upper bound for a modulus) |
| `harmonic` | `1/p = sum_i phi_i / p_i` | the inverse adds by volume: materials in series along the direction that matters; for a sound speed, the ray (short-wavelength) limit, in which travel times add (a lower bound for a modulus) |
| `wood` | `rho = sum_i phi_i * rho_i`; `kappa = sum_i phi_i / (rho_i * c_i**2)`; `c = 1 / sqrt(rho * kappa)` | sound speed in the long-wavelength limit, the structure much finer than the wavelength, the phases responding as fluids (no shear) |
| `series_conduction` | `1/k = sum_i phi_i / k_i` | conduction across layers stacked normal to the flux |
| `parallel_conduction` | `k = sum_i phi_i * k_i` | conduction along layers parallel to the flux |

`series_conduction` and `parallel_conduction` have the equations of `harmonic` and `arithmetic`; they are
named apart because the arrangement they assume is part of the pick the sheet records.

A cell half soft tissue (1050 kg/m3, 1540 m/s) and half bone (1900 kg/m3, 3500 m/s) gives 2138.9 m/s by
`harmonic`, 1746.5 m/s by `wood` and 2520.0 m/s by `arithmetic`: no rule is right for every regime. [MX-009]

```python
def arithmetic(phi, p):
    return np.sum(phi * p, axis=-1)

def harmonic(phi, p):
    return 1.0 / np.sum(phi / p, axis=-1)

def wood(phi, rho, c):
    rho_mix = np.sum(phi * rho, axis=-1)
    kappa_mix = np.sum(phi / (rho * c**2), axis=-1)
    return 1.0 / np.sqrt(rho_mix * kappa_mix)

series_conduction = harmonic
parallel_conduction = arithmetic
```

## 4. Fields with no general rule

1. These fields refuse to mix: failure properties (fracture energy, strength, critical stretch); model
   parameter sets, whose parameters are never averaged; categorical values; reference data. [MX-010]
2. In schema 0.1.0, `fluid.dynamic_viscosity` and every `magnetic` field also have no general rule: a cell
   holding two fluids, or a magnetic material and another, needs a model of the arrangement, which the
   consumer owns. [MX-011]
3. A field added in a later version states its identity, its permitted named rules, or that it has none.
   [not yet covered]

## 5. Conformance

1. Each rule is tested at a single cell, on stated fractions and values, against the expected value to a
   relative 1e-12 in double precision, never through a projector or a solver, where a wrong rule can pass
   unnoticed (prototype P1c; AD 4.12). [MX-012]
2. A consumer that differentiates through a rule also checks its derivatives with respect to the fractions and
   the values at the same cell. [MX-013]

## Cases

| Case | Profile | Tests |
|---|---|---|
| MX-001 | mixing | a cell across a domain's edge is not averaged |
| MX-002 | mixing | fractions that do not sum to one are refused; a background fraction counts inside the domain |
| MX-003 | mixing | an identity applies undeclared; a field with neither identity nor declared rule is refused |
| MX-004 | mixing | a field with no general rule refuses even with a rule declared |
| MX-005 | mixing | the density identity at a cell; a solution is not mixed by it |
| MX-006 | mixing | the composition identity by mass shares |
| MX-007 | mixing | mass attenuation by mass shares equals linear attenuation by volume fractions |
| MX-008 | mixing | the sheet records the rule picked, per model and field |
| MX-009 | mixing | the soft-tissue and bone cell: harmonic 2138.888888888889, Wood 1746.475961727937, arithmetic 2520 m/s |
| MX-010 | mixing | failure properties, parameter sets, categorical values and reference data refuse to mix |
| MX-011 | mixing | 0.1.0's viscosity and magnetic fields refuse to mix |
| MX-012 | mixing | every rule at a single cell, relative 1e-12 |
| MX-013 | mixing | derivatives of each rule with respect to fractions and values at a single cell |
