"""RTT target text must never terminate capture through optional chart parsing."""
import asyncio
import threading
import time
from unittest.mock import Mock

import pytest

from mklink.rtt_viewer import RttLineParser
from mklink.remote.dashboards import RttChannelDecoder, RttStreamManager
from mklink.remote.stream_hub import StreamHub
from mklink.remote.stream_protocol import (
    RTT_RAW_UTF8_LINES, RTT_TERMINAL_UTF8, StreamType,
    decode_rtt_lines, decode_waveform_samples,
)

BANNER = "I/elog    [0.003] EasyLogger V2.2.99 is initialize success."
HEX = "S1| F1 09 71 C6 0C 14 46 FC 00 00 00 ED "
STATS = "S1 stats: total=12 avail=0 lost=0 err=0"
PAYLOAD = (BANNER + "\r\n" + HEX + "\r\n" + STATS + "\r\n").encode()


@pytest.mark.parametrize("token", ["0C", "0c", "0A", "0B", "C6", "FC", "ED", "0x12",
                                    "25C", "3mV", "2Hz", "4%", "1_000", "NaN", "inf", "1e999"])
def test_csv_does_not_strip_hex_or_unit_suffixes(token):
    assert not RttLineParser._is_numeric(token)
    parser = RttLineParser("csv")
    assert parser.parse(f"1,{token},3") is None
    assert parser.parse("1,2,3") == {"v0": 1, "v1": 2, "v2": 3}
    assert parser.parse(f"1,{token},3") is None
    assert parser.parse("4,5,6") == {"v0": 4, "v1": 5, "v2": 6}


@pytest.mark.parametrize("line", [HEX, "F1 09 71 C6 0C 14 46 FC 00 00 00 ED",
                                  "S1| 01 02 03 04", "0C,01,02,03", "M,1,2,3"])
def test_mixed_and_hex_logs_do_not_select_csv(line):
    assert RttLineParser.auto_detect([BANNER, line]).strategy == "kv"
    parser = RttLineParser("csv")
    assert parser.parse(line) is None
    assert parser.parse("1,2") == {"v0": 1, "v1": 2}


@pytest.mark.parametrize("separator", [",", "\t", "  "])
def test_decimal_detection_and_conversion_agree(separator):
    line = separator.join(["[+1.25]", "(-2e-3)", "{.5}", "3."])
    parser = RttLineParser.auto_detect([line])
    assert parser.strategy == "csv"
    assert parser.parse(line) == {"v0": 1.25, "v1": -.002, "v2": .5, "v3": 3}
    assert parser.parse(line) == {"v0": 1.25, "v1": -.002, "v2": .5, "v3": 3}


def test_explicit_headers_kv_units_and_regex_remain_supported():
    parser = RttLineParser("csv")
    assert parser.parse("temp,speed") is None
    assert parser.parse("25,1200") == {"temp": 25, "speed": 1200}
    assert RttLineParser("csv", csv_headers=["x", "y"]).parse("1,2") == {"x": 1, "y": 2}
    assert RttLineParser().parse("temp=25C voltage=3.3mV speed=-1.2e3") == {
        "temp": 25, "voltage": 3.3, "speed": -1200,
    }
    parser = RttLineParser("regex", regex_pattern=r"x=(?P<x>\S+)")
    assert parser.parse("x=1.25e2") == {"x": 125}
    assert parser.parse("x=inf") is None


def _raw(hub):
    return [line.text for call in hub.publish.call_args_list
            if call.kwargs["stream_type"] is StreamType.RTT_RAW
            and call.kwargs["flags"] == RTT_RAW_UTF8_LINES
            for line in decode_rtt_lines(call.args[0], call.kwargs["item_count"])]


def _terminal(hub):
    return b"".join(call.args[0] for call in hub.publish.call_args_list
                    if call.kwargs["flags"] == RTT_TERMINAL_UTF8)


def _waves(hub, columns):
    return [row for call in hub.publish.call_args_list
            if call.kwargs["stream_type"] is StreamType.WAVEFORM
            for row in decode_waveform_samples(call.args[0], call.kwargs["item_count"], columns)]


@pytest.mark.parametrize("chunk_size", [1, 2, 7, 31, 65536])
def test_hex_then_numeric_and_plain_text_survive_chunk_boundaries(chunk_size):
    hub = Mock()
    decoder = RttChannelDecoder(hub)
    payload = PAYLOAD + b"1,2\r\n3,4\r\n" + HEX.encode() + "\r\n后续日志\r\ntail".encode()
    for offset in range(0, len(payload), chunk_size):
        decoder.feed_rtt_bytes(payload[offset:offset + chunk_size])
        decoder.flush_pending()
    decoder.flush_pending(final=True)
    assert _terminal(hub) == payload
    assert _raw(hub) == payload.decode().splitlines()
    assert _waves(hub, 2) == [(1, 2), (3, 4)]


