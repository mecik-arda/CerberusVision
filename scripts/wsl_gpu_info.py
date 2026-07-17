from __future__ import annotations

import json

from openvino import Core


def main() -> None:
    core = Core()
    report: dict[str, object] = {"available_devices": core.available_devices}
    for device in core.available_devices:
        if not device.startswith("GPU"):
            continue
        properties = [str(item) for item in core.get_property(device, "SUPPORTED_PROPERTIES")]
        details: dict[str, object] = {"supported_properties": properties}
        for name in properties:
            if name in {
                "FULL_DEVICE_NAME",
                "DEVICE_TYPE",
                "DEVICE_ARCHITECTURE",
                "OPTIMIZATION_CAPABILITIES",
                "EXECUTION_DEVICES",
            } or "MEMORY" in name or "_MEM_" in name:
                try:
                    value = core.get_property(device, name)
                    details[name] = str(value)
                except Exception as error:
                    details[name] = f"error: {error}"
        report[device] = details
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
