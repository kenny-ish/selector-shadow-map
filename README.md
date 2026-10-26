# selector-shadow-map

selector-shadow-map compares the dispatcher selectors extracted from two deployed EVM runtimes, so an upgrade reviewer can find proxy and implementation selector collisions using only `eth_getCode`.

## Example

This is real output from Optimism mainnet at `latest`, comparing the Optimism system predeploy `0x4200000000000000000000000000000000000000` with the WETH predeploy `0x4200000000000000000000000000000000000006`.

    $ python selector_shadow.py --rpc-url https://mainnet.optimism.io --proxy 0x4200000000000000000000000000000000000000 --implementation 0x4200000000000000000000000000000000000006
    {
      "block": "latest",
      "collision_count": 0,
      "collisions": [],
      "implementation": {
        "code_bytes": 2041,
        "executable_bytes": 1989,
        "selectors": [
          "0x06fdde03",
          "0x095ea7b3",
          "0x18160ddd",
          "0x23b872dd",
          "0x2e1a7d4d",
          "0x313ce567",
          "0x70a08231",
          "0x95d89b41",
          "0xa9059cbb",
          "0xd0e30db0",
          "0xdd62ed3e"
        ],
        "selector_offsets": {
          "0x06fdde03": [167],
          "0x095ea7b3": [178],
          "0x18160ddd": [129],
          "0x23b872dd": [140],
          "0x2e1a7d4d": [151],
          "0x313ce567": [80],
          "0x70a08231": [91],
          "0x95d89b41": [102],
          "0xa9059cbb": [42],
          "0xd0e30db0": [53],
          "0xdd62ed3e": [64]
        }
      },
      "implementation_address": "0x4200000000000000000000000000000000000006",
      "proxy": {
        "code_bytes": 2055,
        "executable_bytes": 2043,
        "selectors": [
          "0x3659cfe6",
          "0x4f1ef286",
          "0x5c60da1b",
          "0x8f283970",
          "0xf851a440"
        ],
        "selector_offsets": {
          "0x3659cfe6": [69],
          "0x4f1ef286": [80],
          "0x5c60da1b": [31],
          "0x8f283970": [42],
          "0xf851a440": [53]
        }
      },
      "proxy_address": "0x4200000000000000000000000000000000000000",
      "source": "rpc",
      "verdict": "no-selector-collision-found"
    }

## Usage

Use two live contracts:

    python selector_shadow.py --rpc-url RPC_URL --proxy PROXY_ADDRESS --implementation IMPLEMENTATION_ADDRESS [--block latest]

Use saved runtime bytecode without a network request:

    python selector_shadow.py --proxy-code 0x... --implementation-code 0x...

The report lists selectors found in `PUSH4 ... EQ` dispatcher patterns, their byte offsets, and the intersection. It does not prove that either address is a proxy, nor does it resolve selector names.

## How it works

The tool calls `eth_getCode` for each address, disassembles PUSH instructions without confusing their data for opcodes, removes a Solidity CBOR trailer when its length marker is valid, and records `PUSH4` values that are compared by `EQ` nearby. The intersection is a concrete bytecode-level collision set, not an ABI guess.

## Tests

Run `python -m unittest -v`.
