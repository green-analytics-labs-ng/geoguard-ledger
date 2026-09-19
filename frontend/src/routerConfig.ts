/**
 * Router-wide configuration.
 *
 * React Router v6 keeps v7's behavioural changes behind opt-in flags and warns
 * on every render that they are unset. Turning them on now means the eventual
 * major upgrade is a version bump rather than a behaviour change nobody has
 * tested: `v7_startTransition` stops a navigation from blocking paint, and
 * `v7_relativeSplatPath` fixes the route a relative link resolves against.
 *
 * This lives outside `routes.tsx` because that module exports the route table,
 * which the Fast Refresh lint rule reads as a non-component export; adding a
 * second one there trips it. The tests import it too, so the flags under test
 * are the flags that ship.
 */
export const ROUTER_FUTURE_FLAGS = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;
