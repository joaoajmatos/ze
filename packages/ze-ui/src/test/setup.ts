import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver; @visx/responsive's ParentSize (used by the chart
// components) requires one to mount at all.
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).ResizeObserver = MockResizeObserver;
