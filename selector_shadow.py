#!/usr/bin/env python3
"""Find Solidity-style dispatcher selector collisions between two EVM contracts."""

from __future__ import annotations

import argparse
import json
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Instruction:
    offset: int
    opcode: int
    operand: bytes = b""


def disassemble(code: bytes) -> list[Instruction]:
    """Split bytecode into instructions, keeping PUSH data with its opcode."""
    instructions: list[Instruction] = []
    offset = 0
    while offset < len(code):
        opcode = code[offset]
        size = opcode - 0x5F if 0x60 <= opcode <= 0x7F else 0
        end = offset + 1 + size
        if end > len(code):
            instructions.append(Instruction(offset, opcode, code[offset + 1 :]))
            break
        instructions.append(Instruction(offset, opcode, code[offset + 1 : end]))
        offset = end
    return instructions


def executable_prefix(code: bytes) -> bytes:
    """Remove a valid-looking Solidity CBOR trailer from the scan range."""
    if len(code) < 2:
        return code
    metadata_length = int.from_bytes(code[-2:], "big")
    start = len(code) - 2 - metadata_length
    if start >= 0 and start < len(code) and (code[start] >> 5) == 5:
        return code[:start]
    return code


def selector_offsets(code: bytes) -> dict[str, list[int]]:
    """Return PUSH4 constants used in a nearby EQ comparison.

    Solidity dispatchers normally compare calldata's first four bytes with a
    PUSH4 constant. A short forward window catches the direct EQ form and a
    few compiler layout variants, while avoiding every arbitrary PUSH4 literal.
    """
    instructions = disassemble(executable_prefix(code))
    found: dict[str, list[int]] = {}
    stop_ops = {0x00, 0x56, 0x57, 0x5B, 0xF3, 0xFD, 0xFE, 0xFF}
    for index, instruction in enumerate(instructions):
        if instruction.opcode != 0x63 or len(instruction.operand) != 4:
            continue
        for following in instructions[index + 1 : index + 5]:
            if following.opcode == 0x14:  # EQ
                selector = "0x" + instruction.operand.hex()
                found.setdefault(selector, []).append(instruction.offset)
                break
            if following.opcode in stop_ops:
                break
    return found


def analyze_bytecode(code_hex: str) -> dict[str, Any]:
    """Analyze one 0x-prefixed runtime bytecode string."""
    if not code_hex.startswith("0x"):
        raise ValueError("bytecode must start with 0x")
    if len(code_hex) % 2:
        raise ValueError("bytecode hex has an odd number of digits")
    try:
        code = bytes.fromhex(code_hex[2:])
    except ValueError as exc:
        raise ValueError("bytecode is not hexadecimal") from exc
    locations = selector_offsets(code)
    return {
        "code_bytes": len(code),
        "executable_bytes": len(executable_prefix(code)),
        "selectors": sorted(locations),
        "selector_offsets": {key: locations[key] for key in sorted(locations)},
    }


def compare_bytecode(proxy_hex: str, implementation_hex: str) -> dict[str, Any]:
    """Compare dispatcher selectors and mark selectors present in both codes."""
    proxy = analyze_bytecode(proxy_hex)
    implementation = analyze_bytecode(implementation_hex)
    collisions = sorted(set(proxy["selectors"]) & set(implementation["selectors"]))
    return {
        "proxy": proxy,
        "implementation": implementation,
        "collisions": collisions,
        "collision_count": len(collisions),
        "verdict": "collision-found" if collisions else "no-selector-collision-found",
    }


def rpc_call(rpc_url: str, method: str, params: list[Any]) -> Any:
    """Make one JSON-RPC request without a third-party client."""
    request_body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode("utf-8")
    request = urllib.request.Request(
        rpc_url,
        data=request_body,
        headers={"Content-Type": "application/json", "User-Agent": "selector-shadow-map/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        envelope = json.loads(response.read().decode("utf-8"))
    if "error" in envelope:
        raise RuntimeError(str(envelope["error"]))
    return envelope["result"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find Solidity dispatcher selector collisions between two contracts."
    )
    parser.add_argument("--rpc-url", help="JSON-RPC endpoint")
    parser.add_argument("--proxy", help="proxy contract address")
    parser.add_argument("--implementation", help="implementation contract address")
    parser.add_argument("--proxy-code", help="offline proxy runtime bytecode")
    parser.add_argument("--implementation-code", help="offline implementation runtime bytecode")
    parser.add_argument("--block", default="latest", help="block tag or hex block number")
    args = parser.parse_args()

    if args.proxy_code is not None or args.implementation_code is not None:
        if not (args.proxy_code and args.implementation_code):
            parser.error("offline mode needs both --proxy-code and --implementation-code")
        result = compare_bytecode(args.proxy_code, args.implementation_code)
    elif args.rpc_url and args.proxy and args.implementation:
        proxy_code = rpc_call(args.rpc_url, "eth_getCode", [args.proxy, args.block])
        implementation_code = rpc_call(
            args.rpc_url, "eth_getCode", [args.implementation, args.block]
        )
        result = compare_bytecode(proxy_code, implementation_code)
        result["proxy_address"] = args.proxy
        result["implementation_address"] = args.implementation
        result["block"] = args.block
        result["source"] = "rpc"
    else:
        parser.error(
            "use both offline code flags, or provide --rpc-url, --proxy, and --implementation"
        )
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
