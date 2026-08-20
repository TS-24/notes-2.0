import { describe, expect, it } from "vitest";
import { SURFACE_HEIGHT, fitToText } from "~/workspace/note-surface";

/*
  The two rules that keep a long note usable.

  A note is now a window onto its text rather than a column that grows without
  end, so the surface has a fixed height budget and the words scroll inside it.
  Both halves of that have already gone wrong once: the box grew until the page
  was 4218px tall, and measuring a field by collapsing it threw the reader back
  to the top on every keystroke. Neither is reproducible in jsdom — there is no
  layout there, so `scrollHeight` is always 0 — so what is pinned here is the
  arithmetic and the ordering, and the rest is checked in a browser.
*/

describe("the surface's height budget", () => {
  it("keeps the note under two thirds of the window in both modes", () => {
    expect(SURFACE_HEIGHT.page).toBeLessThan(200 / 3);
    expect(SURFACE_HEIGHT.boxed).toBeLessThan(200 / 3);
  });

  it("gives the note its own page more room than the note in the library", () => {
    // The library has a grid under the note; its own page has nothing else.
    expect(SURFACE_HEIGHT.page).toBeGreaterThan(SURFACE_HEIGHT.boxed);
  });
});

/**
 * A field that reports a fixed text height, and tells the scrollers when it has
 * been collapsed — which is the moment a real browser clamps them.
 */
function fieldOf(textHeight: number, onCollapse: () => void) {
  let height = "";
  const style = {
    get height() {
      return height;
    },
    set height(next: string) {
      height = next;
      if (next === "auto") onCollapse();
    },
  };
  return { scrollHeight: textHeight, style } as unknown as HTMLTextAreaElement;
}

/** A scroll position that jumps to the top when the content above it shortens. */
function clampingScroller(from: number) {
  let position = from;
  const writes: number[] = [];
  return {
    clamp: () => {
      position = 0;
    },
    writes,
    scroller: {
      at: () => position,
      to: (next: number) => {
        position = next;
        writes.push(next);
      },
    },
  };
}

describe("fitToText", () => {
  it("sizes the field to its text", () => {
    const field = fieldOf(390, () => {});

    fitToText(field, []);

    expect(field.style.height).toBe("390px");
  });

  it("puts back a scroll position the collapse moved", () => {
    // The whole bug in one line: the height is restored a statement later and
    // the scroll position is not, so the reader loses their place per keystroke.
    const column = clampingScroller(1420);
    const field = fieldOf(3900, column.clamp);

    fitToText(field, [column.scroller]);

    expect(column.scroller.at()).toBe(1420);
  });

  it("restores every scroller, not just the first one to move", () => {
    // The page and the note's own column can both be scrolled at once.
    const page = clampingScroller(240);
    const column = clampingScroller(1420);
    const field = fieldOf(3900, () => {
      page.clamp();
      column.clamp();
    });

    fitToText(field, [page.scroller, column.scroller]);

    expect([page.scroller.at(), column.scroller.at()]).toEqual([240, 1420]);
  });

  it("does not write to a scroller that never moved", () => {
    // Assigning scrollTop is not free — it cancels a smooth scroll in progress
    // and fires a scroll event — so a short note must not pay for the fix.
    const still = clampingScroller(0);
    const field = fieldOf(120, () => {});

    fitToText(field, [still.scroller]);

    expect(still.writes).toEqual([]);
  });
});
