"""Phase-aware adapter for the pinned pyOCD 0.44 loader.

pyOCD reports erase and program as separate 0..1 streams through one callback.
Keep that implementation detail here instead of treating erase as PROGRAM 100%.
The FileProgrammer/MemoryLoader internals used here are covered by integration
tests with the real supported pyOCD classes.
"""

from .pyocd_runtime import import_pyocd_attr


def create_programmer(session, *, already_erased=False, **options):
    FileProgrammer = import_pyocd_attr("pyocd.flash.file_programmer", "FileProgrammer")
    MemoryLoader = import_pyocd_attr("pyocd.flash.loader", "MemoryLoader")

    class PhasedLoader(MemoryLoader):
        def commit(self):
            builders = sorted(self._builders.values(), key=lambda b: b.region.start)
            if not builders:
                return
            try:
                if not already_erased:
                    # Standalone program still performs its own sector erase.
                    # Never forward these callbacks as programming progress.
                    for builder in builders:
                        builder.erase(
                            chip_erase="sector", progress_cb=lambda _value: None,
                            smart_flash=self._smart_flash, fast_verify=self._trust_crc,
                            keep_unwritten=self._keep_unwritten,
                        )
                # Explicit backend erase does not run this Pack sequence. Keep
                # it once, before programming, even when erase was done earlier.
                self._run_done_sequence("FlashEraseDone")
                completed = 0
                perf = []
                for builder in builders:
                    size = builder.buffered_data_size

                    def report(value):
                        overall = (completed + float(value) * size) / self._total_data_size
                        # Final 100% belongs after cleanup and the Pack sequence.
                        if self._progress is not None and overall < 1:
                            self._progress(overall)

                    perf.append(builder.program(
                        progress_cb=report,
                        smart_flash=False if already_erased else self._smart_flash,
                        fast_verify=self._trust_crc,
                        keep_unwritten=False if already_erased else self._keep_unwritten,
                    ))
                    completed += size
                self._run_done_sequence("FlashProgramDone")
                self._log_performance(perf)
                if self._progress is not None:
                    self._progress(1.0)
            finally:
                self._reset_state()

        def _run_done_sequence(self, name):
            if self._delegate is not None and self._delegate.has_sequence_with_name(name):
                self._delegate.run_sequence(name)

    programmer = FileProgrammer(session, **options)
    programmer._loader = PhasedLoader(session, **options)
    return programmer
