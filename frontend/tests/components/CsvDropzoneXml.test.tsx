/**
 * XML upload tests for CsvDropzone.
 *
 * Kept in a dedicated file so the XML-specific expectations are easy to find
 * and do not interleave with the CSV/JSON cases.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CsvDropzone from "../../src/components/CsvDropzone";

const SAMPLE_XML =
  '<report><row id="S1"><pH>7.2</pH><conductivity>450</conductivity></row></report>';

function fileInput(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) throw new Error("file input not found");
  return input;
}

function dropzone(): HTMLElement {
  const label = screen.getByText(/Drop a .*file here/i);
  const zone = label.closest("div");
  if (!zone) throw new Error("dropzone container not found");
  return zone;
}

function xmlFile(content: string, name = "data.xml"): File {
  return new File([content], name, { type: "application/xml" });
}

describe("CsvDropzone XML support", () => {
  it("advertises XML in the file picker", () => {
    const { container } = render(<CsvDropzone onFileSelected={vi.fn()} />);
    expect(fileInput(container).getAttribute("accept")).toContain(".xml");
  });

  it("mentions XML in the dropzone instructions", () => {
    render(<CsvDropzone onFileSelected={vi.fn()} />);
    expect(screen.getByText(/Drop a CSV, JSON, or XML file here/i)).toBeTruthy();
  });

  it("parses an XML file and reports it to the parent", async () => {
    const onFileSelected = vi.fn();
    const { container } = render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.change(fileInput(container), {
      target: { files: [xmlFile(SAMPLE_XML)] },
    });

    await waitFor(() => expect(onFileSelected).toHaveBeenCalledTimes(1));

    const [file, preview] = onFileSelected.mock.calls[0];
    expect(file.name).toBe("data.xml");
    expect(preview.headers).toEqual(["id", "pH", "conductivity"]);
    expect(preview.rows[0]).toEqual(["S1", "7.2", "450"]);
  });

  it("shows a preview table for XML", async () => {
    const { container } = render(<CsvDropzone onFileSelected={vi.fn()} />);

    fireEvent.change(fileInput(container), {
      target: { files: [xmlFile(SAMPLE_XML)] },
    });

    expect(await screen.findByText("conductivity")).toBeTruthy();
    expect(screen.getByText("1 row")).toBeTruthy();
    expect(screen.getByText("3 columns")).toBeTruthy();
  });

  it("reports an error for malformed XML without notifying the parent", async () => {
    const onFileSelected = vi.fn();
    const { container } = render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.change(fileInput(container), {
      target: { files: [xmlFile("<report><row></report>", "broken.xml")] },
    });

    expect(await screen.findByText(/Could not parse XML/)).toBeTruthy();
    expect(onFileSelected).not.toHaveBeenCalled();
  });

  it("reports an error when the XML has no repeating rows", async () => {
    const onFileSelected = vi.fn();
    const { container } = render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.change(fileInput(container), {
      target: { files: [xmlFile("<report></report>", "empty.xml")] },
    });

    expect(await screen.findByText(/Could not parse XML/)).toBeTruthy();
    expect(onFileSelected).not.toHaveBeenCalled();
  });

  it("accepts a dropped XML file", async () => {
    const onFileSelected = vi.fn();
    render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.drop(dropzone(), {
      dataTransfer: { files: [xmlFile(SAMPLE_XML)] },
    });

    await waitFor(() => expect(onFileSelected).toHaveBeenCalledTimes(1));
    expect(onFileSelected.mock.calls[0][1].headers).toEqual(["id", "pH", "conductivity"]);
  });

  it("still routes CSV files to the CSV parser", async () => {
    const onFileSelected = vi.fn();
    const { container } = render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.change(fileInput(container), {
      target: {
        files: [new File(["a,b\n1,2\n"], "data.csv", { type: "text/csv" })],
      },
    });

    await waitFor(() => expect(onFileSelected).toHaveBeenCalledTimes(1));
    expect(onFileSelected.mock.calls[0][1].headers).toEqual(["a", "b"]);
  });
});
