"""Backend transport selection. No process-global patches or USB fallbacks."""


def create_bridge(port, **options):
    if str(port).startswith('s3-'):
        from mklink.s3_registry import load_nodes
        from mklink.s3_transport import WirelessBridge
        try:
            node = load_nodes()[port]
        except KeyError:
            raise ConnectionError('S3 registration missing; no USB fallback') from None
        return WirelessBridge.from_node(node)
    from mklink.bridge import MKLinkSerialBridge
    return MKLinkSerialBridge(port, **options)
