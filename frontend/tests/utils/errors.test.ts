import { describe, it, expect } from "vitest";
import { apiErrorMessage, splitMessage } from "../../src/utils/errors";

describe("apiErrorMessage", () => {
  it("prefers the backend's detail over axios's generic status text", () => {
    const err = {
      message: "Request failed with status code 400",
      response: { data: { detail: "Your Stellar account is not funded on Testnet." } },
    };

    expect(apiErrorMessage(err, "fallback")).toBe(
      "Your Stellar account is not funded on Testnet.",
    );
  });

  it("falls back to the Error message when the response carries no detail", () => {
    expect(apiErrorMessage(new Error("Network Error"), "fallback")).toBe("Network Error");
  });

  it("ignores an empty detail string", () => {
    expect(apiErrorMessage({ response: { data: { detail: "" } } }, "fallback")).toBe("fallback");
  });

  it("ignores a non-string detail", () => {
    expect(apiErrorMessage({ response: { data: { detail: 42 } } }, "fallback")).toBe("fallback");
  });

  it("uses the fallback for a thrown string", () => {
    expect(apiErrorMessage("boom", "fallback")).toBe("fallback");
  });

  it("uses the fallback for null", () => {
    expect(apiErrorMessage(null, "fallback")).toBe("fallback");
  });
});

describe("splitMessage", () => {
  it("returns one text segment when there is no URL", () => {
    expect(splitMessage("Something went wrong")).toEqual([
      { text: "Something went wrong", isUrl: false },
    ]);
  });

  it("flags the URL and leaves the surrounding text", () => {
    const segments = splitMessage("Fund it at https://friendbot.stellar.org?addr=GABC now.");

    expect(segments.filter((s) => s.isUrl).map((s) => s.text)).toEqual([
      "https://friendbot.stellar.org?addr=GABC",
    ]);
    expect(
      segments
        .filter((s) => !s.isUrl)
        .map((s) => s.text)
        .join(""),
    ).toBe("Fund it at  now.");
  });

  it("does not split on a scheme that is not http(s)", () => {
    expect(splitMessage("mailto:someone@example.com")).toEqual([
      { text: "mailto:someone@example.com", isUrl: false },
    ]);
  });
});
