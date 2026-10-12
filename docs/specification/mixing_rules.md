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
   within the model's declared `fraction_sum_tolerance` (`declarations.md`, `mixing`), which follows the
   model's precision (about 1e-9 in double precision; looser in single). A background inside every domain
   that lists it counts as a material where it fills part of a cell (`geometry.md`). A consumer refuses
   fractions that do not sum to one within that tolerance (`fractions_invalid`). [MX-002]
3. The consumer declares the rule per model and field (`declarations.md`, `mixing.rules`): `identity`, a named
   rule, or `refuse`. An identity applies only when declared, because declaring it states that the materials
   sit side by side in the cell, which only the consumer knows. A field with no declared rule is refused
   (`mixing_refused`). [MX-003]
4. A field with no general rule refuses to mix whatever is declared (section 4). [MX-004]
5. Consumers write the rules in their own code (constraint 26 of `DOCUMENTATION_ARCHITECTURE.md`); the numpy
   forms below are the reference against which they are verified. Vesalius's code never runs inside a
   consumer's computation. [not yet covered]
6. A consumer's soft fractions at a moving body's edge are its own declared discretisation, tested for
   convergence (AD 3.5, rule 3); they are not a mixing rule. [not yet covered]

## 2. Identities

| Field | Identity | Holds for |
|---|---|---|
| `bulk.density` | `rho = sum_i phi_i * rho_i` | materials side by side in a cell (spatial mixing); never a solution, such as a contrast agent dissolved in blood, whose density is measured or derived as its own value [MX-005] |
| `bulk.elemental_composition` | `w_e = sum_i m_i * w_{i,e}`, with mass shares `m_i = phi_i * rho_i / rho` | spatial mixing, compositions by mass fraction [MX-006] |

1. The composition identity reads each material's `bulk.density` for the mass shares, so a model that declares
   it MUST also hold a requirement on `bulk.density`, checked like any other. [MX-014]
2. The composition identity refuses a composition whose `sum_rule` is `partial`, or which carries a
   `stated_sum` (the source's fractions do not sum to one): mixing it would treat it as complete. [MX-015]
3. The identity for mass attenuation, and any other identity, arrives with its section (the radiological
   section in 0.2). [not yet covered]

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

1. `harmonic` and `wood` refuse a cell in which any material with a non-zero fraction has a zero or negative
   value of the property they divide by (`mixing_refused`). [MX-016]
2. Rules for conduction across and along layers arrive with the thermal section. [not yet covered]

A cell half soft tissue (1050 kg/m3, 1540 m/s) and half bone (1900 kg/m3, 3500 m/s) gives 2138.9 m/s by
`harmonic`, 1746.5 m/s by `wood` and 2520.0 m/s by `arithmetic`: no rule is right for every regime. The case
holds the numbers to a relative 1e-12. [MX-009]

```python
def arithmetic(phi, p):
    return np.sum(phi * p, axis=-1)

def harmonic(phi, p):
    return 1.0 / np.sum(phi / p, axis=-1)

def wood(phi, rho, c):
    rho_mix = np.sum(phi * rho, axis=-1)
    kappa_mix = np.sum(phi / (rho * c**2), axis=-1)
    return 1.0 / np.sqrt(rho_mix * kappa_mix)
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
| MX-002 | mixing | fractions that do not sum to one within the declared tolerance are refused; a listed background counts |
| MX-003 | mixing | an identity applies only when declared; a field with no declared rule is refused |
| MX-004 | mixing | a field with no general rule refuses even with a rule declared |
| MX-005 | mixing | the density identity at a cell; a solution is not mixed by it |
| MX-006 | mixing | the composition identity by mass shares |
| MX-008 | mixing | the sheet records the rule picked, per model and field |
| MX-009 | mixing | the soft-tissue and bone cell: harmonic 2138.8888888888887, Wood 1746.475961727937, arithmetic 2520.0 m/s, relative 1e-12 |
| MX-010 | mixing | failure properties, parameter sets, categorical values and reference data refuse to mix |
| MX-011 | mixing | 0.1.0's viscosity and magnetic fields refuse to mix |
| MX-012 | mixing | every rule at a single cell, relative 1e-12 |
| MX-013 | mixing | derivatives of each rule with respect to fractions and values at a single cell |
| MX-014 | mixing | the composition identity without a requirement on density is refused |
| MX-015 | mixing | a partial or mis-summed composition is refused by the composition identity |
| MX-016 | mixing | `harmonic` and `wood` refuse a zero or negative value they divide by |