@pytest.mark.parametrize("failure", [ValueError, OverflowError])
def test_optional_conversion_failure_loses_only_that_row(monkeypatch, failure):
    original = RttLineParser._parse_csv
    def parse(self, line):
        if line == HEX.strip():
            raise failure("invalid numeric row")
        return original(self, line)
    monkeypatch.setattr(RttLineParser, "_parse_csv", parse)
    hub = Mock()
    decoder = RttChannelDecoder(hub)
    payload = b"1,2\n" + HEX.encode() + b"\n3,4\ncontinued\n"
    decoder.feed_rtt_bytes(payload)
    decoder.flush_pending(final=True)
    assert _terminal(hub) == payload
    assert _raw(hub) == payload.decode().splitlines()
    assert _waves(hub, 2) == [(1, 2), (3, 4)]


def test_terminal_subscription_never_runs_traffic_parser_and_modes_are_per_channel(monkeypatch):
    async def scenario():
        manager = RttStreamManager()
        hubs = {name: StreamHub(64) for ch in range(8)
                for name in (f"rtt-{ch}", f"rtt-terminal-{ch}")}
        manager.set_channel_stream_hubs(hubs)
        # Exercise the same decoder wiring as start(), including auto-discovery.
        device = _Device([], channels=[0, 1])
        manager.start(device, all_channels=True)
        assert await asyncio.to_thread(device.drained.wait, 2)
        terminal = hubs["rtt-terminal-0"].subscribe()
        traffic = hubs["rtt-1"].subscribe()
        try:
            zero, one = manager._channel_decoders[0], manager._channel_decoders[1]
            forbidden = Mock(side_effect=AssertionError("terminal ran traffic parsing"))
            monkeypatch.setattr(zero._parser, "parse", forbidden)
            monkeypatch.setattr(zero._line_assembler, "feed", forbidden)
            manager.feed_channel_bytes(0, PAYLOAD)
            assert (await terminal.get()).payload == PAYLOAD
            forbidden.assert_not_called()
            assert zero._parser_auto_detect_attempts == 0
            manager.feed_channel_bytes(1, b"1,2\n3,4\n")
            assert one._stats["parsed_lines"] == 2
            assert one._numeric_channels == ("v0", "v1")
            # A second window may request traffic on CH0 independently.
            monkeypatch.undo()
            traffic_zero = hubs["rtt-0"].subscribe()
            manager.feed_channel_bytes(0, b"5,6\n7,8\n")
            assert zero._stats["parsed_lines"] == 2
            hubs["rtt-0"].unsubscribe(traffic_zero)
            manager.feed_channel_bytes(0, PAYLOAD)
            assert zero._stats["parsed_lines"] == 2
            assert one._stats["parsed_lines"] == 2
        finally:
            hubs["rtt-terminal-0"].unsubscribe(terminal)
            hubs["rtt-1"].unsubscribe(traffic)
            await asyncio.to_thread(manager.stop)
    asyncio.run(scenario())


def test_legacy_dashboard_hub_does_not_parse_without_traffic_subscribers(monkeypatch):
    manager = RttStreamManager()
    manager.set_stream_hub(StreamHub(64))
    manager.set_terminal_stream_hub(Mock())
    monkeypatch.setattr(RttLineParser, "auto_detect", Mock(side_effect=AssertionError("unexpected detection")))
    manager.feed_rtt_bytes(PAYLOAD)
    manager.flush_pending(final=True)
    assert manager._stats["parsed_lines"] == 0
    assert _terminal(manager._terminal_stream_hub) == PAYLOAD


def test_mode_switch_does_not_join_old_line_fragments_or_lose_terminal_bytes():
    hub = Mock()
    decoder = RttChannelDecoder(hub)
    requested = [True]
    decoder._traffic_requested = lambda: requested[0]
    decoder.feed_rtt_bytes(b"old=")
    requested[0] = False
    decoder.feed_rtt_bytes(b"ignored\r\n")
    requested[0] = True
    decoder.feed_rtt_bytes(b"1,2\r\n3,4\r\n")
    decoder.flush_pending(final=True)
    assert _raw(hub) == ["1,2", "3,4"]
    assert _terminal(hub) == b"old=ignored\r\n1,2\r\n3,4\r\n"
    assert _waves(hub, 2) == [(1, 2), (3, 4)]


