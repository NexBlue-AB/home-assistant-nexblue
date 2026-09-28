# NexBlue Home Assistant Integration

NexBlue-maintained Home Assistant custom integration for supported NexBlue EV
chargers. It connects to the NexBlue cloud service and presents charger data and
basic charging controls in Home Assistant.

### Features

- Charger discovery for the signed-in account
- Cloud-polled charger status and telemetry, including charging state, power,
  session and lifetime energy, current, voltage, network status, and selected
  diagnostic values
- Start and stop charging
- Automatic access-token renewal and recovery from an invalid refresh token
- Home Assistant reauthentication when saved credentials can no longer sign in

The integration polls the NexBlue cloud service approximately once per minute.
It does not currently provide charger configuration controls such as changing a
charging-current limit.

### Installation

1. Download a release of this repository.
2. Copy the `custom_components/nexblue` directory into your Home Assistant
   configuration directory:

   ```text
   <config>/custom_components/nexblue
   ```

3. Restart Home Assistant.
4. In Home Assistant, open **Settings** → **Devices & services** → **Add
   integration**, search for **NexBlue**, and sign in with your NexBlue account.

On first load, Home Assistant automatically installs the public
[`nexblue-api`](https://pypi.org/project/nexblue-api/) Python dependency. An
internet connection is required for that initial installation and for cloud
operation.

### Local Modbus TCP configuration

For supported chargers, see the [Modbus TCP YAML example](examples/modbus/README.md)
for local readings, charging commands, and one-shot parameter writes using Home
Assistant's built-in Modbus integration.

This example is configured separately and does not require the cloud integration.
Installing or updating the custom integration through HACS does not automatically
install the YAML package. Follow the example's manual setup instructions and
control limitations, including the absence of a periodic current-limit heartbeat.

### Credentials and privacy

To support automatic session recovery, Home Assistant stores the NexBlue
username, password, and refresh token in its local configuration storage. The
short-lived access token is kept only in memory.

Treat your Home Assistant configuration directory and its backups as sensitive:
limit access to them and never share their contents. Do not include passwords,
tokens, or charger serial numbers in bug reports.

### Support

Please report reproducible issues through the
[issue tracker](https://github.com/NexBlue-AB/home-assistant-nexblue/issues).
Include the Home Assistant version, integration version, and non-sensitive log
messages. Remove credentials, tokens, and personally identifiable charger data
before posting.

### License

Copyright 2026 NexBlue. Licensed under the Apache License, Version 2.0. See
[LICENSE](LICENSE) and [NOTICE](NOTICE).
