//! libFuzzer entry point for the contract's `verify_inclusion`.
//!
//! Everything of substance lives in `src/harness.rs`; this file is the driver
//! that lets libFuzzer own the process. The target is named with a hyphen
//! (`cargo fuzz run verify-inclusion`) because Cargo warns on non-kebab-case
//! binary names.
//!
//! `cargo fuzz` is what sets `--cfg fuzzing`. Without it this is not a fuzzer,
//! so the fallback entry point fails loudly rather than quietly producing a
//! binary that fuzzes nothing.

#![cfg_attr(fuzzing, no_main)]

#[path = "../src/harness.rs"]
#[allow(dead_code)]
mod harness;

#[cfg(fuzzing)]
libfuzzer_sys::fuzz_target!(|data: &[u8]| harness::check(data));

#[cfg(not(fuzzing))]
fn main() {
    // Also reachable via `cargo build` on stable, which is fine — it just must
    // not be mistaken for a working fuzzer.
    panic!(
        "verify_inclusion is a libFuzzer target; run it with `cargo fuzz run verify_inclusion`, \
         which builds with --cfg fuzzing"
    );
}
