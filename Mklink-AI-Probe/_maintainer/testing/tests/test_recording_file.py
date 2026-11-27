from array import array
from pathlib import Path

import pytest

from mklink.recording_file import capture_rows
from mklink.remote.dashboards import SuperWatchStreamManager
from mklink.traffic_recording import TrafficRecordings


@pytest.mark.parametrize("kind", ["superwatch", "rtt", "serial"])
def test_stop_and_restart_in_same_directory_keeps_two_independent_sessions(tmp_path, kind):
    if kind == "superwatch":
        manager = SuperWatchStreamManager()
        start, stop = manager.start_recording, manager.stop_recording
        def record(number):
            manager._recorder.append(array('f', [number]), array('d', [0]), [{'name': 'v'}])
    else:
        manager = TrafficRecordings(kind)
        start, stop = manager.start, manager.stop
        def record(number):
            manager.append(0, bytes([number]), 'RX', 'same-source', 1)
    paths = []
    for number in (1, 2):
        opened = start(str(tmp_path))
        record(number)
        result = stop()
        assert result['state'] == 'completed' and opened['path'] == result['path']
        paths.append(Path(result['path']))
        if number == 1:
            original = paths[0].read_bytes()
    assert paths[0] != paths[1] and paths[0].read_bytes() == original
    assert set(tmp_path.iterdir()) == set(paths)
    saved = [list(capture_rows(p)) for p in paths]
    assert [len(records) for records in saved] == [1, 1]
    if kind == 'superwatch':
        assert [records[0]['v'] for records in saved] == [1, 2]
    else:
        assert [records[0]['hex'] for records in saved] == ['01', '02']
