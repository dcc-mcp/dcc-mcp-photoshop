# Bridge Protocol Ownership

dcc-mcp-photoshop does not own a Photoshop-specific WebSocket protocol. All
adapter-to-host communication goes through the adobepy broker, Python facade,
and UXP bridge.

The protocol contract, capability negotiation, error codes, and bridge
templates live in the [adobepy repository](https://github.com/dcc-mcp/adobepy):

- `contracts/adobepy_protocol_contract.json`
- `docs/protocol.md`
- `bridges/uxp/photoshop/`

Skills should call `adobe.photoshop.Photoshop` and must not open bridge sockets
or duplicate the JSON-RPC dialect. Runtime acceptance requires broker health,
at least one connected Photoshop bridge session, and a successful real host
call.
