# Factorio Tools: 2.0.55 to 2.1.8 Dataset Transition Report

This document outlines the key differences and schema updates between the 2.0.55 and 2.1.8 datasets (both Vanilla and Space Age). It is designed to help Claude (or any developer) update the frontend calculator implementation.

---

## 1. Top-Level Changes: Quality Definitions (`qualities`)

A new top-level key `"qualities"` has been added to the database. In Vanilla it contains only the `normal` quality, while in Space Age it lists all five qualities in gameplay level order:
1. `normal` (level 0)
2. `uncommon` (level 1)
3. `rare` (level 2)
4. `epic` (level 3)
5. `legendary` (level 5 - double bonus tier)

### Quality Schema
```json
"qualities": [
  {
    "key": "epic",
    "level": 3,
    "localized_name": { "en": "Epic" },
    "icon_col": 17,
    "icon_row": 11,
    "beacon_power_usage_multiplier": 0.5,
    "science_pack_drain_multiplier": 0.97,
    "cargo_wagon_inventory_size_multiplier": 1.75,
    "locomotive_power_multiplier": 1.6,
    "mining_drill_resource_drain_multiplier": 0.97,
    "rolling_stock_max_speed_multiplier": 1.5
  }
]
```
> [!NOTE]
> Quality icons are now packed directly into the main sprite sheet, and their locations are mapped via `"icon_col"` and `"icon_row"`.

---

## 2. Recipe Schema Changes

### A. Multiple Categories Support
* **2.0.55**: A recipe defined a single category as a string: `"category": "organic"`.
* **2.1.8**: A recipe now defines a list of compatible categories as an array: `"categories": [ "organic" ]`.

### B. Module Restriction Array (`allowed_effects`)
* **2.0.55**: Disallowing productivity modules was tracked using `"allow_productivity": true` (or omitted).
* **2.1.8**: The `"allow_productivity"` boolean has been replaced with an `"allowed_effects"` array containing the list of allowed module effects (`"consumption"`, `"speed"`, `"pollution"`, `"productivity"`, `"quality"`).
  * If productivity is disallowed, `"productivity"` is omitted from the array.
  * If quality is disallowed (e.g., in asteroid reprocessing recipes), `"quality"` is omitted from the array.
  * **Example (Asteroid reprocessing)**: `"allowed_effects": [ "consumption", "speed", "pollution" ]`

---

## 3. Entity Statistics: Quality Arrays

Rather than exporting static numbers for a single "common" quality, key stats on machines, beacons, and boilers have been converted into **arrays of numbers**. 
The index of each value in these arrays maps 1-to-1 to the index in the top-level `"qualities"` list:
* Index 0: Normal
* Index 1: Uncommon
* Index 2: Rare
* Index 3: Epic
* Index 4: Legendary

### A. Crafting, Mining, and Pumping Speeds
Speeds scale by $+30\%$ per quality level (with Legendary level 5 scaling to $+150\%$ / $2.5\times$ base):
* **Assembling Machine 3**: `"crafting_speed": [ 1.25, 1.625, 2.0, 2.375, 3.125 ]`
* **Electric Mining Drill**: `"mining_speed": [ 0.5, 0.65, 0.8, 0.95, 1.25 ]`
* **Offshore Pump**: `"pumping_speed": [ 20.0, 26.0, 32.0, 38.0, 50.0 ]`

### B. Beacons
* `"distribution_effectivity"` (scales linearly by $+0.2$ per quality level): `[ 1.5, 1.7, 1.9, 2.1, 2.5 ]`
* `"energy_usage"` (scales down via quality `beacon_power_usage_multiplier`): `[ 480000.0, 400000.0, 320000.0, 240000.0, 80000.0 ]`

### C. Boilers & Heat Exchangers
Boilers are now fully characterized with thermodynamic arrays for maximum inputs and outputs across all qualities:
* `"energy_consumption"` (maximum fuel/heat intake rate): `[ 1800000.0, 2340000.0, 2880000.0, 3420000.0, 4500000.0 ]`
* `"heat_output"` (maximum steam/heat generation rate): `[ 60.0, 78.0, 96.0, 114.0, 150.0 ]`
* `"fluid_consumption"` (maximum water/input fluid usage): `[ 6.0, 7.8, 9.6, 11.4, 15.0 ]`
* `"emissions_per_minute.pollution"` (within `energy_source`): `[ 30.0, 39.0, 48.0, 57.0, 75.0 ]`

---

## 4. New Power/Boiler Entities (Space Age)

Two new entities have been added to the `"boilers"` array in Space Age:
1. **Heating Tower (`"heating-tower"`)**:
   * Consumes chemical fuel to produce heat.
   * `"energy_consumption"` (burner fuel intake rate at 250% efficiency): `[ 16.0MW, 20.8MW, 25.6MW, 30.4MW, 40.0MW ]`
   * `"heat_output"` (thermal heat output rate): `[ 40.0MW, 52.0MW, 64.0MW, 76.0MW, 100.0MW ]`
   * `"emissions_per_minute.pollution"`: `[ 100.0, 130.0, 160.0, 190.0, 250.0 ]`
   * Does not consume fluid (`"fluid_consumption"` is omitted).
2. **Fusion Generator (`"fusion-generator"`)**:
   * Consumes plasma to generate electricity and hot fluoroketone.
   * `"energy_consumption"` (electric power generation limit): `[ 50.0MW, 65.0MW, 80.0MW, 95.0MW, 125.0MW ]`
   * `"fluid_consumption"` (fusion plasma intake rate): `[ 2.0, 2.6, 3.2, 3.8, 5.0 ]`
   * `"heat_output"` (hot fluoroketone discharge rate): `[ 2.0, 2.6, 3.2, 3.8, 5.0 ]`

---

## 5. Transport Belts Sorting

* **2.0.55**: Belts were returned sorted alphabetically by key name.
* **2.1.8**: Belts in the `"belts"` array are now returned sorted by `"speed"` ascending (lowest to highest), allowing for cleaner drop-down layout ordering.
