HPM peripheral descriptions

Source: HPMicro HPM SDK 1.13.0, soc/<series>/<device>/*_svd.xml.
These are CMSIS-SVD XML files, redistributed unmodified under BSD-3-Clause.
LICENSE.txt preserves the SDK license; each XML retains its own copyright notice.
manifest.json records the SDK-relative source path and original SHA-256 digest.

One common catalog is bundled for each of the nine SDK series. Model names and
package suffixes select their series; an exact installed Pack remains preferred.
HPM5301's supported register/field map is a subset of HPM5361 and HPM53M1 with
identical common definitions. HPM5E31 and HPM5E3Y have identical supported maps.
For model-specific extensions, load that model's *_svd.xml manually in SuperWatch,
CLI or MCP. Do not load hpm_ses_riscv_cpu_regs.xml: it describes SES CPU registers,
not CMSIS-SVD peripherals.

Catalog availability does not prove a peripheral is present or clocked on a
particular board. Existing read-only, 32-bit alignment and read-side-effect
filters apply. No probe firmware or local SDK installation is required to load
these descriptions.