class _Device:
    def __init__(self, chunks, channels=None, error=None):
        self.chunks = iter(chunks)
        self.channels = channels or [0, 1]
        self.drained = threading.Event()
        self.stops = 0
        self.error = error

    def rtt_start(self, *_args, **_kwargs):
        return {"transport": "cdc-mux", "channels": self.channels}

    def rtt_read_channels(self, **_kwargs):
        chunk = next(self.chunks, None)
        if chunk is not None:
            return chunk
        self.drained.set()
        if self.error:
            raise self.error
        time.sleep(.002)
        return {}

    def rtt_stop(self):
        self.stops += 1


@pytest.mark.parametrize("chunk_size", [1, 17, 65536])
def test_mux_capture_survives_hex_and_other_channel_continues(chunk_size):
    payload = PAYLOAD + b"still running\r\n"
    chunks = [{0: payload[i:i + chunk_size]} for i in range(0, len(payload), chunk_size)]
    chunks.append({1: b"1,2\n3,4\n"})
    device = _Device(chunks)
    hub = Mock()
    manager = RttStreamManager(hub)
    failed = Mock()
    manager.set_start_failure_callback(failed)
    manager.start(device, channels=[0, 1])
    try:
        assert device.drained.wait(2)
        assert manager.running and manager._thread.is_alive()
        assert not manager.get_status()["error"]
        failed.assert_not_called()
        assert device.stops == 0
        assert bytes.fromhex(manager.read_channel(0)["data_hex"]) == payload
        assert manager._channel_decoders[1]._stats["parsed_lines"] == 2
        assert _terminal(hub) == payload
        assert _raw(hub) == payload.decode().splitlines()
    finally:
        manager.stop()
    assert device.stops == 1
    failed.assert_not_called()


@pytest.mark.parametrize("failure_site", ["read", "publish"])
def test_actual_transport_and_publish_errors_still_stop_mux_capture(failure_site):
    # ValueError outside the parser must not be caught by numeric isolation.
    failure = ValueError("real transport or resource failure")
    hub = Mock()
    if failure_site == "publish":
        def publish(*_args, **_kwargs):
            hub.publish.side_effect = None
            raise failure
        hub.publish.side_effect = publish
    device = _Device([{0: PAYLOAD}], error=failure if failure_site == "read" else None)
    manager = RttStreamManager(hub, raw_batch_lines=1)
    failed = Mock()
    manager.set_start_failure_callback(failed)
    manager.start(device, channels=[0, 1])
    manager._thread.join(2)
    assert not manager.running
    assert not manager._thread.is_alive()
    assert device.stops == 1
    failed.assert_called_once_with(failure)


def test_mcp_rtt_encoding_keeps_hex_raw_and_continues_curve_rows(monkeypatch):
    from mklink.mcp_stream_bridge import McpStreamSidecar
    sidecar = McpStreamSidecar()
    published = Mock()
    monkeypatch.setattr(sidecar, "_publish_hub", published)
    payload = b"1,2\r\n" + PAYLOAD + b"3,4\r\ncontinued\r\n"
    sidecar._encode_rtt(payload.decode())
    raw, wave = published.call_args_list
    assert raw.args[0] == "rtt"
    assert [line.text for line in decode_rtt_lines(raw.args[1], raw.kwargs["item_count"])] == payload.decode().splitlines()
    assert wave.args[0] == "vofa"
    assert decode_waveform_samples(wave.args[1], wave.kwargs["item_count"], 2) == ((1, 2), (3, 4))


def test_standalone_cli_visualizer_continues_after_hex(monkeypatch):
    from mklink import rtt_viewer
    server = Mock()
    server.collecting = threading.Event()
    server.collecting.set()
    monkeypatch.setattr(rtt_viewer, "VisualizationServer", Mock(return_value=server))
    monkeypatch.setattr(rtt_viewer.atexit, "register", Mock())
    monkeypatch.setattr(rtt_viewer.signal, "signal", Mock())
    chunks = iter(["1,2\n", PAYLOAD.decode(), "3,4\n"])
    session = Mock()
    def read(_timeout):
        value = next(chunks, "")
        if not value:
            time.sleep(.002)
        return value
    session.read_output.side_effect = read
    bridge = Mock()
    rtt_viewer.run_rtt_visualizer(session, bridge, no_browser=True, duration=.1)
    assert [{k: v for k, v in call.args[0].items() if k != "_t"}
            for call in server.push_data_point.call_args_list] == [
                {"v0": 1, "v1": 2}, {"total": 12, "avail": 0, "lost": 0, "err": 0},
                {"v0": 3, "v1": 4},
            ]
    session.stop.assert_called_once()
    bridge.close.assert_called_once()
