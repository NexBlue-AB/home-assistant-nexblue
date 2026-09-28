# NexBlue Modbus TCP configuration for Home Assistant

This YAML package uses Home Assistant's built-in [Modbus integration](https://www.home-assistant.io/integrations/modbus/) to communicate with a NexBlue charger over the local network. It provides 37 sensors, a charging command switch, and one-shot scripts for setting current limits, fallback parameters, and phase mode.

You do not need to install the NexBlue cloud integration or the custom integration in this repository to use this package. The package requires manual YAML setup and does not automatically discover or add chargers.

## Supported models

| Models | Minimum firmware |
| --- | --- |
| Edge 2, Edge Max, Point 2 (UK) | 03.09.88 |
| Delta, Delta Max, Delta Max (UK) | 03.08.59 |

## Requirements

- Enable **Modbus TCP** in the charger settings in the NexBlue App.
- Home Assistant must be able to reach the charger's local network address on TCP port **502**.
- The default Unit ID is **200**. If you changed it, update every `slave: 200` entry in the package, including scripts and the switch. The documented range is 1–247.
- Tested firmware accepts one Modbus TCP client at a time. Disconnect other Modbus clients before using this package. All entities in this package share one hub connection.

## Install for one charger

1. Download [nexblue_modbus.yaml](nexblue_modbus.yaml) and place it in your Home Assistant configuration directory, alongside `configuration.yaml`.
2. Check the `host` setting:

   ```yaml
   host: NexBlue-EVC-Modbus.local.
   port: 502
   ```

   This hostname has been tested for a single charger. It must match the device's actual advertised hostname, and your Home Assistant environment must be able to resolve it. If resolution fails, replace it with the charger's local IP address. A DHCP reservation on your router helps keep that IP stable.

   Do not use `_nexblue_modbus._tcp.local.` as `host`: it is a DNS-SD service type, not a device hostname.

3. Add the following to `configuration.yaml`. If `homeassistant:` or `packages:` already exists, merge the entries instead of creating duplicate keys:

   ```yaml
   homeassistant:
     packages:
       nexblue_modbus: !include nexblue_modbus.yaml
   ```

   The supplied file already contains a top-level `modbus:` section and additional helper and script sections. Load it as a package, not with `modbus: !include nexblue_modbus.yaml`.

4. Run Home Assistant's configuration check, then restart Home Assistant.
5. In **Developer tools → States**, find **NexBlue Serial Number Raw** and confirm that it identifies the intended charger before using any controls.

## Readings

Sensors include identification and firmware, charging state, phase currents and voltages, power, session and lifetime energy, limits, phase mode, and diagnostic bitsets. A sensor with `(RW)` in its name only reads a writable register; use the controls below to write it.

Charging state and bitsets are displayed as raw values. Modbus charging-state codes are:

| Value | Meaning |
| --- | --- |
| 0 | Available |
| 1 | Preparing |
| 2 | Charging |
| 3 | SuspendedEVSE |
| 4 | SuspendedEV |
| 5 | Finishing |
| 6 | Reserved |
| 7 | Unavailable |
| 8 | Faulted |

The Modbus mapping version is also raw: for example, 256 is `0x0100`, meaning version 1.0. Lifetime energy is converted from Wh to kWh by the package.

## Charging switch

**NexBlue Modbus Charging Command** writes `1` to holding register 1006 to request charging, and `0` to request stopping. It reads the register back after one second and polls every 15 seconds.

The switch reflects the command register, not actual energy transfer. Use charging state, current, and power to check what the charger is doing. Delayed device readback can cause the switch to temporarily change back before showing the updated value.

The protocol does not allow this register to start or stop an OCPP-controlled charger. Avoid issuing conflicting charging commands from the app, portal, OpenAPI, and Modbus at the same time.

## Other write controls

Set a target value, then run its matching **Apply** script. Editing a target or restarting Home Assistant does not automatically write it to the charger. Targets are local input values, not device readbacks; check the existing `(RW)` sensors after applying a change.

| Register | Target | Apply script | Allowed input |
| --- | --- | --- | --- |
| 1000–1001 | Current Limit Target | Apply Current Limit | 0–32 A, in 0.1 A steps |
| 1002–1003 | Fallback Limit Target | Apply Fallback Limit | 0–16 A; firmware treats values below 6 A as 0 A |
| 1004–1005 | Fallback Timeout Target | Apply Fallback Timeout | 30–1800 seconds |
| 1007 | Phase Mode Target | Apply Phase Mode | Adaptive, Force single phase, Force three phase |

