import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CsvDropzone from "../../src/components/CsvDropzone";

function fileInput(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) throw new Error("file input not found");
  return input;
}

function dropzone(): HTMLElement {
  // The drop target is the button that also opens the file picker, so dropping
  // and browsing go through the same element.
  const prompt = screen.getByText(/Drop a .*file here/i);
  const zone = prompt.closest("button");
  if (!zone) throw new Error("dropzone button not found");
  return zone;
}

function csvFile(content: string, name = "data.csv", type = "text/csv"): File {
  return new File([content], name, { type });
}

describe("CsvDropzone", () => {
  it("advertises the supported formats and size limit", () => {
    const { container } = render(<CsvDropzone onFileSelected={vi.fn()} />);

    const accept = fileInput(container).getAttribute("accept") ?? "";
    expect(accept).toContain(".csv");
    expect(accept).toContain(".json");
    expect(screen.getByText(/max 50 MB/)).toBeTruthy();
  });

  it("rejects an unsupported extension without notifying the parent", () => {
    const onFileSelected = vi.fn();
    const { container } = render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.change(fileInput(container), {
      target: { files: [csvFile("a,b\n1,2\n", "data.txt", "text/plain")] },
    });

    expect(screen.getByText(/File must be a .*csv/)).toBeTruthy();
    expect(onFileSelected).not.toHaveBeenCalled();
  });

  it("rejects an empty file", () => {
    const { container } = render(<CsvDropzone onFileSelected={vi.fn()} />);

    fireEvent.change(fileInput(container), {
      target: { files: [csvFile("", "empty.csv")] },
    });

    expect(screen.getByText("File is empty")).toBeTruthy();
  });

  it("parses a CSV file and reports it to the parent", async () => {
    const onFileSelected = vi.fn();
    const { container } = render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.change(fileInput(container), {
      target: { files: [csvFile("a,b\n1,2\n3,4\n")] },
    });

    await waitFor(() => expect(onFileSelected).toHaveBeenCalledTimes(1));

    const [file, preview] = onFileSelected.mock.calls[0];
    expect(file.name).toBe("data.csv");
    expect(preview).toEqual({
      headers: ["a", "b"],
      rows: [
        ["1", "2"],
        ["3", "4"],
      ],
      totalRows: 2,
    });
    expect(screen.getByText("2 rows")).toBeTruthy();
    expect(screen.getByText("2 columns")).toBeTruthy();
  });

  it("renders a preview table for the parsed rows", async () => {
    const { container } = render(<CsvDropzone onFileSelected={vi.fn()} />);

    fireEvent.change(fileInput(container), {
      target: { files: [csvFile("sample_id,pH\nS001,7.2\n")] },
    });

    expect(await screen.findByText("sample_id")).toBeTruthy();
    expect(screen.getByText("S001")).toBeTruthy();
  });

  it("notes when the preview is truncated", async () => {
    const rows = Array.from({ length: 8 }, (_, i) => `${i},${i}`).join("\n");
    const { container } = render(<CsvDropzone onFileSelected={vi.fn()} />);

    fireEvent.change(fileInput(container), {
      target: { files: [csvFile(`h1,h2\n${rows}\n`)] },
    });

    expect(await screen.findByText("Showing first 5 of 8 rows")).toBeTruthy();
  });

  it("accepts JSON files and sorts preview columns to match the backend", async () => {
    const onFileSelected = vi.fn();
    const { container } = render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.change(fileInput(container), {
      target: {
        files: [csvFile('[{"b": 2, "a": 1}]', "data.json", "application/json")],
      },
    });

    await waitFor(() => expect(onFileSelected).toHaveBeenCalledTimes(1));
    expect(onFileSelected.mock.calls[0][1].headers).toEqual(["a", "b"]);
  });

  it("reports an error for a CSV with no data rows", async () => {
    const onFileSelected = vi.fn();
    const { container } = render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.change(fileInput(container), {
      target: { files: [csvFile("a,b\n")] },
    });

    expect(await screen.findByText("CSV has no data rows")).toBeTruthy();
    expect(onFileSelected).not.toHaveBeenCalled();
  });

  it("reports an error for a JSON document that is not tabular", async () => {
    const { container } = render(<CsvDropzone onFileSelected={vi.fn()} />);

    fireEvent.change(fileInput(container), {
      target: {
        files: [csvFile('{"just": "a dict"}', "data.json", "application/json")],
      },
    });

    expect(await screen.findByText(/Could not parse JSON/)).toBeTruthy();
  });

  it("accepts a dropped file", async () => {
    const onFileSelected = vi.fn();
    render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.drop(dropzone(), {
      dataTransfer: { files: [csvFile("a,b\n1,2\n")] },
    });

    await waitFor(() => expect(onFileSelected).toHaveBeenCalledTimes(1));
    expect(onFileSelected.mock.calls[0][1].headers).toEqual(["a", "b"]);
  });

  it("is a real button, so the picker is reachable without a mouse", () => {
    render(<CsvDropzone onFileSelected={vi.fn()} />);

    // A `<div>` with an onClick is not focusable: keyboard users could never
    // open the file picker. A native button is a tab stop and activates on
    // Enter and Space without any key handler of ours.
    const zone = screen.getByRole("button", { name: /Drop a .*file here/i });
    expect(zone.tagName).toBe("BUTTON");

    const openPicker = vi.spyOn(HTMLInputElement.prototype, "click");
    openPicker.mockImplementation(() => undefined);

    fireEvent.click(zone);

    expect(openPicker).toHaveBeenCalledTimes(1);
    openPicker.mockRestore();
  });

  it("validates a dropped file the same way as a browsed one", () => {
    const onFileSelected = vi.fn();
    render(<CsvDropzone onFileSelected={onFileSelected} />);

    fireEvent.drop(dropzone(), {
      dataTransfer: { files: [csvFile("x", "data.exe", "application/octet-stream")] },
    });

    expect(screen.getByText(/File must be a .*csv/)).toBeTruthy();
    expect(onFileSelected).not.toHaveBeenCalled();
  });
});
