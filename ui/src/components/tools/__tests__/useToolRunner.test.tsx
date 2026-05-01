import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useToolRunner } from "../useToolRunner";

function Probe({ run, enabled }: { run: () => void; enabled: boolean }) {
  useToolRunner(run, enabled);
  return <div data-testid="probe" />;
}

describe("useToolRunner", () => {
  it("invokes run on Cmd/Ctrl+Enter when enabled", async () => {
    const run = vi.fn();
    render(<Probe run={run} enabled={true} />);
    await userEvent.keyboard("{Control>}{Enter}{/Control}");
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("does not invoke run when disabled", async () => {
    const run = vi.fn();
    render(<Probe run={run} enabled={false} />);
    await userEvent.keyboard("{Control>}{Enter}{/Control}");
    expect(run).not.toHaveBeenCalled();
  });

  it("ignores plain Enter (textarea-newline default)", async () => {
    const run = vi.fn();
    render(<Probe run={run} enabled={true} />);
    await userEvent.keyboard("{Enter}");
    expect(run).not.toHaveBeenCalled();
  });
});