**Current-limit writes are one-shot.** Each write to register 1000 resets the control timeout, but this package does not send a periodic heartbeat. Once the configured timeout expires without another valid write, the charger uses its fallback behavior. This is not a continuous current-control implementation.

**Phase-switching limits are not enforced by the scripts.** Observe the documented minimum interval of 10 minutes, maximum of two switches in any one-hour period, and maximum of six switches per charging session.

According to the protocol, these holding-register settings revert to defaults after an AC power cycle. Script completion alone does not confirm that a physical operation has completed. Additional write controls require validation on your target charger and firmware.

## Add controls to a dashboard

Edit a dashboard, add a manual card, and paste this configuration:

```yaml
type: entities
title: NexBlue Modbus controls
show_header_toggle: false
entities:
  - entity: input_number.nexblue_modbus_current_limit_target
    name: Current limit target
  - entity: script.nexblue_modbus_apply_current_limit
    name: Apply current limit
  - type: divider
  - entity: input_number.nexblue_modbus_fallback_limit_target
    name: Fallback current target
  - entity: script.nexblue_modbus_apply_fallback_limit
    name: Apply fallback current
  - type: divider
  - entity: input_number.nexblue_modbus_fallback_timeout_target
    name: Fallback timeout target
  - entity: script.nexblue_modbus_apply_fallback_timeout
    name: Apply fallback timeout
  - type: divider
  - entity: input_select.nexblue_modbus_phase_mode_target
    name: Phase mode target
  - entity: script.nexblue_modbus_apply_phase_mode
    name: Apply phase mode
```

Add **NexBlue Modbus Charging Command** using the card editor's entity picker. Entity IDs can differ if previously created entities already use the suggested names. If a row is missing, check the actual ID in Developer tools and update the card.

This is dashboard YAML; do not paste the card into `configuration.yaml` or the package file. Enter the intended target before running a script: a helper's initial value is not necessarily the charger's current setting.

## Multiple chargers

Default mDNS names can change when multiple chargers negotiate duplicate names, including `-2` suffixes. Do not use these suffixes as stable charger identities.

1. Reserve an IP for each charger in the router and record its serial number and IP.
2. Copy the package into separate files, for example `nexblue_modbus_a.yaml` and `nexblue_modbus_b.yaml`.
3. Give each hub a different `name` and the correct reserved `host` IP.
4. Give every sensor and switch a distinct name and unique ID, preferably incorporating the charger serial number.
5. Rename the `input_number`, `input_select`, and `script` keys for each charger. Update the helper entity IDs referenced by each script, the script's `hub`, and dashboard references to match. Separate packages do not automatically namespace these identifiers.
6. Replace the single-package import with:

   ```yaml
   homeassistant:
     packages:
       nexblue_modbus_a: !include nexblue_modbus_a.yaml
       nexblue_modbus_b: !include nexblue_modbus_b.yaml
   ```

7. Check configuration, restart, and verify each serial-number reading before using controls.

Different chargers at different IP addresses can both use Unit ID 200. Do not import the original package as well as its copies, as this would create duplicate connections.

## Troubleshooting

- **Hostname cannot be resolved:** use the charger's IP and a DHCP reservation. Discovery via a separate mDNS tool does not guarantee that the Home Assistant runtime can resolve `.local` hostnames.
- **Connection closes or entities are unavailable:** check that Modbus TCP is enabled, the address is reachable, and no other Modbus client is occupying the connection.
- **Unexpected charger data:** compare the serial-number sensor with the intended charger, especially after adding a second device to the network.
- **Write result is delayed:** allow time for device processing and the corresponding sensor's polling interval. Inspect the register readback and actual charging state before repeating a command.
- **Controls are missing:** check configuration, restart, and search for `NexBlue Modbus` in the entity list. These manually configured entities are separate from the NexBlue cloud integration.

This is a configuration example, not a guarantee of compatibility with every Home Assistant environment or charger firmware. Configuration and value-encoding checks have passed; validate device behavior before relying on the write controls in automations.
