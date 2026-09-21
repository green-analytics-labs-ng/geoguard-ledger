/**
 * Shared Vitest setup.
 *
 * `vitest-axe` ships its assertion as a matcher rather than a bare function, so
 * it has to be registered on `expect` once per test file's environment. Doing it
 * here keeps that registration out of the individual suites and guarantees the
 * accessibility tests and any future component test agree on the same setup.
 *
 * The dependency was already installed when the jsx-a11y lint rules landed; this
 * is what actually runs it.
 */

import { expect } from "vitest";
import * as matchers from "vitest-axe/matchers";

expect.extend(matchers);
